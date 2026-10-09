import React, { useState } from 'react';
import { HelpCircle, ChevronUp, BookOpen, X } from 'lucide-react';
import { MetaPayload } from '../types';

interface SlimHeaderProps {
  meta?: MetaPayload;
}

export const SlimHeader: React.FC<SlimHeaderProps> = ({ meta: _meta }) => {
  const [showGuide, setShowGuide] = useState<boolean>(() => {
    try {
      const dismissed = localStorage.getItem('glossary_dismissed');
      return dismissed !== 'true'; // Open by default on first visit
    } catch {
      return true;
    }
  });

  const handleToggle = () => {
    const nextState = !showGuide;
    setShowGuide(nextState);
    if (!nextState) {
      try {
        localStorage.setItem('glossary_dismissed', 'true');
      } catch {}
    }
  };

  const handleDismiss = () => {
    setShowGuide(false);
    try {
      localStorage.setItem('glossary_dismissed', 'true');
    } catch {}
  };

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
            onClick={handleToggle}
            data-testid="how-to-read-toggle"
            className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent transition-colors cursor-pointer"
          >
            {showGuide ? <ChevronUp className="h-3.5 w-3.5 text-accent" /> : <HelpCircle className="h-3.5 w-3.5" />}
            <span>How to read this</span>
          </button>
        </div>
      </div>

      {/* Expandable Guide & Glossary */}
      {showGuide && (
        <div className="mt-2.5 pt-3 border-t border-border/40 max-w-[1600px] mx-auto text-xs text-text-secondary leading-relaxed space-y-4 pb-2">
          {/* Top banner with dismiss button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-semibold text-text-primary font-sans">
              <BookOpen className="h-3.5 w-3.5 text-accent" />
              <span>Guide & Glossary</span>
            </div>
            <button
              onClick={handleDismiss}
              data-testid="dismiss-guide-btn"
              className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
            >
              <span>Dismiss</span>
              <X className="h-3 w-3" />
            </button>
          </div>

          {/* 3 Pipeline stages */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="p-2.5 rounded bg-surface-secondary/30 border border-border/30">
              <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
                1 News
              </div>
              <p>
                Headlines arriving before 21:00 UTC are attributed to portfolio companies and processed by FinBERT for sentiment (-1 to +1) and an Event Classifier for impact (1 to 10).
              </p>
            </div>
            <div className="p-2.5 rounded bg-surface-secondary/30 border border-border/30">
              <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
                2 Signal
              </div>
              <p>
                Sentiment within ±0.20 deadband is ignored. Valid negative sentiment is multiplied 1.25x based on hand-labeled FinBERT precision (85% on negative text).
              </p>
            </div>
            <div className="p-2.5 rounded bg-surface-secondary/30 border border-border/30">
              <div className="font-semibold text-text-primary mb-1 font-mono text-[11px] uppercase tracking-wider text-accent">
                3 Portfolio
              </div>
              <p>
                Exponential tilt shifts weights away from base (7.14%). If needed turnover exceeds 10%, changes are capped. Holdings rebalance daily at close with 5 bps slippage.
              </p>
            </div>
          </div>

          {/* "What do these terms mean?" Glossary Popover / Section */}
          <div className="p-3 rounded bg-surface-secondary/20 border border-border/40">
            <div className="font-semibold text-text-primary mb-2 text-xs flex items-center gap-1.5 font-sans">
              <span className="text-accent">●</span>
              <span>What do these terms mean?</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2.5 text-[11px]">
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Sentiment:</strong>
                <span>How positive or negative the AI judged the text, scored on a scale from -1.0 to +1.0.</span>
              </div>
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Impact score:</strong>
                <span>The estimated magnitude of stock price reaction expected from the event, rated from 1.0 to 10.0.</span>
              </div>
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Confidence:</strong>
                <span>FinBERT's certainty in its sentiment classification and event categorization.</span>
              </div>
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Cut-off (deadband):</strong>
                <span>The ±0.20 threshold that filters out mild sentiment so model noise does not alter portfolio weights.</span>
              </div>
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Weight:</strong>
                <span>The fraction of total portfolio capital currently invested in a specific company.</span>
              </div>
              <div>
                <strong className="text-text-primary font-mono block mb-0.5">Base weight:</strong>
                <span>The equal 1/14 (~7.14%) benchmark starting weight assigned to every asset before signals arrive.</span>
              </div>
              <div className="md:col-span-2 lg:col-span-3">
                <strong className="text-text-primary font-mono inline mr-1">Overweight / Underweight:</strong>
                <span>Holding more (overweight) or less (underweight) of an asset than its equal 7.14% base share.</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
