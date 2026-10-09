import React from 'react';
import {
  PortfolioSnapshot,
  DrivingSignal,
} from '../types';
import { ShieldAlert, ArrowUpRight, ArrowDownRight, Minus, Eye } from 'lucide-react';

interface HoldingsTableProps {
  snapshot?: PortfolioSnapshot | null;
  onSelectSignal?: (signal: DrivingSignal) => void;
  onSelectTickerSignals: (ticker: string, signals: DrivingSignal[]) => void;
}

export const HoldingsTable: React.FC<HoldingsTableProps> = ({
  snapshot,
  onSelectSignal: _onSelectSignal,
  onSelectTickerSignals,
}) => {
  if (!snapshot) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 text-center text-text-secondary text-sm">
        Loading portfolio holdings snapshot...
      </div>
    );
  }

  const { positions, hold_threshold_bps, turnover, turnover_constrained, bounds_constrained } = snapshot;

  return (
    <div className="rounded-lg border border-border bg-surface shadow-sm overflow-hidden">
      {/* Header bar */}
      <div className="border-b border-border bg-surface-secondary/40 px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary">
              Asset Holdings & Tactical Allocation Snapshot
            </h2>
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-accent/10 border border-accent/30 text-accent">
              {snapshot.date}
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-0.5">
            Hold Threshold: <span className="font-mono text-text-primary font-medium">{hold_threshold_bps} bps</span> • Daily Turnover: <span className="font-mono text-text-primary font-medium">{(turnover * 100).toFixed(2)}%</span> • Change = (Current Wt − Prev Wt) × 10,000 bps
          </p>
        </div>

        <div className="flex items-center gap-2">
          {turnover_constrained && (
            <span className="flex items-center gap-1 rounded bg-warning/10 border border-warning/30 px-2.5 py-1 text-[11px] font-medium text-warning">
              <ShieldAlert className="h-3 w-3" /> Turnover Capped (10%)
            </span>
          )}
          {bounds_constrained && (
            <span className="flex items-center gap-1 rounded bg-accent/10 border border-accent/30 px-2.5 py-1 text-[11px] font-medium text-accent">
              Bounds Active [3.57%, 14.29%]
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border bg-surface text-text-secondary uppercase text-[10px] tracking-wider">
            <tr>
              <th className="py-2.5 px-4 font-semibold">Ticker</th>
              <th className="py-2.5 px-3 font-semibold">Prev Wt</th>
              <th className="py-2.5 px-3 font-semibold">Current Wt</th>
              <th className="py-2.5 px-3 font-semibold">Base Wt</th>
              <th className="py-2.5 px-3 font-semibold">Target Wt</th>
              <th className="py-2.5 px-3 font-semibold">Change (bps)</th>
              <th className="py-2.5 px-3 font-semibold text-center">ACTION</th>
              <th className="py-2.5 px-3 font-semibold text-right">Raw Score</th>
              <th className="py-2.5 px-3 font-semibold text-right">EMA Score</th>
              <th className="py-2.5 px-4 font-semibold text-center">Signals</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {positions.map((pos) => {
              const changeBps = pos.weight_change_bps;
              const hasSignals = pos.top_driving_signals && pos.top_driving_signals.length > 0;

              return (
                <tr
                  key={pos.ticker}
                  className="hover:bg-surface-secondary/50 transition-colors group"
                >
                  {/* Ticker */}
                  <td className="py-3 px-4 font-bold font-mono text-text-primary text-xs">
                    {pos.ticker}
                  </td>

                  {/* Previous Executed Weight */}
                  <td className="py-3 px-3 font-mono text-text-secondary">
                    {(pos.prev_weight * 100).toFixed(2)}%
                  </td>

                  {/* Current Weight */}
                  <td className="py-3 px-3 font-mono font-semibold text-text-primary">
                    {(pos.weight * 100).toFixed(2)}%
                  </td>

                  {/* Base Weight */}
                  <td className="py-3 px-3 font-mono text-text-secondary/70">
                    {(pos.base_weight * 100).toFixed(2)}%
                  </td>

                  {/* Target Weight */}
                  <td className="py-3 px-3 font-mono text-text-secondary">
                    {(pos.target_weight * 100).toFixed(2)}%
                  </td>

                  {/* Weight Change (bps) */}
                  <td className="py-3 px-3 font-mono">
                    <span
                      className={`inline-flex items-center gap-0.5 ${
                        changeBps > 0
                          ? 'text-positive'
                          : changeBps < 0
                          ? 'text-negative'
                          : 'text-text-secondary'
                      }`}
                    >
                      {changeBps > 0 && <ArrowUpRight className="h-3 w-3" />}
                      {changeBps < 0 && <ArrowDownRight className="h-3 w-3" />}
                      {changeBps === 0 && <Minus className="h-3 w-3" />}
                      {changeBps > 0 ? `+${changeBps.toFixed(1)}` : changeBps.toFixed(1)}
                    </span>
                  </td>

                  {/* Action Badge */}
                  <td className="py-3 px-3 text-center">
                    {pos.action === 'INCREASE' && (
                      <span className="inline-flex items-center rounded-md border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold text-positive">
                        INCREASE
                      </span>
                    )}
                    {pos.action === 'REDUCE' && (
                      <span className="inline-flex items-center rounded-md border border-negative/30 bg-negative/10 px-2 py-0.5 text-[10px] font-semibold text-negative">
                        REDUCE
                      </span>
                    )}
                    {pos.action === 'HOLD' && (
                      <span className="inline-flex items-center rounded-md border border-border bg-surface-secondary px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                        HOLD
                      </span>
                    )}
                  </td>

                  {/* Daily Raw Score */}
                  <td className="py-3 px-3 font-mono text-right">
                    <span
                      className={
                        pos.raw_score > 0
                          ? 'text-positive'
                          : pos.raw_score < 0
                          ? 'text-negative'
                          : 'text-text-secondary'
                      }
                    >
                      {pos.raw_score !== 0 ? pos.raw_score.toFixed(4) : '0.0000'}
                    </span>
                  </td>

                  {/* Smoothed EMA Score */}
                  <td className="py-3 px-3 font-mono text-right font-medium text-text-primary">
                    <span
                      className={
                        pos.smoothed_score > 0
                          ? 'text-positive'
                          : pos.smoothed_score < 0
                          ? 'text-negative'
                          : 'text-text-secondary'
                      }
                    >
                      {pos.smoothed_score.toFixed(4)}
                    </span>
                  </td>

                  {/* Driving Signals Button */}
                  <td className="py-3 px-4 text-center">
                    {hasSignals ? (
                      <button
                        onClick={() => onSelectTickerSignals(pos.ticker, pos.top_driving_signals)}
                        className="inline-flex items-center gap-1.5 rounded border border-accent/20 bg-accent/5 px-2 py-1 text-[11px] font-medium text-accent hover:bg-accent/15 transition-colors"
                      >
                        <Eye className="h-3 w-3" />
                        <span>{pos.top_driving_signals.length} Signals</span>
                      </button>
                    ) : (
                      <span className="text-[11px] text-text-secondary/50 font-mono">None</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
