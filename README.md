# SYNAPTRA: Collaborative Multi-Agent AI Workflow Platform

SYNAPTRA is an enterprise-grade collaborative multi-agent AI platform combining specialized **Lyzr AI agents** and **Qdrant vector memory** for intelligent, audit-compliant document and workflow orchestration.

---

## 🏛 Architecture Overview

```
User Task ───► POST /api/workflows
                     │
    ┌────────────────▼────────────────┐
    │     Multi-Agent Orchestrator     │
    └──────┬────────────────────┬─────┘
           │                    │
   [1. Qdrant Search]    [6. Qdrant Save]
           │                    │
    ┌──────▼──────┐      ┌──────▼──────┐
    │ Memory Agent│      │ Vector DB   │
    └──────┬──────┘      │  (Qdrant)   │
           │ Context     └─────────────┘
    ┌──────▼──────┐
    │Planner Agent│
    └──────┬──────┘
           │ Action Plan
    ┌──────▼──────┐
    │Executor Agt │ (Bounded concurrency)
    └──────┬──────┘
           │ Execution Results
    ┌──────▼──────┐
    │Reviewer Agt │ (Quality & completeness audit)
    └──────┬──────┘
           │
     Final Response & Execution Trace
```

### Agent Roles

| Agent | ID Environment Variable | Responsibility |
| :--- | :--- | :--- |
| **Memory Agent** | `LYZR_MEMORY_AGENT_ID` | Retrieves relevant historical context from Qdrant vector memory and proposes critical domain knowledge. |
| **Planner Agent** | `LYZR_PLANNER_AGENT_ID` | Decomposes complex user goals into ordered, actionable subtasks. |
| **Executor Agent** | `LYZR_EXECUTOR_AGENT_ID` | Implements each planned subtask using bounded concurrency when subtasks permit. |
| **Reviewer Agent** | `LYZR_REVIEWER_AGENT_ID` | Audits executor outputs, verifies completeness against the plan, and synthesizes the authoritative final answer. |

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your Lyzr credentials and Qdrant settings:

```env
# ==============================================================================
# Lyzr Agent API Credentials (Studio API Key)
# ==============================================================================
LYZR_API_KEY=sk-default-your_api_key_here

# 1. Planner Agent: Decomposes high-level user tasks into sequential action plans
LYZR_PLANNER_AGENT_ID=your_planner_agent_id_here

# 2. Executor Agent: Implements and executes assigned subtasks
LYZR_EXECUTOR_AGENT_ID=your_executor_agent_id_here

# 3. Memory Agent: Synthesizes context from Qdrant vector memory
LYZR_MEMORY_AGENT_ID=your_memory_agent_id_here

# 4. Reviewer Agent: Audits results, checks for missing work, produces final answer
LYZR_REVIEWER_AGENT_ID=your_reviewer_agent_id_here

# ==============================================================================
# Google Gemini AI Studio (Self-Healing Engine & AI Copilot)
# ==============================================================================
GEMINI_API_KEY=your_gemini_api_key_here

# ==============================================================================
# Qdrant Vector Database
# ==============================================================================
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=synaptra_memory
QDRANT_API_KEY=
```

> **Security Note:** Secrets are strictly loaded on the backend from root `.env` and are never exposed in logs or API diagnostics.

---

## ☁️ 1-Click Vercel Deployment (Unified Monorepo)

