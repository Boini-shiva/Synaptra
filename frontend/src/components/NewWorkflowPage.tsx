import React, { useState, useEffect } from 'react';
import {
  Send,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Copy,
  Check,
  Database,
  ListTodo,
  Zap,
  CheckSquare,
  Flag,
  AlertCircle,
  Activity,
  Layers,
  Sparkles,
} from 'lucide-react';
import type {
  TraceStep,
  WorkflowEvent,
  WorkflowExecutionResponse,
} from '../types/api';


interface NewWorkflowPageProps {
  initialPrompt?: string;
  activeWorkspace: string;
  onWorkspaceChange: (ws: string) => void;
  onSubmitTask: (task: string, workspace: string) => Promise<void>;
  isExecuting: boolean;
  workflowResult: WorkflowExecutionResponse | null;
  workflowTrace: TraceStep[];
  workflowEvents: WorkflowEvent[];
  errorMessage: string | null;
  onRetry: () => void;
  onInspectTaskId?: string | null;
}

type PipelineStageId = 'planning' | 'execution' | 'memory' | 'review' | 'completed';

interface StageMeta {
  id: PipelineStageId;
  name: string;
  role: string;
  icon: React.ElementType;
  description: string;
}

const STAGES: StageMeta[] = [
  {
    id: 'planning',
    name: 'Planning',
    role: 'Planner Agent',
    icon: ListTodo,
    description: 'Decomposes the high-level objective into structured subtasks.',
  },
  {
    id: 'execution',
    name: 'Execution',
    role: 'Executor Agent',
    icon: Zap,
    description: 'Executes subtasks with concurrency controls and live telemetry.',
  },
  {
    id: 'memory',
    name: 'Memory',
    role: 'Memory Agent',
    icon: Database,
    description: 'Retrieves relevant semantic memories from Qdrant vector index.',
  },
  {
    id: 'review',
    name: 'Review',
    role: 'Reviewer Agent',
    icon: CheckSquare,
    description: 'Audits completeness and synthesizes the validated final response.',
  },
  {
    id: 'completed',
    name: 'Completed',
    role: 'Orchestrator Core',
    icon: Flag,
    description: 'Final execution synthesis persisted to vector memory.',
  },
];

