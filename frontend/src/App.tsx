import { useState } from 'react';
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
    <div className="h-screen w-screen flex flex-col bg-darkBg overflow-hidden">
      <Header
        onOpenExportModal={() => setIsExportModalOpen(true)}
        canExport={!!lastResponse?.is_success}
      />
      <div className="flex-1 flex min-h-0 overflow-hidden">
        <ChatStream
          messages={messages}
          isLoading={isLoading}
          inputPrompt={inputPrompt}
          setInputPrompt={setInputPrompt}
          onSendMessage={handleSendMessage}
          onChipClick={(chip) => setInputPrompt(chip)}
        />
        <SourceDrawer lastResponse={lastResponse} />
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
