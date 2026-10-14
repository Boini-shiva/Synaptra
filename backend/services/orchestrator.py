import asyncio
import re
import time
import uuid
import datetime
import logging
from typing import Optional, Dict, Any, List

import config
from services.lyzr_client import execute_lyzr_agent, LyzrClientError
from services.gemini_client import execute_gemini_agent, GeminiClientError
from services.qdrant_service import (
    memory_service,
    QdrantServiceError,
    QdrantUnavailableError,
)

logger = logging.getLogger(__name__)


class WorkflowExecutionError(Exception):
    """Raised when an unrecoverable workflow execution error occurs."""
    def __init__(self, message: str, task_id: str, trace: List[Dict[str, Any]], status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.task_id = task_id
        self.trace = trace
        self.status_code = status_code


class MultiAgentOrchestrator:
    """
    Coordinates multi-agent workflows using Lyzr AI agents and Qdrant vector memory:
    1. Memory Retrieval (Qdrant semantic search in tenant workspace)
    2. Memory Agent (Context synthesis & memory proposal)
    3. Planner Agent (Task decomposition & sequential action plan)
    4. Executor Agent (Subtask implementation & execution with bounded concurrency)
    5. Reviewer Agent (Quality review, missing work check & final synthesis)
    6. Memory Storage (Persisting execution outcome to Qdrant)
    """

    def __init__(self, memory_svc=None):
        self.memory_service = memory_svc or memory_service
        # In-memory storage for workflow state and chronological events
        self._workflows_store: Dict[str, Dict[str, Any]] = {}
        self._events_store: Dict[str, List[Dict[str, Any]]] = {}

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _emit_event(
        self,
        task_id: str,
        event_type: str,
        step_name: Optional[str] = None,
        agent_role: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: str = "RUNNING",
        duration_ms: Optional[float] = None,
        input_summary: Optional[str] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """Appends a new chronological execution event for the specified task."""
        event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "task_id": task_id,
            "event_type": event_type,
            "step_name": step_name,
            "agent_role": agent_role,
            "agent_id": agent_id,
            "status": status,
            "timestamp": self._now_iso(),
            "duration_ms": duration_ms,
            "input_summary": input_summary,
            "output": output,
            "error": error,
            "retry_count": retry_count,
        }
        if task_id not in self._events_store:
            self._events_store[task_id] = []
        self._events_store[task_id].append(event)
        return event

    def get_workflow(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves workflow record by task_id."""
        return self._workflows_store.get(task_id)

    def get_workflow_events(self, task_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieves list of chronological events for a task_id."""
        return self._events_store.get(task_id)

    def list_workflows(self, workspace_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves list of all executed workflows, newest first."""
        items = list(self._workflows_store.values())
        if workspace_id:
            items = [w for w in items if w.get("workspace_id") == workspace_id]
        return items[::-1][:limit]

    @staticmethod
    def _parse_plan_subtasks(plan_text: str) -> List[str]:
        """
        Extracts itemized subtasks from the Planner Agent's output.
        Looks for numbered lists (e.g., '1.', '2.', 'Step 1:').
        Returns list of cleaned subtask descriptions.
        """
        if not plan_text or not plan_text.strip():
            return []

        lines = plan_text.strip().splitlines()
        extracted: List[str] = []
        pattern = re.compile(r"^(?:\d+[\.\)]|step\s+\d+[:\.]|subtask\s+\d+[:\.]|- \[[ xX]\])\s*(.+)$", re.IGNORECASE)

        for line in lines:
            line_str = line.strip()
            match = pattern.match(line_str)
            if match:
                content = match.group(1).strip()
                if len(content) > 5:
                    extracted.append(content)

        # Cap at 4 subtasks to keep execution bounded and responsive
        return extracted[:4]

    async def execute_workflow(
        self,
        task: str,
        workspace_id: str = "default",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        timeout_seconds: float = 90.0,
    ) -> Dict[str, Any]:
        """
        Executes the full multi-agent orchestration lifecycle.
        Ensures strict status tracking, timestamps, bounded retries, and comprehensive trace & event logging.
        """
        if not task or not task.strip():
            raise ValueError("Task description must not be empty.")
        if not workspace_id or not workspace_id.strip():
            raise ValueError("workspace_id must not be empty.")

        task_clean = task.strip()
        ws_clean = workspace_id.strip()
        assigned_task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"
        effective_session_id = session_id or f"synaptra_sess_{uuid.uuid4().hex[:10]}"
        effective_user_id = user_id or "synaptra_auditor"

        started_at = self._now_iso()
        start_mono = time.monotonic()
        trace: List[Dict[str, Any]] = []

        # Initialize workflow record and emit start event
        workflow_record = {
            "task_id": assigned_task_id,
            "status": "RUNNING",
            "task": task_clean,
            "workspace_id": ws_clean,
            "final_response": None,
            "execution_trace": trace,
            "error": None,
            "started_at": started_at,
            "completed_at": None,
            "total_duration_ms": None,
        }
        self._workflows_store[assigned_task_id] = workflow_record
        self._events_store[assigned_task_id] = []

        self._emit_event(
            task_id=assigned_task_id,
            event_type="workflow_started",
            status="RUNNING",
            input_summary=f"Task initiated in workspace '{ws_clean}'",
        )

        # 0. Validate all required workflow credentials
        try:
            creds = config.validate_workflow_credentials()
        except ValueError as val_err:
            duration_ms = round((time.monotonic() - start_mono) * 1000, 2)
            completed_at = self._now_iso()
            cred_step = {
                "step_name": "credential_validation",
                "agent_role": "system",
                "agent_id": None,
                "status": "FAILED",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "input_summary": "Validate Lyzr workflow credentials",
                "output": None,
                "error": str(val_err),
                "retry_count": 0,
            }
            trace.append(cred_step)
            self._emit_event(
                task_id=assigned_task_id,
                event_type="step_failed",
                step_name="credential_validation",
                agent_role="system",
                status="FAILED",
                duration_ms=duration_ms,
                error=str(val_err),
            )
            self._emit_event(
                task_id=assigned_task_id,
                event_type="workflow_failed",
                status="FAILED",
                duration_ms=duration_ms,
                error=str(val_err),
            )
            workflow_record.update({
                "status": "FAILED",
                "error": str(val_err),
                "completed_at": completed_at,
                "total_duration_ms": duration_ms,
            })
            return workflow_record

        planner_id = creds["planner_agent_id"]
        executor_id = creds["executor_agent_id"]
        memory_agent_id = creds["memory_agent_id"]
        reviewer_id = creds["reviewer_agent_id"]

        # =====================================================================
        # Step 1: Memory Retrieval from Qdrant Vector Memory
        # =====================================================================
        step1_start_mono = time.monotonic()
        step1_start = self._now_iso()
        retrieved_memories: List[Dict[str, Any]] = []
        retrieval_error: Optional[str] = None

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="memory_retrieval",
            agent_role="qdrant_vector_memory",
            status="RUNNING",
            input_summary=f"Semantic search: '{task_clean[:80]}...' in workspace '{ws_clean}'",
        )

        try:
            retrieved_memories = self.memory_service.search_memories(
                query=task_clean,
                workspace_id=ws_clean,
                limit=5,
            )
            step1_status = "SUCCESS"
            step1_output = f"Retrieved {len(retrieved_memories)} relevant context records from workspace '{ws_clean}'."
        except (QdrantUnavailableError, QdrantServiceError, Exception) as exc:
            step1_status = "WARNING"
            retrieval_error = f"Memory retrieval warning (proceeding with cold start): {str(exc)}"
            step1_output = retrieval_error
            logger.warning(f"Workflow {assigned_task_id}: {retrieval_error}")

        step1_duration = round((time.monotonic() - step1_start_mono) * 1000, 2)
        trace.append({
            "step_name": "memory_retrieval",
            "agent_role": "qdrant_vector_memory",
            "agent_id": None,
            "status": step1_status,
            "started_at": step1_start,
            "completed_at": self._now_iso(),
            "duration_ms": step1_duration,
            "input_summary": f"Semantic query: '{task_clean[:80]}...' in workspace '{ws_clean}'",
            "output": step1_output,
            "error": retrieval_error,
            "retry_count": 0,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed" if step1_status == "SUCCESS" else "step_warning",
            step_name="memory_retrieval",
            agent_role="qdrant_vector_memory",
            status=step1_status,
            duration_ms=step1_duration,
            output=step1_output,
            error=retrieval_error,
        )

        # Format retrieved context
        if retrieved_memories:
            context_snippets = []
            for idx, m in enumerate(retrieved_memories, start=1):
                c = m.get("content", "").strip()
                score = m.get("score", 0.0)
                context_snippets.append(f"[{idx}] (Score: {score}): {c}")
            context_text = "\n".join(context_snippets)
        else:
            context_text = "No prior memories found in this workspace."

        # =====================================================================
        # Step 2: Memory Agent - Context Synthesis & Memory Proposals
        # =====================================================================
        step2_start_mono = time.monotonic()
        step2_start = self._now_iso()

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="memory_synthesis",
            agent_role="memory_agent",
            agent_id=memory_agent_id,
            status="RUNNING",
            input_summary=f"Synthesize context for task: '{task_clean[:80]}...'",
        )

        memory_prompt = (
            f"You are the SYNAPTRA Memory Agent.\n"
            f"User Task: {task_clean}\n\n"
            f"Retrieved Workspace Context:\n{context_text}\n\n"
            f"Your responsibilities:\n"
            f"1. Synthesize relevant historical context and domain constraints for this task.\n"
            f"2. Formulate critical knowledge points that the Planner and Executor must take into account.\n"
            f"3. Highlight any known pitfalls, preferences, or guidelines."
        )

        try:
            mem_result = await execute_lyzr_agent(
                agent_id=memory_agent_id,
                message=memory_prompt,
                user_id=effective_user_id,
                session_id=effective_session_id,
                timeout_seconds=timeout_seconds,
            )
            memory_synthesis = mem_result["response"]
            step2_provider = "lyzr"
            step2_healed = False
            step2_agent_id = memory_agent_id
            step2_retries = mem_result.get("retry_count", 0)
        except LyzrClientError as exc:
            gemini_key = config.get_gemini_api_key()
            if gemini_key:
                logger.info(f"Memory Agent Lyzr failed ({exc.message}). Auto-rectifying with Google Gemini AI Studio...")
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="agent_rectification",
                    step_name="memory_synthesis",
                    agent_role="memory_agent",
                    agent_id=memory_agent_id,
                    status="RECTIFYING",
                    input_summary=f"Lyzr credits/error detected ({exc.message[:80]}). Auto-rectifying via Gemini AI Studio...",
                )
                try:
                    memory_synthesis = await execute_gemini_agent(
                        agent_role="memory_agent",
                        task=task_clean,
                        context=context_text,
                    )
                    step2_provider = "gemini (auto-rectified)"
                    step2_healed = True
                    step2_agent_id = "gemini-auto-rectified"
                    step2_retries = 0
                except Exception as g_err:
                    step2_duration = round((time.monotonic() - step2_start_mono) * 1000, 2)
                    trace.append({
                        "step_name": "memory_synthesis",
                        "agent_role": "memory_agent",
                        "agent_id": memory_agent_id,
                        "status": "FAILED",
                        "started_at": step2_start,
                        "completed_at": self._now_iso(),
                        "duration_ms": step2_duration,
                        "input_summary": f"Context synthesis for task: '{task_clean[:80]}...'",
                        "output": None,
                        "error": f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                        "retry_count": 0,
                    })
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="step_failed",
                        step_name="memory_synthesis",
                        agent_role="memory_agent",
                        agent_id=memory_agent_id,
                        status="FAILED",
                        duration_ms=step2_duration,
                        error=f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                    )
                    total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="workflow_failed",
                        status="FAILED",
                        duration_ms=total_duration,
                        error=f"Memory Agent failed: {exc.message}",
                    )
                    workflow_record.update({
                        "status": "FAILED",
                        "error": f"Memory Agent failed: {exc.message}",
                        "completed_at": self._now_iso(),
                        "total_duration_ms": total_duration,
                    })
                    return workflow_record
            else:
                step2_duration = round((time.monotonic() - step2_start_mono) * 1000, 2)
                trace.append({
                    "step_name": "memory_synthesis",
                    "agent_role": "memory_agent",
                    "agent_id": memory_agent_id,
                    "status": "FAILED",
                    "started_at": step2_start,
                    "completed_at": self._now_iso(),
                    "duration_ms": step2_duration,
                    "input_summary": f"Context synthesis for task: '{task_clean[:80]}...'",
                    "output": None,
                    "error": exc.message,
                    "retry_count": 0,
                })
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="step_failed",
                    step_name="memory_synthesis",
                    agent_role="memory_agent",
                    agent_id=memory_agent_id,
                    status="FAILED",
                    duration_ms=step2_duration,
                    error=exc.message,
                )
                total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="workflow_failed",
                    status="FAILED",
                    duration_ms=total_duration,
                    error=f"Memory Agent failed: {exc.message}",
                )
                workflow_record.update({
                    "status": "FAILED",
                    "error": f"Memory Agent failed: {exc.message}",
                    "completed_at": self._now_iso(),
                    "total_duration_ms": total_duration,
                })
                return workflow_record

        step2_duration = round((time.monotonic() - step2_start_mono) * 1000, 2)
        trace.append({
            "step_name": "memory_synthesis",
            "agent_role": "memory_agent",
            "agent_id": step2_agent_id,
            "status": "SUCCESS",
            "started_at": step2_start,
            "completed_at": self._now_iso(),
            "duration_ms": step2_duration,
            "input_summary": f"Context synthesis for task: '{task_clean[:80]}...'",
            "output": memory_synthesis,
            "error": None,
            "retry_count": step2_retries,
            "provider": step2_provider,
            "self_healed": step2_healed,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed",
            step_name="memory_synthesis",
            agent_role="memory_agent",
            agent_id=step2_agent_id,
            status="SUCCESS",
            duration_ms=step2_duration,
            output=memory_synthesis,
            retry_count=step2_retries,
        )


        # =====================================================================
        # Step 3: Planner Agent - Decomposition into Sequential Subtasks
        # =====================================================================
        step3_start_mono = time.monotonic()
        step3_start = self._now_iso()

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="plan_generation",
            agent_role="planner_agent",
            agent_id=planner_id,
            status="RUNNING",
            input_summary=f"Decompose task: '{task_clean[:80]}...'",
        )

        planner_prompt = (
            f"You are the SYNAPTRA Planner Agent.\n"
            f"User Task: {task_clean}\n\n"
            f"Context and Knowledge from Memory Agent:\n{memory_synthesis}\n\n"
            f"Instruction:\n"
            f"Break this task down into sequential, actionable subtasks.\n"
            f"Itemize each subtask clearly with numbering (e.g. 1. [Subtask], 2. [Subtask]).\n"
            f"Specify objectives, expected outputs, and constraints for each subtask."
        )

        try:
            plan_result = await execute_lyzr_agent(
                agent_id=planner_id,
                message=planner_prompt,
                user_id=effective_user_id,
                session_id=effective_session_id,
                timeout_seconds=timeout_seconds,
            )
            plan_response = plan_result["response"]

            # Validate plan response
            if not plan_response or not plan_response.strip():
                raise LyzrClientError("Planner Agent returned empty plan response.", status_code=502)

            step3_provider = "lyzr"
            step3_healed = False
            step3_agent_id = planner_id
            step3_retries = plan_result.get("retry_count", 0)
        except LyzrClientError as exc:
            gemini_key = config.get_gemini_api_key()
            if gemini_key:
                logger.info(f"Planner Agent Lyzr failed ({exc.message}). Auto-rectifying with Google Gemini AI Studio...")
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="agent_rectification",
                    step_name="plan_generation",
                    agent_role="planner_agent",
                    agent_id=planner_id,
                    status="RECTIFYING",
                    input_summary=f"Lyzr credits/error detected ({exc.message[:80]}). Auto-rectifying via Gemini AI Studio...",
                )
                try:
                    plan_response = await execute_gemini_agent(
                        agent_role="planner_agent",
                        task=task_clean,
                        context=memory_synthesis,
                    )
                    step3_provider = "gemini (auto-rectified)"
                    step3_healed = True
                    step3_agent_id = "gemini-auto-rectified"
                    step3_retries = 0
                except Exception as g_err:
                    step3_duration = round((time.monotonic() - step3_start_mono) * 1000, 2)
                    trace.append({
                        "step_name": "plan_generation",
                        "agent_role": "planner_agent",
                        "agent_id": planner_id,
                        "status": "FAILED",
                        "started_at": step3_start,
                        "completed_at": self._now_iso(),
                        "duration_ms": step3_duration,
                        "input_summary": f"Decomposition prompt for task: '{task_clean[:80]}...'",
                        "output": None,
                        "error": f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                        "retry_count": 0,
                    })
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="step_failed",
                        step_name="plan_generation",
                        agent_role="planner_agent",
                        agent_id=planner_id,
                        status="FAILED",
                        duration_ms=step3_duration,
                        error=f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                    )
                    total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="workflow_failed",
                        status="FAILED",
                        duration_ms=total_duration,
                        error=f"Planner Agent failed: {exc.message}",
                    )
                    workflow_record.update({
                        "status": "FAILED",
                        "error": f"Planner Agent failed: {exc.message}",
                        "completed_at": self._now_iso(),
                        "total_duration_ms": total_duration,
                    })
                    return workflow_record
            else:
                step3_duration = round((time.monotonic() - step3_start_mono) * 1000, 2)
                trace.append({
                    "step_name": "plan_generation",
                    "agent_role": "planner_agent",
                    "agent_id": planner_id,
                    "status": "FAILED",
                    "started_at": step3_start,
                    "completed_at": self._now_iso(),
                    "duration_ms": step3_duration,
                    "input_summary": f"Decomposition prompt for task: '{task_clean[:80]}...'",
                    "output": None,
                    "error": exc.message,
                    "retry_count": 0,
                })
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="step_failed",
                    step_name="plan_generation",
                    agent_role="planner_agent",
                    agent_id=planner_id,
                    status="FAILED",
                    duration_ms=step3_duration,
                    error=exc.message,
                )
                total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="workflow_failed",
                    status="FAILED",
                    duration_ms=total_duration,
                    error=f"Planner Agent failed: {exc.message}",
                )
                workflow_record.update({
                    "status": "FAILED",
                    "error": f"Planner Agent failed: {exc.message}",
                    "completed_at": self._now_iso(),
                    "total_duration_ms": total_duration,
                })
                return workflow_record

        step3_duration = round((time.monotonic() - step3_start_mono) * 1000, 2)
        trace.append({
            "step_name": "plan_generation",
            "agent_role": "planner_agent",
            "agent_id": step3_agent_id,
            "status": "SUCCESS",
            "started_at": step3_start,
            "completed_at": self._now_iso(),
            "duration_ms": step3_duration,
            "input_summary": f"Decomposition prompt for task: '{task_clean[:80]}...'",
            "output": plan_response,
            "error": None,
            "retry_count": step3_retries,
            "provider": step3_provider,
            "self_healed": step3_healed,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed",
            step_name="plan_generation",
            agent_role="planner_agent",
            agent_id=step3_agent_id,
            status="SUCCESS",
            duration_ms=step3_duration,
            output=plan_response,
            retry_count=step3_retries,
        )


        # =====================================================================
        # Step 4: Executor Agent - Execution of Subtasks (Bounded Concurrency)
        # =====================================================================
        step4_start_mono = time.monotonic()
        step4_start = self._now_iso()

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="subtask_execution",
            agent_role="executor_agent",
            agent_id=executor_id,
            status="RUNNING",
            input_summary=f"Execute action plan for: '{task_clean[:80]}...'",
        )

        subtasks = self._parse_plan_subtasks(plan_response)
        executor_response: str = ""
        executor_retry_count: int = 0
        step4_provider: str = "lyzr"
        step4_healed: bool = False
        step4_agent_id: Optional[str] = executor_id

        if len(subtasks) >= 2:
            # Multi-subtask execution with bounded concurrency (semaphore=2)
            semaphore = asyncio.Semaphore(2)

            async def _run_subtask(idx: int, st_desc: str) -> Dict[str, Any]:
                st_substart = time.monotonic()
                subtask_msg = (
                    f"Task Goal: {task_clean}\n"
                    f"Subtask #{idx}: {st_desc}\n"
                    f"Context & Memory Insights: {memory_synthesis}\n"
                    f"Instruction: Execute this specific subtask thoroughly and provide complete findings."
                )
                async with semaphore:
                    try:
                        st_result = await execute_lyzr_agent(
                            agent_id=executor_id,
                            message=subtask_msg,
                            user_id=effective_user_id,
                            session_id=effective_session_id,
                            timeout_seconds=timeout_seconds,
                        )
                        st_resp = st_result["response"]
                        st_retry = st_result.get("retry_count", 0)
                        st_healed = False
                    except LyzrClientError as sub_exc:
                        if config.get_gemini_api_key():
                            logger.info(f"Subtask #{idx} executor Lyzr error ({sub_exc.message}). Auto-rectifying via Gemini...")
                            st_resp = await execute_gemini_agent(
                                agent_role="executor_agent",
                                task=f"{task_clean} - Subtask #{idx}: {st_desc}",
                                context=memory_synthesis,
                                plan=st_desc,
                            )
                            st_retry = 0
                            st_healed = True
                        else:
                            raise sub_exc

                    st_dur = round((time.monotonic() - st_substart) * 1000, 2)
                    return {
                        "index": idx,
                        "subtask": st_desc,
                        "response": st_resp,
                        "duration_ms": st_dur,
                        "retry_count": st_retry,
                        "self_healed": st_healed,
                    }

            try:
                subtask_results = await asyncio.gather(*[_run_subtask(i, s) for i, s in enumerate(subtasks, start=1)])
                combined_outputs = []
                any_subtask_healed = False
                for res in subtask_results:
                    combined_outputs.append(f"### Subtask {res['index']}: {res['subtask']}\n{res['response']}")
                    executor_retry_count += res.get("retry_count", 0)
                    if res.get("self_healed"):
                        any_subtask_healed = True
                executor_response = "\n\n".join(combined_outputs)
                if any_subtask_healed:
                    step4_provider = "gemini (auto-rectified)"
                    step4_healed = True
                    step4_agent_id = "gemini-auto-rectified"

            except LyzrClientError as exc:
                gemini_key = config.get_gemini_api_key()
                if gemini_key:
                    logger.info(f"Executor gather failed ({exc.message}). Auto-rectifying with Gemini AI Studio...")
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="agent_rectification",
                        step_name="subtask_execution",
                        agent_role="executor_agent",
                        agent_id=executor_id,
                        status="RECTIFYING",
                        input_summary=f"Lyzr credits/error detected ({exc.message[:80]}). Auto-rectifying via Gemini AI Studio...",
                    )
                    try:
                        executor_response = await execute_gemini_agent(
                            agent_role="executor_agent",
                            task=task_clean,
                            context=memory_synthesis,
                            plan=plan_response,
                        )
                        step4_provider = "gemini (auto-rectified)"
                        step4_healed = True
                        step4_agent_id = "gemini-auto-rectified"
                        executor_retry_count = 0
                    except Exception as g_err:
                        step4_duration = round((time.monotonic() - step4_start_mono) * 1000, 2)
                        trace.append({
                            "step_name": "subtask_execution",
                            "agent_role": "executor_agent",
                            "agent_id": executor_id,
                            "status": "FAILED",
                            "started_at": step4_start,
                            "completed_at": self._now_iso(),
                            "duration_ms": step4_duration,
                            "input_summary": f"Execute action plan for: '{task_clean[:80]}...'",
                            "output": None,
                            "error": f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                            "retry_count": 0,
                        })
                        self._emit_event(
                            task_id=assigned_task_id,
                            event_type="step_failed",
                            step_name="subtask_execution",
                            agent_role="executor_agent",
                            agent_id=executor_id,
                            status="FAILED",
                            duration_ms=step4_duration,
                            error=f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                        )
                        total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                        self._emit_event(
                            task_id=assigned_task_id,
                            event_type="workflow_failed",
                            status="FAILED",
                            duration_ms=total_duration,
                            error=f"Executor Agent failed: {exc.message}",
                        )
                        workflow_record.update({
                            "status": "FAILED",
                            "error": f"Executor Agent failed: {exc.message}",
                            "completed_at": self._now_iso(),
                            "total_duration_ms": total_duration,
                        })
                        return workflow_record
                else:
                    step4_duration = round((time.monotonic() - step4_start_mono) * 1000, 2)
                    trace.append({
                        "step_name": "subtask_execution",
                        "agent_role": "executor_agent",
                        "agent_id": executor_id,
                        "status": "FAILED",
                        "started_at": step4_start,
                        "completed_at": self._now_iso(),
                        "duration_ms": step4_duration,
                        "input_summary": f"Execute action plan for: '{task_clean[:80]}...'",
                        "output": None,
                        "error": exc.message,
                        "retry_count": 0,
                    })
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="step_failed",
                        step_name="subtask_execution",
                        agent_role="executor_agent",
                        agent_id=executor_id,
                        status="FAILED",
                        duration_ms=step4_duration,
                        error=exc.message,
                    )
                    total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="workflow_failed",
                        status="FAILED",
                        duration_ms=total_duration,
                        error=f"Executor Agent failed: {exc.message}",
                    )
                    workflow_record.update({
                        "status": "FAILED",
                        "error": f"Executor Agent failed: {exc.message}",
                        "completed_at": self._now_iso(),
                        "total_duration_ms": total_duration,
                    })
                    return workflow_record

        else:
            # Unified plan execution
            executor_prompt = (
                f"You are the SYNAPTRA Executor Agent.\n"
                f"User Task: {task_clean}\n\n"
                f"Execution Plan from Planner Agent:\n{plan_response}\n\n"
                f"Context from Memory Agent:\n{memory_synthesis}\n\n"
                f"Instruction:\n"
                f"Execute each planned subtask in order. Provide concrete, comprehensive details, "
                f"findings, calculations, drafts, or implementations for every subtask."
            )

            try:
                exec_result = await execute_lyzr_agent(
                    agent_id=executor_id,
                    message=executor_prompt,
                    user_id=effective_user_id,
                    session_id=effective_session_id,
                    timeout_seconds=timeout_seconds,
                )
                executor_response = exec_result["response"]
                executor_retry_count = exec_result.get("retry_count", 0)
                step4_provider = "lyzr"
                step4_healed = False
                step4_agent_id = executor_id

            except LyzrClientError as exc:
                gemini_key = config.get_gemini_api_key()
                if gemini_key:
                    logger.info(f"Unified executor Lyzr error ({exc.message}). Auto-rectifying with Gemini AI Studio...")
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="agent_rectification",
                        step_name="subtask_execution",
                        agent_role="executor_agent",
                        agent_id=executor_id,
                        status="RECTIFYING",
                        input_summary=f"Lyzr credits/error detected ({exc.message[:80]}). Auto-rectifying via Gemini AI Studio...",
                    )
                    try:
                        executor_response = await execute_gemini_agent(
                            agent_role="executor_agent",
                            task=task_clean,
                            context=memory_synthesis,
                            plan=plan_response,
                        )
                        step4_provider = "gemini (auto-rectified)"
                        step4_healed = True
                        step4_agent_id = "gemini-auto-rectified"
                        executor_retry_count = 0
                    except Exception as g_err:
                        step4_duration = round((time.monotonic() - step4_start_mono) * 1000, 2)
                        trace.append({
                            "step_name": "subtask_execution",
                            "agent_role": "executor_agent",
                            "agent_id": executor_id,
                            "status": "FAILED",
                            "started_at": step4_start,
                            "completed_at": self._now_iso(),
                            "duration_ms": step4_duration,
                            "input_summary": f"Execute action plan for: '{task_clean[:80]}...'",
                            "output": None,
                            "error": f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                            "retry_count": 0,
                        })
                        self._emit_event(
                            task_id=assigned_task_id,
                            event_type="step_failed",
                            step_name="subtask_execution",
                            agent_role="executor_agent",
                            agent_id=executor_id,
                            status="FAILED",
                            duration_ms=step4_duration,
                            error=f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                        )
                        total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                        self._emit_event(
                            task_id=assigned_task_id,
                            event_type="workflow_failed",
                            status="FAILED",
                            duration_ms=total_duration,
                            error=f"Executor Agent failed: {exc.message}",
                        )
                        workflow_record.update({
                            "status": "FAILED",
                            "error": f"Executor Agent failed: {exc.message}",
                            "completed_at": self._now_iso(),
                            "total_duration_ms": total_duration,
                        })
                        return workflow_record
                else:
                    step4_duration = round((time.monotonic() - step4_start_mono) * 1000, 2)
                    trace.append({
                        "step_name": "subtask_execution",
                        "agent_role": "executor_agent",
                        "agent_id": executor_id,
                        "status": "FAILED",
                        "started_at": step4_start,
                        "completed_at": self._now_iso(),
                        "duration_ms": step4_duration,
                        "input_summary": f"Execute action plan for: '{task_clean[:80]}...'",
                        "output": None,
                        "error": exc.message,
                        "retry_count": 0,
                    })
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="step_failed",
                        step_name="subtask_execution",
                        agent_role="executor_agent",
                        agent_id=executor_id,
                        status="FAILED",
                        duration_ms=step4_duration,
                        error=exc.message,
                    )
                    total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="workflow_failed",
                        status="FAILED",
                        duration_ms=total_duration,
                        error=f"Executor Agent failed: {exc.message}",
                    )
                    workflow_record.update({
                        "status": "FAILED",
                        "error": f"Executor Agent failed: {exc.message}",
                        "completed_at": self._now_iso(),
                        "total_duration_ms": total_duration,
                    })
                    return workflow_record

        step4_duration = round((time.monotonic() - step4_start_mono) * 1000, 2)
        trace.append({
            "step_name": "subtask_execution",
            "agent_role": "executor_agent",
            "agent_id": step4_agent_id,
            "status": "SUCCESS",
            "started_at": step4_start,
            "completed_at": self._now_iso(),
            "duration_ms": step4_duration,
            "input_summary": f"Execute action plan for: '{task_clean[:80]}...'",
            "output": executor_response,
            "error": None,
            "retry_count": executor_retry_count,
            "provider": step4_provider,
            "self_healed": step4_healed,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed",
            step_name="subtask_execution",
            agent_role="executor_agent",
            agent_id=step4_agent_id,
            status="SUCCESS",
            duration_ms=step4_duration,
            output=executor_response,
            retry_count=executor_retry_count,
        )


        # =====================================================================
        # Step 5: Reviewer Agent - Verification, Missing Work Check & Final Synthesis
        # =====================================================================
        step5_start_mono = time.monotonic()
        step5_start = self._now_iso()

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="review_and_synthesis",
            agent_role="reviewer_agent",
            agent_id=reviewer_id,
            status="RUNNING",
            input_summary=f"Review execution output for task: '{task_clean[:80]}...'",
        )

        reviewer_prompt = (
            f"You are the SYNAPTRA Reviewer Agent.\n"
            f"Original Task: {task_clean}\n\n"
            f"Action Plan:\n{plan_response}\n\n"
            f"Execution Results:\n{executor_response}\n\n"
            f"Memory Context:\n{memory_synthesis}\n\n"
            f"Instruction:\n"
            f"1. Check results rigorously against the original task and action plan.\n"
            f"2. Identify any missing items, inaccuracies, or potential risks.\n"
            f"3. Produce the final, authoritative, high-quality response for the user."
        )

        try:
            review_result = await execute_lyzr_agent(
                agent_id=reviewer_id,
                message=reviewer_prompt,
                user_id=effective_user_id,
                session_id=effective_session_id,
                timeout_seconds=timeout_seconds,
            )
            reviewer_response = review_result["response"]
            step5_provider = "lyzr"
            step5_healed = False
            step5_agent_id = reviewer_id
            step5_retries = review_result.get("retry_count", 0)
        except LyzrClientError as exc:
            gemini_key = config.get_gemini_api_key()
            if gemini_key:
                logger.info(f"Reviewer Agent Lyzr error ({exc.message}). Auto-rectifying with Gemini AI Studio...")
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="agent_rectification",
                    step_name="review_and_synthesis",
                    agent_role="reviewer_agent",
                    agent_id=reviewer_id,
                    status="RECTIFYING",
                    input_summary=f"Lyzr credits/error detected ({exc.message[:80]}). Auto-rectifying via Gemini AI Studio...",
                )
                try:
                    reviewer_response = await execute_gemini_agent(
                        agent_role="reviewer_agent",
                        task=task_clean,
                        context=memory_synthesis,
                        plan=plan_response,
                        execution_results=executor_response,
                    )
                    step5_provider = "gemini (auto-rectified)"
                    step5_healed = True
                    step5_agent_id = "gemini-auto-rectified"
                    step5_retries = 0
                except Exception as g_err:
                    step5_duration = round((time.monotonic() - step5_start_mono) * 1000, 2)
                    trace.append({
                        "step_name": "review_and_synthesis",
                        "agent_role": "reviewer_agent",
                        "agent_id": reviewer_id,
                        "status": "FAILED",
                        "started_at": step5_start,
                        "completed_at": self._now_iso(),
                        "duration_ms": step5_duration,
                        "input_summary": f"Review execution output for task: '{task_clean[:80]}...'",
                        "output": None,
                        "error": f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                        "retry_count": 0,
                    })
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="step_failed",
                        step_name="review_and_synthesis",
                        agent_role="reviewer_agent",
                        agent_id=reviewer_id,
                        status="FAILED",
                        duration_ms=step5_duration,
                        error=f"Lyzr ({exc.message}) and Gemini fallback failed: {str(g_err)}",
                    )
                    total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                    self._emit_event(
                        task_id=assigned_task_id,
                        event_type="workflow_failed",
                        status="FAILED",
                        duration_ms=total_duration,
                        error=f"Reviewer Agent failed: {exc.message}",
                    )
                    workflow_record.update({
                        "status": "FAILED",
                        "error": f"Reviewer Agent failed: {exc.message}",
                        "completed_at": self._now_iso(),
                        "total_duration_ms": total_duration,
                    })
                    return workflow_record
            else:
                step5_duration = round((time.monotonic() - step5_start_mono) * 1000, 2)
                trace.append({
                    "step_name": "review_and_synthesis",
                    "agent_role": "reviewer_agent",
                    "agent_id": reviewer_id,
                    "status": "FAILED",
                    "started_at": step5_start,
                    "completed_at": self._now_iso(),
                    "duration_ms": step5_duration,
                    "input_summary": f"Review execution output for task: '{task_clean[:80]}...'",
                    "output": None,
                    "error": exc.message,
                    "retry_count": 0,
                })
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="step_failed",
                    step_name="review_and_synthesis",
                    agent_role="reviewer_agent",
                    agent_id=reviewer_id,
                    status="FAILED",
                    duration_ms=step5_duration,
                    error=exc.message,
                )
                total_duration = round((time.monotonic() - start_mono) * 1000, 2)
                self._emit_event(
                    task_id=assigned_task_id,
                    event_type="workflow_failed",
                    status="FAILED",
                    duration_ms=total_duration,
                    error=f"Reviewer Agent failed: {exc.message}",
                )
                workflow_record.update({
                    "status": "FAILED",
                    "error": f"Reviewer Agent failed: {exc.message}",
                    "completed_at": self._now_iso(),
                    "total_duration_ms": total_duration,
                })
                return workflow_record

        step5_duration = round((time.monotonic() - step5_start_mono) * 1000, 2)
        trace.append({
            "step_name": "review_and_synthesis",
            "agent_role": "reviewer_agent",
            "agent_id": step5_agent_id,
            "status": "SUCCESS",
            "started_at": step5_start,
            "completed_at": self._now_iso(),
            "duration_ms": step5_duration,
            "input_summary": f"Review execution output for task: '{task_clean[:80]}...'",
            "output": reviewer_response,
            "error": None,
            "retry_count": step5_retries,
            "provider": step5_provider,
            "self_healed": step5_healed,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed",
            step_name="review_and_synthesis",
            agent_role="reviewer_agent",
            agent_id=step5_agent_id,
            status="SUCCESS",
            duration_ms=step5_duration,
            output=reviewer_response,
            retry_count=step5_retries,
        )


        # =====================================================================
        # Step 6: Memory Storage - Save Task Summary & Result in Qdrant
        # =====================================================================
        step6_start_mono = time.monotonic()
        step6_start = self._now_iso()
        save_error: Optional[str] = None
        saved_memory_id: Optional[str] = None

        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_started",
            step_name="memory_storage",
            agent_role="qdrant_vector_memory",
            status="RUNNING",
            input_summary=f"Store workflow summary in workspace '{ws_clean}'",
        )

        summary_content = (
            f"TASK: {task_clean}\n"
            f"PLAN SUMMARY: {plan_response[:250]}\n"
            f"FINAL ANSWER: {reviewer_response[:400]}"
        )

        try:
            saved_item = self.memory_service.insert_memory(
                content=summary_content,
                memory_type="workflow_summary",
                source_agent="reviewer_agent",
                workspace_id=ws_clean,
                visibility="shared",
            )
            saved_memory_id = saved_item.get("memory_id")
            step6_status = "SUCCESS"
            step6_output = f"Successfully persisted workflow summary to vector memory (id={saved_memory_id})."
        except (QdrantUnavailableError, QdrantServiceError, Exception) as exc:
            step6_status = "WARNING"
            save_error = f"Failed to persist workflow summary to Qdrant: {str(exc)}"
            step6_output = save_error
            logger.warning(f"Workflow {assigned_task_id}: {save_error}")

        step6_duration = round((time.monotonic() - step6_start_mono) * 1000, 2)
        trace.append({
            "step_name": "memory_storage",
            "agent_role": "qdrant_vector_memory",
            "agent_id": None,
            "status": step6_status,
            "started_at": step6_start,
            "completed_at": self._now_iso(),
            "duration_ms": step6_duration,
            "input_summary": f"Store workflow summary in workspace '{ws_clean}'",
            "output": step6_output,
            "error": save_error,
            "retry_count": 0,
        })
        self._emit_event(
            task_id=assigned_task_id,
            event_type="step_completed" if step6_status == "SUCCESS" else "step_warning",
            step_name="memory_storage",
            agent_role="qdrant_vector_memory",
            status=step6_status,
            duration_ms=step6_duration,
            output=step6_output,
            error=save_error,
        )

        # =====================================================================
        # Complete Workflow
        # =====================================================================
        completed_at = self._now_iso()
        total_duration = round((time.monotonic() - start_mono) * 1000, 2)

        self._emit_event(
            task_id=assigned_task_id,
            event_type="workflow_completed",
            status="COMPLETED",
            duration_ms=total_duration,
            output=reviewer_response[:200],
        )

        workflow_record.update({
            "status": "COMPLETED",
            "final_response": reviewer_response,
            "completed_at": completed_at,
            "total_duration_ms": total_duration,
        })

        return workflow_record


# Global singleton instance
workflow_orchestrator = MultiAgentOrchestrator()
