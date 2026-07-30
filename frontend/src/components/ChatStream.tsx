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
      if (!isLoading && inputPrompt.trim()) {
        onSendMessage();
      }
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
    <main className="flex-1 flex flex-col h-full bg-slate-950 min-w-0 overflow-hidden relative">
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.map((msg) => {
          const isAgent = msg.sender === 'agent';
          return (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${
                isAgent ? 'max-w-3xl mr-auto' : 'max-w-2xl ml-auto flex-row-reverse'
              }`}
            >
              {/* Avatar Icon */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-md ${
                  isAgent
                    ? 'bg-blue-950/80 text-blue-400 border border-blue-500/40'
                    : 'bg-indigo-600 text-white border border-indigo-400/40'
                }`}
              >
                {isAgent ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
              </div>

              {/* Message Bubble Container */}
              <div
                className={`rounded-2xl p-4 text-sm leading-relaxed shadow-lg ${
                  isAgent
                    ? 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-sm'
                    : 'bg-gradient-to-r from-blue-600 to-indigo-600 border border-blue-400/30 text-white rounded-tr-sm'
                }`}
              >
                {/* Header info */}
                <div
                  className={`flex items-center gap-2 mb-2 pb-1.5 border-b ${
                    isAgent ? 'border-slate-800/80 justify-between' : 'border-blue-400/20 justify-end'
                  }`}
                >
                  <span
                    className={`font-semibold text-[11px] ${
                      isAgent ? 'text-blue-400 font-heading' : 'text-blue-100'
                    }`}
                  >
                    {isAgent
                      ? `SEC Analyst Agent • (${msg.data?.model_used || 'Vertex AI (gemini-2.5-pro)'})`
                      : 'Financial Analyst'}
                  </span>
                  <span className={`text-[10px] ${isAgent ? 'text-slate-500' : 'text-blue-200/80'}`}>
                    {msg.timestamp}
                  </span>
                </div>

                {/* Content */}
                <div
                  className={`prose prose-invert max-w-none text-sm space-y-2.5 ${
                    isAgent
                      ? 'text-slate-200 prose-p:leading-relaxed prose-headings:font-heading prose-headings:text-blue-400 prose-table:border prose-table:border-slate-800 prose-th:bg-slate-800/80 prose-th:text-blue-300 prose-td:border-b prose-td:border-slate-800/50'
                      : 'text-white prose-p:leading-relaxed prose-headings:text-white prose-a:text-blue-200'
                  }`}
                  dangerouslySetInnerHTML={renderMarkdown(msg.text)}
                />
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-start gap-3 max-w-3xl mr-auto">
            <div className="w-8 h-8 rounded-xl bg-blue-950/80 text-blue-400 border border-blue-500/40 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="rounded-2xl p-4 bg-slate-900/90 border border-slate-800 text-sm text-slate-300 flex items-center gap-3 rounded-tl-sm">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
              <span>Parsing natural language intent & querying SEC 10-K RAG corpus...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Prompt Dock */}
      <div className="p-4 glass-panel border-t border-slate-800/80 shrink-0">
        <div className="max-w-4xl mx-auto space-y-3">
          {messages.filter((m) => m.sender === 'user').length === 0 && (
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
          )}

          <div className="relative glass-card rounded-2xl p-3 border border-slate-700/80 focus-within:border-blue-500/80 focus-within:ring-2 focus-within:ring-blue-500/20 transition-all duration-200">
            <textarea
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
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
