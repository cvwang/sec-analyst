import React from 'react';
import { useFetchPeerMetrics } from '../../hooks/useQueries';

interface PeerComparisonTableProps {
  ticker: any;
  peerTicker: any;
  year: any;
}

export const PeerComparisonTable: React.FC<PeerComparisonTableProps> = ({
  ticker,
  peerTicker,
  year,
}) => {
  let safeTicker = typeof ticker === 'string' ? ticker.trim() : (Array.isArray(ticker) && ticker.length > 0 ? String(ticker[0]).trim() : (ticker ? String(ticker).trim() : 'NVDA'));
  let safePeerTicker = typeof peerTicker === 'string' ? peerTicker.trim() : (Array.isArray(peerTicker) && peerTicker.length > 0 ? String(peerTicker[0]).trim() : (peerTicker ? String(peerTicker).trim() : 'AAPL'));
  const safeYear = year ? String(year).trim() : '2023';

  if (!safePeerTicker && safeTicker.includes(',')) {
    const parts = safeTicker.split(',').map((s) => s.trim());
    safeTicker = parts[0];
    safePeerTicker = parts[1] || 'AAPL';
  }

  const { data, isLoading, error } = useFetchPeerMetrics(safeTicker, safePeerTicker, safeYear);

  if (isLoading) {
    return (
      <div className="w-full p-4 my-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 animate-pulse flex items-center gap-2">
        <div className="w-3 h-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
        <span>Fetching peer comparison metrics for {safeTicker} vs {safePeerTicker} ({safeYear})...</span>
      </div>
    );
  }

  if (error || !data?.primary || !data?.peer) {
    return (
      <div className="my-3 p-3 text-xs rounded-xl bg-red-950/20 border border-red-500/30 text-red-400">
        Failed to load peer comparison table for {safeTicker} vs {safePeerTicker}.
      </div>
    );
  }

  const { primary, peer } = data;

  const revDiff = primary.revenue - peer.revenue;
  const isPrimaryRevLarger = revDiff > 0;
  const revRatio = peer.revenue > 0 ? (primary.revenue / peer.revenue).toFixed(1) : 'N/A';
  const revRatioPeer = primary.revenue > 0 ? (peer.revenue / primary.revenue).toFixed(1) : 'N/A';

  const marginDiffBps = Math.round((primary.operating_margin - peer.operating_margin) * 100);
  const isPrimaryMarginHigher = marginDiffBps > 0;

  const netDiff = primary.net_income - peer.net_income;
  const isPrimaryNetLarger = netDiff > 0;
  const netRatio = peer.net_income > 0 ? (primary.net_income / peer.net_income).toFixed(1) : 'N/A';
  const netRatioPeer = primary.net_income > 0 ? (peer.net_income / primary.net_income).toFixed(1) : 'N/A';

  return (
    <div className="my-4 border border-slate-800 rounded-xl bg-slate-900/90 overflow-hidden shadow-lg">
      <div className="px-4 py-2.5 bg-slate-800/80 border-b border-slate-700/80 flex items-center justify-between">
        <span className="font-heading font-semibold text-xs text-blue-400">
          ⚔️ {primary.ticker} vs. {peer.ticker} Side-by-Side Financial Comparison
        </span>
        <span className="text-[10px] font-mono text-slate-400">
          FY {safeYear}
        </span>
      </div>
      <table className="w-full text-xs text-left border-collapse">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold text-[11px]">
            <th className="p-3">Metric</th>
            <th className="p-3 text-right">{primary.ticker}</th>
            <th className="p-3 text-right">{peer.ticker}</th>
            <th className="p-3 text-right">Comparison Variance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 text-slate-200">
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Revenue</td>
            <td className="p-3 text-right font-mono font-semibold">${((primary.revenue || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono font-semibold">${((peer.revenue || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono text-slate-300">
              {isPrimaryRevLarger ? `${primary.ticker} +$${(revDiff / 1e9).toFixed(2)}B (${revRatio}x)` : `${peer.ticker} +$${(Math.abs(revDiff) / 1e9).toFixed(2)}B (${revRatioPeer}x)`}
            </td>
          </tr>
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Operating Income</td>
            <td className="p-3 text-right font-mono">${((primary.operating_income || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono">${((peer.operating_income || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono text-slate-300">
              {primary.operating_income > peer.operating_income ? `${primary.ticker} +$${((primary.operating_income - peer.operating_income) / 1e9).toFixed(2)}B` : `${peer.ticker} +$${((peer.operating_income - primary.operating_income) / 1e9).toFixed(2)}B`}
            </td>
          </tr>
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Operating Margin</td>
            <td className="p-3 text-right font-mono">{(primary.operating_margin || 0).toFixed(2)}%</td>
            <td className="p-3 text-right font-mono">{(peer.operating_margin || 0).toFixed(2)}%</td>
            <td className={`p-3 text-right font-bold font-mono ${isPrimaryMarginHigher ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPrimaryMarginHigher ? `${primary.ticker} +${marginDiffBps} bps` : `${peer.ticker} +${Math.abs(marginDiffBps)} bps`}
            </td>
          </tr>
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Net Income</td>
            <td className="p-3 text-right font-mono font-semibold">${((primary.net_income || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono font-semibold">${((peer.net_income || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono text-slate-300">
              {isPrimaryNetLarger ? `${primary.ticker} +$${(netDiff / 1e9).toFixed(2)}B (${netRatio}x)` : `${peer.ticker} +$${(Math.abs(netDiff) / 1e9).toFixed(2)}B (${netRatioPeer}x)`}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};
