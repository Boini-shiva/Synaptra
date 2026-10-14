import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  ArrowRight,
  Database,
  Layers,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
  Lightbulb,
  Server,
} from 'lucide-react';
import { api } from '../services/api';
import type {
  BackendHealthResponse,
  MemoryHealthResponse,
  WorkflowListItem,
} from '../types/api';
import type { NavTab } from './Sidebar';

interface OverviewPageProps {
  onNavigate: (tab: NavTab) => void;
  onLaunchWorkflow: (taskText: string) => void;
  onSelectWorkflow: (taskId: string) => void;
  activeWorkspace: string;
  backendHealth: BackendHealthResponse | null;
  memoryHealth: MemoryHealthResponse | null;
}

const SAMPLE_PROMPTS = [
  'Create a 3-step plan for preparing a hackathon project. Retrieve relevant memories and review.',
  'Analyze municipal vendor procurement contracts to detect duplicate billing anomalies.',
  'Formulate an audit checklist for cloud infrastructure invoices with sudden compute spikes.',
];

export const OverviewPage: React.FC<OverviewPageProps> = ({
  onNavigate,
  onLaunchWorkflow,
  onSelectWorkflow,
  activeWorkspace,
  backendHealth,
  memoryHealth,
}) => {
  const [taskInput, setTaskInput] = useState('');
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);

  const isBackendOk = backendHealth?.status === 'ok';
  const isQdrantOk = memoryHealth?.status === 'ok';

  // Load real workflows for this workspace
  const fetchWorkflows = async () => {
    setLoadingWorkflows(true);
    try {
      const res = await api.listWorkflows(activeWorkspace, 10);
      setWorkflows(res.workflows || []);
    } catch {
      setWorkflows([]);
    } finally {
      setLoadingWorkflows(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, [activeWorkspace]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskInput.trim()) return;
    onLaunchWorkflow(taskInput.trim());
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* 1. Header Hero */}
      <div className="space-y-1.5 pt-2">
        <h1 className="text-3xl font-extrabold text-[#0F172A] tracking-tight">
          Your AI workspace
        </h1>
        <p className="text-base text-[#64748B]">
          Turn requests into coordinated workflows.
        </p>
      </div>

      {/* 2. Prominent Task Input Composer (Visual Focus) */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-sm focus-within:border-[#7C3AED] focus-within:ring-2 focus-within:ring-[#7C3AED]/10 transition">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B] flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[#7C3AED]" />
              <span>Multi-Agent Task Dispatcher</span>
            </span>
            <span className="text-xs text-[#64748B] font-mono bg-[#F8F9FC] px-2.5 py-1 rounded-md border border-[#E2E8F0]">
              workspace: <span className="font-semibold text-[#7C3AED]">{activeWorkspace}</span>
            </span>
          </div>

          {/* Multiline textarea */}
          <div className="relative">
            <textarea
              rows={3}
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              placeholder="What goal would you like the multi-agent team to accomplish?"
              className="w-full bg-transparent text-[#0F172A] placeholder-[#94A3B8] text-base focus:outline-none resize-none leading-relaxed"
            />
          </div>

          {/* Bottom Bar: Quick prompts + Primary CTA */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-[#F1F5F9]">
            {/* Quick starter chips */}
            <div className="flex items-center space-x-1.5 overflow-x-auto py-1">
              <Lightbulb className="w-3.5 h-3.5 text-[#D97706] shrink-0" />
              {SAMPLE_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setTaskInput(prompt)}
                  className="text-xs text-[#475569] hover:text-[#7C3AED] hover:bg-[#F5F3FF] bg-[#F8F9FC] border border-[#E2E8F0] rounded-md px-2.5 py-1 whitespace-nowrap transition cursor-pointer"
                >
                  {prompt.substring(0, 32)}...
                </button>
              ))}
            </div>

            {/* Run Workflow CTA */}
            <button
              type="submit"
              disabled={!taskInput.trim()}
              className="inline-flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold shadow-xs transition cursor-pointer shrink-0"
            >
              <span>Run workflow</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>

      {/* 3. Compact Summary Cards (Real API data only) */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {/* Workflows Executed */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Recorded Workflows
            </span>
            <div className="w-7 h-7 rounded-lg bg-[#F5F3FF] flex items-center justify-center text-[#7C3AED]">
              <Sparkles className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#0F172A] mb-0.5">
            {workflows.length}
          </div>
          <p className="text-xs text-[#64748B]">
            {workflows.length > 0
              ? `${workflows.length} workflow${workflows.length === 1 ? '' : 's'} in ${activeWorkspace}`
              : 'No tasks run in this session'}
          </p>
        </div>

        {/* Vector Memories */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Vector Memories
            </span>
            <div className="w-7 h-7 rounded-lg bg-[#ECFDF5] flex items-center justify-center text-[#059669]">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#0F172A] mb-0.5">
            {memoryHealth && isQdrantOk ? memoryHealth.points_count : '—'}
          </div>
          <p className="text-xs text-[#64748B]">
            {isQdrantOk ? 'Indexed in Qdrant collection' : 'Status unknown'}
          </p>
        </div>

        {/* Backend API */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              FastAPI Backend
            </span>
            <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] flex items-center justify-center text-[#2563EB]">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#0F172A] mb-0.5">
            {isBackendOk ? 'Online' : 'Offline'}
          </div>
          <p className="text-xs text-[#64748B]">
            {isBackendOk ? 'Orchestrator ready' : 'Connecting to API'}
          </p>
        </div>

        {/* Workspace Isolation */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Tenant Workspace
            </span>
            <div className="w-7 h-7 rounded-lg bg-[#F1F5F9] flex items-center justify-center text-[#475569]">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-[#7C3AED] truncate mb-0.5">
            {activeWorkspace}
          </div>
          <p className="text-xs text-[#64748B]">
            Isolated vector search partition
          </p>
        </div>
      </div>

      {/* 4. Recent Workflows Section */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
          <div>
            <h2 className="text-base font-bold text-[#0F172A]">Recent Workflows</h2>
            <p className="text-xs text-[#64748B]">
              Real-time activity log from orchestrator
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={fetchWorkflows}
              disabled={loadingWorkflows}
              className="text-[#64748B] hover:text-[#0F172A] p-1.5 rounded-lg hover:bg-[#F1F5F9] transition cursor-pointer"
              title="Refresh workflows"
            >
              <RefreshCw className={`w-4 h-4 ${loadingWorkflows ? 'animate-spin text-[#7C3AED]' : ''}`} />
            </button>
            <button
              onClick={() => onNavigate('history')}
              className="text-xs font-semibold text-[#7C3AED] hover:text-[#6D28D9] flex items-center space-x-1 cursor-pointer"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Loading state */}
        {loadingWorkflows && (
          <div className="py-8 text-center text-[#64748B] space-y-2">
            <Loader2 className="w-5 h-5 animate-spin mx-auto text-[#7C3AED]" />
            <p className="text-xs">Loading workflow runs...</p>
          </div>
        )}

        {/* Empty state (Clean, truthful, as required) */}
        {!loadingWorkflows && workflows.length === 0 && (
          <div className="py-10 px-4 text-center space-y-2.5">
            <div className="w-10 h-10 rounded-full bg-[#F8F9FC] border border-[#E2E8F0] flex items-center justify-center mx-auto text-[#94A3B8]">
              <Clock className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-[#1E293B]">
              No workflows executed yet
            </h3>
            <p className="text-xs text-[#64748B] max-w-sm mx-auto">
              Submit your first task using the composer above. Your agent plan, memory retrieval, and final review will appear here.
            </p>
          </div>
        )}

        {/* List of real workflows */}
        {!loadingWorkflows && workflows.length > 0 && (
          <div className="divide-y divide-[#F1F5F9]">
            {workflows.slice(0, 5).map((wf) => {
              const isCompleted = wf.status === 'COMPLETED';
              const isFailed = wf.status === 'FAILED';

              return (
                <div
                  key={wf.task_id}
                  onClick={() => onSelectWorkflow(wf.task_id)}
                  className="py-3.5 flex items-center justify-between gap-4 hover:bg-[#F8F9FC] px-2 rounded-lg transition cursor-pointer group"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold font-mono ${
                          isCompleted
                            ? 'bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]'
                            : isFailed
                            ? 'bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]'
                            : 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE]'
                        }`}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : isFailed ? (
                          <XCircle className="w-3 h-3" />
                        ) : (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        )}
                        <span>{wf.status}</span>
                      </span>
                      <span className="text-[11px] font-mono text-[#94A3B8]">
                        {wf.task_id}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-[#0F172A] truncate">
                      {wf.task}
                    </p>
                  </div>

                  <div className="flex items-center space-x-3 text-right shrink-0">
                    <div className="text-xs text-[#64748B]">
                      {wf.total_duration_ms ? `${Math.round(wf.total_duration_ms / 1000)}s` : '—'}
                    </div>
                    <ArrowRight className="w-4 h-4 text-[#CBD5E1] group-hover:text-[#7C3AED] transition" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
