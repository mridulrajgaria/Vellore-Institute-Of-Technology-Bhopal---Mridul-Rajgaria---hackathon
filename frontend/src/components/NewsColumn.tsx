import React, { useState, useMemo } from 'react';
import { DrivingSignal } from '../types';
import { ChevronDown, ChevronRight, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

interface NewsColumnProps {
  signals: DrivingSignal[];
  selectedSignal: DrivingSignal | null;
  onSelectSignal: (sig: DrivingSignal) => void;
}

export const NewsColumn: React.FC<NewsColumnProps> = ({
  signals,
  selectedSignal,
  onSelectSignal,
}) => {
  const [showIgnored, setShowIgnored] = useState<boolean>(false);

  // Partition signals into driving signals and deadband-ignored signals
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

    driving.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
    ignored.sort((a, b) => a.rank - b.rank);

    return { drivingSignals: driving, ignoredSignals: ignored };
  }, [signals]);

  const renderCard = (sig: DrivingSignal, isIgnored: boolean = false) => {
    const isSelected = selectedSignal?.text_id === sig.text_id;
    const isNeg = sig.sentiment_score < 0;

    return (
      <div
        key={`${sig.text_id}-${sig.rank}`}
        onClick={() => onSelectSignal(sig)}
        className={`py-2 px-2.5 rounded transition-all cursor-pointer border ${
          isSelected
            ? 'border-accent bg-accent/10 shadow-sm'
            : isIgnored
            ? 'border-transparent opacity-60 hover:opacity-100 hover:bg-surface-secondary/20'
            : 'border-transparent hover:bg-surface-secondary/30'
        }`}
      >
        {/* Ticker & metadata top row */}
        <div className="flex items-center justify-between text-xs mb-1">
          <div className="flex items-center gap-1.5">
            {sig.ticker && (
              <span className={`font-mono font-bold text-xs ${
                isSelected ? 'text-accent' : 'text-text-primary'
              }`}>
                {sig.ticker}
              </span>
            )}
            <span className="text-[11px] font-sans text-text-secondary">{sig.source}</span>
          </div>

          <div className="flex items-center gap-1 font-mono text-[10px]">
            {isIgnored ? (
              <span className="text-text-secondary/60 flex items-center gap-0.5">
                <Minus className="h-3 w-3" /> deadband
              </span>
            ) : isNeg ? (
              <span className="text-negative flex items-center font-medium">
                <ArrowDownRight className="h-3 w-3" /> reduce
              </span>
            ) : (
              <span className="text-positive flex items-center font-medium">
                <ArrowUpRight className="h-3 w-3" /> increase
              </span>
            )}
          </div>
        </div>

        {/* Headline: Inter font */}
        <p className={`text-xs font-sans leading-relaxed line-clamp-2 ${
          isSelected ? 'text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'
        }`}>
          {sig.headline}
        </p>

        {/* Bottom metrics: IBM Plex Mono for numbers */}
        <div className="flex items-center justify-between mt-1.5 pt-1 border-t border-border/20 text-[10px] text-text-secondary">
          <span className="font-sans">{sig.event_type}</span>
          <span className="font-mono">Imp {sig.impact_score.toFixed(1)}/10</span>
          <span className={`font-mono ${sig.filtered_by_deadband ? 'text-text-secondary' : isNeg ? 'text-negative' : 'text-positive'}`}>
            Sent {sig.sentiment_score > 0 ? '+' : ''}{sig.sentiment_score.toFixed(2)}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-[520px] border-r border-border/30 pr-5">
      {/* Column Header: Quieter small-caps label in secondary text colour */}
      <div className="flex items-baseline justify-between pb-2 mb-2 border-b border-border/30">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            1. News & Social Stream
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            Pre-21:00 UTC ingested items
          </div>
        </div>
        <span className="text-xs font-mono text-text-secondary">
          <strong className="text-text-primary font-semibold">{drivingSignals.length}</strong> active
          {ignoredSignals.length > 0 && <span className="text-text-secondary/70"> / {signals.length} total</span>}
        </span>
      </div>

      {/* Stream list */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 divide-y divide-border/20">
        {signals.length === 0 ? (
          <div className="p-8 text-center text-xs text-text-secondary font-sans italic">
            No headlines ingested for this trading day.
          </div>
        ) : (
          <>
            {/* Driving signals */}
            {drivingSignals.length === 0 ? (
              <div className="p-4 text-center text-xs text-text-secondary font-sans italic">
                All headlines today fell below the ±0.20 deadband.
              </div>
            ) : (
              drivingSignals.map((sig) => renderCard(sig, false))
            )}

            {/* Ignored below deadband accordion */}
            {ignoredSignals.length > 0 && (
              <div className="pt-2">
                <button
                  onClick={() => setShowIgnored(!showIgnored)}
                  className="w-full flex items-center justify-between p-1.5 rounded text-xs text-text-secondary hover:text-text-primary hover:bg-surface-secondary/20 transition-colors"
                >
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    {showIgnored ? <ChevronDown className="h-3.5 w-3.5 text-accent" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    <span>Ignored (below deadband): {ignoredSignals.length}</span>
                  </div>
                  <span className="text-[10px] text-text-secondary/60 font-sans">
                    {showIgnored ? 'Collapse' : 'Expand'}
                  </span>
                </button>

                {showIgnored && (
                  <div className="space-y-1.5 mt-1 pt-1 border-l border-border/30 pl-2">
                    {ignoredSignals.map((sig) => renderCard(sig, true))}
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