export const NewWorkflowPage: React.FC<NewWorkflowPageProps> = ({
  initialPrompt = '',
  activeWorkspace,
  onWorkspaceChange,
  onSubmitTask,
  isExecuting,
  workflowResult,
  workflowTrace,
  workflowEvents,
  errorMessage,
  onRetry,
}) => {
  const [taskText, setTaskText] = useState(initialPrompt);
  const [selectedStage, setSelectedStage] = useState<PipelineStageId>('planning');
  const [copiedResponse, setCopiedResponse] = useState(false);
  const [copiedTaskId, setCopiedTaskId] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);

  // Sync initialPrompt if changed
  useEffect(() => {
    if (initialPrompt) {
      setTaskText(initialPrompt);
    }
  }, [initialPrompt]);

  // Handle submit with duplicate prevention
  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskText.trim() || isExecuting) return;
    await onSubmitTask(taskText.trim(), activeWorkspace);
  };

  // Determine stage status from trace steps & events
  const getStageStatus = (stageId: PipelineStageId): 'SUCCESS' | 'FAILED' | 'RUNNING' | 'PENDING' | 'SKIPPED' => {
    if (stageId === 'completed') {
      if (workflowResult?.status === 'COMPLETED') return 'SUCCESS';
      if (workflowResult?.status === 'FAILED') return 'FAILED';
      if (isExecuting) return 'PENDING';
      return 'PENDING';
    }

    // Match keywords for the stage
    const traceMatches = workflowTrace.filter((step) => {
      const name = (step.step_name || '').toLowerCase();
      const role = (step.agent_role || '').toLowerCase();
      if (stageId === 'planning') return name.includes('plan') || role.includes('planner');
      if (stageId === 'execution') return name.includes('exec') || role.includes('executor');
      if (stageId === 'memory') return name.includes('mem') || role.includes('memory') || name.includes('qdrant');
      if (stageId === 'review') return name.includes('review') || role.includes('reviewer');
      return false;
    });

    if (traceMatches.length > 0) {
      if (traceMatches.some((s) => s.status === 'FAILED')) return 'FAILED';
      if (traceMatches.some((s) => s.status === 'RUNNING')) return 'RUNNING';
      if (traceMatches.every((s) => s.status === 'SUCCESS')) return 'SUCCESS';
      if (traceMatches.some((s) => s.status === 'SKIPPED')) return 'SKIPPED';
    }

    // If currently executing, check events
    if (isExecuting) {
      const eventMatches = workflowEvents.filter((evt) => {
        const name = (evt.step_name || evt.event_type || '').toLowerCase();
        const role = (evt.agent_role || '').toLowerCase();
        if (stageId === 'planning') return name.includes('plan') || role.includes('planner');
        if (stageId === 'execution') return name.includes('exec') || role.includes('executor');
        if (stageId === 'memory') return name.includes('mem') || role.includes('memory');
        if (stageId === 'review') return name.includes('review') || role.includes('reviewer');
        return false;
      });

      if (eventMatches.length > 0) {
        const latest = eventMatches[eventMatches.length - 1];
        if (latest.status === 'RUNNING') return 'RUNNING';
        if (latest.status === 'SUCCESS') return 'SUCCESS';
        if (latest.status === 'FAILED') return 'FAILED';
      }
    }

    return 'PENDING';
  };

  // Get trace steps for selected stage
  const getSelectedStageSteps = (): TraceStep[] => {
    if (selectedStage === 'completed') return [];
    return workflowTrace.filter((step) => {
      const name = (step.step_name || '').toLowerCase();
      const role = (step.agent_role || '').toLowerCase();
      if (selectedStage === 'planning') return name.includes('plan') || role.includes('planner');
      if (selectedStage === 'execution') return name.includes('exec') || role.includes('executor');
      if (selectedStage === 'memory') return name.includes('mem') || role.includes('memory') || name.includes('qdrant');
      if (selectedStage === 'review') return name.includes('review') || role.includes('reviewer');
      return false;
    });
  };

  const selectedMeta = STAGES.find((s) => s.id === selectedStage) || STAGES[0];
  const selectedStageSteps = getSelectedStageSteps();
  const selectedStatus = getStageStatus(selectedStage);

  const handleCopyText = (text: string, type: 'response' | 'taskId') => {
    navigator.clipboard.writeText(text);
    if (type === 'response') {
      setCopiedResponse(true);
      setTimeout(() => setCopiedResponse(false), 2000);
    } else {
      setCopiedTaskId(true);
      setTimeout(() => setCopiedTaskId(false), 2000);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* 1. Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">
          New Workflow
        </h1>
        <p className="text-sm text-[#64748B] mt-0.5">
          Submit tasks to coordinated agents with real-time pipeline monitoring
        </p>
      </div>

      {/* 2. Task Input Card */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs">
        <form onSubmit={handleFormSubmit} className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Task Instructions
            </label>
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-[#64748B]">Workspace:</span>
              <div className="flex items-center space-x-1.5 bg-[#F8F9FC] border border-[#E2E8F0] rounded-lg px-2 py-1">
                <Layers className="w-3 h-3 text-[#7C3AED]" />
                <input
                  type="text"
                  value={activeWorkspace}
                  disabled={isExecuting}
                  onChange={(e) => onWorkspaceChange(e.target.value.trim() || 'default')}
                  placeholder="default"
                  className="bg-transparent font-mono text-[#0F172A] text-xs focus:outline-none w-24"
                />
              </div>
            </div>
          </div>

          <textarea
            rows={4}
            value={taskText}
            disabled={isExecuting}
            onChange={(e) => setTaskText(e.target.value)}
            placeholder="E.g., Create a 3-step plan for preparing a college hackathon project. Retrieve relevant saved memories, execute the plan, and review the result."
            className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white rounded-xl p-4 text-sm text-[#0F172A] placeholder-[#94A3B8] focus:outline-none transition resize-none font-sans"
          />

          {/* Validation & Error Alert */}
          {errorMessage && (
            <div className="p-3.5 rounded-xl bg-[#FEF2F2] border border-[#FECACA] text-xs text-[#DC2626] flex items-start justify-between">
              <div className="flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-[#DC2626] shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-[#991B1B]">Execution Notice</p>
                  <p className="mt-0.5 text-[#B91C1C] leading-relaxed">{errorMessage}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onRetry}
                disabled={isExecuting}
                className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-[#FEE2E2] hover:bg-[#FCA5A5] text-[#991B1B] font-medium text-xs transition cursor-pointer shrink-0 ml-3"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {/* Action Row */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-[#64748B]">
              {taskText.length} characters
            </span>

            <button
              type="submit"
              disabled={isExecuting || !taskText.trim()}
              className="inline-flex items-center space-x-2 px-6 py-2.5 rounded-xl bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold shadow-xs transition cursor-pointer"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Coordinating Agents...</span>
                </>
              ) : (
                <>
                  <span>Submit Task</span>
                  <Send className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* 3. Workflow Execution View (Active or Result) */}
      {(isExecuting || workflowResult || workflowTrace.length > 0) && (
        <div className="space-y-6">
          {/* Status Header Banner */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div
                className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                  workflowResult?.status === 'COMPLETED'
                    ? 'bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]'
                    : workflowResult?.status === 'FAILED'
                    ? 'bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]'
                    : 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE]'
                }`}
              >
                {workflowResult?.status === 'COMPLETED' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : workflowResult?.status === 'FAILED' ? (
                  <XCircle className="w-5 h-5" />
                ) : (
                  <Loader2 className="w-5 h-5 animate-spin" />
                )}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-bold text-[#0F172A]">
                    {workflowResult?.status === 'COMPLETED'
                      ? 'Workflow Completed'
                      : workflowResult?.status === 'FAILED'
                      ? 'Workflow Failed'
                      : 'Workflow Running'}
                  </h2>
                  <span
                    className={`text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded ${
                      workflowResult?.status === 'COMPLETED'
                        ? 'bg-[#ECFDF5] text-[#059669]'
                        : workflowResult?.status === 'FAILED'
                        ? 'bg-[#FEF2F2] text-[#DC2626]'
                        : 'bg-[#F5F3FF] text-[#7C3AED]'
                    }`}
                  >
                    {workflowResult ? workflowResult.status : 'RUNNING'}
                  </span>
                  {workflowTrace.some((s) => s.self_healed || s.provider?.includes('gemini')) && (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#FAF5FF] text-[#7C3AED] border border-[#DDD6FE]">
                      <Sparkles className="w-3 h-3 text-[#7C3AED]" />
                      <span>Auto-Rectified via Gemini AI Studio</span>
                    </span>
                  )}
                </div>

                {workflowResult?.task_id && (
                  <div className="flex items-center space-x-1.5 text-xs text-[#64748B] font-mono mt-0.5">
                    <span>Task ID:</span>
                    <span className="text-[#0F172A] font-semibold">{workflowResult.task_id}</span>
                    <button
                      onClick={() => handleCopyText(workflowResult.task_id, 'taskId')}
                      className="text-[#94A3B8] hover:text-[#7C3AED] transition p-0.5"
                      title="Copy Task ID"
                    >
                      {copiedTaskId ? <Check className="w-3 h-3 text-[#059669]" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Metrics */}
            <div className="flex items-center space-x-4 text-xs font-mono text-[#64748B]">
              {workflowResult?.total_duration_ms !== null && workflowResult?.total_duration_ms !== undefined && (
                <div className="flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5 text-[#94A3B8]" />
                  <span>{(workflowResult.total_duration_ms / 1000).toFixed(2)}s</span>
                </div>
              )}
              <div className="bg-[#F8F9FC] px-2.5 py-1 rounded-md border border-[#E2E8F0]">
                {workflowTrace.length} trace step{workflowTrace.length === 1 ? '' : 's'}
              </div>
            </div>
          </div>

          {/* 4. Five-Stage Workflow Pipeline: Planning → Execution → Memory → Review → Completed */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">
                  Execution Pipeline Stages
                </h3>
                <p className="text-xs text-[#64748B]">
                  Select any stage to inspect agent role, live status, and verified execution output
                </p>
              </div>
              <span className="text-[11px] font-mono text-[#64748B] bg-[#F8F9FC] px-2 py-0.5 rounded border border-[#E2E8F0]">
                Sequential Orchestration
              </span>
            </div>

            {/* Stage Buttons Grid / Breadcrumbs */}
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 pt-1">
              {STAGES.map((st) => {
                const status = getStageStatus(st.id);
                const isSelected = selectedStage === st.id;
                const Icon = st.icon;

                return (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => setSelectedStage(st.id)}
                    className={`p-3 rounded-xl border text-left transition relative cursor-pointer ${
                      isSelected
                        ? 'border-[#7C3AED] bg-[#F5F3FF]/60 ring-2 ring-[#7C3AED]/15'
                        : 'border-[#E2E8F0] bg-white hover:bg-[#F8F9FC]'
                    } ${status === 'RUNNING' ? 'stage-running' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div
                        className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                          status === 'SUCCESS'
                            ? 'bg-[#ECFDF5] text-[#059669]'
                            : status === 'FAILED'
                            ? 'bg-[#FEF2F2] text-[#DC2626]'
                            : status === 'RUNNING'
                            ? 'bg-[#F5F3FF] text-[#7C3AED]'
                            : 'bg-[#F8F9FC] text-[#94A3B8]'
                        }`}
                      >
                        {status === 'RUNNING' ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Icon className="w-3.5 h-3.5" />
                        )}
                      </div>

                      <span
                        className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.2 rounded ${
                          status === 'SUCCESS'
                            ? 'bg-[#ECFDF5] text-[#059669]'
                            : status === 'FAILED'
                            ? 'bg-[#FEF2F2] text-[#DC2626]'
                            : status === 'RUNNING'
                            ? 'bg-[#F5F3FF] text-[#7C3AED]'
                            : 'bg-[#F1F5F9] text-[#94A3B8]'
                        }`}
                      >
                        {status}
                      </span>
                    </div>

                    <div className="text-xs font-bold text-[#0F172A] truncate">
                      {st.name}
                    </div>
                    <div className="text-[10px] text-[#64748B] truncate mt-0.5">
                      {st.role}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Stage Detail Card (When Selected) */}
            <div className="mt-4 p-5 rounded-xl bg-[#F8F9FC] border border-[#E2E8F0] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-[#0F172A]">
                      {selectedMeta.name} Stage
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-white text-[#7C3AED] border border-[#DDD6FE]">
                      {selectedMeta.role}
                    </span>
                  </div>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    {selectedMeta.description}
                  </p>
                </div>

                <span
                  className={`text-xs font-mono font-bold px-2.5 py-1 rounded ${
                    selectedStatus === 'SUCCESS'
                      ? 'bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]'
                      : selectedStatus === 'FAILED'
                      ? 'bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]'
                      : selectedStatus === 'RUNNING'
                      ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE]'
                      : 'bg-white text-[#94A3B8] border border-[#E2E8F0]'
                  }`}
                >
                  {selectedStatus}
                </span>
              </div>

              {/* Stage Step Outputs or Final Completed Preview */}
              {selectedStage === 'completed' ? (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-[#0F172A]">Final Response:</div>
                  {workflowResult?.final_response ? (
                    <div className="p-3.5 rounded-lg bg-white border border-[#E2E8F0] text-xs text-[#0F172A] whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                      {workflowResult.final_response}
                    </div>
                  ) : workflowResult?.error ? (
                    <div className="p-3.5 rounded-lg bg-[#FEF2F2] border border-[#FECACA] text-xs text-[#DC2626] font-mono whitespace-pre-wrap">
                      {workflowResult.error}
                    </div>
                  ) : (
                    <div className="text-xs text-[#64748B] italic">
                      Awaiting completion of upstream agent stages...
                    </div>
                  )}
                </div>
              ) : selectedStageSteps.length > 0 ? (
                <div className="space-y-2">
                  {selectedStageSteps.map((step, idx) => (
                    <div key={idx} className="p-3 rounded-lg bg-white border border-[#E2E8F0] space-y-1.5 text-xs">
                      <div className="flex items-center justify-between font-mono text-[11px] text-[#64748B]">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-[#0F172A]">{step.step_name}</span>
                          {(step.self_healed || step.provider?.includes('gemini')) && (
                            <span className="inline-flex items-center space-x-1 px-1.5 py-0.2 rounded text-[9px] font-semibold bg-[#FAF5FF] text-[#7C3AED] border border-[#DDD6FE]">
                              <Sparkles className="w-2.5 h-2.5 text-[#7C3AED]" />
                              <span>Gemini Auto-Rectified</span>
                            </span>
                          )}
                        </div>
                        <span>{Math.round(step.duration_ms)}ms</span>
                      </div>

                      {step.input_summary && (
                        <p className="text-[#64748B] text-[11px]">
                          <strong className="text-[#475569]">Input:</strong> {step.input_summary}
                        </p>
                      )}
                      {step.output && (
                        <div className="p-2.5 rounded bg-[#F8F9FC] border border-[#E2E8F0] text-[#0F172A] whitespace-pre-wrap text-[11px] max-h-40 overflow-y-auto font-sans leading-relaxed">
                          {step.output}
                        </div>
                      )}
                      {step.error && (
                        <div className="p-2 rounded bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] font-mono text-[11px]">
                          {step.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-[#64748B] italic py-2">
                  {selectedStatus === 'RUNNING'
                    ? 'Agent is currently processing this stage...'
                    : 'No telemetry steps recorded for this stage yet.'}
                </div>
              )}
            </div>
          </div>

          {/* 5. Final Result Panel */}
          {workflowResult && (
            <div
              className={`rounded-2xl border p-6 shadow-xs space-y-4 ${
                workflowResult.status === 'COMPLETED'
                  ? 'bg-white border-[#A7F3D0]'
                  : 'bg-white border-[#FECACA]'
              }`}
            >
              <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
                <div className="flex items-center space-x-2">
                  <CheckCircle2
                    className={`w-5 h-5 ${
                      workflowResult.status === 'COMPLETED' ? 'text-[#059669]' : 'text-[#DC2626]'
                    }`}
                  />
                  <h3 className="text-base font-bold text-[#0F172A]">
                    {workflowResult.status === 'COMPLETED'
                      ? 'Validated Multi-Agent Synthesis'
                      : 'Workflow Error Details'}
                  </h3>
                </div>

                <div className="flex items-center space-x-2">
                  {workflowResult.status === 'FAILED' && (
                    <button
                      onClick={onRetry}
                      disabled={isExecuting}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#FEF2F2] hover:bg-[#FEE2E2] text-[#DC2626] text-xs font-semibold transition cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  )}
                  {workflowResult.final_response && (
                    <button
                      onClick={() => handleCopyText(workflowResult.final_response || '', 'response')}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#F8F9FC] hover:bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] text-xs font-medium transition cursor-pointer"
                    >
                      {copiedResponse ? <Check className="w-3.5 h-3.5 text-[#059669]" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedResponse ? 'Copied' : 'Copy Result'}</span>
                    </button>
                  )}
                </div>
              </div>

              {workflowResult.status === 'COMPLETED' && workflowResult.final_response && (
                <div className="p-4 rounded-xl bg-[#F8F9FC] border border-[#E2E8F0] text-sm text-[#0F172A] leading-relaxed whitespace-pre-wrap">
                  {workflowResult.final_response}
                </div>
              )}

              {workflowResult.status === 'FAILED' && workflowResult.error && (
                <div className="p-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] text-xs text-[#DC2626] font-mono whitespace-pre-wrap">
                  {workflowResult.error}
                </div>
              )}
            </div>
          )}

          {/* 6. Chronological Execution Events Toggle */}
          {workflowEvents.length > 0 && (
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs">
              <button
                type="button"
                onClick={() => setShowTimeline(!showTimeline)}
                className="w-full flex items-center justify-between text-xs font-semibold text-[#0F172A] cursor-pointer"
              >
                <div className="flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-[#7C3AED]" />
                  <span>Execution Events Audit Log ({workflowEvents.length})</span>
                </div>
                <span className="text-[#7C3AED] hover:underline">
                  {showTimeline ? 'Hide details' : 'Show details'}
                </span>
              </button>

              {showTimeline && (
                <div className="mt-4 pt-3 border-t border-[#F1F5F9] space-y-2 max-h-72 overflow-y-auto">
                  {workflowEvents.map((evt) => (
                    <div
                      key={evt.event_id}
                      className="p-2.5 rounded-lg bg-[#F8F9FC] border border-[#E2E8F0] text-xs flex items-center justify-between font-mono"
                    >
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-[#0F172A]">
                          {evt.step_name || evt.event_type}
                        </span>
                        {evt.agent_role && (
                          <span className="text-[10px] text-[#64748B]">({evt.agent_role})</span>
                        )}
                      </div>
                      <div className="flex items-center space-x-2 text-[#64748B] text-[11px]">
                        <span>{evt.duration_ms ? `${Math.round(evt.duration_ms)}ms` : ''}</span>
                        <span
                          className={`font-bold ${
                            evt.status === 'SUCCESS'
                              ? 'text-[#059669]'
                              : evt.status === 'FAILED'
                              ? 'text-[#DC2626]'
                              : 'text-[#7C3AED]'
                          }`}
                        >
                          {evt.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
