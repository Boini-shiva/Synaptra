import { useState, useEffect, useCallback } from 'react';
import {
  Database,
  Search,
  Plus,
  Trash2,
  RefreshCw,
  Layers,
  User,
  AlertCircle,
  Copy,
  Check,
  X,
  Sparkles,
  Loader2,
  Lock,
  Globe,
  Tag,
} from 'lucide-react';
import { api } from '../services/api';
import type { MemoryItem, MemorySearchItem } from '../types/api';

interface MemoryBrowserProps {
  activeWorkspace: string;
  onWorkspaceChange: (ws: string) => void;
  onMemoryCountUpdated?: () => void;
}

export const MemoryBrowser: React.FC<MemoryBrowserProps> = ({
  activeWorkspace,
  onWorkspaceChange,
  onMemoryCountUpdated,
}) => {
  const [workspace, setWorkspace] = useState(activeWorkspace || 'default');
  const [workspaceInput, setWorkspaceInput] = useState(activeWorkspace || 'default');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [memoryType, setMemoryType] = useState('all');
  const [visibility, setVisibility] = useState('all');

  const [memories, setMemories] = useState<(MemoryItem | MemorySearchItem)[]>([]);
  const [isSearchMode, setIsSearchMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Delete modal state
  const [itemToDelete, setItemToDelete] = useState<MemoryItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newType, setNewType] = useState('note');
  const [newSource, setNewSource] = useState('user');
  const [newVisibility, setNewVisibility] = useState('shared');
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Sync workspace from props
  useEffect(() => {
    if (activeWorkspace) {
      setWorkspace(activeWorkspace);
      setWorkspaceInput(activeWorkspace);
    }
  }, [activeWorkspace]);

  // Debounce search query by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Fetch memories routine
  const fetchMemories = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      if (debouncedQuery) {
        setIsSearchMode(true);
        const res = await api.searchMemories(
          debouncedQuery,
          workspace,
          20,
          memoryType,
          visibility
        );
        setMemories(res.results || []);
      } else {
        setIsSearchMode(false);
        const res = await api.listMemories(workspace, 40, memoryType, visibility);
        setMemories(res.memories || []);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load memories from Qdrant vector database.');
      setMemories([]);
    } finally {
      setIsLoading(false);
    }
  }, [workspace, debouncedQuery, memoryType, visibility]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  // Handle Delete
  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteMemory(itemToDelete.memory_id, itemToDelete.workspace_id);
      setItemToDelete(null);
      await fetchMemories();
      onMemoryCountUpdated?.();
    } catch (err: any) {
      setDeleteError(err.message || 'Failed to delete memory record.');
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle Create
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      await api.createMemory({
        content: newContent.trim(),
        workspace_id: workspace,
        memory_type: newType,
        source_agent: newSource,
        visibility: newVisibility,
      });
      setNewContent('');
      setShowCreateModal(false);
      await fetchMemories();
      onMemoryCountUpdated?.();
    } catch (err: any) {
      setCreateError(err.message || 'Failed to store memory in Qdrant.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleWorkspaceSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = workspaceInput.trim() || 'default';
    setWorkspace(clean);
    onWorkspaceChange(clean);
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">
            Vector Memory
          </h1>
          <p className="text-sm text-[#64748B] mt-0.5">
            Qdrant semantic index with 384-dimensional dense embeddings
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => fetchMemories()}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F8F9FC] border border-[#E2E8F0] text-xs font-semibold text-[#0F172A] shadow-2xs transition cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Insert Memory</span>
          </button>
        </div>
      </div>

      {/* Filters and Search Strip */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Semantic Search Input */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-[#94A3B8] absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by meaning across vector memories..."
              className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white text-xs text-[#0F172A] rounded-lg pl-9 pr-8 py-2 focus:outline-none transition"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-2.5 text-[#94A3B8] hover:text-[#0F172A]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Workspace Filter */}
          <div className="md:col-span-3">
            <form onSubmit={handleWorkspaceSubmit} className="relative">
              <Layers className="w-3.5 h-3.5 text-[#7C3AED] absolute left-3 top-2.5" />
              <input
                type="text"
                value={workspaceInput}
                onChange={(e) => setWorkspaceInput(e.target.value)}
                onBlur={handleWorkspaceSubmit}
                placeholder="Workspace ID"
                title="Press Enter to switch workspace"
                className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white text-xs text-[#0F172A] rounded-lg pl-8 pr-3 py-2 font-mono focus:outline-none transition"
              />
            </form>
          </div>

          {/* Type Filter */}
          <div className="md:col-span-2">
            <select
              value={memoryType}
              onChange={(e) => setMemoryType(e.target.value)}
              className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] text-xs text-[#0F172A] rounded-lg px-2.5 py-2 focus:outline-none cursor-pointer"
            >
              <option value="all">All Types</option>
              <option value="note">Note</option>
              <option value="project_note">Project Note</option>
              <option value="task">Task</option>
              <option value="plan">Plan</option>
              <option value="execution">Execution</option>
              <option value="workflow_summary">Workflow Summary</option>
            </select>
          </div>

          {/* Visibility Filter */}
          <div className="md:col-span-2">
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] text-xs text-[#0F172A] rounded-lg px-2.5 py-2 focus:outline-none cursor-pointer"
            >
              <option value="all">All Visibilities</option>
              <option value="shared">Shared</option>
              <option value="private">Private</option>
              <option value="team">Team</option>
            </select>
          </div>
        </div>

        {/* Filter Summary Status */}
        <div className="flex items-center justify-between text-xs text-[#64748B] pt-1 border-t border-[#F1F5F9]">
          <div className="flex items-center space-x-2">
            <span>Workspace:</span>
            <span className="font-mono text-[#7C3AED] font-semibold">{workspace}</span>
            {isSearchMode && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE]">
                <Sparkles className="w-3 h-3" />
                <span>Semantic Similarity Search</span>
              </span>
            )}
          </div>
          <span>{memories.length} item{memories.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {/* Error State */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] text-xs text-[#DC2626] flex items-start justify-between">
          <div className="flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-[#DC2626] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-[#991B1B]">Failed to Retrieve Vector Memories</p>
              <p className="mt-0.5">{errorMessage}</p>
            </div>
          </div>
          <button
            onClick={() => fetchMemories()}
            className="text-xs font-semibold text-[#991B1B] hover:underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="py-12 text-center text-[#64748B] space-y-2">
          <Loader2 className="w-6 h-6 animate-spin mx-auto text-[#7C3AED]" />
          <p className="text-xs">Searching Qdrant vector index...</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !errorMessage && memories.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-10 text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-[#F8F9FC] border border-[#E2E8F0] flex items-center justify-center mx-auto text-[#94A3B8]">
            <Database className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-[#0F172A]">
            {isSearchMode ? 'No Semantic Matches Found' : 'No Memories in Workspace'}
          </h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto">
            {isSearchMode
              ? `No vector memories matched query "${searchQuery}" in workspace "${workspace}". Try broadening terms.`
              : `Workspace "${workspace}" has no vector memories stored yet. Add a note or run a workflow.`}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center space-x-1 px-3.5 py-1.5 rounded-lg bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create First Memory</span>
          </button>
        </div>
      )}

      {/* Memory Cards Grid */}
      {!isLoading && memories.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {memories.map((item) => {
            const hasScore = 'score' in item;
            const scoreVal = hasScore ? (item as MemorySearchItem).score : null;

            return (
              <div
                key={item.memory_id}
                className="bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] rounded-xl p-5 transition flex flex-col justify-between shadow-2xs group"
              >
                <div>
                  {/* Top Bar: Type, Visibility, Actions */}
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] font-mono flex items-center space-x-1">
                        <Tag className="w-2.5 h-2.5" />
                        <span>{item.memory_type}</span>
                      </span>

                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F8F9FC] text-[#64748B] border border-[#E2E8F0] font-mono flex items-center space-x-1">
                        {item.visibility === 'private' ? (
                          <Lock className="w-2.5 h-2.5" />
                        ) : (
                          <Globe className="w-2.5 h-2.5" />
                        )}
                        <span>{item.visibility}</span>
                      </span>
                    </div>

                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => handleCopyId(item.memory_id)}
                        className="text-[#94A3B8] hover:text-[#7C3AED] p-1 rounded hover:bg-[#F8F9FC] transition"
                        title="Copy Memory ID"
                      >
                        {copiedId === item.memory_id ? (
                          <Check className="w-3.5 h-3.5 text-[#059669]" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => setItemToDelete(item)}
                        className="text-[#94A3B8] hover:text-[#DC2626] p-1 rounded hover:bg-[#FEF2F2] transition cursor-pointer"
                        title="Delete Memory"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Similarity Score Bar (if search mode) */}
                  {scoreVal !== null && (
                    <div className="mb-2.5 bg-[#F8F9FC] p-2 rounded-lg border border-[#E2E8F0]">
                      <div className="flex items-center justify-between text-[11px] font-mono text-[#059669] mb-1">
                        <span className="flex items-center space-x-1">
                          <Sparkles className="w-3 h-3 text-[#059669]" />
                          <span>Similarity Score</span>
                        </span>
                        <span className="font-bold">{scoreVal.toFixed(4)}</span>
                      </div>
                      <div className="w-full bg-[#E2E8F0] h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-[#059669] h-1.5 rounded-full transition-all"
                          style={{ width: `${Math.min(100, Math.max(5, scoreVal * 100))}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Content */}
                  <p className="text-xs text-[#0F172A] leading-relaxed whitespace-pre-wrap break-words font-sans">
                    {item.content}
                  </p>
                </div>

                {/* Footer Metadata */}
                <div className="border-t border-[#F1F5F9] pt-3 mt-4 flex items-center justify-between text-[11px] text-[#64748B]">
                  <span className="flex items-center space-x-1">
                    <User className="w-3 h-3 text-[#94A3B8]" />
                    <span className="font-mono">{item.source_agent}</span>
                  </span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {itemToDelete && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center space-x-3 text-[#DC2626]">
              <div className="w-10 h-10 rounded-xl bg-[#FEF2F2] border border-[#FECACA] flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5 text-[#DC2626]" />
              </div>
              <div>
                <h3 className="font-bold text-[#0F172A] text-base">Delete Memory Record</h3>
                <p className="text-xs text-[#64748B]">Permanent removal from Qdrant vector index</p>
              </div>
            </div>

            <p className="text-xs text-[#475569] leading-relaxed">
              Are you sure you want to permanently delete this vector record from workspace{' '}
              <span className="font-mono text-[#7C3AED] font-semibold">{itemToDelete.workspace_id}</span>?
            </p>

            <div className="p-3 rounded-xl bg-[#F8F9FC] border border-[#E2E8F0] text-xs text-[#0F172A] font-sans line-clamp-3">
              "{itemToDelete.content}"
            </div>

            {deleteError && (
              <p className="text-xs text-[#DC2626] bg-[#FEF2F2] p-2.5 rounded border border-[#FECACA]">
                {deleteError}
              </p>
            )}

            <div className="flex items-center justify-end space-x-2.5 pt-2">
              <button
                type="button"
                onClick={() => setItemToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl bg-[#F8F9FC] hover:bg-[#F1F5F9] text-[#475569] text-xs font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
                className="px-4 py-2 rounded-xl bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-semibold shadow-xs cursor-pointer"
              >
                {isDeleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Insert Memory Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
              <div className="flex items-center space-x-2 text-[#0F172A]">
                <Database className="w-5 h-5 text-[#7C3AED]" />
                <h3 className="font-bold text-base">Insert Vector Memory</h3>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-[#94A3B8] hover:text-[#0F172A]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="text-xs text-[#475569] block mb-1 font-semibold">
                  Memory Content
                </label>
                <textarea
                  rows={4}
                  required
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="Enter policy, specification, knowledge snippet, or context..."
                  className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white rounded-xl p-3 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none transition resize-none font-sans"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-[#475569] block mb-1 font-semibold">Workspace</label>
                  <input
                    type="text"
                    disabled
                    value={workspace}
                    className="w-full bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-[#7C3AED] font-mono"
                  />
                </div>
                <div>
                  <label className="text-[#475569] block mb-1 font-semibold">Memory Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full bg-[#F8F9FC] border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-[#0F172A]"
                  >
                    <option value="note">Note</option>
                    <option value="project_note">Project Note</option>
                    <option value="task">Task</option>
                    <option value="plan">Plan</option>
                    <option value="execution">Execution</option>
                    <option value="workflow_summary">Workflow Summary</option>
                  </select>
                </div>
                <div>
                  <label className="text-[#475569] block mb-1 font-semibold">Source Agent</label>
                  <input
                    type="text"
                    value={newSource}
                    onChange={(e) => setNewSource(e.target.value)}
                    className="w-full bg-[#F8F9FC] border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-[#0F172A] font-mono"
                  />
                </div>
                <div>
                  <label className="text-[#475569] block mb-1 font-semibold">Visibility</label>
                  <select
                    value={newVisibility}
                    onChange={(e) => setNewVisibility(e.target.value)}
                    className="w-full bg-[#F8F9FC] border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-[#0F172A]"
                  >
                    <option value="shared">Shared</option>
                    <option value="private">Private</option>
                    <option value="team">Team</option>
                  </select>
                </div>
              </div>

              {createError && (
                <p className="text-xs text-[#DC2626] bg-[#FEF2F2] p-2.5 rounded border border-[#FECACA]">
                  {createError}
                </p>
              )}

              <div className="flex items-center justify-end space-x-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  disabled={isCreating}
                  className="px-4 py-2 rounded-xl bg-[#F8F9FC] hover:bg-[#F1F5F9] text-[#475569] text-xs font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newContent.trim()}
                  className="px-4 py-2 rounded-xl bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  {isCreating ? 'Embedding & Saving...' : 'Save to Qdrant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
