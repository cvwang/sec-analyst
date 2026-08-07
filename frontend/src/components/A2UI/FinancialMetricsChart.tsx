import React from 'react';
import { useFetchMetrics } from '../../hooks/useQueries';

interface FinancialMetricsChartProps {
  ticker: any;
  startYear: any;
  endYear: any;
  metricType?: 'all' | 'revenue' | 'net_income' | 'operating_margin';
}

interface MiniBarChartProps {
  label: string;
  startVal: number;
  endVal: number;
  startLabel: string;
  endLabel: string;
  formattedStart: string;
  formattedEnd: string;
  changeLabel: string;
  trend: 'up' | 'down' | 'neutral';
}

const MiniBarChart: React.FC<MiniBarChartProps> = ({
  label,
  startVal,
  endVal,
  startLabel,
  endLabel,
  formattedStart,
  formattedEnd,
  changeLabel,
  trend,
}) => {
  const allPositive = startVal >= 0 && endVal >= 0;
  const baselineY = allPositive ? 75 : 50;
  const chartHeight = allPositive ? 55 : 35;
  const barWidth = 22;

  const maxAbs = Math.max(Math.abs(startVal), Math.abs(endVal), 1);
  const h1 = (Math.abs(startVal) / maxAbs) * chartHeight;
  const h2 = (Math.abs(endVal) / maxAbs) * chartHeight;

  let y1 = baselineY;
  const height1 = h1;
  if (startVal >= 0) {
    y1 = baselineY - h1;
  }

  let y2 = baselineY;
  const height2 = h2;
  if (endVal >= 0) {
    y2 = baselineY - h2;
  }

  const isUp = trend === 'up';
  const isDown = trend === 'down';

  const barColor1 = 'fill-slate-600/60 hover:fill-slate-500/80 transition-colors duration-200';
  const barColor2 = isUp
    ? 'fill-emerald-500/80 hover:fill-emerald-400/90 transition-colors duration-200'
    : isDown
    ? 'fill-rose-500/80 hover:fill-rose-400/90 transition-colors duration-200'
    : 'fill-blue-500/80 hover:fill-blue-400/90 transition-colors duration-200';

  const labelY1 = startVal >= 0 ? y1 - 6 : y1 + height1 + 12;
  const labelY2 = endVal >= 0 ? y2 - 6 : y2 + height2 + 12;

  return (
    <div className="flex flex-col items-center p-4 border border-slate-800 rounded-xl bg-slate-900/80 hover:border-slate-700 transition-all duration-200 flex-1 min-w-[150px] shadow-md">
      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-2">
        {label}
      </span>
      <svg width="130" height="110" className="overflow-visible mt-1">
        {/* Baseline Grid Line */}
        <line x1="0" y1={baselineY} x2="130" y2={baselineY} className="stroke-slate-700 stroke-1" />

        {!allPositive && (
          <line
            x1="0"
            y1={baselineY}
            x2="130"
            y2={baselineY}
            className="stroke-slate-600 stroke-1 stroke-dasharray-2"
          />
        )}

        {/* Bar 1 (Start Year) */}
        <rect
          x="22"
          y={y1}
          width={barWidth}
          height={Math.max(height1, 2)}
          rx="4"
          className={barColor1}
        />
        <text
          x={22 + barWidth / 2}
          y={labelY1}
          textAnchor="middle"
          className="text-[10px] font-semibold fill-slate-300 font-mono"
        >
          {formattedStart}
        </text>
        <text
          x={22 + barWidth / 2}
          y="95"
          textAnchor="middle"
          className="text-[9px] fill-slate-400 font-medium"
        >
          {startLabel}
        </text>

        {/* Bar 2 (End Year) */}
        <rect
          x="80"
          y={y2}
          width={barWidth}
          height={Math.max(height2, 2)}
          rx="4"
          className={barColor2}
        />
        <text
          x={80 + barWidth / 2}
          y={labelY2}
          textAnchor="middle"
          className="text-[10px] font-bold fill-white font-mono"
        >
          {formattedEnd}
        </text>
        <text
          x={80 + barWidth / 2}
          y="95"
          textAnchor="middle"
          className="text-[9px] fill-slate-400 font-medium"
        >
          {endLabel}
        </text>
      </svg>
      <span
        className={`text-[10px] font-bold mt-4 px-2 py-0.5 rounded-full inline-flex items-center gap-0.5 ${
          isUp
            ? 'text-emerald-300 bg-emerald-500/15 border border-emerald-500/30'
            : isDown
            ? 'text-rose-300 bg-rose-500/15 border border-rose-500/30'
            : 'text-slate-300 bg-slate-800 border border-slate-700'
        }`}
      >
        {changeLabel}
      </span>
    </div>
  );
};

