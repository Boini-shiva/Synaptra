import React from 'react';
import {
  Server,
  Database,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  ShieldCheck,
  Layers,
  Cpu,
  Info,
  Sparkles,
  Zap,
} from 'lucide-react';
import { API_BASE_URL } from '../services/api';
import type { BackendHealthResponse, MemoryHealthResponse } from '../types/api';

interface SettingsPageProps {
  backendHealth: BackendHealthResponse | null;
  memoryHealth: MemoryHealthResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
  activeWorkspace: string;
  onWorkspaceChange: (ws: string) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  backendHealth,
  memoryHealth,
  isLoading,
  onRefresh,
  activeWorkspace,
  onWorkspaceChange,
}) => {
  const isBackendOk = backendHealth?.status === 'ok';
  const isQdrantOk = memoryHealth?.status === 'ok';
  const isAgentsReady = backendHealth?.config?.all_workflow_agents_configured;
  const isGeminiConfigured = backendHealth?.config?.gemini_api_key_configured ?? false;
  const isSelfHealingActive = backendHealth?.config?.self_healing_enabled ?? false;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">
            Settings & System Status
          </h1>
          <p className="text-sm text-[#64748B] mt-0.5">
            Operational connectivity, memory status, and workspace configuration
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-white hover:bg-[#F8F9FC] border border-[#E2E8F0] text-xs font-semibold text-[#0F172A] shadow-2xs transition cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#7C3AED]' : 'text-[#64748B]'}`} />
          <span>Check Status</span>
        </button>
      </div>

      {/* 1. Safe Operational Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Backend Connection */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                <Server className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-[#0F172A]">
                Backend Connection
              </span>
            </div>

            <span
              className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isBackendOk
                  ? 'bg-[#ECFDF5] text-[#059669]'
                  : 'bg-[#FEF2F2] text-[#DC2626]'
              }`}
            >
              {isBackendOk ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
              <span>{isBackendOk ? 'Connected' : 'Disconnected'}</span>
            </span>
          </div>

          <div className="text-xs text-[#64748B] space-y-1">
            <div className="flex justify-between">
              <span>Service:</span>
              <span className="font-mono text-[#0F172A]">{backendHealth?.service || 'synaptra-backend'}</span>
            </div>
            <div className="flex justify-between">
              <span>Endpoint:</span>
              <span className="font-mono text-[#0F172A]">{API_BASE_URL}</span>
            </div>
          </div>
        </div>

        {/* Vector Memory */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-[#ECFDF5] text-[#059669] flex items-center justify-center">
                <Database className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-[#0F172A]">
                Vector Memory
              </span>
            </div>

            <span
              className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isQdrantOk
                  ? 'bg-[#ECFDF5] text-[#059669]'
                  : !isBackendOk
                  ? 'bg-[#F1F5F9] text-[#64748B]'
                  : 'bg-[#FEF2F2] text-[#DC2626]'
              }`}
            >
              {isQdrantOk ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : !isBackendOk ? (
                <HelpCircle className="w-3.5 h-3.5" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
              <span>
                {isQdrantOk
                  ? 'Connected'
                  : !isBackendOk
                  ? 'Unknown'
                  : 'Disconnected'}
              </span>
            </span>
          </div>

          <div className="text-xs text-[#64748B] space-y-1">
            <div className="flex justify-between">
              <span>Indexed Vectors:</span>
              <span className="font-mono font-semibold text-[#0F172A]">
                {memoryHealth ? `${memoryHealth.points_count} points` : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Collection:</span>
              <span className="font-mono text-[#0F172A]">
                {memoryHealth?.collection || 'synaptra_memory'}
              </span>
            </div>
          </div>
        </div>

        {/* Agent Readiness */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-[#F5F3FF] text-[#7C3AED] flex items-center justify-center">
                <Cpu className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-[#0F172A]">
                Agent Readiness
              </span>
            </div>

            <span
              className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isAgentsReady
                  ? 'bg-[#ECFDF5] text-[#059669]'
                  : !isBackendOk
                  ? 'bg-[#F1F5F9] text-[#64748B]'
                  : 'bg-[#FFFBEB] text-[#D97706]'
              }`}
            >
              {isAgentsReady ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <Info className="w-3.5 h-3.5" />
              )}
              <span>
                {isAgentsReady
                  ? 'Ready'
                  : !isBackendOk
                  ? 'Unknown'
                  : 'Incomplete'}
              </span>
            </span>
          </div>

          <p className="text-xs text-[#64748B] leading-relaxed">
            Multi-agent workflow orchestration capabilities managed server-side.
          </p>
        </div>

        {/* Gemini AI Studio & Self-Healing Engine */}
        <div className="bg-gradient-to-br from-white to-[#F5F3FF]/40 border border-[#DDD6FE] rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-[#EDE9FE] text-[#7C3AED] flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <span className="font-semibold text-sm text-[#0F172A] block leading-tight">
                  Gemini AI Studio
                </span>
                <span className="text-[10px] text-[#7C3AED] font-semibold">
                  Self-Healing Engine
                </span>
              </div>
            </div>

            <span
              className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isSelfHealingActive
                  ? 'bg-[#ECFDF5] text-[#059669]'
                  : 'bg-[#FFFBEB] text-[#D97706]'
              }`}
            >
              <Zap className="w-3 h-3" />
              <span>{isSelfHealingActive ? 'Auto-Healing Active' : 'Fallback Idle'}</span>
            </span>
          </div>

          <div className="text-xs text-[#64748B] space-y-1">
            <div className="flex justify-between">
              <span>Failover Provider:</span>
              <span className="font-mono text-[#0F172A]">Google Gemini 2.5 / Flash</span>
            </div>
            <div className="flex justify-between">
              <span>API Key Status:</span>
              <span className={`font-semibold ${isGeminiConfigured ? 'text-[#059669]' : 'text-[#DC2626]'}`}>
                {isGeminiConfigured ? 'Validated & Loaded' : 'Missing'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Auto-Recovery:</span>
              <span className="text-[#059669] font-medium">Credits 402 / 429 / 500+</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Workspace Management Card */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#F1F5F9] pb-3">
          <Layers className="w-4 h-4 text-[#7C3AED]" />
          <h2 className="text-base font-bold text-[#0F172A]">
            Current Workspace Configuration
          </h2>
        </div>

        <div className="max-w-md space-y-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#64748B] block">
            Workspace Identifier
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={activeWorkspace}
              onChange={(e) => onWorkspaceChange(e.target.value.trim() || 'default')}
              placeholder="default"
              className="w-full bg-[#F8F9FC] border border-[#E2E8F0] focus:border-[#7C3AED] focus:bg-white text-xs font-mono text-[#0F172A] rounded-lg px-3 py-2 focus:outline-none transition"
            />
          </div>
          <p className="text-[11px] text-[#64748B]">
            All memory embeddings and workflow histories are strictly partitioned by this workspace identifier.
          </p>
        </div>
      </div>

      {/* 3. Security & Architecture Notice */}
      <div className="p-4 rounded-xl bg-[#F8F9FC] border border-[#E2E8F0] text-xs text-[#64748B] space-y-1.5">
        <div className="flex items-center space-x-1.5 font-semibold text-[#0F172A]">
          <ShieldCheck className="w-4 h-4 text-[#059669]" />
          <span>Server-Side Credential Management</span>
        </div>
        <p className="leading-relaxed">
          SYNAPTRA maintains high-security zero-credential standards on the client. Third-party API keys, agent IDs, and internal connection strings are stored exclusively in backend environment configuration and validated server-side.
        </p>
      </div>
    </div>
  );
};
