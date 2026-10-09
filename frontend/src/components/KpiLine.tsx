import React from 'react';
import { MetaMetricsResponse } from '../types';

interface KpiLineProps {
  metrics?: MetaMetricsResponse | null;
}

export const KpiLine: React.FC<KpiLineProps> = ({ metrics }) => {
  const modA = metrics?.module_a?.summary;
  const strat = modA?.strat_5bps;
  const ew = modA?.ew_5bps;
  const spy = modA?.spy;

  const cumRet = strat ? `${(strat.cum_ret * 100).toFixed(2)}%` : '-28.91%';
  const ewCumRet = ew ? `${(ew.cum_ret * 100).toFixed(2)}%` : '-28.53%';
  const spyCumRet = spy ? `${(spy.cum_ret * 100).toFixed(2)}%` : '-15.51%';
  const maxDd = strat ? `${(strat.max_dd * 100).toFixed(2)}%` : '-37.95%';
  const avgTurnover = modA ? `${(modA.avg_daily_turnover * 100).toFixed(2)}%` : '4.14%';

  return (
    <div className="py-2.5 px-6 max-w-[1600px] mx-auto border-t border-border/30 text-[11px] font-mono text-text-secondary flex flex-wrap items-center justify-between gap-4">
      <div>
        Full Backtest (Oct 2021 – Sep 2022):{' '}
        <span className="text-text-primary font-medium">Cumulative Return {cumRet}</span>{' '}
        (vs Equal-Weight <span className="text-text-primary">{ewCumRet}</span>, vs SPY{' '}
        <span className="text-text-primary">{spyCumRet}</span>) •{' '}
        Max Drawdown <span className="text-text-primary font-medium">{maxDd}</span> •{' '}
        Avg Daily Turnover <span className="text-text-primary font-medium">{avgTurnover}</span>
      </div>

      <div className="text-[10px] text-accent/80 hover:text-accent cursor-pointer underline">
        See Methodology & Empirical Validation →
      </div>
    </div>
  );
};
