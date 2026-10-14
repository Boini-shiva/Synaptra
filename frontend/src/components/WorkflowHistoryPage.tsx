import { useState, useEffect, useCallback } from 'react';
import {
  History,
  Search,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  Copy,
  Check,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '../services/api';
import type { WorkflowListItem } from '../types/api';

interface WorkflowHistoryPageProps {
  activeWorkspace: string;
  onInspectWorkflow: (taskId: string) => void;
}

export const WorkflowHistoryPage: React.FC<WorkflowHistoryPageProps> = ({
  activeWorkspace,
  onInspectWorkflow,
}) => {
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchWorkflows = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.listWorkflows(activeWorkspace, 50);
      setWorkflows(res.workflows || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch workflow history from orchestrator.');
      setWorkflows([]);
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleCopyId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredWorkflows = workflows.filter((wf) => {
    const matchesSearch =
      wf.task.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.task_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || wf.status.toUpperCase() === statusFilter.toUpperCase();
    return matchesSearch && matchesStatus;
  });

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">
            Workflow History
          </h1>
          <p className="text-sm text-[#64748B] mt-0.5">
            Audit history of all executed multi-agent tasks in workspace{' '}
            <span className="font-mono text-[#7C3AED] font-semibold">{activeWorkspace}</span>
          </p>
        </div>

        <button
          onClick={fetchWorkflows}
          disabled={isLoading}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F8F9FC] border border-[#E2E8F0] text-xs font-semibold text-[#0F172A] shadow-2xs transition cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#7C3AED]' : 'text-[#64748B]'}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs flex flex-col sm:flex-row items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-[#94A3B8] absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by task description or task ID..."
            className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white text-xs text-[#0F172A] rounded-lg pl-9 pr-3 py-2 focus:outline-none transition"
          />
        </div>

        {/* Status Dropdown */}
        <div className="w-full sm:w-44">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] text-xs text-[#0F172A] rounded-lg px-3 py-2 focus:outline-none cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="RUNNING">Running</option>
          </select>
        </div>

        <div className="text-xs text-[#64748B] font-mono shrink-0">
          {filteredWorkflows.length} item{filteredWorkflows.length === 1 ? '' : 's'}
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] text-xs text-[#DC2626] flex items-center justify-between">
          <span>{errorMessage}</span>
          <button
            onClick={fetchWorkflows}
            className="text-xs font-semibold text-[#991B1B] hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="py-12 text-center text-[#64748B] space-y-2">
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-[#7C3AED]" />
          <p className="text-xs">Fetching history from orchestrator...</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !errorMessage && filteredWorkflows.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-10 text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-[#F8F9FC] border border-[#E2E8F0] flex items-center justify-center mx-auto text-[#94A3B8]">
            <History className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-[#0F172A]">
            No Workflows Found
          </h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto">
            {searchQuery || statusFilter !== 'all'
              ? 'No workflow runs match the applied filters. Try clearing your search.'
              : `Workspace "${activeWorkspace}" has no recorded workflow executions yet.`}
          </p>
        </div>
      )}

      {/* Workflow List Cards */}
      {!isLoading && filteredWorkflows.length > 0 && (
        <div className="space-y-3">
          {filteredWorkflows.map((wf) => {
            const isCompleted = wf.status === 'COMPLETED';
            const isFailed = wf.status === 'FAILED';
            const isExpanded = expandedId === wf.task_id;

            return (
              <div
                key={wf.task_id}
                className="bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] rounded-xl p-4 shadow-2xs transition"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1 mb-1.5">
                      {/* Status Badge */}
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
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

                      {/* Task ID with Copy */}
                      <span className="inline-flex items-center space-x-1 text-[11px] font-mono text-[#64748B] bg-[#F8F9FC] px-1.5 py-0.5 rounded border border-[#E2E8F0]">
                        <span>{wf.task_id}</span>
                        <button
                          onClick={(e) => handleCopyId(e, wf.task_id)}
                          className="text-[#94A3B8] hover:text-[#7C3AED] transition"
                          title="Copy Task ID"
                        >
                          {copiedId === wf.task_id ? (
                            <Check className="w-3 h-3 text-[#059669]" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </span>

                      {/* Timestamp */}
                      <span className="text-[11px] text-[#94A3B8] flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(wf.started_at)}</span>
                      </span>
                    </div>

                    {/* Task Title */}
                    <h3 className="text-sm font-semibold text-[#0F172A] leading-snug">
                      {wf.task}
                    </h3>
                  </div>

                  {/* Actions Strip */}
                  <div className="flex items-center space-x-2 shrink-0 self-end sm:self-auto">
                    {wf.total_duration_ms !== null && wf.total_duration_ms !== undefined && (
                      <span className="text-xs font-mono text-[#64748B]">
                        {(wf.total_duration_ms / 1000).toFixed(1)}s
                      </span>
                    )}

                    {(wf.final_response || wf.error) && (
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : wf.task_id)}
                        className="p-1.5 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8F9FC] text-xs font-medium transition cursor-pointer"
                        title={isExpanded ? 'Collapse preview' : 'Expand preview'}
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    )}

                    <button
                      onClick={() => onInspectWorkflow(wf.task_id)}
                      className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#F5F3FF] hover:bg-[#EDE9FE] text-[#7C3AED] text-xs font-semibold transition cursor-pointer"
                    >
                      <span>Inspect</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Collapsible Result Preview */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-[#F1F5F9] text-xs">
                    {wf.final_response && (
                      <div className="p-3 rounded-lg bg-[#F8F9FC] border border-[#E2E8F0] text-[#0F172A] whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-sans">
                        {wf.final_response}
                      </div>
                    )}
                    {wf.error && (
                      <div className="p-3 rounded-lg bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] font-mono whitespace-pre-wrap">
                        {wf.error}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
