import React, { useRef, useEffect } from 'react';
import { Bot, User, Send, Loader2 } from 'lucide-react';
import { marked } from 'marked';
import { ChatMessage } from '../types';

interface ChatStreamProps {
  messages: ChatMessage[];
  isLoading: boolean;
  inputPrompt: string;
  setInputPrompt: (val: string) => void;
  onSendMessage: () => void;
  onChipClick: (prompt: string) => void;
}

export const ChatStream: React.FC<ChatStreamProps> = ({
  messages,
  isLoading,
  inputPrompt,
  setInputPrompt,
  onSendMessage,
  onChipClick,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSendMessage();
    }
  };

  const renderMarkdown = (content: string) => {
    try {
      return { __html: marked.parse(content) as string };
    } catch {
      return { __html: content };
    }
  };

  const suggestionChips = [
    "Analyze Apple revenue 2023 vs 2022",
    "Compare Nvidia and Microsoft operating income in 2023",
    "Explain Tesla 2023 financial highlights",
    "Analyze Meta risk factors disclosure",
  ];

  return (
    <main className="flex-1 flex flex-col h-full bg-darkBg min-w-0 overflow-hidden relative">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className="flex items-start gap-4 max-w-4xl mx-auto">
            <div
              className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-md ${
                msg.sender === 'agent'
                  ? 'bg-slate-800 text-blue-400 border border-slate-700'
                  : 'bg-gradient-to-tr from-blue-600 to-indigo-500 text-white'
              }`}
            >
              {msg.sender === 'agent' ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
            </div>

            <div
              className={`flex-1 rounded-2xl p-5 border text-sm leading-relaxed ${
                msg.sender === 'agent'
                  ? 'bg-slate-900/70 border-slate-800 text-slate-200 shadow-lg shadow-black/20'
                  : 'bg-blue-600/20 border-blue-500/40 text-blue-50'
              }`}
            >
              <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-800/60">
                <span className="font-heading font-semibold text-xs text-slate-400">
                  {msg.sender === 'agent'
                    ? `SEC Analyst Agent • (${msg.data?.model_used || 'Gemini 3.1 Pro'})`
                    : 'Financial Analyst'}
                </span>
                <span className="text-[10px] text-slate-500">{msg.timestamp}</span>
              </div>

              <div
                className="prose prose-invert max-w-none text-slate-200 space-y-3 prose-p:leading-relaxed prose-headings:font-heading prose-headings:text-blue-400 prose-table:border prose-table:border-slate-800 prose-th:bg-slate-800/80 prose-th:text-blue-300 prose-td:border-b prose-td:border-slate-800/50"
                dangerouslySetInnerHTML={renderMarkdown(msg.text)}
              />
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-start gap-4 max-w-4xl mx-auto">
            <div className="w-9 h-9 rounded-xl bg-slate-800 text-blue-400 border border-slate-700 flex items-center justify-center shrink-0">
              <Bot className="w-5 h-5" />
            </div>
            <div className="flex-1 rounded-2xl p-4 bg-slate-900/70 border border-slate-800 text-sm text-slate-400 flex items-center gap-3">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
              <span>Parsing natural language intent with Gemini & querying SEC 10-K RAG corpus...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Prompt Dock */}
      <div className="p-4 glass-panel border-t border-slate-800 shrink-0">
        <div className="max-w-4xl mx-auto space-y-3">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            {suggestionChips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => onChipClick(chip)}
                className="whitespace-nowrap px-3 py-1 rounded-full bg-slate-800/80 hover:bg-blue-600/20 text-xs font-medium text-slate-300 hover:text-blue-300 border border-slate-700/80 hover:border-blue-500/40 transition-all duration-200 shrink-0"
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="relative glass-card rounded-2xl p-3 border border-slate-700/80 focus-within:border-blue-500/80 focus-within:ring-2 focus-within:ring-blue-500/20 transition-all duration-200">
            <textarea
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder="Ask any financial query (e.g., 'Compare Nvidia and Microsoft operating income in 2023')..."
              rows={2}
              className="w-full bg-transparent border-none outline-none text-slate-100 text-sm placeholder-slate-500 resize-none"
            />
            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-slate-500 font-mono">Press Shift + Enter for new line</span>
              <button
                onClick={onSendMessage}
                disabled={isLoading || !inputPrompt.trim()}
                className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200 ${
                  inputPrompt.trim() && !isLoading
                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 cursor-pointer'
                    : 'bg-slate-800 text-slate-600 border border-slate-700/50 cursor-not-allowed'
                }`}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};
