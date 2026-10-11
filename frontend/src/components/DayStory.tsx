import React, { useState } from 'react';
import { PortfolioSnapshot, DrivingSignal } from '../types';
import { ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';

interface DayStoryProps {
  snapshot?: PortfolioSnapshot | null;
}

export const COMPANY_NAMES: Record<string, string> = {
  AAPL: 'Apple',
  AMD: 'Advanced Micro Devices',
  AMZN: 'Amazon',
  BAC: 'Bank of America',
  DIS: 'Walt Disney',
  GOOGL: 'Alphabet (Google)',
  INTC: 'Intel',
  JPM: 'JPMorgan Chase',
  META: 'Meta Platforms',
  MSFT: 'Microsoft',
  NFLX: 'Netflix',
  NVDA: 'NVIDIA',
  TSLA: 'Tesla',
  XOM: 'ExxonMobil',
};

export function cleanHeadlineText(raw: string): string {
  if (!raw) return '';
  return raw.replace(/^\$[A-Z0-9_]+\s+/i, '').trim();
}

export const DayStory: React.FC<DayStoryProps> = ({ snapshot }) => {
  const [isHeadlineExpanded, setIsHeadlineExpanded] = useState<boolean>(false);
  const [showAllSignals, setShowAllSignals] = useState<boolean>(false);

  if (!snapshot) {
    return (
      <div className="px-6 max-w-[1600px] mx-auto my-3.5">
        <div className="p-4 rounded-xl border border-border bg-surface shadow-xs text-xs font-sans text-text-secondary">
          Select a date on the timeline to view the day summary.
        </div>
      </div>
    );
  }

  const { positions = [], date } = snapshot;

  // 1. Calculate aggregated counts across all positions
  let totalSignals = 0;
  let activeDrivingSignals = 0;

  positions.forEach((pos) => {
    if (pos.top_driving_signals) {
      totalSignals += pos.top_driving_signals.length;
      activeDrivingSignals += pos.top_driving_signals.filter((s) => !s.filtered_by_deadband).length;
    }
  });

  // 2. Identify the ticker with the largest absolute weight change
  let maxPos = positions.length > 0 ? positions[0] : null;
  let maxAbsBps = 0;

  positions.forEach((pos) => {
    const absBps = Math.abs(pos.weight_change_bps);
    if (absBps > maxAbsBps) {
      maxAbsBps = absBps;
      maxPos = pos;
    }
  });

  const hasPositions = positions.length > 0 && maxPos !== null;
  const hasWeightChange = hasPositions && maxAbsBps >= 1.0;
  const prevWeight = maxPos ? maxPos.prev_weight : 0;
  const currWeight = maxPos ? maxPos.weight : 0;
  const diffPp = maxPos ? (currWeight - prevWeight) * 100 : 0;
  const diffBps = maxPos ? maxPos.weight_change_bps : 0;
  const isPositiveChange = diffBps > 0;
  const isNegativeChange = diffBps < 0;

  const oldPct = (prevWeight * 100).toFixed(2);
  const newPct = (currWeight * 100).toFixed(2);
  const company = maxPos ? COMPANY_NAMES[maxPos.ticker] || maxPos.ticker : '';

  // 3. Inspect driving signals for the largest mover
  const moverActiveSignals: DrivingSignal[] = maxPos?.top_driving_signals
    ? maxPos.top_driving_signals.filter((s) => !s.filtered_by_deadband)
    : [];
  const primarySignal: DrivingSignal | null = moverActiveSignals.length > 0 ? moverActiveSignals[0] : null;

  // 4. B. Generate headline describing the largest verified portfolio change
  let headline = '';
  if (!hasPositions) {
    headline = 'No portfolio positions recorded for this date.';
  } else if (!hasWeightChange) {
    if (totalSignals === 0) {
      headline = 'No market posts received today; weights remained unchanged.';
    } else if (activeDrivingSignals === 0) {
      headline = 'All posts fell within the neutral deadband; weights held steady.';
    } else {
      headline = 'Portfolio weights remained unchanged today.';
    }
  } else {
    const direction = isPositiveChange ? 'increase' : 'decrease';
    headline = `${maxPos?.ticker || ''} had the largest portfolio weight ${direction} today.`;
  }

  // 5. Format Largest Weight Change Metric
  let largestChangeDisplay = 'None (0.00 percentage points)';
  let largestChangeColor = 'text-text-primary';
  if (hasWeightChange && maxPos) {
    const sign = isPositiveChange ? '+' : '';
    largestChangeDisplay = `${maxPos.ticker} ${sign}${diffPp.toFixed(2)} percentage points`;
    largestChangeColor = isPositiveChange ? 'text-positive' : 'text-negative';
  }

  const cleanedPrimaryHeadline = primarySignal ? cleanHeadlineText(primarySignal.headline) : '';
  const isLongHeadline = cleanedPrimaryHeadline.length > 120;

  return (
    <section
      aria-labelledby="day-summary-title"
      className="px-6 max-w-[1600px] mx-auto my-3.5"
    >
      <div className="rounded-xl border border-border bg-surface p-5 shadow-xs">
        {/* A. Section Label & B. Headline */}
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary bg-surface-secondary px-2.5 py-0.5 rounded border border-border font-sans">
              Day Summary
            </span>
            {date && (
              <span className="text-xs font-mono text-text-secondary">
                {date}
              </span>
            )}
          </div>
        </div>

        <h2
          id="day-summary-title"
          className="text-base sm:text-lg font-semibold text-text-primary tracking-tight font-sans mt-1"
        >
          {headline}
        </h2>

        {/* C. Three Key Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 my-4">
          {/* Metric 1: Posts Analysed */}
          <div className="p-3.5 rounded-lg bg-surface-secondary/50 border border-border flex flex-col justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-sans">
              Posts Analysed
            </span>
            <div className="mt-1">
              <span className="text-2xl font-bold font-mono text-text-primary">
                {totalSignals}
              </span>
            </div>
            <span className="text-xs text-text-secondary mt-1 font-sans">
              Total market posts evaluated
            </span>
          </div>

          {/* Metric 2: Posts Above Threshold */}
          <div className="p-3.5 rounded-lg bg-surface-secondary/50 border border-border flex flex-col justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-sans">
              Posts Above Threshold
            </span>
            <div className="mt-1">
              <span className="text-2xl font-bold font-mono text-text-primary">
                {activeDrivingSignals}
              </span>
            </div>
            <span className="text-xs text-text-secondary mt-1 font-sans">
              Passed sentiment deadband cut-off
            </span>
          </div>

          {/* Metric 3: Largest Weight Change */}
          <div className="p-3.5 rounded-lg bg-surface-secondary/50 border border-border flex flex-col justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-sans">
              Largest Weight Change
            </span>
            <div className="mt-1">
              <span className={`text-xl sm:text-2xl font-bold font-mono ${largestChangeColor}`}>
                {largestChangeDisplay}
              </span>
            </div>
            <span className="text-xs text-text-secondary mt-1 font-sans">
              {hasWeightChange && maxPos ? company : 'All positions within deadband'}
            </span>
          </div>
        </div>

        {/* D. Portfolio Change & E. Explanation */}
        <div className="pt-4 border-t border-border grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* D. Portfolio Change */}
          <div className="lg:col-span-4 p-3.5 rounded-lg bg-surface-secondary/40 border border-border flex flex-col justify-between h-full">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-sans">
                Portfolio Weight
              </span>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-mono text-lg sm:text-xl font-bold text-text-primary">
                  {oldPct}%
                </span>
                <ArrowRight className="h-4 w-4 text-text-secondary flex-shrink-0" />
                <span className="font-mono text-lg sm:text-xl font-bold text-text-primary">
                  {newPct}%
                </span>
              </div>
              {hasWeightChange && maxPos && (
                <div
                  className={`text-xs font-mono font-medium mt-1 ${
                    isPositiveChange ? 'text-positive' : isNegativeChange ? 'text-negative' : 'text-text-secondary'
                  }`}
                >
                  {isPositiveChange ? '+' : ''}{diffPp.toFixed(2)} percentage points ({diffBps >= 0 ? '+' : ''}{Math.round(diffBps)} bps)
                </div>
              )}
            </div>
            <p className="text-[11px] text-text-secondary mt-3 font-sans leading-snug">
              Allocated output of algorithmic rebalancing rules following daily signal accumulation.
            </p>
          </div>

          {/* E. Explanation */}
          <div className="lg:col-span-8 p-3.5 rounded-lg bg-surface-secondary/40 border border-border">
            <div className="flex items-center justify-between pb-1">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary font-sans">
                Why did the weight change?
              </h3>
            </div>

            {/* Causal / attribution logic */}
            {!hasPositions ? (
              <p className="text-xs text-text-secondary mt-2 font-sans leading-relaxed">
                No portfolio position records were returned for this date.
              </p>
            ) : !hasWeightChange ? (
              <p className="text-xs text-text-secondary mt-2 font-sans leading-relaxed">
                {totalSignals === 0
                  ? 'No market posts were received today. Portfolio weights remained at target without rebalancing adjustments.'
                  : activeDrivingSignals === 0
                  ? `All ${totalSignals} posts received today fell within the neutral sentiment deadband (±0.20), so none altered portfolio allocations.`
                  : 'Daily signal updates remained within model holding thresholds, requiring no weight reallocation.'}
              </p>
            ) : moverActiveSignals.length === 0 ? (
              <p className="text-xs text-text-secondary mt-2 font-sans leading-relaxed">
                No signals passed the deadband threshold for {company} ({maxPos?.ticker || ''}) today. This position shifted due to portfolio re-normalization as other assets adjusted and earlier signals decayed toward benchmark.
              </p>
            ) : (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-text-secondary font-sans leading-relaxed">
                  {moverActiveSignals.length > 1 ? (
                    <>
                      <strong className="text-text-primary font-medium">{moverActiveSignals.length} signals</strong>{' '}
                      contributed to this change under the rebalancing model. Primary contributing signal:
                    </>
                  ) : (
                    <>
                      A qualifying{' '}
                      <strong className={primarySignal!.sentiment_score >= 0 ? 'text-positive font-medium' : 'text-negative font-medium'}>
                        {primarySignal!.sentiment_score >= 0 ? 'positive' : 'negative'}
                      </strong>{' '}
                      signal ({primarySignal!.sentiment_score >= 0 ? `+${primarySignal!.sentiment_score.toFixed(2)}` : primarySignal!.sentiment_score.toFixed(2)}) was incorporated by the rebalancing rules into {company}'s score:
                    </>
                  )}
                </p>

                {/* Primary headline display */}
                {cleanedPrimaryHeadline && (
                  <div className="p-2.5 rounded-md bg-white border border-border">
                    <p
                      className={`text-xs sm:text-sm text-text-primary italic leading-relaxed font-sans ${
                        isHeadlineExpanded ? '' : 'line-clamp-2'
                      }`}
                    >
                      “{cleanedPrimaryHeadline}”
                    </p>
                    {isLongHeadline && (
                      <button
                        type="button"
                        onClick={() => setIsHeadlineExpanded(!isHeadlineExpanded)}
                        className="mt-1.5 text-xs font-mono text-accent hover:underline flex items-center gap-1 cursor-pointer focus:outline-none"
                      >
                        {isHeadlineExpanded ? (
                          <>
                            <ChevronUp className="h-3 w-3" />
                            <span>Show less</span>
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-3 w-3" />
                            <span>View full headline</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}

                {/* Multi-signal expandable toggle if > 1 signal */}
                {moverActiveSignals.length > 1 && (
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => setShowAllSignals(!showAllSignals)}
                      className="text-xs font-mono text-accent hover:underline flex items-center gap-1 cursor-pointer focus:outline-none"
                    >
                      {showAllSignals ? (
                        <>
                          <ChevronUp className="h-3 w-3" />
                          <span>Hide other contributing signals</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-3 w-3" />
                          <span>View all {moverActiveSignals.length} contributing signals</span>
                        </>
                      )}
                    </button>

                    {showAllSignals && (
                      <div className="mt-2 space-y-1.5 pl-2 border-l-2 border-accent-border">
                        {moverActiveSignals.map((sig, idx) => (
                          <div key={sig.text_id || idx} className="text-xs font-sans py-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[11px] text-text-secondary">#{sig.rank}</span>
                              <span
                                className={`font-mono text-[11px] font-semibold ${
                                  sig.sentiment_score >= 0 ? 'text-positive' : 'text-negative'
                                }`}
                              >
                                {sig.sentiment_score >= 0 ? `+${sig.sentiment_score.toFixed(2)}` : sig.sentiment_score.toFixed(2)}
                              </span>
                              <span className="text-[11px] text-text-secondary">({sig.event_type})</span>
                            </div>
                            <p className="text-text-primary text-xs mt-0.5 leading-snug italic">
                              “{cleanHeadlineText(sig.headline)}”
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="text-[11px] text-text-secondary/80 font-sans italic pt-1">
                  Portfolio weights reflect algorithmic rebalancing rules and risk constraints, not forecasted returns.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
