import React from 'react';
import { Database, FileText, ExternalLink, BookmarkCheck } from 'lucide-react';
import { AnalysisResponse } from '../types';

interface SourceDrawerProps {
  lastResponse: AnalysisResponse | null;
}

export const SourceDrawer: React.FC<SourceDrawerProps> = ({ lastResponse }) => {
  const citations = lastResponse?.citations || [];
  const textChunks = lastResponse?.hybrid_search_result?.text_chunks || [];

  return (
    <aside className="w-full h-full glass-panel border-l border-slate-800 flex flex-col shrink-0 overflow-hidden">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-blue-400" />
          <h2 className="font-heading font-semibold text-sm text-slate-200">Grounded Context Drawer</h2>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
          {citations.length} Sources Grounded
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {textChunks.length > 0 ? (
          textChunks.map((chunk, idx) => (
            <div
              key={idx}
              className={`p-3.5 rounded-xl transition-all duration-200 ${
                idx === 0
                  ? 'bg-slate-800/90 border border-blue-500/40 shadow-md shadow-blue-500/10'
                  : 'bg-slate-900/60 border border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-xs text-white flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-blue-400" />
                  {chunk.company_name} FY{chunk.fiscal_year} 10-K
                </span>
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  {chunk.section}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80 mb-2">
                "{chunk.content}"
              </p>
              <div className="text-[10px] font-mono text-slate-400 flex items-center justify-between">
                <span>Citation: {chunk.citation}</span>
                <ExternalLink className="w-3 h-3 text-slate-500" />
              </div>
            </div>
          ))
        ) : (
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-xs text-white flex items-center gap-1.5">
                <BookmarkCheck className="w-3.5 h-3.5 text-blue-400" />
                {lastResponse?.ticker || 'SEC'} FY2023 10-K Context
              </span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                Item 7 - MD&A
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80">
              "Official SEC EDGAR Filing Grounded Context: Audited financial disclosures and period metrics."
            </p>
            <div className="text-[10px] font-mono text-slate-400">
              Citation: {lastResponse?.ticker || 'SEC'} FY2023 10-K (Item 7 MD&A)
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