SYNAPTRA is structured to deploy both **React Vite frontend** and **FastAPI Python backend** together on [Vercel](https://vercel.com) in one click!

1. Import this repository into Vercel.
2. Leave the Root Directory as `./` (the root).
3. Add your environment variables (`GEMINI_API_KEY`, `LYZR_API_KEY`, agent IDs, `QDRANT_URL`) in Vercel Project Settings.
4. Click **Deploy**. Vercel automatically:
   - Builds frontend React bundle with `npm --prefix frontend run build` to `frontend/dist`.
   - Mounts the Python serverless function at `/api` using `api/index.py`.
   - Routes same-origin `/api/...` calls without any CORS configuration needed!

*See [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for full deployment instructions.*

---

## 🚀 Running the Full Stack (Three-Terminal Workflow)

To run the complete SYNAPTRA platform locally, launch the following services in three separate terminals:

### Terminal 1: Qdrant Vector Database
Start the containerized Qdrant vector memory instance:
```bash
docker-compose up -d
```
Verify Qdrant is listening at `http://127.0.0.1:6333`.

### Terminal 2: FastAPI Multi-Agent Backend
Activate the virtual environment and start the Uvicorn ASGI server:
```bash
# Windows PowerShell
.\backend\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# Linux / macOS
source backend/.venv/bin/activate
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
Verify the backend diagnostics at `http://127.0.0.1:8000/api/health`.

### Terminal 3: React + Vite Frontend Dashboard
Install frontend dependencies and launch the development server on port 5173:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://127.0.0.1:5173/` to view the SYNAPTRA dashboard.

---

## 🎨 Frontend Configuration & Architecture

The frontend is built with **React**, **Vite**, **TypeScript**, and **Tailwind CSS**.

### Environment Setup
Create `frontend/.env` based on `frontend/.env.example`:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```
> **Security Guarantee:** No Lyzr API keys or agent credentials exist in the client environment. The frontend interacts strictly with the verified backend API.

### Component Structure
- `Sidebar.tsx`: Navigation (Overview, Orchestrator, Vector Memory, Diagnostics) and live backend connectivity status.
- `DashboardOverview.tsx`: System-wide metrics, active workspace badge, and interactive 5-phase pipeline architecture visualizer.
- `TaskComposer.tsx`: Task input text area, sample prompts, workspace picker, advanced session parameters, and execution dispatch.
- `AgentWorkflow.tsx`: Real-time visualization of the 4 specialized agents (**Memory**, **Planner**, **Executor**, **Reviewer**) derived from backend telemetry.
- `ExecutionTimeline.tsx`: Live audit trail of chronological execution events with expandable input/output details.
- `ResultPanel.tsx`: Final synthesized Reviewer Agent response or truthful upstream failure trace, with copy-to-clipboard functionality.
- `MemoryBrowser.tsx`: Qdrant vector memory explorer with debounced semantic search, tenant workspace filtering, delete confirmation modal, and memory creation.
- `SettingsPanel.tsx`: Infrastructure diagnostics displaying backend health, vector collection stats, and Lyzr agent credential verification without secret exposure.

### Building for Production
```bash
cd frontend
npm run build
```

---

## 📡 API Reference & Examples

### Multi-Agent Workflows

#### 1. Execute Multi-Agent Workflow
- **Endpoint**: `POST /api/workflows` (or alias `POST /api/workflow/execute`)
- **Headers**: `Content-Type: application/json`

**PowerShell Example**:
```powershell
$body = @{
    task = "Audit invoice INV-2026-901 for duplicate vendor billing and verify tax calculation"
    workspace_id = "gov_audit_workspace"
    timeout_seconds = 60.0
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/api/workflows `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

**Response**:
```json
{
  "task_id": "task_a9f8b12c4e67",
  "status": "COMPLETED",
  "task": "Audit invoice INV-2026-901 for duplicate vendor billing and verify tax calculation",
  "workspace_id": "gov_audit_workspace",
  "final_response": "Audit Verification Report: Vendor invoice INV-2026-901 verified against procurement rules...",
  "execution_trace": [
    {
      "step_name": "memory_retrieval",
      "agent_role": "qdrant_vector_memory",
      "status": "SUCCESS",
      "duration_ms": 14.2
    },
    {
      "step_name": "memory_synthesis",
      "agent_role": "memory_agent",
      "status": "SUCCESS",
      "duration_ms": 7820.5
    },
    {
      "step_name": "plan_generation",
      "agent_role": "planner_agent",
      "status": "SUCCESS",
      "duration_ms": 6410.1
    },
    {
      "step_name": "subtask_execution",
      "agent_role": "executor_agent",
      "status": "SUCCESS",
      "duration_ms": 9120.3
    },
    {
      "step_name": "review_and_synthesis",
      "agent_role": "reviewer_agent",
      "status": "SUCCESS",
      "duration_ms": 8100.2
    },
    {
      "step_name": "memory_storage",
      "agent_role": "qdrant_vector_memory",
      "status": "SUCCESS",
      "duration_ms": 35.1
    }
  ],
  "started_at": "2026-10-14T10:30:00.000000+00:00",
  "completed_at": "2026-10-14T10:30:31.500000+00:00",
  "total_duration_ms": 31500.0
}
```

#### 2. Get Workflow State & Details
- **Endpoint**: `GET /api/workflows/{task_id}`

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/workflows/task_a9f8b12c4e67 -Method Get
```

#### 3. Get Workflow Chronological Events
- **Endpoint**: `GET /api/workflows/{task_id}/events`

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/workflows/task_a9f8b12c4e67/events -Method Get
```

#### 4. Workflow Diagnostics Status
- **Endpoint**: `GET /api/workflows/status`

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/workflows/status -Method Get
```

---

### Vector Memory Operations

#### 1. Store Memory
- **Endpoint**: `POST /api/memory`

```powershell
$body = @{
    content = "Procurement Rule 402: Contracts exceeding $100,000 require independent committee review."
    memory_type = "policy_rule"
    source_agent = "compliance_agent"
    workspace_id = "gov_audit_workspace"
    visibility = "shared"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/api/memory `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

#### 2. Semantic Search in Workspace
- **Endpoint**: `GET /api/memory/search?q={query}&workspace_id={workspace_id}`

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/memory/search?q=procurement+spending+limits&workspace_id=gov_audit_workspace" `
    -Method Get
```

#### 3. List Memories
- **Endpoint**: `GET /api/memory?workspace_id={workspace_id}`

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/memory?workspace_id=gov_audit_workspace" -Method Get
```

---

## 🧪 Testing

The test suite contains automated tests covering request validation, mocked multi-agent orchestration, agent failure handling, Qdrant resilience, workspace isolation, event ordering, and live Lyzr execution:

```powershell
# Run the complete test suite
.\backend\.venv\Scripts\python.exe -m pytest backend -v

# Run only unit & mocked workflow tests (fast, ~3 seconds)
.\backend\.venv\Scripts\python.exe -m pytest backend/test_workflow.py -k "not live" -v

# Run full live integration test against real Lyzr agents and Qdrant
.\backend\.venv\Scripts\python.exe -m pytest backend/test_workflow.py -k "test_workflow_live_execution_if_configured" -v -s
```
