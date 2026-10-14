import { useState, useEffect, useRef, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import type { NavTab } from './components/Sidebar';
import { OverviewPage } from './components/OverviewPage';
import { NewWorkflowPage } from './components/NewWorkflowPage';
import { WorkflowHistoryPage } from './components/WorkflowHistoryPage';
import { MemoryBrowser } from './components/MemoryBrowser';
import { SettingsPage } from './components/SettingsPage';
import { ChatAssistantPage } from './components/ChatAssistantPage';
import { api, ApiError } from './services/api';
import type {
  BackendHealthResponse,
  MemoryHealthResponse,
  WorkflowEvent,
  WorkflowExecutionResponse,
  TraceStep,
} from './types/api';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [activeWorkspace, setActiveWorkspace] = useState<string>('default');

  // Health and connection state
  const [backendHealth, setBackendHealth] = useState<BackendHealthResponse | null>(null);
  const [memoryHealth, setMemoryHealth] = useState<MemoryHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // Workflow Task Execution State
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [workflowResult, setWorkflowResult] = useState<WorkflowExecutionResponse | null>(null);
  const [workflowEvents, setWorkflowEvents] = useState<WorkflowEvent[]>([]);
  const [workflowTrace, setWorkflowTrace] = useState<TraceStep[]>([]);
  const [taskErrorMessage, setTaskErrorMessage] = useState<string | null>(null);
  const [activeTaskPrompt, setActiveTaskPrompt] = useState<string>('');

  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 1. Initial Health Checks
  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const [bHealth, mHealth] = await Promise.allSettled([
        api.getHealth(),
        api.getMemoryHealth(),
      ]);

      if (bHealth.status === 'fulfilled') {
        setBackendHealth(bHealth.value);
      } else {
        setBackendHealth(null);
      }

      if (mHealth.status === 'fulfilled') {
        setMemoryHealth(mHealth.value);
      } else {
        setMemoryHealth(null);
      }
    } catch {
      // Handled by allSettled
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 30000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  // 2. Stop Polling Helper
  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // 3. Workflow Polling Routine
  const pollWorkflowStatus = useCallback(
    async (taskId: string) => {
      try {
        const [detailRes, eventsRes] = await Promise.allSettled([
          api.getWorkflow(taskId),
          api.getWorkflowEvents(taskId),
        ]);

        if (eventsRes.status === 'fulfilled') {
          setWorkflowEvents(eventsRes.value.events || []);
        }

        if (detailRes.status === 'fulfilled') {
          const detail = detailRes.value;
          if (detail.execution_trace) {
            setWorkflowTrace(detail.execution_trace);
          }

          if (detail.status === 'COMPLETED' || detail.status === 'FAILED') {
            setWorkflowResult({
              task_id: detail.task_id,
              status: detail.status,
              task: detail.task,
              workspace_id: detail.workspace_id,
              final_response: detail.final_response,
              execution_trace: detail.execution_trace,
              error: detail.error,
              started_at: detail.started_at,
              completed_at: detail.completed_at,
              total_duration_ms: detail.total_duration_ms,
            });
            setIsExecuting(false);
            stopPolling();
            refreshHealth();
          }
        }
      } catch {
        // Silently continue polling
      }
    },
    [stopPolling, refreshHealth]
  );

  // 4. Submit Task Handler
  const handleTaskSubmit = async (task: string, workspaceId: string) => {
    setActiveTaskPrompt(task);
    setTaskErrorMessage(null);
    setIsExecuting(true);
    setWorkflowResult(null);
    setWorkflowEvents([]);
    setWorkflowTrace([]);
    stopPolling();

    const clientTaskId = `task_${Math.random().toString(36).substring(2, 10)}${Date.now().toString(36).slice(-4)}`;

    pollingTimerRef.current = setInterval(() => {
      pollWorkflowStatus(clientTaskId);
    }, 1500);

    try {
      const response = await api.submitWorkflow({
        task,
        workspace_id: workspaceId,
        task_id: clientTaskId,
      });

      setWorkflowResult(response);
      setWorkflowTrace(response.execution_trace || []);
      setIsExecuting(false);
      stopPolling();

      try {
        const evts = await api.getWorkflowEvents(response.task_id);
        setWorkflowEvents(evts.events || []);
      } catch {
        // Ignore
      }
      refreshHealth();
    } catch (err: any) {
      stopPolling();
      setIsExecuting(false);

      if (err instanceof ApiError && err.data && err.data.detail) {
        const detail = err.data.detail;
        if (typeof detail === 'object' && detail.task_id) {
          const failedResult: WorkflowExecutionResponse = {
            task_id: detail.task_id,
            status: 'FAILED',
            task,
            workspace_id: workspaceId,
            error: detail.message || err.message,
            execution_trace: detail.execution_trace || [],
            started_at: new Date().toISOString(),
          };
          setWorkflowResult(failedResult);
          setWorkflowTrace(detail.execution_trace || []);
          setTaskErrorMessage(detail.message || err.message);

          try {
            const evts = await api.getWorkflowEvents(detail.task_id);
            setWorkflowEvents(evts.events || []);
          } catch {
            // Ignore
          }
          return;
        }
      }

      setTaskErrorMessage(err.message || 'An error occurred while submitting task to orchestrator.');
    }
  };

  const handleLaunchFromOverview = (taskText: string) => {
    setActiveTaskPrompt(taskText);
    setActiveTab('new_workflow');
    handleTaskSubmit(taskText, activeWorkspace);
  };

  const handleInspectWorkflow = async (taskId: string) => {
    try {
      const [detail, evts] = await Promise.all([
        api.getWorkflow(taskId),
        api.getWorkflowEvents(taskId),
      ]);
      setWorkflowResult({
        task_id: detail.task_id,
        status: detail.status,
        task: detail.task,
        workspace_id: detail.workspace_id,
        final_response: detail.final_response,
        execution_trace: detail.execution_trace || [],
        error: detail.error,
        started_at: detail.started_at,
        completed_at: detail.completed_at,
        total_duration_ms: detail.total_duration_ms,
      });
      setWorkflowTrace(detail.execution_trace || []);
      setWorkflowEvents(evts.events || []);
      setActiveTaskPrompt(detail.task);
      setActiveTab('new_workflow');
    } catch (err: any) {
      setTaskErrorMessage(`Failed to load workflow ${taskId}: ${err.message}`);
    }
  };

  return (
    <div className="flex h-screen bg-[#F8F9FC] text-[#0F172A] overflow-hidden font-sans">
      {/* 1. Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab)}
        backendHealth={backendHealth}
        memoryHealth={memoryHealth}
        healthLoading={healthLoading}
        activeWorkspace={activeWorkspace}
        onWorkspaceChange={(ws) => setActiveWorkspace(ws)}
      />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Header Bar */}
        <header className="h-16 border-b border-[#E2E8F0] bg-white/80 backdrop-blur-md px-6 lg:px-8 flex items-center justify-between sticky top-0 z-10 shrink-0">
          <div className="flex items-center space-x-3">
            <h2 className="text-base font-bold text-[#0F172A] capitalize">
              {activeTab === 'overview'
                ? 'Overview'
                : activeTab === 'new_workflow'
                ? 'New Workflow'
                : activeTab === 'history'
                ? 'Workflow History'
                : activeTab === 'memory'
                ? 'Vector Memory'
                : activeTab === 'chat'
                ? 'AI Assistant'
                : 'Settings'}
            </h2>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#F8F9FC] text-[#7C3AED] border border-[#DDD6FE]">
              workspace: {activeWorkspace}
            </span>
          </div>

          <div className="flex items-center space-x-3 text-xs text-[#64748B]">
            <span className="font-mono text-[#94A3B8] hidden sm:inline">SYNAPTRA v0.3.0</span>
            <div className="h-3 w-px bg-[#E2E8F0] hidden sm:block" />
            <span className="flex items-center space-x-1.5 font-medium">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendHealth?.status === 'ok' ? 'bg-[#059669]' : 'bg-[#DC2626]'
                }`}
              />
              <span className={backendHealth?.status === 'ok' ? 'text-[#059669]' : 'text-[#DC2626]'}>
                {backendHealth?.status === 'ok' ? 'Connected' : 'Disconnected'}
              </span>
            </span>
          </div>
        </header>

        {/* View Content Tabs */}
        <div className="p-6 lg:p-8 flex-1">
          {activeTab === 'overview' && (
            <OverviewPage
              onNavigate={(tab) => setActiveTab(tab)}
              onLaunchWorkflow={handleLaunchFromOverview}
              onSelectWorkflow={handleInspectWorkflow}
              activeWorkspace={activeWorkspace}
              backendHealth={backendHealth}
              memoryHealth={memoryHealth}
            />
          )}

          {activeTab === 'new_workflow' && (
            <NewWorkflowPage
              initialPrompt={activeTaskPrompt}
              activeWorkspace={activeWorkspace}
              onWorkspaceChange={(ws) => setActiveWorkspace(ws)}
              onSubmitTask={(task, ws) => handleTaskSubmit(task, ws)}
              isExecuting={isExecuting}
              workflowResult={workflowResult}
              workflowTrace={workflowTrace}
              workflowEvents={workflowEvents}
              errorMessage={taskErrorMessage}
              onRetry={() => {
                if (activeTaskPrompt) handleTaskSubmit(activeTaskPrompt, activeWorkspace);
              }}
            />
          )}

          {activeTab === 'history' && (
            <WorkflowHistoryPage
              activeWorkspace={activeWorkspace}
              onInspectWorkflow={handleInspectWorkflow}
            />
          )}

          {activeTab === 'memory' && (
            <MemoryBrowser
              activeWorkspace={activeWorkspace}
              onWorkspaceChange={(ws) => setActiveWorkspace(ws)}
              onMemoryCountUpdated={refreshHealth}
            />
          )}

          {activeTab === 'chat' && (
            <ChatAssistantPage activeWorkspace={activeWorkspace} />
          )}

          {activeTab === 'settings' && (
            <SettingsPage
              backendHealth={backendHealth}
              memoryHealth={memoryHealth}
              isLoading={healthLoading}
              onRefresh={refreshHealth}
              activeWorkspace={activeWorkspace}
              onWorkspaceChange={(ws) => setActiveWorkspace(ws)}
            />
          )}
        </div>
      </main>
    </div>
  );
}


export default App;
