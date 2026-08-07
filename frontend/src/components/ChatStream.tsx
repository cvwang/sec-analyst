import React, { useRef, useEffect } from 'react';
import { Bot, User, Send, Loader2 } from 'lucide-react';
import { marked } from 'marked';
import { AnalysisResponse, ChatMessage } from '../types';
import { A2UISurface } from './A2UI/A2UISurface';
import { FinancialInlineTable } from './A2UI/FinancialInlineTable';

interface ChatStreamProps {
  messages: ChatMessage[];
  isLoading: boolean;
  inputPrompt: string;
  setInputPrompt: (val: string) => void;
  onSendMessage: () => void;
  onChipClick: (prompt: string) => void;
  onSelectMessageResponse?: (data: AnalysisResponse) => void;
  onSelectSourceQuery?: (query: string) => void;
}

interface MessageSegment {
  type: 'markdown' | 'a2ui' | 'financial_table';
  content: string;
  ticker?: string;
  startYear?: string;
  endYear?: string;
}

function parseMessageSegments(text: string): MessageSegment[] {
  if (!text) return [];

  const segments: MessageSegment[] = [];
  const regex = /(```a2ui[\s\S]*?```|<FinancialTable\s+ticker="[A-Z0-9\-\.]+"[\s\S]*?\/>)/gi;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: 'markdown',
        content: text.substring(lastIndex, match.index),
      });
    }

    const block = match[0];
    if (block.toLowerCase().startsWith('```a2ui')) {
      const payload = block.replace(/^```a2ui\s*/i, '').replace(/\s*```$/, '').trim();
      segments.push({
        type: 'a2ui',
        content: payload,
      });
    } else if (block.toLowerCase().startsWith('<financialtable')) {
      const tMatch = block.match(/ticker="([^"]+)"/i);
      const sMatch = block.match(/start_year="([^"]+)"/i);
      const eMatch = block.match(/end_year="([^"]+)"/i);
      if (tMatch && sMatch && eMatch) {
        segments.push({
          type: 'financial_table',
          content: block,
          ticker: tMatch[1],
          startYear: sMatch[1],
          endYear: eMatch[1],
        });
      } else {
        segments.push({
          type: 'markdown',
          content: block,
        });
      }
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({
      type: 'markdown',
      content: text.substring(lastIndex),
    });
  }

  return segments;
}

// Configure marked parser for GitHub Flavored Markdown with automatic line breaks
marked.use({
  gfm: true,
  breaks: true,
});

