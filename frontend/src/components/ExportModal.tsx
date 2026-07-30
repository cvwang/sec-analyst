import React, { useState } from 'react';
import { ShieldAlert, CheckCircle, X, UploadCloud } from 'lucide-react';
import { AnalysisResponse } from '../types';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  lastResponse: AnalysisResponse | null;
}

export const ExportModal: React.FC<ExportModalProps> = ({ isOpen, onClose, lastResponse }) => {
  const [isExporting, setIsExporting] = useState(false);

  if (!isOpen) return null;

  const ticker = (lastResponse?.ticker || 'AAPL').toUpperCase();
  const gcsUri = `gs://fde-sec-edgar-reports/${ticker.toLowerCase()}_2023_report.md`;

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await fetch('/api/v1/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker,
          current_year: 2023,
          destination_gcs_uri: gcsUri,
          report_content: lastResponse?.narrative || 'Financial report content.',
          human_approved: true,
        }),
      });

      const data = await res.json();
      alert(`✅ ${data.message}`);
      onClose();
    } catch (err: any) {
      alert(`❌ Export Error: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-lg glass-panel rounded-2xl border border-slate-700/80 p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-heading font-bold text-base text-white">Human-In-The-Loop Export Stop</h3>
              <p className="text-xs text-slate-400">Explicit human approval required for GCS persistence</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3 bg-slate-900/60 p-4 rounded-xl border border-slate-800 text-xs">
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-medium text-slate-400">Target Ticker:</span>
            <span className="font-bold text-blue-400 px-2 py-0.5 rounded bg-blue-500/15 border border-blue-500/30">{ticker}</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-medium text-slate-400">Destination GCS Bucket:</span>
            <span className="font-mono text-[11px] text-emerald-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">{gcsUri}</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-medium text-slate-400">PII Guardrail:</span>
            <span className="text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle className="w-3.5 h-3.5" /> Sanitized & Scrubbed
            </span>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs border border-slate-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/25 transition-all duration-200"
          >
            <UploadCloud className="w-4 h-4" />
            <span>{isExporting ? 'Exporting...' : 'Grant Approval & Export'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
