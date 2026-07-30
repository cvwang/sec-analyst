import React from 'react';
import { Bot, ShieldCheck, Download, Activity } from 'lucide-react';

interface HeaderProps {
  onOpenExportModal: () => void;
  canExport: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onOpenExportModal, canExport }) => {
  return (
    <header className="h-16 px-6 glass-panel flex items-center justify-between border-b border-slate-800 shrink-0 z-10">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Bot className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-heading font-bold text-base text-white tracking-wide">SEC EDGAR Analyst</h1>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30">
              Agent ADK
            </span>
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
            <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
            <span>GCP Project: <strong className="text-slate-300">sec-analyst</strong> (us-central1)</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>PII Redaction & Grounding Rules Active</span>
        </div>

        <button
          onClick={onOpenExportModal}
          disabled={!canExport}
          className={`px-3.5 py-2 rounded-lg font-medium text-xs flex items-center gap-1.5 transition-all duration-200 ${
            canExport
              ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/25 cursor-pointer'
              : 'bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed'
          }`}
        >
          <Download className="w-4 h-4" />
          <span>Export GCS Report (HITL)</span>
        </button>
      </div>
    </header>
  );
};
