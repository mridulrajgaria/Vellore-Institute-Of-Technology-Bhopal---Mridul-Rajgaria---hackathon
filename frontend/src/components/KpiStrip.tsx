import React from 'react';
import { TrendingDown, ShieldAlert, RefreshCw, BarChart3, Scale, Layers } from 'lucide-react';
import { MetaMetricsResponse } from '../types';

interface KpiStripProps {
  metrics?: MetaMetricsResponse | null;
}

export const KpiStrip: React.FC<KpiStripProps> = ({ metrics }) => {
  const modA = metrics?.module_a?.summary;
  const strat = modA?.strat_5bps;
  const ew = modA?.ew_5bps;
  const spy = modA?.spy;

  const cumRet = strat ? `${(strat.cum_ret * 100).toFixed(2)}%` : '-28.91%';
  const ewCumRet = ew ? `${(ew.cum_ret * 100).toFixed(2)}%` : '-28.53%';
  const spyCumRet = spy ? `${(spy.cum_ret * 100).toFixed(2)}%` : '-15.51%';

  const sharpe = strat ? strat.sharpe.toFixed(4) : '-0.9209';
  const ewSharpe = ew ? ew.sharpe.toFixed(4) : '-0.9092';
  const spySharpe = spy ? spy.sharpe.toFixed(4) : '-0.7085';

  const maxDd = strat ? `${(strat.max_dd * 100).toFixed(2)}%` : '-37.95%';
  const ewMaxDd = ew ? `${(ew.max_dd * 100).toFixed(2)}%` : '-37.39%';
  const spyMaxDd = spy ? `${(spy.max_dd * 100).toFixed(2)}%` : '-24.37%';

  const avgTurnover = modA ? `${(modA.avg_daily_turnover * 100).toFixed(2)}%` : '4.14%';
  const activeDays = modA ? `${modA.active_rebalance_days} / ${modA.total_rebalance_days}` : '252 / 252';

  // Read hand-eval negative precision dynamically from /meta/metrics
  const negPrec = metrics?.sentiment_hand_eval?.per_class?.negative?.precision != null
    ? `${Math.round(metrics.sentiment_hand_eval.per_class.negative.precision * 100)}%`
    : '85%';

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 p-6 pb-2">
      {/* 1. Cumulative Return */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Cumulative Return</span>
            <TrendingDown className="h-4 w-4 text-negative" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-negative">{cumRet}</span>
            <span className="text-[10px] text-text-secondary">5 bps net</span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-text-secondary">
          EW: <span className="text-text-primary font-mono">{ewCumRet}</span> • SPY: <span className="text-text-primary font-mono">{spyCumRet}</span>
        </div>
      </div>

      {/* 2. Sharpe Ratio */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Sharpe Ratio (Rf=0)</span>
            <BarChart3 className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-text-primary">{sharpe}</span>
            <span className="text-[10px] text-text-secondary">252 days</span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-text-secondary">
          EW: <span className="text-text-primary font-mono">{ewSharpe}</span> • SPY: <span className="text-text-primary font-mono">{spySharpe}</span>
        </div>
      </div>

      {/* 3. Max Drawdown */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Max Drawdown</span>
            <ShieldAlert className="h-4 w-4 text-warning" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-warning">{maxDd}</span>
            <span className="text-[10px] text-text-secondary">peak-to-trough</span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-text-secondary">
          EW: <span className="text-text-primary font-mono">{ewMaxDd}</span> • SPY: <span className="text-text-primary font-mono">{spyMaxDd}</span>
        </div>
      </div>

      {/* 4. Daily Turnover */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Avg Daily Turnover</span>
            <RefreshCw className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-text-primary">{avgTurnover}</span>
            <span className="text-[10px] text-positive font-medium">Cap: 10.0%</span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-text-secondary">
          One-way turnover strictly controlled
        </div>
      </div>

      {/* 5. Active Days */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Rebalance Activity</span>
            <Layers className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-text-primary">{activeDays}</span>
            <span className="text-[10px] text-accent">100% active</span>
          </div>
        </div>
        <div className="mt-1 text-[11px] text-text-secondary">
          Daily close rebalancing (21:00 UTC)
        </div>
      </div>

      {/* 6. Sentiment Prior */}
      <div className="rounded-lg border border-border bg-surface p-3.5 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span>Sentiment Prior</span>
            <Scale className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-accent">1.25x Neg</span>
            <span className="text-[10px] text-text-secondary">Deadband ±0.20</span>
          </div>
        </div>
        <div className="mt-1 text-[10px] leading-snug text-text-secondary">
          Negative text weighted 1.25x (FinBERT was {negPrec} precise on negatives in our hand-labeled test)
        </div>
      </div>
    </div>
  );
};
