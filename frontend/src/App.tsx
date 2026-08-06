import { useState, useCallback, useEffect } from 'react';
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
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Per-session background execution tracking
  const [runningSessionIds, setRunningSessionIds] = useState<Record<string, boolean>>({});

  // Optimistic pending user messages per session ID (preserves user query when switching active threads while running)
  const [pendingUserMessages, setPendingUserMessages] = useState<Record<string, ChatMessage[]>>({});

  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [lastResponse, setLastResponse] = useState<AnalysisResponse | null>(null);
  const [activeSourceQuery, setActiveSourceQuery] = useState<string | null>(null);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Draggable Split View State (leftWidth in percentage)
  const [leftWidth, setLeftWidth] = useState<number>(60);
  const [isDragging, setIsDragging] = useState<boolean>(false);

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
      } else {
        const targetId = selectSessionId || activeSessionId || list[0].session_id;
        if (targetId !== activeSessionId) {
          setActiveSessionId(targetId);
        }
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
        detail.turns.forEach((turn) => {
          const respData = turn.metadata?.last_response || turn.metadata?.response || undefined;
          loadedMsgs.push({
            id: `user_${turn.turn_id}`,
            sender: 'user',
            text: turn.user_query,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          });
          loadedMsgs.push({
            id: `agent_${turn.turn_id}`,
            sender: 'agent',
            text: turn.agent_response,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            data: respData,
          });
        });

        if (!effectiveLastResp) {
          const turnWithResp = [...detail.turns].reverse().find((t) => t.metadata?.last_response || t.metadata?.response);
          if (turnWithResp) {
            effectiveLastResp = turnWithResp.metadata?.last_response || turnWithResp.metadata?.response || null;
          }
        }
      }

      // Combine persistent backend turns with any pending optimistic user messages currently running in background
      const pendingForSession = pendingUserMessages[sessionId] || [];
      const combined = [WELCOME_MESSAGE, ...loadedMsgs, ...pendingForSession];

      setMessages(combined);
      setLastResponse(effectiveLastResp);
    } catch (err) {
      console.error(`Failed to load session ${sessionId}:`, err);
    }
  }, [pendingUserMessages]);

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

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;
      const newWidth = (e.clientX / window.innerWidth) * 100;
      if (newWidth >= 25 && newWidth <= 75) {
        setLeftWidth(newWidth);
      }
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
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
  }, [isDragging, handleMouseMove, handleMouseUp]);

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

    // Store user message in pending state map so switching threads retains the user's prompt
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

      // Clear pending user message for target session now that response is ready
      setPendingUserMessages((prev) => ({
        ...prev,
        [targetSessionId]: [],
      }));

      // If user is currently viewing this session, append agent response directly
      setActiveSessionId((currentActiveId) => {
        if (currentActiveId === targetSessionId) {
          setMessages((prev) => [...prev, agentMsg]);
          setLastResponse(data);
        }
        return currentActiveId;
      });

      // Refresh sidebar list to update titles and turn counts
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
    <div className={`h-screen w-screen flex flex-col bg-darkBg overflow-hidden ${isDragging ? 'select-none' : ''}`}>
      <Header
        onOpenExportModal={() => setIsExportModalOpen(true)}
        canExport={!!lastResponse?.is_success}
      />
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Collapsible Left Sidebar with Running status indicator */}
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
        />

        {/* Left Pane: Chat Stream */}
        <div style={{ width: `${leftWidth}%` }} className="h-full flex flex-col min-w-0 overflow-hidden">
          <ChatStream
            messages={messages}
            isLoading={isCurrentActiveSessionLoading}
            inputPrompt={inputPrompt}
            setInputPrompt={setInputPrompt}
            onSendMessage={handleSendMessage}
            onChipClick={(chip) => setInputPrompt(chip)}
            onSelectMessageResponse={(data) => setLastResponse(data)}
            onSelectSourceQuery={(query) => setActiveSourceQuery(query)}
          />
        </div>

        {/* Center Draggable Resizer Line */}
        <div
          onMouseDown={handleMouseDown}
          className={`w-2.5 hover:w-2.5 z-20 cursor-col-resize flex items-center justify-center transition-colors duration-150 relative group ${
            isDragging
              ? 'bg-blue-600/80 shadow-[0_0_12px_rgba(59,130,246,0.6)]'
              : 'bg-slate-900/90 hover:bg-blue-600/50 border-x border-slate-800/80'
          }`}
          title="Drag to resize split panes"
        >
          {/* Visual Grip Handle Indicator */}
          <div
            className={`w-1 h-8 rounded-full transition-all duration-150 ${
              isDragging ? 'bg-white shadow-glow' : 'bg-slate-600 group-hover:bg-blue-300'
            }`}
          />
        </div>

        {/* Right Pane: Source Drawer */}
        <div style={{ width: `${100 - leftWidth}%` }} className="h-full flex flex-col min-w-0 overflow-hidden">
          <SourceDrawer lastResponse={lastResponse} activeSourceQuery={activeSourceQuery} />
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