export const FinancialMetricsChart: React.FC<FinancialMetricsChartProps> = ({
  ticker,
  startYear,
  endYear,
  metricType = 'all',
}) => {
  const safeTicker = typeof ticker === 'string' ? ticker.trim() : (Array.isArray(ticker) && ticker.length > 0 ? String(ticker[0]).trim() : (ticker ? String(ticker).trim() : 'AAPL'));
  const safeStartYear = startYear ? String(startYear).trim() : '2022';
  const safeEndYear = endYear ? String(endYear).trim() : '2023';

  const { data, isLoading, error } = useFetchMetrics(safeTicker, safeStartYear, safeEndYear);

  if (isLoading) {
    return (
      <div className="w-full flex items-center justify-center p-6 border border-dashed border-slate-800 rounded-xl bg-slate-900/40">
        <div className="flex flex-col items-center gap-2">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
          <span className="text-xs text-slate-400 animate-pulse">Generating SVG chart visuals...</span>
        </div>
      </div>
    );
  }

  if (error || !data?.metrics?.start_period || !data?.metrics?.end_period || !data?.metrics?.variances) {
    return (
      <div className="text-xs text-rose-400 p-3 border rounded-xl border-rose-500/30 bg-rose-950/20">
        Failed to fetch chart metrics for {safeTicker}.
      </div>
    );
  }

  const { start_period, end_period, variances } = data.metrics;

  const showRevenue = metricType === 'all' || metricType === 'revenue';
  const showNetIncome = metricType === 'all' || metricType === 'net_income';
  const showMargin = metricType === 'all' || metricType === 'operating_margin';

  const startYrShort = safeStartYear.slice(-2);
  const endYrShort = safeEndYear.slice(-2);

  return (
    <div className="my-3 flex flex-col gap-3">
      <div className="flex flex-row gap-3 flex-wrap w-full">
        {showRevenue && (
          <MiniBarChart
            label="Revenue"
            startVal={start_period.revenue || 0}
            endVal={end_period.revenue || 0}
            startLabel={`'${startYrShort}`}
            endLabel={`'${endYrShort}`}
            formattedStart={`$${((start_period.revenue || 0) / 1e9).toFixed(1)}B`}
            formattedEnd={`$${((end_period.revenue || 0) / 1e9).toFixed(1)}B`}
            changeLabel={`${variances.revenue_yoy_change_percent > 0 ? '+' : ''}${variances.revenue_yoy_change_percent}%`}
            trend={variances.revenue_yoy_change_percent > 0 ? 'up' : variances.revenue_yoy_change_percent < 0 ? 'down' : 'neutral'}
          />
        )}
        {showMargin && (
          <MiniBarChart
            label="Operating Margin"
            startVal={start_period.operating_margin || 0}
            endVal={end_period.operating_margin || 0}
            startLabel={`'${startYrShort}`}
            endLabel={`'${endYrShort}`}
            formattedStart={`${(start_period.operating_margin || 0).toFixed(1)}%`}
            formattedEnd={`${(end_period.operating_margin || 0).toFixed(1)}%`}
            changeLabel={`${variances.operating_margin_yoy_change_bps > 0 ? '+' : ''}${variances.operating_margin_yoy_change_bps} bps`}
            trend={variances.operating_margin_yoy_change_bps > 0 ? 'up' : variances.operating_margin_yoy_change_bps < 0 ? 'down' : 'neutral'}
          />
        )}
        {showNetIncome && (
          <MiniBarChart
            label="Net Income"
            startVal={start_period.net_income || 0}
            endVal={end_period.net_income || 0}
            startLabel={`'${startYrShort}`}
            endLabel={`'${endYrShort}`}
            formattedStart={`$${((start_period.net_income || 0) / 1e9).toFixed(1)}B`}
            formattedEnd={`$${((end_period.net_income || 0) / 1e9).toFixed(1)}B`}
            changeLabel={`${variances.net_income_yoy_change_percent > 0 ? '+' : ''}${variances.net_income_yoy_change_percent}%`}
            trend={variances.net_income_yoy_change_percent > 0 ? 'up' : variances.net_income_yoy_change_percent < 0 ? 'down' : 'neutral'}
          />
        )}
      </div>
    </div>
  );
};
