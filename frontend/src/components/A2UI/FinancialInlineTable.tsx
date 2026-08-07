import React from 'react';
import { useFetchMetrics } from '../../hooks/useQueries';

interface FinancialInlineTableProps {
  ticker: any;
  startYear: any;
  endYear: any;
}

export const FinancialInlineTable: React.FC<FinancialInlineTableProps> = ({
  ticker,
  startYear,
  endYear,
}) => {
  const safeTicker = typeof ticker === 'string' ? ticker.trim() : (Array.isArray(ticker) && ticker.length > 0 ? String(ticker[0]).trim() : (ticker ? String(ticker).trim() : 'AAPL'));
  const safeStartYear = startYear ? String(startYear).trim() : '2022';
  const safeEndYear = endYear ? String(endYear).trim() : '2023';

  const { data, isLoading, error } = useFetchMetrics(safeTicker, safeStartYear, safeEndYear);

  if (isLoading) {
    return (
      <div className="w-full p-4 my-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 animate-pulse flex items-center gap-2">
        <div className="w-3 h-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
        <span>Fetching deterministic financial metrics for {safeTicker}...</span>
      </div>
    );
  }

  if (error || !data?.metrics?.start_period || !data?.metrics?.end_period || !data?.metrics?.variances) {
    return (
      <div className="my-3 p-3 text-xs rounded-xl bg-red-950/20 border border-red-500/30 text-red-400">
        Failed to load financial metrics table for {safeTicker}.
      </div>
    );
  }

  const { start_period, end_period, variances } = data.metrics;

  const revVal = variances.revenue_yoy_change_percent;
  const isRevGrowth = revVal > 0;
  const isRevDecline = revVal < 0;

  const marginVal = variances.operating_margin_yoy_change_bps;
  const isMarginGrowth = marginVal > 0;
  const isMarginDecline = marginVal < 0;

  const netVal = variances.net_income_yoy_change_percent;
  const isNetGrowth = netVal > 0;
  const isNetDecline = netVal < 0;

  return (
    <div className="my-4 border border-slate-800 rounded-xl bg-slate-900/90 overflow-hidden shadow-lg">
      <div className="px-4 py-2.5 bg-slate-800/80 border-b border-slate-700/80 flex items-center justify-between">
        <span className="font-heading font-semibold text-xs text-blue-400">
          📊 {safeTicker.toUpperCase()} Financial Metrics Table
        </span>
        <span className="text-[10px] font-mono text-slate-400">
          FY {safeStartYear} → FY {safeEndYear}
        </span>
      </div>
      <table className="w-full text-xs text-left border-collapse">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold text-[11px]">
            <th className="p-3">Metric</th>
            <th className="p-3 text-right">FY {safeStartYear}</th>
            <th className="p-3 text-right">FY {safeEndYear}</th>
            <th className="p-3 text-right">YoY Variance</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 text-slate-200">
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Revenue</td>
            <td className="p-3 text-right font-mono">${((start_period.revenue || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono">${((end_period.revenue || 0) / 1e9).toFixed(2)}B</td>
            <td className={`p-3 text-right font-bold font-mono ${
              isRevGrowth ? 'text-emerald-400' : isRevDecline ? 'text-rose-400' : 'text-slate-400'
            }`}>
              {isRevGrowth ? '+' : ''}{revVal}%
            </td>
          </tr>
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Operating Margin</td>
            <td className="p-3 text-right font-mono">{(start_period.operating_margin || 0).toFixed(2)}%</td>
            <td className="p-3 text-right font-mono">{(end_period.operating_margin || 0).toFixed(2)}%</td>
            <td className={`p-3 text-right font-bold font-mono ${
              isMarginGrowth ? 'text-emerald-400' : isMarginDecline ? 'text-rose-400' : 'text-slate-400'
            }`}>
              {isMarginGrowth ? '+' : ''}{marginVal} bps
            </td>
          </tr>
          <tr className="hover:bg-slate-800/40 transition-colors">
            <td className="p-3 font-medium">Net Income</td>
            <td className="p-3 text-right font-mono">${((start_period.net_income || 0) / 1e9).toFixed(2)}B</td>
            <td className="p-3 text-right font-mono">${((end_period.net_income || 0) / 1e9).toFixed(2)}B</td>
            <td className={`p-3 text-right font-bold font-mono ${
              isNetGrowth ? 'text-emerald-400' : isNetDecline ? 'text-rose-400' : 'text-slate-400'
            }`}>
              {isNetGrowth ? '+' : ''}{netVal}%
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};
