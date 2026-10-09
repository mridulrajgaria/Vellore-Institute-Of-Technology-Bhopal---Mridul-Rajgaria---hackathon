import React, { useState, useMemo } from 'react';
import { DrivingSignal, ActionType } from '../types';
import { Radio, ArrowUpRight, ArrowDownRight, ChevronDown, ChevronRight, Minus } from 'lucide-react';

interface SignalFeedProps {
  signals: DrivingSignal[];
  activeTicker?: string | null;
  onSelectSignal: (sig: DrivingSignal) => void;
  onClearFilter?: () => void;
}

export const SignalFeed: React.FC<SignalFeedProps> = ({
  signals,
  activeTicker,
  onSelectSignal,
  onClearFilter,
}) => {
  const [showIgnored, setShowIgnored] = useState<boolean>(false);

  // Single source partitioning: active driving signals vs deadband-ignored signals
  const { drivingSignals, ignoredSignals } = useMemo(() => {
    const driving: DrivingSignal[] = [];
    const ignored: DrivingSignal[] = [];

    signals.forEach((sig) => {
      if (sig.filtered_by_deadband) {
        ignored.push(sig);
      } else {
        driving.push(sig);
      }
    });

    // Driving signals sorted strictly by absolute contribution descending
    driving.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
    // Ignored signals sorted by rank
    ignored.sort((a, b) => a.rank - b.rank);

    return { drivingSignals: driving, ignoredSignals: ignored };
  }, [signals]);

  const totalCount = signals.length;

  const renderSignalCard = (sig: DrivingSignal, isIgnored: boolean = false) => {
    const isNegative = sig.sentiment_score < 0;
    const isDeadband = sig.filtered_by_deadband;
    const confPct = Math.round(sig.event_confidence * 100);

    const actionBadge: ActionType = isDeadband
      ? 'HOLD'
      : isNegative
      ? 'REDUCE'
      : 'INCREASE';

    return (
      <div
        key={`${sig.text_id}-${sig.rank}-${sig.ticker ?? ''}`}
        onClick={() => onSelectSignal(sig)}
        className={`p-3 rounded-md transition-all cursor-pointer group flex flex-col gap-2 my-1 border ${
          isIgnored
            ? 'bg-surface-secondary/30 border-border/40 hover:bg-surface-secondary/60 hover:border-border opacity-75 hover:opacity-100'
            : 'hover:bg-surface-secondary/60 border-transparent hover:border-border'
        }`}
      >
        {/* Top line: Badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            {sig.ticker && (
              <span className="font-mono font-bold text-accent px-1.5 py-0.5 rounded bg-accent/10 border border-accent/25 text-[11px]">
                {sig.ticker}
              </span>
            )}
            {/* Event Type */}
            <span className="rounded bg-surface-secondary px-2 py-0.5 text-[10px] font-medium text-text-secondary border border-border">
              {sig.event_type}
            </span>

            {/* Source */}
            <span className="text-[10px] font-mono text-text-secondary/70">
              {sig.source}
            </span>
          </div>

          {/* ACTION Badge */}
          <div className="flex items-center gap-1.5">
            {actionBadge === 'INCREASE' && (
              <span className="inline-flex items-center gap-0.5 rounded border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold text-positive">
                <ArrowUpRight className="h-2.5 w-2.5" /> BUY TILT
              </span>
            )}
            {actionBadge === 'REDUCE' && (
              <span className="inline-flex items-center gap-0.5 rounded border border-negative/30 bg-negative/10 px-2 py-0.5 text-[10px] font-semibold text-negative">
                <ArrowDownRight className="h-2.5 w-2.5" /> SELL TILT
              </span>
            )}
            {actionBadge === 'HOLD' && (
              <span className="inline-flex items-center gap-0.5 rounded border border-border bg-surface-secondary px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                <Minus className="h-2.5 w-2.5" /> NEUTRAL
              </span>
            )}
          </div>
        </div>

        {/* Headline text */}
        <p className="text-xs text-text-primary line-clamp-2 leading-relaxed group-hover:text-accent transition-colors">
          {sig.headline}
        </p>

        {/* Bottom Metrics Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-[11px] text-text-secondary border-t border-border/30">
          {/* Confidence meter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px]">Confidence:</span>
            <div className="w-14 h-1.5 bg-surface-secondary rounded-full overflow-hidden border border-border">
              <div
                className="h-full bg-accent"
                style={{ width: `${confPct}%` }}
              />
            </div>
            <span className="font-mono text-[10px] text-text-primary font-medium">
              {confPct}%
            </span>
          </div>

          {/* Sentiment, Impact, & Contribution */}
          <div className="flex items-center gap-3">
            {!isIgnored && sig.contribution !== 0 && (
              <span className="flex items-center gap-1">
                <span className="text-[10px]">Contrib:</span>
                <span className={`font-mono font-semibold ${sig.contribution > 0 ? 'text-positive' : 'text-negative'}`}>
                  {sig.contribution > 0 ? '+' : ''}{sig.contribution.toFixed(4)}
                </span>
              </span>
            )}

            <span className="flex items-center gap-1">
              <span className="text-[10px]">Impact:</span>
              <span className="font-mono font-semibold text-text-primary">
                {sig.impact_score.toFixed(1)}/10
              </span>
            </span>

            <span className="flex items-center gap-1">
              <span className="text-[10px]">Sentiment:</span>
              <span
                className={`font-mono font-semibold ${
                  isDeadband
                    ? 'text-text-secondary'
                    : isNegative
                    ? 'text-negative'
                    : 'text-positive'
                }`}
              >
                {sig.sentiment_score > 0 ? '+' : ''}
                {sig.sentiment_score.toFixed(2)}
              </span>
              {isDeadband && (
                <span className="text-[9px] text-warning px-1 rounded bg-warning/10">
                  deadband
                </span>
              )}
            </span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="rounded-lg border border-border bg-surface shadow-sm overflow-hidden flex flex-col h-[520px]">
      {/* Header */}
      <div className="border-b border-border bg-surface-secondary/40 px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-accent animate-pulse" />
          <h2 className="text-sm font-semibold text-text-primary">
            Risk Signal Feed
          </h2>
          {activeTicker && (
            <span className="flex items-center gap-1.5 rounded-full bg-accent/15 border border-accent/30 px-2 py-0.5 text-[10px] font-mono text-accent">
              Filtered: {activeTicker}
              {onClearFilter && (
                <button
                  onClick={onClearFilter}
                  className="hover:text-white font-bold ml-1"
                >
                  ×
                </button>
              )}
            </span>
          )}
        </div>
        <div className="text-xs text-text-secondary">
          <span className="font-mono text-text-primary font-semibold">{drivingSignals.length}</span> Active
          {ignoredSignals.length > 0 && (
            <span className="text-text-secondary/70"> • <span className="font-mono">{ignoredSignals.length}</span> Ignored</span>
          )}
          <span className="text-text-secondary/50"> ({totalCount} Total)</span>
        </div>
      </div>

      {/* Signal List */}
      <div className="flex-1 overflow-y-auto divide-y divide-border/50 p-2">
        {totalCount === 0 ? (
          <div className="p-8 text-center text-text-secondary text-xs">
            No risk signals detected for this trading session. Portfolio weights decayed via half-life EMA.
          </div>
        ) : (
          <>
            {/* Driving signals that actually moved portfolio weights */}
            {drivingSignals.length === 0 ? (
              <div className="p-4 text-center text-text-secondary text-xs italic">
                No active signals exceeded the FinBERT ±0.20 deadband today.
              </div>
            ) : (
              drivingSignals.map((sig) => renderSignalCard(sig, false))
            )}

            {/* Collapsed section for deadband-filtered signals */}
            {ignoredSignals.length > 0 && (
              <div className="pt-2">
                <button
                  onClick={() => setShowIgnored(!showIgnored)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-surface-secondary/50 hover:bg-surface-secondary text-xs text-text-secondary hover:text-text-primary transition-colors border border-border/50"
                >
                  <div className="flex items-center gap-2">
                    {showIgnored ? (
                      <ChevronDown className="h-3.5 w-3.5 text-accent" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-text-secondary" />
                    )}
                    <span className="font-medium text-text-primary">
                      Ignored (below deadband): {ignoredSignals.length}
                    </span>
                  </div>
                  <span className="text-[10px] text-text-secondary font-mono">
                    {showIgnored ? 'Click to hide' : 'Click to view'}
                  </span>
                </button>

                {showIgnored && (
                  <div className="mt-2 space-y-1 pl-2 border-l-2 border-border/60">
                    {ignoredSignals.map((sig) => renderSignalCard(sig, true))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
