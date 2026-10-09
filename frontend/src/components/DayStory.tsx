import React from 'react';
import { PortfolioSnapshot, DrivingSignal } from '../types';

interface DayStoryProps {
  snapshot?: PortfolioSnapshot | null;
}

export const DayStory: React.FC<DayStoryProps> = ({ snapshot }) => {
  if (!snapshot) {
    return (
      <div className="py-3 px-6 max-w-[1600px] mx-auto text-xs font-sans text-text-secondary">
        Loading snapshot...
      </div>
    );
  }

  const { positions } = snapshot;

  // Total signals arrived today across all 14 tickers
  let totalSignals = 0;
  let activeDrivingSignals = 0;
  positions.forEach((pos) => {
    if (pos.top_driving_signals) {
      totalSignals += pos.top_driving_signals.length;
      activeDrivingSignals += pos.top_driving_signals.filter((s) => !s.filtered_by_deadband).length;
    }
  });

  // Find ticker with the largest absolute weight change
  let maxPos = positions[0];
  let maxAbsBps = 0;
  positions.forEach((pos) => {
    const absBps = Math.abs(pos.weight_change_bps);
    if (absBps > maxAbsBps) {
      maxAbsBps = absBps;
      maxPos = pos;
    }
  });

  const deltaBps = maxPos.weight_change_bps;
  const oldPct = (maxPos.prev_weight * 100).toFixed(2);
  const newPct = (maxPos.weight * 100).toFixed(2);

  // Find top driving signal for the largest mover that actually drove weights
  const moverActiveSignals = (maxPos.top_driving_signals || []).filter(
    (s) => !s.filtered_by_deadband
  );
  const topSig: DrivingSignal | null = moverActiveSignals.length > 0 ? moverActiveSignals[0] : null;

  // Construct story sentence: Inter for prose, IBM Plex Mono only for numbers
  let storyContent: React.ReactNode;

  if (maxAbsBps < 1.0 || (!topSig && activeDrivingSignals === 0)) {
    // Days where no new driving signals arrived
    storyContent = (
      <span className="font-sans text-text-secondary">
        No new driving signals arrived for today's movers; portfolio weights followed half-life EMA decay toward benchmark.
      </span>
    );
  } else if (!topSig) {
    // Mover shifted without its own direct signal (due to universe re-normalization)
    const isIncrease = deltaBps > 0;
    storyContent = (
      <span className="font-sans">
        <span className="font-mono font-semibold text-text-primary">{totalSignals}</span> signals arrived across the index;{' '}
        <span className="font-mono font-semibold text-text-primary">{maxPos.ticker}</span> saw the largest reallocation with a{' '}
        <span className={`font-mono font-semibold ${isIncrease ? 'text-positive' : 'text-negative'}`}>
          {isIncrease ? '+' : ''}{deltaBps.toFixed(1)} bps
        </span>{' '}
        shift (<span className="font-mono text-text-secondary">{oldPct}% → {newPct}%</span>) through universe re-normalization, with no direct signal of its own today.
      </span>
    );
  } else {
    // Active movement with direct signal
    const isIncrease = deltaBps > 0;
    const isNeg = topSig.sentiment_score < 0;
    const sentAdj = isNeg ? 'negative' : 'positive';
    const sentFormatted = `${topSig.sentiment_score > 0 ? '+' : ''}${topSig.sentiment_score.toFixed(2)}`;

    let eventDescription: React.ReactNode;
    if (topSig.event_type && topSig.event_type !== 'Other') {
      eventDescription = (
        <span>
          {sentAdj} (<span className="font-mono">{sentFormatted}</span>) <span className="font-medium text-text-primary">{topSig.event_type}</span> event
        </span>
      );
    } else {
      // Event type is "Other": do not write "Other event"; write a descriptive post snippet or plain signal
      let topicSnippet = '';
      if (topSig.headline) {
        // Strip leading $TICKER references
        const cleaned = topSig.headline.replace(/^\$[A-Z]+\s+/i, '').trim();
        if (cleaned.length > 15) {
          topicSnippet = ` about "${cleaned.slice(0, 48).trim()}..."`;
        }
      }

      eventDescription = (
        <span>
          {sentAdj} (<span className="font-mono">{sentFormatted}</span>) post{topicSnippet || ' signal'}
        </span>
      );
    }

    storyContent = (
      <span className="font-sans">
        <span className="font-mono font-semibold text-text-primary">{totalSignals}</span> signals arrived;{' '}
        <span className="font-mono font-semibold text-text-primary">{maxPos.ticker}</span> saw the largest reallocation with a{' '}
        <span className={`font-mono font-semibold ${isIncrease ? 'text-positive' : 'text-negative'}`}>
          {isIncrease ? '+' : ''}{deltaBps.toFixed(1)} bps
        </span>{' '}
        delta (<span className="font-mono text-text-secondary">{oldPct}% → {newPct}%</span>) driven by a {eventDescription}.
      </span>
    );
  }

  return (
    <div className="py-3 px-6 max-w-[1600px] mx-auto border-t border-b border-border/40 bg-surface/40">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        {/* Visual Anchor: Inter prose, IBM Plex Mono numbers, larger type */}
        <div className="text-sm font-sans leading-relaxed text-text-secondary max-w-4xl">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary mr-2 font-sans">
            Day Summary:
          </span>
          {storyContent}
        </div>

        {/* Large numeral strictly for the largest weight change */}
        {maxAbsBps >= 1.0 && (
          <div className="flex items-baseline gap-2 font-mono">
            <span className="text-[11px] text-text-secondary">Max Tilt:</span>
            <span
              className={`text-xl font-bold tracking-tight ${
                deltaBps > 0 ? 'text-positive' : 'text-negative'
              }`}
            >
              {deltaBps > 0 ? `+${deltaBps.toFixed(1)}` : deltaBps.toFixed(1)} bps
            </span>
            <span className="text-xs text-text-secondary">({maxPos.ticker})</span>
          </div>
        )}
      </div>
    </div>
  );
};
