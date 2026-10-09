import React from 'react';
import { PortfolioSnapshot, DrivingSignal } from '../types';

interface DayStoryProps {
  snapshot?: PortfolioSnapshot | null;
}

const COMPANY_NAMES: Record<string, string> = {
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

function formatHeadlineQuote(raw: string, maxLen = 80): string {
  // Strip leading ticker tag like $AMD or $TSLA if present
  const cleaned = raw.replace(/^\$[A-Z0-9_]+\s+/i, '').trim();
  if (cleaned.length <= maxLen) {
    return `"${cleaned}"`;
  }
  const slice = cleaned.slice(0, maxLen);
  const lastSpace = slice.lastIndexOf(' ');
  const cut = lastSpace > 25 ? slice.slice(0, lastSpace) : slice;
  return `"${cut}..."`;
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

  const oldPct = (maxPos.prev_weight * 100).toFixed(2);
  const newPct = (maxPos.weight * 100).toFixed(2);
  const company = COMPANY_NAMES[maxPos.ticker] || maxPos.ticker;

  // Find top driving signal for the largest mover that actually drove weights
  const moverActiveSignals = (maxPos.top_driving_signals || []).filter(
    (s) => !s.filtered_by_deadband
  );
  const topSig: DrivingSignal | null = moverActiveSignals.length > 0 ? moverActiveSignals[0] : null;

  let sentence: React.ReactNode;

  if (maxAbsBps < 1.0 && totalSignals === 0) {
    sentence = (
      <span>
        Today the system read <span className="font-mono font-semibold text-text-primary">0</span> posts. Portfolio weights followed half-life EMA decay toward benchmark.
      </span>
    );
  } else if (!topSig) {
    sentence = (
      <span>
        Today the system read <span className="font-mono font-semibold text-text-primary">{totalSignals}</span> posts{' '}
        (<span className="font-mono text-text-primary">{activeDrivingSignals}</span> strong enough to count). The biggest change:{' '}
        <strong className="text-text-primary">{company} ({maxPos.ticker})</strong> went from{' '}
        <span className="font-mono text-text-primary">{oldPct}%</span> to{' '}
        <span className="font-mono text-text-primary">{newPct}%</span> of the portfolio, moved as earlier signals faded and weights re-balanced.
      </span>
    );
  } else {
    const isNeg = topSig.sentiment_score < 0;
    const sentWord = isNeg ? 'negative' : 'positive';
    const quote = formatHeadlineQuote(topSig.headline, 80);

    sentence = (
      <span>
        Today the system read <span className="font-mono font-semibold text-text-primary">{totalSignals}</span> posts{' '}
        (<span className="font-mono text-text-primary">{activeDrivingSignals}</span> strong enough to count). The biggest change:{' '}
        <strong className="text-text-primary">{company} ({maxPos.ticker})</strong> went from{' '}
        <span className="font-mono text-text-primary">{oldPct}%</span> to{' '}
        <span className="font-mono text-text-primary">{newPct}%</span> of the portfolio, mostly because of a{' '}
        <span className={isNeg ? 'text-negative font-medium' : 'text-positive font-medium'}>{sentWord}</span> post about{' '}
        <span className="font-sans italic text-text-primary">{quote}</span>.
      </span>
    );
  }

  return (
    <div className="py-3 px-6 max-w-[1600px] mx-auto border-t border-b border-border/40 bg-surface/40">
      <div className="text-sm font-sans leading-relaxed text-text-secondary max-w-5xl">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary mr-2 font-sans">
          Day Summary:
        </span>
        {sentence}
      </div>
    </div>
  );
};
