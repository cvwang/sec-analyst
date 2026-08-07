import React, { useState, useEffect, useRef } from 'react';
import { Database, FileText, ExternalLink, BookmarkCheck, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { AnalysisResponse } from '../types';

interface SourceDrawerProps {
  lastResponse: AnalysisResponse | null;
  activeSourceQuery?: string | null;
}

export const SourceDrawer: React.FC<SourceDrawerProps> = ({ lastResponse, activeSourceQuery }) => {
  const [expandedChunks, setExpandedChunks] = useState<Record<number, boolean>>({});
  const [highlightedIdx, setHighlightedIdx] = useState<number | null>(null);
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const citations = lastResponse?.citations || [];
  const textChunks = lastResponse?.hybrid_search_result?.text_chunks || [];
  const derivedTicker = lastResponse?.ticker || (lastResponse?.tickers && lastResponse.tickers.length > 0 ? lastResponse.tickers[0] : 'SEC');

  // Group and merge chunks from the same document section into a single unified context block per source file
  const consolidatedChunks = React.useMemo(() => {
    if (!textChunks || textChunks.length === 0) return [];

    const map = new Map<string, typeof textChunks[0]>();
    for (const chunk of textChunks) {
      const key = chunk.gcs_uri || `${chunk.company_name}_${chunk.fiscal_year}_${chunk.section}`;
      if (map.has(key)) {
        const existing = { ...map.get(key)! };
        if (chunk.content && !existing.content.includes(chunk.content)) {
          existing.content = `${existing.content}\n\n${chunk.content}`;
        }
        if (
          chunk.highlight_excerpt &&
          existing.highlight_excerpt &&
          !existing.highlight_excerpt.includes(chunk.highlight_excerpt)
        ) {
          existing.highlight_excerpt = `${existing.highlight_excerpt}\n\n${chunk.highlight_excerpt}`;
        }
        map.set(key, existing);
      } else {
        map.set(key, { ...chunk });
      }
    }
    return Array.from(map.values());
  }, [textChunks]);

  // Auto-scroll and highlight when a source citation badge is clicked in chat stream
  useEffect(() => {
    if (!activeSourceQuery || consolidatedChunks.length === 0) return;

    const query = activeSourceQuery.toLowerCase().trim();

    // 1. Match GCS URI, citation name, or company/year metadata
    let matchIdx = consolidatedChunks.findIndex((chunk) => {
      if (chunk.gcs_uri && query.includes(chunk.gcs_uri.toLowerCase())) return true;
      if (chunk.citation && query.includes(chunk.citation.toLowerCase())) return true;
      if (chunk.company_name && query.includes(chunk.company_name.toLowerCase()) &&
          chunk.fiscal_year && query.includes(String(chunk.fiscal_year))) return true;
      return false;
    });

    // 2. Direct text content inclusion match
    if (matchIdx === -1) {
      matchIdx = consolidatedChunks.findIndex((chunk) =>
        chunk.content && (chunk.content.toLowerCase().includes(query) || query.includes(chunk.content.toLowerCase()))
      );
    }

    // 3. Fallback company name match
    if (matchIdx === -1) {
      matchIdx = consolidatedChunks.findIndex((chunk) =>
        chunk.company_name && query.includes(chunk.company_name.toLowerCase())
      );
    }

    if (matchIdx !== -1) {
      setExpandedChunks((prev) => ({ ...prev, [matchIdx]: true }));
      setHighlightedIdx(matchIdx);

      const el = cardRefs.current[matchIdx];
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }

      const timer = setTimeout(() => {
        setHighlightedIdx(null);
      }, 3500);
      return () => clearTimeout(timer);
    }
  }, [activeSourceQuery, consolidatedChunks]);

  const toggleExpand = (idx: number) => {
    setExpandedChunks((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const renderHighlightedText = (text: string) => {
    if (!text) return null;

    // Safely parse LLM-annotated <mark>...</mark> sentence blocks
    const parts = text.split(/(<mark>.*?<\/mark>)/gs);

    return (
      <span>
        {parts.map((part, i) => {
          if (part.startsWith('<mark>') && part.endsWith('</mark>')) {
            const innerText = part.substring(6, part.length - 7);
            return (
              <mark
                key={i}
                className="bg-amber-400/25 text-amber-200 px-1 py-0.5 rounded border border-amber-400/40 font-semibold inline-block my-0.5"
              >
                {innerText}
              </mark>
            );
          }
          return part;
        })}
      </span>
    );
  };

  return (
    <aside className="w-full h-full glass-panel border-l border-slate-800 flex flex-col shrink-0 overflow-hidden">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-blue-400" />
          <h2 className="font-heading font-semibold text-sm text-slate-200">Grounded Context Drawer</h2>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
          {consolidatedChunks.length} {consolidatedChunks.length === 1 ? 'Source Cited' : 'Sources Cited'}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {consolidatedChunks.length > 0 ? (
          consolidatedChunks.map((chunk, idx) => {
            const isExpanded = !!expandedChunks[idx];
            const isHighlighted = highlightedIdx === idx;
            const textToDisplay = isExpanded ? chunk.content : (chunk.highlight_excerpt || chunk.content);

            return (
              <div
                key={idx}
                ref={(el) => (cardRefs.current[idx] = el)}
                className={`p-3.5 rounded-xl transition-all duration-300 ${
                  isHighlighted
                    ? 'source-card-highlight'
                    : idx === 0
                    ? 'bg-slate-800/90 border border-blue-500/40 shadow-md shadow-blue-500/10'
                    : 'bg-slate-900/60 border border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-xs text-white flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-blue-400" />
                    {chunk.company_name} FY{chunk.fiscal_year} 10-K
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" /> Cited
                    </span>
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                      {chunk.section}
                    </span>
                  </div>
                </div>

                <div className="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-3 rounded-lg border border-slate-800/80 mb-2">
                  <div className="text-[10px] font-semibold text-amber-300/90 uppercase tracking-wider mb-1 flex items-center justify-between">
                    <span>{isExpanded ? 'Full Document Context' : 'Relevant Grounded Excerpt'}</span>
                    <button
                      onClick={() => toggleExpand(idx)}
                      className="text-blue-400 hover:text-blue-300 flex items-center gap-0.5 text-[10px] normal-case"
                    >
                      {isExpanded ? (
                        <>Show Excerpt <ChevronUp className="w-3 h-3" /></>
                      ) : (
                        <>Show Full Text <ChevronDown className="w-3 h-3" /></>
                      )}
                    </button>
                  </div>
                  <div className="italic whitespace-pre-line leading-relaxed text-slate-300">
                    "{renderHighlightedText(textToDisplay)}"
                  </div>
                </div>

                <div className="text-[10px] font-mono text-slate-400 flex items-center justify-between">
                  <span className="truncate pr-2">Citation: {chunk.citation}</span>
                  <ExternalLink className="w-3 h-3 text-slate-500 shrink-0" />
                </div>
              </div>
            );
          })
        ) : (
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-xs text-white flex items-center gap-1.5">
                <BookmarkCheck className="w-3.5 h-3.5 text-blue-400" />
                {derivedTicker} Grounded Context
              </span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                Item 7 - MD&A
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80">
              "Official SEC EDGAR Filing Grounded Context: Audited financial disclosures and period metrics."
            </p>
            <div className="text-[10px] font-mono text-slate-400">
              Citation: {derivedTicker} 10-K Filing Grounded Context
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
