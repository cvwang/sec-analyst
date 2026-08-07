import React, { useState, useCallback, useEffect } from 'react';
import { PanelRightOpen, Database } from 'lucide-react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatStream } from './components/ChatStream';
import { SourceDrawer } from './components/SourceDrawer';
import { ExportModal } from './components/ExportModal';
import { ChatMessage, AnalysisResponse, SessionSummary, SessionDetail } from './types';

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  sender: 'agent',
  text: 'Hello! I am your SEC EDGAR Natural Language Analyst. Ask me any financial question in plain English (e.g., *"Compare Apple and Microsoft operating income in 2023"*, *"Explain Tesla 2023 financial highlights"*).',
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
};

export function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');

  // Sidebar Open & Width State
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [sidebarWidth, setSidebarWidth] = useState<number>(280);

  // Source Drawer Open State
  const [isSourceDrawerOpen, setIsSourceDrawerOpen] = useState<boolean>(true);

  // Per-session background execution tracking
  const [runningSessionIds, setRunningSessionIds] = useState<Record<string, boolean>>({});

  // Optimistic pending user messages per session ID
  const [pendingUserMessages, setPendingUserMessages] = useState<Record<string, ChatMessage[]>>({});

  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [lastResponse, setLastResponse] = useState<AnalysisResponse | null>(null);
  const [activeSourceQuery, setActiveSourceQuery] = useState<string | null>(null);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Split View Drag State (leftWidth in percentage for ChatStream when drawer is open)
  const [leftWidth, setLeftWidth] = useState<number>(55);
  const [activeDrag, setActiveDrag] = useState<'sidebar' | 'split' | null>(null);

  // Fetch list of all saved session threads
  const fetchSessions = useCallback(async (selectSessionId?: string) => {
    try {
      const res = await fetch('/api/v1/sessions');
      if (!res.ok) return;
      const data = await res.json();
      const list: SessionSummary[] = data.sessions || [];
      setSessions(list);

      if (list.length === 0) {
        // Create initial session if none exist
        await handleCreateNewSession();
      } else if (selectSessionId && selectSessionId !== activeSessionId) {
        setActiveSessionId(selectSessionId);
      } else if (!activeSessionId && list.length > 0) {
        setActiveSessionId(list[0].session_id);
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  }, [activeSessionId]);

  // Load session turns and last response state when active session changes
  const loadSessionDetails = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}`);
      if (!res.ok) return;
      const detail: SessionDetail = await res.json();

      let effectiveLastResp: AnalysisResponse | null = detail.last_response || null;
      const loadedMsgs: ChatMessage[] = [];

      if (detail.turns && detail.turns.length > 0) {
        detail.turns.forEach((turn, idx) => {
          const respData = turn.metadata?.last_response || turn.metadata?.response || undefined;
          if (turn.user_query && turn.user_query.trim()) {
            loadedMsgs.push({
              id: `${sessionId}_user_${turn.turn_id}_${idx}`,
              sender: 'user',
              text: turn.user_query.trim(),
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            });
          }
          if (turn.agent_response && turn.agent_response.trim()) {
            loadedMsgs.push({
              id: `${sessionId}_agent_${turn.turn_id}_${idx}`,
              sender: 'agent',
              text: turn.agent_response.trim(),
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              data: respData,
            });
          }
        });

        if (!effectiveLastResp) {
          const turnWithResp = [...detail.turns].reverse().find((t) => t.metadata?.last_response || t.metadata?.response);
          if (turnWithResp) {
            effectiveLastResp = turnWithResp.metadata?.last_response || turnWithResp.metadata?.response || null;
          }
        }
      }

      const combined = [WELCOME_MESSAGE, ...loadedMsgs];
      setMessages(combined);
      setLastResponse(effectiveLastResp);
    } catch (err) {
      console.error(`Failed to load session ${sessionId}:`, err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSessions();
  }, []);

  // Load session details on activeSessionId change
  useEffect(() => {
    if (activeSessionId) {
      loadSessionDetails(activeSessionId);
    }
  }, [activeSessionId, loadSessionDetails]);

  // Create new session thread
  const handleCreateNewSession = async () => {
    try {
      const res = await fetch('/api/v1/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Analysis' }),
      });
      if (res.ok) {
        const newMeta: SessionSummary = await res.json();
        setSessions((prev) => [newMeta, ...prev]);
        setActiveSessionId(newMeta.session_id);
        setMessages([WELCOME_MESSAGE]);
        setLastResponse(null);
      }
    } catch (err) {
      console.error('Failed to create new session:', err);
    }
  };

  // Rename session title
  const handleRenameSession = async (sessionId: string, newTitle: string) => {
    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        const updatedMeta: SessionSummary = await res.json();
        setSessions((prev) =>
          prev.map((s) => (s.session_id === sessionId ? updatedMeta : s))
        );
      }
    } catch (err) {
      console.error(`Failed to rename session ${sessionId}:`, err);
    }
  };

  // Delete session thread
  const handleDeleteSession = async (sessionId: string) => {
    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        setSessions(remaining);

        if (sessionId === activeSessionId) {
          if (remaining.length > 0) {
            setActiveSessionId(remaining[0].session_id);
          } else {
            await handleCreateNewSession();
          }
        }
      }
    } catch (err) {
      console.error(`Failed to delete session ${sessionId}:`, err);
    }
  };

  // Clear all session threads
  const handleClearAllSessions = async () => {
    if (!window.confirm('Are you sure you want to clear all conversation history?')) return;
    try {
      const res = await fetch('/api/v1/sessions', { method: 'DELETE' });
      if (res.ok) {
        setSessions([]);
        setPendingUserMessages({});
        await handleCreateNewSession();
      }
    } catch (err) {
      console.error('Failed to clear all sessions:', err);
    }
  };

  // Resizer Mouse Handlers
  const handleMouseDown = useCallback((e: React.MouseEvent, type: 'sidebar' | 'split') => {
    e.preventDefault();
    setActiveDrag(type);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!activeDrag) return;

      if (activeDrag === 'sidebar') {
        const newWidth = Math.max(180, Math.min(480, e.clientX));
        setSidebarWidth(newWidth);
      } else if (activeDrag === 'split') {
        const currentSidebarWidth = isSidebarOpen ? sidebarWidth : 0;
        const availableWidth = window.innerWidth - currentSidebarWidth;
        const relativeX = e.clientX - currentSidebarWidth;
        const newPct = (relativeX / availableWidth) * 100;
        if (newPct >= 25 && newPct <= 75) {
          setLeftWidth(newPct);
        }
      }
    },
    [activeDrag, isSidebarOpen, sidebarWidth]
  );

  const handleMouseUp = useCallback(() => {
    setActiveDrag(null);
  }, []);

  useEffect(() => {
    if (activeDrag) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [activeDrag, handleMouseMove, handleMouseUp]);

  // Send message - supports concurrent background execution per session ID
  const handleSendMessage = async () => {
    const targetSessionId = activeSessionId || 'default_session';
    if (!inputPrompt.trim() || runningSessionIds[targetSessionId]) return;

    const userText = inputPrompt.trim();
    setInputPrompt('');

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setPendingUserMessages((prev) => ({
      ...prev,
      [targetSessionId]: [...(prev[targetSessionId] || []), userMsg],
    }));

    if (targetSessionId === activeSessionId) {
      setMessages((prev) => [...prev, userMsg]);
    }

    setRunningSessionIds((prev) => ({ ...prev, [targetSessionId]: true }));

    try {
      const res = await fetch('/api/v1/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userText, session_id: targetSessionId }),
      });

      const data: AnalysisResponse = await res.json();

      const agentMsg: ChatMessage = {
        id: `agent_${Date.now()}`,
        sender: 'agent',
        text: data.narrative || data.error || 'No analysis narrative returned.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        data,
      };

      setPendingUserMessages((prev) => ({
        ...prev,
        [targetSessionId]: [],
      }));

      setActiveSessionId((currentActiveId) => {
        if (currentActiveId === targetSessionId) {
          setMessages((prev) => [...prev, agentMsg]);
          setLastResponse(data);
        }
        return currentActiveId;
      });

      fetchSessions();
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: 'agent',
        text: `⚠️ API Error: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setPendingUserMessages((prev) => ({
        ...prev,
        [targetSessionId]: [],
      }));

      setActiveSessionId((currentActiveId) => {
        if (currentActiveId === targetSessionId) {
          setMessages((prev) => [...prev, errorMsg]);
        }
        return currentActiveId;
      });
    } finally {
      setRunningSessionIds((prev) => ({ ...prev, [targetSessionId]: false }));
    }
  };

  const isCurrentActiveSessionLoading = !!runningSessionIds[activeSessionId];

  return (
    <div className={`h-screen w-screen flex flex-col bg-darkBg overflow-hidden ${activeDrag ? 'select-none' : ''}`}>
      <Header
        onOpenExportModal={() => setIsExportModalOpen(true)}
        canExport={!!lastResponse?.is_success}
      />
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Collapsible & Drag-Resizable Left Sidebar */}
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={(id) => setActiveSessionId(id)}
          onCreateNewSession={handleCreateNewSession}
          onRenameSession={handleRenameSession}
          onDeleteSession={handleDeleteSession}
          onClearAllSessions={handleClearAllSessions}
          isOpen={isSidebarOpen}
          onToggleOpen={() => setIsSidebarOpen((prev) => !prev)}
          runningSessionIds={runningSessionIds}
          width={sidebarWidth}
        />

        {/* Sidebar Drag Resizer Line */}
        {isSidebarOpen && (
          <div
            onMouseDown={(e) => handleMouseDown(e, 'sidebar')}
            className={`w-2.5 z-20 cursor-col-resize flex items-center justify-center transition-colors duration-150 relative group ${
              activeDrag === 'sidebar'
                ? 'bg-blue-600/80 shadow-[0_0_12px_rgba(59,130,246,0.6)]'
                : 'bg-slate-900/90 hover:bg-blue-600/50 border-r border-slate-800/80'
            }`}
            title="Drag to resize conversation sidebar width"
          >
            <div
              className={`w-1 h-8 rounded-full transition-all duration-150 ${
                activeDrag === 'sidebar' ? 'bg-white shadow-glow' : 'bg-slate-600 group-hover:bg-blue-300'
              }`}
            />
          </div>
        )}

        {/* Main Content Area (Chat Stream + optional Source Drawer) */}
        <div className="flex-1 h-full flex min-w-0 overflow-hidden">
          {/* Chat Stream Pane */}
          <div
            style={{ width: isSourceDrawerOpen ? `${leftWidth}%` : '100%' }}
            className="h-full flex flex-col min-w-0 overflow-hidden transition-all duration-75"
          >
            <ChatStream
              messages={messages}
              isLoading={isCurrentActiveSessionLoading}
              inputPrompt={inputPrompt}
              setInputPrompt={setInputPrompt}
              onSendMessage={handleSendMessage}
              onChipClick={(chip) => setInputPrompt(chip)}
              onSelectMessageResponse={(data) => setLastResponse(data)}
              onSelectSourceQuery={(query) => {
                setActiveSourceQuery(query);
                if (!isSourceDrawerOpen) setIsSourceDrawerOpen(true);
              }}
            />
          </div>

          {/* Split Drag Resizer Line between ChatStream and SourceDrawer */}
          {isSourceDrawerOpen && (
            <div
              onMouseDown={(e) => handleMouseDown(e, 'split')}
              className={`w-2.5 z-20 cursor-col-resize flex items-center justify-center transition-colors duration-150 relative group ${
                activeDrag === 'split'
                  ? 'bg-blue-600/80 shadow-[0_0_12px_rgba(59,130,246,0.6)]'
                  : 'bg-slate-900/90 hover:bg-blue-600/50 border-x border-slate-800/80'
              }`}
              title="Drag to resize split panes"
            >
              <div
                className={`w-1 h-8 rounded-full transition-all duration-150 ${
                  activeDrag === 'split' ? 'bg-white shadow-glow' : 'bg-slate-600 group-hover:bg-blue-300'
                }`}
              />
            </div>
          )}

          {/* Right Pane: Collapsible & Draggable Grounded Context Drawer */}
          {isSourceDrawerOpen ? (
            <div
              style={{ width: `${100 - leftWidth}%` }}
              className="h-full flex flex-col min-w-0 overflow-hidden transition-all duration-75"
            >
              <SourceDrawer
                lastResponse={lastResponse}
                activeSourceQuery={activeSourceQuery}
                onToggleCollapse={() => setIsSourceDrawerOpen(false)}
              />
            </div>
          ) : (
            <div className="h-full bg-slate-900/95 backdrop-blur-md border-l border-slate-800/80 flex flex-col items-center py-3.5 px-2 select-none z-30 transition-all duration-200 w-14 shrink-0 justify-between">
              <div className="flex flex-col items-center gap-4">
                <button
                  onClick={() => setIsSourceDrawerOpen(true)}
                  title="Expand Grounded Context Drawer"
                  className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors cursor-pointer flex items-center justify-center mb-2"
                >
                  <PanelRightOpen className="w-5 h-5 text-blue-400" />
                </button>
                <div
                  onClick={() => setIsSourceDrawerOpen(true)}
                  className="cursor-pointer p-2 rounded-lg hover:bg-slate-800/60 text-slate-400 hover:text-blue-300 flex flex-col items-center gap-2 transition-colors"
                  title="Expand Grounded Context Drawer"
                >
                  <Database className="w-4 h-4 text-blue-400" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 [writing-mode:vertical-lr] rotate-180 mt-1">
                    Grounded Context
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        lastResponse={lastResponse}
      />
    </div>
  );
}

export default App;
