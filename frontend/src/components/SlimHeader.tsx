import React, { useState } from 'react';
import { HelpCircle, ChevronUp } from 'lucide-react';
import { MetaPayload } from '../types';

interface SlimHeaderProps {
  meta?: MetaPayload;
}

export const SlimHeader: React.FC<SlimHeaderProps> = ({ meta: _meta }) => {
  const [showGuide, setShowGuide] = useState<boolean>(false);

  return (
    <header className="border-b border-border/40 bg-surface px-6 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3 max-w-[1600px] mx-auto">
        {/* Left: Index Name & Replay Label */}
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm tracking-tight text-text-primary">
            AI Risk Signal Index Rebalancer
          </span>
          <span className="text-border/60">•</span>
          <span className="text-xs text-text-secondary font-mono">
            Replay: Oct 2021 – Sep 2022 (historical, not live)
          </span>
        </div>

        {/* Right: How to read this toggle */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowGuide(!showGuide)}
            className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent transition-colors"
          >
            {showGuide ? <ChevronUp className="h-3.5 w-3.5" /> : <HelpCircle className="h-3.5 w-3.5" />}
            <span>How to read this</span>
          </button>
        </div>
      </div>

      {/* Expandable How To Read Guide */}
      {showGuide && (
        <div className="mt-2.5 pt-2.5 border-t border-border/40 max-w-[1600px] mx-auto text-xs text-text-secondary leading-relaxed grid grid-cols-1 md:grid-cols-3 gap-6 py-2">
          <div>
            <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
              1. News & Social Ingestion
            </div>
            <p>
              Headlines arriving before 21:00 UTC are attributed to portfolio companies and processed by FinBERT for sentiment (-1 to +1) and an Event Classifier for impact (1 to 10).
            </p>
          </div>
          <div>
            <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
              2. Signal & Asymmetry Filter
            </div>
            <p>
              Sentiment within ±0.20 deadband is ignored. Valid negative sentiment is multiplied 1.25x based on hand-labeled FinBERT precision (85% on negative text).
            </p>
          </div>
          <div>
            <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
              3. Portfolio Reaction & Execution
            </div>
            <p>
              Exponential tilt shifts weights away from benchmark (7.14%). If needed turnover exceeds 10%, changes are capped. Holdings rebalance daily at close with 5 bps slippage.
            </p>
          </div>
        </div>
      )}
    </header>
  );
};
