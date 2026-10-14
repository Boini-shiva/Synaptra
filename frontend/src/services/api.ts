import type {
  BackendHealthResponse,
  ConfigDiagnostic,
  MemoryCreateRequest,
  MemoryDeleteResponse,
  MemoryHealthResponse,
  MemoryItem,
  MemoryListResponse,
  MemorySearchResponse,
  WorkflowDetailResponse,
  WorkflowEventsResponse,
  WorkflowExecutionRequest,
  WorkflowExecutionResponse,
  WorkflowListItem,
  WorkflowListResponse,
  WorkflowStatusResponse,
} from '../types/api';

export type { WorkflowListItem, WorkflowListResponse };

// If VITE_API_BASE_URL is explicitly defined, use it.
// In production (Vercel deployment), default to '' for relative same-origin calls (/api/...)
// In development, fallback to local backend on http://127.0.0.1:8002
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined
  ? import.meta.env.VITE_API_BASE_URL
  : (import.meta.env.PROD ? '' : 'http://127.0.0.1:8002');
// Strip trailing slash if present
export const API_BASE_URL = (RAW_BASE_URL || '').replace(/\/+$/, '');


export class ApiError extends Error {
  public status: number;
  public data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new ApiError(0, `Network error connecting to backend: ${err.message || 'Connection refused'}`);
  }

  let responseData: any = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      responseData = await response.json();
    } catch {
      responseData = null;
    }
  } else {
    try {
      responseData = await response.text();
    } catch {
      responseData = null;
    }
  }

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status} ${response.statusText}`;
    if (responseData && typeof responseData === 'object') {
      if (typeof responseData.detail === 'string') {
        errorMsg = responseData.detail;
      } else if (responseData.detail && typeof responseData.detail.message === 'string') {
        errorMsg = responseData.detail.message;
      } else if (responseData.message) {
        errorMsg = responseData.message;
      }
    }
    throw new ApiError(response.status, errorMsg, responseData);
  }

  return responseData as T;
}

export const api = {
  // System Diagnostics
  async getHealth(): Promise<BackendHealthResponse> {
    return request<BackendHealthResponse>('/api/health');
  },

  async getConfigStatus(): Promise<ConfigDiagnostic> {
    return request<ConfigDiagnostic>('/api/config/status');
  },

  async getWorkflowStatus(): Promise<WorkflowStatusResponse> {
    return request<WorkflowStatusResponse>('/api/workflows/status');
  },

  // Workflow Orchestration
  async listWorkflows(workspaceId?: string, limit: number = 50): Promise<WorkflowListResponse> {
    const params = new URLSearchParams();
    if (workspaceId) {
      params.set('workspace_id', workspaceId);
    }
    params.set('limit', String(limit));
    return request<WorkflowListResponse>(`/api/workflows?${params.toString()}`);
  },

  async submitWorkflow(req: WorkflowExecutionRequest): Promise<WorkflowExecutionResponse> {
    return request<WorkflowExecutionResponse>('/api/workflows', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async getWorkflow(taskId: string): Promise<WorkflowDetailResponse> {
    return request<WorkflowDetailResponse>(`/api/workflows/${encodeURIComponent(taskId)}`);
  },

  async getWorkflowEvents(taskId: string): Promise<WorkflowEventsResponse> {
    return request<WorkflowEventsResponse>(`/api/workflows/${encodeURIComponent(taskId)}/events`);
  },

  // Qdrant Vector Memory
  async getMemoryHealth(): Promise<MemoryHealthResponse> {
    return request<MemoryHealthResponse>('/api/memory/health');
  },

  async listMemories(
    workspaceId: string,
    limit: number = 30,
    memoryType?: string,
    visibility?: string
  ): Promise<MemoryListResponse> {
    const params = new URLSearchParams();
    params.set('workspace_id', workspaceId);
    params.set('limit', String(limit));
    if (memoryType && memoryType !== 'all') {
      params.set('memory_type', memoryType);
    }
    if (visibility && visibility !== 'all') {
      params.set('visibility', visibility);
    }
    return request<MemoryListResponse>(`/api/memory?${params.toString()}`);
  },

  async searchMemories(
    query: string,
    workspaceId: string,
    limit: number = 10,
    memoryType?: string,
    visibility?: string
  ): Promise<MemorySearchResponse> {
    const params = new URLSearchParams();
    params.set('q', query);
    params.set('workspace_id', workspaceId);
    params.set('limit', String(limit));
    if (memoryType && memoryType !== 'all') {
      params.set('memory_type', memoryType);
    }
    if (visibility && visibility !== 'all') {
      params.set('visibility', visibility);
    }
    return request<MemorySearchResponse>(`/api/memory/search?${params.toString()}`);
  },

  async createMemory(req: MemoryCreateRequest): Promise<MemoryItem> {
    return request<MemoryItem>('/api/memory', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async deleteMemory(memoryId: string, workspaceId: string): Promise<MemoryDeleteResponse> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    return request<MemoryDeleteResponse>(
      `/api/memory/${encodeURIComponent(memoryId)}?${params.toString()}`,
      { method: 'DELETE' }
    );
  },

  // Interactive AI Assistant (Google Gemini AI Studio + Vector Memory)
  async sendChatMessage(req: import('../types/api').ChatRequest): Promise<import('../types/api').ChatResponse> {
    return request<import('../types/api').ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async getChatSuggestions(): Promise<{ suggestions: import('../types/api').ChatSuggestion[] }> {
    return request<{ suggestions: import('../types/api').ChatSuggestion[] }>('/api/chat/suggestions');
  },
};