function formatSourceBadgeHtml(rawText: string): string {
  const gsMatch = rawText.match(/gs:\/\/[^\s\n\)\<\>"]+/i);
  const gcsUri = gsMatch ? gsMatch[0].replace(/[\)\.,;]+$/, '') : '';
  const filename = gcsUri ? gcsUri.split('/').pop() || '' : '';
  const fullText = `${filename} ${rawText}`;

  // Extract Ticker (e.g. AAPL, TSLA, META, NVDA, MSFT)
  let ticker = '';
  const tickerMatch = fullText.match(/\b(AAPL|TSLA|META|NVDA|MSFT|GOOGL|AMZN)\b/i);
  if (tickerMatch) {
    ticker = tickerMatch[0].toUpperCase();
  }

  // Extract Fiscal Year (e.g. 2022, 2023, 2024)
  let year = '';
  const yearMatch = fullText.match(/\b(202[0-9])\b/);
  if (yearMatch) {
    year = yearMatch[0];
  }

  // Extract SEC Section
  let section = '';
  if (/Item\s*7|Item7|MDA/i.test(fullText)) {
    section = 'Item 7 MD&A';
  } else if (/Item\s*1A|Item1A|Risk/i.test(fullText)) {
    section = 'Item 1A Risk Factors';
  } else if (/Item\s*1|Item1|Business/i.test(fullText)) {
    section = 'Item 1 Business';
  }

  // Construct natural SEC filing display label without parentheses or raw file extensions
  const labelParts: string[] = [];
  if (ticker && year) {
    labelParts.push(`${ticker} ${year} 10-K`);
  } else if (ticker) {
    labelParts.push(`${ticker} 10-K`);
  } else {
    // Fallback title from raw text without URI/Source prefix
    const titleClean = rawText
      .replace(gcsUri, '')
      .replace(/^source:\s*/i, '')
      .replace(/[\(\)]/g, '')
      .replace(/^[\s,:\(\[\)]+|[\s,:\(\[\)]+$/g, '')
      .trim();
    if (titleClean) {
      labelParts.push(titleClean);
    }
  }

  if (section && !labelParts.join(' ').includes(section)) {
    labelParts.push(section);
  }

  const labelText = labelParts.length > 0 ? labelParts.join(' • ') : 'SEC 10-K Filing';
  const queryAttr = (gcsUri || rawText).replace(/"/g, '&quot;');

  return `<button data-source-query="${queryAttr}" class="source-citation-badge hover:scale-105 active:scale-95 cursor-pointer" title="Click to highlight grounded SEC source section">📌 ${labelText}</button>`;
}

export const ChatStream: React.FC<ChatStreamProps> = ({
  messages,
  isLoading,
  inputPrompt,
  setInputPrompt,
  onSendMessage,
  onChipClick,
  onSelectMessageResponse,
  onSelectSourceQuery,
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

  const handleChatContainerClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    const badge = target.closest('.source-citation-badge') as HTMLElement;
    if (badge) {
      e.stopPropagation();
      const query = badge.getAttribute('data-source-query') || badge.innerText;
      if (query) {
        onSelectSourceQuery?.(query);
      }
      return;
    }

    // Generic narrative element click (bullet point <li>, paragraph <p>, table row <tr>)
    const container = target.closest('.markdown-content li, .markdown-content p, .markdown-content tr') as HTMLElement;
    if (container) {
      const text = container.innerText.trim();
      if (text && text.length > 8) {
        onSelectSourceQuery?.(text);
      }
    }
  };

  const renderMarkdown = (content: string) => {
    if (!content) return { __html: '' };
    try {
      // Single-pass replacement on raw content to prevent nested regex tag corruption
      let formatted = content.replace(
        /(\([\s\S]*?\)|\[[\s\S]*?\]|\bgs:\/\/[^\s\n\)\<\>"]+)/gi,
        (match) => {
          if (/\b(Source|gs:\/\/)\b/i.test(match)) {
            let inner = match.replace(/^[\(\[]|[\)\]]$/g, '').trim();
            return formatSourceBadgeHtml(inner);
          }
          return match;
        }
      );

      return { __html: marked.parse(formatted) as string };
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
    <main onClick={handleChatContainerClick} className="flex-1 flex flex-col h-full bg-slate-950 min-w-0 overflow-hidden relative">
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages
          .filter((msg, idx, arr) => {
            if (idx === 0) return true;
            const prev = arr[idx - 1];
            // Filter out duplicate consecutive messages with identical sender and text
            if (msg.sender === prev.sender && msg.text === prev.text && msg.text.length > 20) {
              return false;
            }
            return true;
          })
          .map((msg) => {
          const isAgent = msg.sender === 'agent';
          const segments = parseMessageSegments(msg.text);
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
                onClick={() => isAgent && msg.data && onSelectMessageResponse?.(msg.data)}
                title={isAgent && msg.data ? "Click to view grounded sources for this response" : undefined}
                className={`rounded-2xl p-4 text-sm leading-relaxed shadow-lg ${
                  isAgent
                    ? 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-sm transition-all hover:border-blue-500/40 cursor-pointer'
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
                <div className="space-y-3">
                  {segments.map((segment, idx) => {
                    if (segment.type === 'a2ui') {
                      return <A2UISurface key={idx} payload={segment.content} isMessageRunning={isLoading} />;
                    }
                    if (
                      segment.type === 'financial_table' &&
                      segment.ticker &&
                      segment.startYear &&
                      segment.endYear
                    ) {
                      return (
                        <FinancialInlineTable
                          key={idx}
                          ticker={segment.ticker}
                          startYear={segment.startYear}
                          endYear={segment.endYear}
                        />
                      );
                    }
                    return (
                      <div
                        key={idx}
                        className={`markdown-content max-w-none text-sm ${
                          isAgent ? 'text-slate-200' : 'text-white'
                        }`}
                        dangerouslySetInnerHTML={renderMarkdown(segment.content)}
                      />
                    );
                  })}
                </div>
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
