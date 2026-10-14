import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  Copy,
  Check,
  RotateCcw,
  Database,
  Layers,
  Loader2,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { api, ApiError } from '../services/api';
import type { ChatMessage, ChatResponse, Citation, ChatSuggestion } from '../types/api';

interface ChatAssistantPageProps {
  activeWorkspace: string;
}

interface MessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  model?: string;
  provider?: string;
  citations?: Citation[];
}

export const ChatAssistantPage: React.FC<ChatAssistantPageProps> = ({ activeWorkspace }) => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [injectMemory, setInjectMemory] = useState(true);
  const [suggestions, setSuggestions] = useState<ChatSuggestion[]>([
    {
      title: 'Municipal Fraud Detection',
      prompt: 'How does SYNAPTRA audit municipal vendor procurement contracts to detect duplicate billing anomalies?',
      category: 'Fraud Audit',
    },
    {
      title: 'Ghost Vendor Red Flags',
      prompt: 'What are the key red flags and risk indicators for identifying ghost vendors in government expenditure?',
      category: 'Audit Patterns',
    },
    {
      title: 'Multi-Agent Self-Healing',
      prompt: 'Explain how SYNAPTRA multi-agent architecture uses Google Gemini AI Studio for automated self-healing when upstream agents fail.',
      category: 'Architecture',
    },
    {
      title: 'Tender Bid Rigging',
      prompt: 'What algorithmic checks should be performed on public tender bids to detect collusion or bid rigging between competing vendors?',
      category: 'Procurement',
    },
  ]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [openCitationId, setOpenCitationId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load suggestions from backend
  useEffect(() => {
    api.getChatSuggestions()
      .then((res) => {
        if (res.suggestions && res.suggestions.length > 0) {
          setSuggestions(res.suggestions);
        }
      })
      .catch(() => {
        // Fallback to static suggestions
      });
  }, []);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Copy handler
  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Submit message
  const handleSend = async (customPrompt?: string) => {
    const textToSend = (customPrompt || inputText).trim();
    if (!textToSend || isLoading) return;

    setErrorMessage(null);
    const userMessageId = `user_${Date.now()}`;
    const newUserMessage: MessageItem = {
      id: userMessageId,
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const nextMessages = [...messages, newUserMessage];
    setMessages(nextMessages);
    setInputText('');
    setIsLoading(true);

    try {
      // Build conversation history for API
      const historyPayload: ChatMessage[] = nextMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res: ChatResponse = await api.sendChatMessage({
        message: textToSend,
        workspace_id: activeWorkspace,
        history: historyPayload,
        inject_memory: injectMemory,
      });

      const assistantMessage: MessageItem = {
        id: `ast_${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        model: res.model,
        provider: res.provider,
        citations: res.citations || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const errDetail = err instanceof ApiError ? err.message : (err?.message || 'Failed to generate response');
      setErrorMessage(errDetail);
    } finally {
      setIsLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setErrorMessage(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto bg-white rounded-2xl border border-[#E2E8F0] shadow-xs overflow-hidden">
      {/* Top Header Bar */}
      <div className="px-6 py-4 border-b border-[#E2E8F0] bg-gradient-to-r from-white via-[#FAF5FF] to-white flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7C3AED] to-[#4F46E5] flex items-center justify-center text-white shadow-xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-[#0F172A] tracking-tight">SYNAPTRA AI Assistant</h2>
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
                <span>Gemini AI Studio Online</span>
              </span>
            </div>
            <p className="text-xs text-[#64748B]">
              Workspace semantic copilot with automated vector memory citation
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Inject Vector Memory toggle */}
          <button
            onClick={() => setInjectMemory(!injectMemory)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition cursor-pointer ${
              injectMemory
                ? 'bg-[#F5F3FF] text-[#7C3AED] border-[#DDD6FE]'
                : 'bg-white text-[#64748B] border-[#E2E8F0] hover:text-[#0F172A]'
            }`}
            title="Query Qdrant vector database to ground answers in workspace knowledge"
          >
            <Database className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Vector Context:</span>
            <span>{injectMemory ? 'Enabled' : 'Disabled'}</span>
          </button>

          {/* Clear button */}
          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#DC2626] hover:bg-[#FEF2F2] border border-[#E2E8F0] hover:border-[#FECACA] transition cursor-pointer"
              title="Clear current conversation"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Chat Thread Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#FAFAFC]">
        {/* Empty State / Quick Suggestions */}
        {messages.length === 0 && (
          <div className="max-w-3xl mx-auto py-8 text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-[#F5F3FF] border border-[#DDD6FE] flex items-center justify-center text-[#7C3AED] mx-auto shadow-sm">
              <Sparkles className="w-8 h-8" />
            </div>

            <div className="space-y-2">
              <h3 className="text-lg font-bold text-[#0F172A] tracking-tight">
                How can I assist your financial audit today?
              </h3>
              <p className="text-xs text-[#64748B] max-w-md mx-auto">
                Ask questions about government expenditure auditing, duplicate invoices, ghost vendors, or SYNAPTRA&apos;s self-healing orchestration architecture.
              </p>
            </div>

            {/* Suggestions Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-left">
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(s.prompt)}
                  className="p-3.5 bg-white border border-[#E2E8F0] hover:border-[#7C3AED] hover:shadow-xs rounded-xl transition cursor-pointer group flex flex-col justify-between text-left"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-[#7C3AED] bg-[#F5F3FF] px-2 py-0.5 rounded">
                      {s.category}
                    </span>
                    <Sparkles className="w-3.5 h-3.5 text-[#94A3B8] group-hover:text-[#7C3AED] transition" />
                  </div>
                  <h4 className="text-xs font-semibold text-[#0F172A] group-hover:text-[#7C3AED] transition">
                    {s.title}
                  </h4>
                  <p className="text-[11px] text-[#64748B] mt-1 line-clamp-2">
                    {s.prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message Bubbles */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 space-y-2 shadow-xs ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-[#7C3AED] to-[#6D28D9] text-white rounded-br-xs'
                  : 'bg-white border border-[#E2E8F0] text-[#0F172A] rounded-bl-xs'
              }`}
            >
              {/* Header Info */}
              <div
                className={`flex items-center justify-between text-[11px] pb-1 border-b ${
                  msg.role === 'user'
                    ? 'border-white/20 text-white/80'
                    : 'border-[#E2E8F0] text-[#64748B]'
                }`}
              >
                <div className="flex items-center space-x-1.5 font-medium">
                  {msg.role === 'user' ? (
                    <>
                      <User className="w-3.5 h-3.5" />
                      <span>You</span>
                    </>
                  ) : (
                    <>
                      <Bot className="w-3.5 h-3.5 text-[#7C3AED]" />
                      <span className="font-semibold text-[#0F172A]">SYNAPTRA Copilot</span>
                      {msg.model && (
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#F1F5F9] text-[#475569]">
                          {msg.model}
                        </span>
                      )}
                    </>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  <span>{msg.timestamp}</span>
                  <button
                    onClick={() => handleCopy(msg.id, msg.content)}
                    className="p-1 hover:opacity-80 transition cursor-pointer"
                    title="Copy message text"
                  >
                    {copiedId === msg.id ? (
                      <Check className="w-3 h-3 text-[#10B981]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>

              {/* Message Body with clean whitespace & formatting */}
              <div
                className={`text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-sans ${
                  msg.role === 'user' ? 'text-white' : 'text-[#1E293B]'
                }`}
              >
                {msg.content}
              </div>

              {/* Citations Accordion (if assistant and has citations) */}
              {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                <div className="pt-2 border-t border-[#E2E8F0] mt-3">
                  <button
                    onClick={() =>
                      setOpenCitationId(openCitationId === msg.id ? null : msg.id)
                    }
                    className="flex items-center space-x-1.5 text-[11px] font-medium text-[#7C3AED] hover:text-[#6D28D9] transition cursor-pointer"
                  >
                    <Database className="w-3 h-3 text-[#7C3AED]" />
                    <span>
                      {msg.citations.length} Grounded Context Citation{msg.citations.length > 1 ? 's' : ''} (Qdrant)
                    </span>
                    {openCitationId === msg.id ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                  </button>

                  {openCitationId === msg.id && (
                    <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-[#DDD6FE]">
                      {msg.citations.map((cite, cIdx) => (
                        <div
                          key={cIdx}
                          className="bg-[#F8F9FC] p-2 rounded-lg text-[11px] text-[#475569] border border-[#E2E8F0]"
                        >
                          <div className="flex items-center justify-between text-[10px] text-[#64748B] mb-1">
                            <span className="font-mono">Record #{cIdx + 1}</span>
                            {cite.score !== undefined && cite.score !== null && (
                              <span className="font-mono text-[#059669]">
                                Match: {(cite.score * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                          <p className="line-clamp-3 italic text-[#334155]">{cite.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-[#E2E8F0] rounded-2xl rounded-bl-xs p-4 shadow-xs flex items-center space-x-3 text-xs text-[#64748B]">
              <div className="w-7 h-7 rounded-lg bg-[#F5F3FF] flex items-center justify-center text-[#7C3AED]">
                <Bot className="w-4 h-4 animate-bounce" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center space-x-1.5 font-medium text-[#0F172A]">
                  <span>Analyzing with Google Gemini AI Studio</span>
                  <span className="flex space-x-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED] animate-ping" />
                  </span>
                </div>
                <p className="text-[11px] text-[#94A3B8]">
                  Synthesizing audit context and Qdrant memory...
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {errorMessage && (
          <div className="p-3 bg-[#FEF2F2] border border-[#FECACA] rounded-xl flex items-start space-x-2 text-xs text-[#DC2626]">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold">AI Assistant Error: </span>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Area */}
      <div className="p-4 border-t border-[#E2E8F0] bg-white shrink-0">
        <div className="flex items-end space-x-2 bg-[#F8F9FC] border border-[#E2E8F0] rounded-xl p-2 focus-within:border-[#7C3AED] focus-within:ring-1 focus-within:ring-[#7C3AED] transition">
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask SYNAPTRA Copilot anything in workspace '${activeWorkspace}'...`}
            rows={2}
            disabled={isLoading}
            className="w-full bg-transparent text-xs sm:text-sm text-[#0F172A] placeholder-[#94A3B8] focus:outline-none resize-none px-2 py-1 max-h-32"
          />

          <button
            onClick={() => handleSend()}
            disabled={!inputText.trim() || isLoading}
            className="p-2.5 rounded-lg bg-[#7C3AED] text-white hover:bg-[#6D28D9] disabled:opacity-40 disabled:cursor-not-allowed transition shrink-0 cursor-pointer shadow-xs"
            title="Send Message (Enter)"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>

        <div className="flex items-center justify-between text-[10px] text-[#94A3B8] mt-2 px-1">
          <div className="flex items-center space-x-2">
            <span>Press <kbd className="font-mono bg-[#E2E8F0] px-1 py-0.5 rounded text-[#475569]">Enter</kbd> to send</span>
            <span>•</span>
            <span><kbd className="font-mono bg-[#E2E8F0] px-1 py-0.5 rounded text-[#475569]">Shift + Enter</kbd> for new line</span>
          </div>
          <div className="flex items-center space-x-1.5 font-mono text-[#64748B]">
            <Layers className="w-3 h-3 text-[#7C3AED]" />
            <span>workspace: {activeWorkspace}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
