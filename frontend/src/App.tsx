import { useState, useCallback, useEffect } from 'react';
import { Header } from './components/Header';
import { ChatStream } from './components/ChatStream';
import { SourceDrawer } from './components/SourceDrawer';
import { ExportModal } from './components/ExportModal';
import { ChatMessage, AnalysisResponse } from './types';

export function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: 'Hello! I am your SEC EDGAR Natural Language Analyst. Ask me any financial question in plain English (e.g., *"Compare Apple and Microsoft operating income in 2023"*, *"Explain Tesla 2023 financial highlights"*).',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<AnalysisResponse | null>(null);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Draggable Split View State (leftWidth in percentage)
  const [leftWidth, setLeftWidth] = useState<number>(60);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;
      const newWidth = (e.clientX / window.innerWidth) * 100;
      // Clamp split view width between 25% and 75%
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

  const handleSendMessage = async () => {
    if (!inputPrompt.trim() || isLoading) return;

    const userText = inputPrompt.trim();
    setInputPrompt('');

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await fetch('/api/v1/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userText, session_id: 'user_session_001' }),
      });

      const data: AnalysisResponse = await res.json();
      setLastResponse(data);

      const agentMsg: ChatMessage = {
        id: `agent_${Date.now()}`,
        sender: 'agent',
        text: data.narrative || data.error || 'No analysis narrative returned.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        data,
      };

      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: 'agent',
        text: `⚠️ API Error: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`h-screen w-screen flex flex-col bg-darkBg overflow-hidden ${isDragging ? 'select-none' : ''}`}>
      <Header
        onOpenExportModal={() => setIsExportModalOpen(true)}
        canExport={!!lastResponse?.is_success}
      />
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Left Pane: Chat Stream */}
        <div style={{ width: `${leftWidth}%` }} className="h-full flex flex-col min-w-0 overflow-hidden">
          <ChatStream
            messages={messages}
            isLoading={isLoading}
            inputPrompt={inputPrompt}
            setInputPrompt={setInputPrompt}
            onSendMessage={handleSendMessage}
            onChipClick={(chip) => setInputPrompt(chip)}
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
          <SourceDrawer lastResponse={lastResponse} />
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
