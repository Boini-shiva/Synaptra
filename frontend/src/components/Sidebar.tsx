import React from 'react';
import {
  LayoutDashboard,
  PlayCircle,
  History,
  Database,
  Settings,
  Layers,
  CircleDot,
  Server,
  Bot,
} from 'lucide-react';
import type { BackendHealthResponse, MemoryHealthResponse } from '../types/api';

export type NavTab = 'overview' | 'new_workflow' | 'history' | 'memory' | 'chat' | 'settings';

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  backendHealth: BackendHealthResponse | null;
  memoryHealth: MemoryHealthResponse | null;
  healthLoading: boolean;
  activeWorkspace: string;
  onWorkspaceChange: (ws: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  backendHealth,
  memoryHealth,
  healthLoading,
  activeWorkspace,
  onWorkspaceChange,
}) => {
  const isBackendOk = backendHealth?.status === 'ok';
  const isQdrantOk = memoryHealth?.status === 'ok';

  return (
    <aside className="w-64 bg-white border-r border-[#E2E8F0] flex flex-col justify-between select-none shrink-0 z-20">
      {/* Brand & Workspace Section */}
      <div>
        {/* SYNAPTRA Brand Logo with geometric neural connected nodes */}
        <div className="p-5 border-b border-[#E2E8F0] flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-[#F5F3FF] border border-[#DDD6FE] flex items-center justify-center shrink-0">
            <svg
              className="w-5 h-5 text-[#7C3AED]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-label="SYNAPTRA neural nodes"
            >
              {/* Connected neural nodes geometric graph */}
              <circle cx="12" cy="12" r="3" fill="#7C3AED" fillOpacity="0.2" />
              <circle cx="6" cy="6" r="2" />
              <circle cx="18" cy="6" r="2" />
              <circle cx="6" cy="18" r="2" />
              <circle cx="18" cy="18" r="2" />
              <line x1="7.4" y1="7.4" x2="9.8" y2="9.8" />
              <line x1="16.6" y1="7.4" x2="14.2" y2="9.8" />
              <line x1="7.4" y1="16.6" x2="9.8" y2="14.2" />
              <line x1="16.6" y1="16.6" x2="14.2" y2="14.2" />
            </svg>
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-base tracking-tight text-[#0F172A]">SYNAPTRA</span>
            </div>
            <p className="text-[11px] text-[#64748B]">Multi-Agent Workspace</p>
          </div>
        </div>

        {/* Compact Workspace Switcher */}
        <div className="px-4 py-3 border-b border-[#E2E8F0] bg-[#F8F9FC]/60">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B] block mb-1.5">
            Active Workspace
          </label>
          <div className="flex items-center space-x-1.5 bg-white border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 focus-within:border-[#7C3AED] focus-within:ring-1 focus-within:ring-[#7C3AED] transition">
            <Layers className="w-3.5 h-3.5 text-[#7C3AED] shrink-0" />
            <input
              type="text"
              value={activeWorkspace}
              onChange={(e) => onWorkspaceChange(e.target.value.trim() || 'default')}
              placeholder="default"
              className="w-full bg-transparent text-xs text-[#0F172A] focus:outline-none font-mono"
              title="Workspace identifier for tenant memory isolation"
            />
          </div>
        </div>

        {/* Navigation Items (5 requested tabs) */}
        <nav className="p-3 space-y-1">
          {/* 1. Overview */}
          <button
            onClick={() => onTabChange('overview')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <LayoutDashboard className={`w-4 h-4 ${activeTab === 'overview' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span>Overview</span>
          </button>

          {/* 2. New Workflow */}
          <button
            onClick={() => onTabChange('new_workflow')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'new_workflow'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <PlayCircle className={`w-4 h-4 ${activeTab === 'new_workflow' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span>New Workflow</span>
          </button>

          {/* 3. Workflow History */}
          <button
            onClick={() => onTabChange('history')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'history'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <History className={`w-4 h-4 ${activeTab === 'history' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span>Workflow History</span>
          </button>

          {/* 4. Memory */}
          <button
            onClick={() => onTabChange('memory')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'memory'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <Database className={`w-4 h-4 ${activeTab === 'memory' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span className="flex-1 text-left">Memory</span>
            {memoryHealth && isQdrantOk && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
                {memoryHealth.points_count}
              </span>
            )}
          </button>

          {/* 5. AI Assistant / Copilot (Gemini AI Studio) */}
          <button
            onClick={() => onTabChange('chat')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'chat'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <Bot className={`w-4 h-4 ${activeTab === 'chat' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span className="flex-1 text-left">AI Assistant</span>
            <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-[#FAF5FF] text-[#7C3AED] border border-[#DDD6FE]">
              Gemini
            </span>
          </button>

          {/* 6. Settings */}
          <button
            onClick={() => onTabChange('settings')}
            className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
              activeTab === 'settings'
                ? 'bg-[#F5F3FF] text-[#7C3AED] border border-[#DDD6FE] shadow-xs'
                : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]'
            }`}
          >
            <Settings className={`w-4 h-4 ${activeTab === 'settings' ? 'text-[#7C3AED]' : 'text-[#64748B]'}`} />
            <span>Settings</span>
          </button>
        </nav>

      </div>

      {/* System Status Footer */}
      <div className="p-4 border-t border-[#E2E8F0] bg-[#F8F9FC] space-y-2.5">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
          System Status
        </div>

        {/* Backend API status */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <Server className="w-3.5 h-3.5 text-[#64748B]" />
            <span className="text-[#334155] font-medium">FastAPI Backend</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <CircleDot
              className={`w-3 h-3 ${
                healthLoading
                  ? 'text-[#D97706] animate-spin'
                  : isBackendOk
                  ? 'text-[#059669]'
                  : 'text-[#DC2626]'
              }`}
            />
            <span className={`text-[11px] font-medium ${isBackendOk ? 'text-[#059669]' : 'text-[#DC2626]'}`}>
              {healthLoading ? 'Checking...' : isBackendOk ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Qdrant status */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <Database className="w-3.5 h-3.5 text-[#64748B]" />
            <span className="text-[#334155] font-medium">Vector Memory</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <CircleDot
              className={`w-3 h-3 ${
                healthLoading
                  ? 'text-[#D97706] animate-spin'
                  : isQdrantOk
                  ? 'text-[#059669]'
                  : !isBackendOk
                  ? 'text-[#94A3B8]'
                  : 'text-[#DC2626]'
              }`}
            />
            <span
              className={`text-[11px] font-medium ${
                isQdrantOk
                  ? 'text-[#059669]'
                  : !isBackendOk
                  ? 'text-[#64748B]'
                  : 'text-[#DC2626]'
              }`}
            >
              {healthLoading
                ? 'Checking...'
                : isQdrantOk
                ? `${memoryHealth?.points_count} pts`
                : !isBackendOk
                ? 'Unknown'
                : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
