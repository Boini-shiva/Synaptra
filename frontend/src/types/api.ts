export interface TraceStep {
  step_name: string;
  agent_role: string;
  agent_id?: string | null;
  status: 'SUCCESS' | 'FAILED' | 'WARNING' | 'SKIPPED' | 'RUNNING';
  started_at: string;
  completed_at: string;
  duration_ms: number;
  input_summary: string;
  output?: string | null;
  error?: string | null;
  retry_count: number;
  provider?: string;
  self_healed?: boolean;
}


export interface WorkflowEvent {
  event_id: string;
  task_id: string;
  event_type: string;
  step_name?: string | null;
  agent_role?: string | null;
  agent_id?: string | null;
  status: string;
  timestamp: string;
  duration_ms?: number | null;
  input_summary?: string | null;
  output?: string | null;
  error?: string | null;
  retry_count: number;
}

export interface WorkflowExecutionRequest {
  task: string;
  workspace_id?: string;
  user_id?: string | null;
  session_id?: string | null;
  task_id?: string | null;
  timeout_seconds?: number;
}

export interface WorkflowExecutionResponse {
  task_id: string;
  status: 'COMPLETED' | 'FAILED' | 'RUNNING';
  task: string;
  workspace_id: string;
  final_response?: string | null;
  execution_trace: TraceStep[];
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
  total_duration_ms?: number | null;
}

export interface WorkflowDetailResponse {
  task_id: string;
  status: 'COMPLETED' | 'FAILED' | 'RUNNING';
  task: string;
  workspace_id: string;
  final_response?: string | null;
  execution_trace: TraceStep[];
  events_count: number;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
  total_duration_ms?: number | null;
}

export interface WorkflowEventsResponse {
  task_id: string;
  count: number;
  events: WorkflowEvent[];
}

export interface WorkflowListItem {
  task_id: string;
  status: 'COMPLETED' | 'FAILED' | 'RUNNING';
  task: string;
  workspace_id: string;
  started_at: string;
  completed_at?: string | null;
  final_response?: string | null;
  total_duration_ms?: number | null;
  error?: string | null;
}

export interface WorkflowListResponse {
  count: number;
  workflows: WorkflowListItem[];
}

export interface MemoryItem {
  memory_id: string;
  content: string;
  memory_type: string;
  created_at: string;
  source_agent: string;
  workspace_id: string;
  visibility: string;
}

export interface MemorySearchItem extends MemoryItem {
  score: number;
}

export interface MemorySearchResponse {
  status: string;
  query: string;
  workspace_id: string;
  count: number;
  results: MemorySearchItem[];
}

export interface MemoryListResponse {
  status: string;
  workspace_id: string;
  count: number;
  memories: MemoryItem[];
}

export interface MemoryCreateRequest {
  content: string;
  memory_type?: string;
  source_agent?: string;
  workspace_id: string;
  visibility?: string;
  memory_id?: string | null;
}

export interface MemoryDeleteResponse {
  status: string;
  deleted_id: string;
  message: string;
}

export interface MemoryHealthResponse {
  status: string;
  qdrant_url: string;
  collection: string;
  collection_exists: boolean;
  points_count: number;
  embedding_model: string;
  vector_dim: number;
}

export interface ConfigDiagnostic {
  env_file_path: string;
  env_file_exists: boolean;
  lyzr_api_key_configured: boolean;
  lyzr_planner_agent_id_configured: boolean;
  lyzr_executor_agent_id_configured: boolean;
  lyzr_memory_agent_id_configured: boolean;
  lyzr_reviewer_agent_id_configured: boolean;
  gemini_api_key_configured?: boolean;
  self_healing_enabled?: boolean;
  all_configured: boolean;
  all_workflow_agents_configured: boolean;
  qdrant_url: string;
  qdrant_collection: string;
}

export interface BackendHealthResponse {
  status: string;
  service: string;
  version: string;
  config: ConfigDiagnostic;
}

export interface WorkflowStatusResponse {
  status: string;
  diagnostic: ConfigDiagnostic;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface Citation {
  id?: string | null;
  content: string;
  score?: number | null;
  workspace_id?: string | null;
}

export interface ChatRequest {
  message: string;
  workspace_id?: string;
  history?: ChatMessage[];
  inject_memory?: boolean;
}

export interface ChatResponse {
  reply: string;
  model: string;
  provider: string;
  workspace_id: string;
  citations: Citation[];
  timestamp: string;
}

export interface ChatSuggestion {
  title: string;
  prompt: string;
  category: string;
}
