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
  const [showAllDriving, setShowAllDriving] = useState<boolean>(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const selectedCardRef = React.useRef<HTMLDivElement>(null);

  // Auto-expand ignored section if selected signal is filtered by deadband
  React.useEffect(() => {
    if (selectedSignal?.filtered_by_deadband) {
      setShowIgnored(true);
    }
  }, [selectedSignal?.filtered_by_deadband]);

  // Scroll selected card fully into view on selection and on date change with padding
  React.useEffect(() => {
    if (selectedCardRef.current && containerRef.current) {
      const card = selectedCardRef.current;
      const container = containerRef.current;
      const cardRect = card.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const topPadding = 12;
      const bottomPadding = 12;

      if (cardRect.top < containerRect.top + topPadding) {
        container.scrollTo({
          top: Math.max(0, container.scrollTop + (cardRect.top - containerRect.top) - topPadding),
          behavior: 'smooth',
        });
      } else if (cardRect.bottom > containerRect.bottom - bottomPadding) {
        container.scrollTo({
          top: container.scrollTop + (cardRect.bottom - containerRect.bottom) + bottomPadding,
          behavior: 'smooth',
        });
      }
    }
  }, [selectedSignal?.text_id, signals]);

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

  const visibleDrivingSignals = showAllDriving ? drivingSignals : drivingSignals.slice(0, 3);
  const hiddenDrivingCount = Math.max(0, drivingSignals.length - 3);

  const renderCard = (sig: DrivingSignal, isIgnored: boolean = false) => {
    const isSelected = selectedSignal?.text_id === sig.text_id;
    const isNeg = sig.sentiment_score < 0;

    return (
      <div
        key={`${sig.text_id}-${sig.rank}`}
        ref={isSelected ? selectedCardRef : undefined}
        onClick={() => onSelectSignal(sig)}
        className={`py-2 px-2.5 rounded-md transition-all cursor-pointer border scroll-mt-3 ${
          isSelected
            ? 'border-accent bg-blue-50/70 shadow-xs ring-1 ring-accent/20'
            : isIgnored
            ? 'bg-slate-50/70 border-slate-200/80 opacity-70 hover:opacity-100 hover:bg-slate-100'
            : 'bg-white border-border shadow-xs hover:border-slate-300 hover:bg-slate-50/50'
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
              <span className="text-text-secondary flex items-center gap-0.5">
                <Minus className="h-3 w-3" /> too weak
              </span>
            ) : isNeg ? (
              <span className="text-negative flex items-center font-semibold">
                <ArrowDownRight className="h-3 w-3" /> reduce
              </span>
            ) : (
              <span className="text-positive flex items-center font-semibold">
                <ArrowUpRight className="h-3 w-3" /> increase
              </span>
            )}
          </div>
        </div>

        {/* Headline: Geist Sans font */}
        <p className={`text-xs font-sans leading-relaxed line-clamp-2 ${
          isSelected ? 'text-text-primary font-medium' : 'text-slate-700 hover:text-text-primary'
        }`}>
          {sig.headline}
        </p>

        {/* Bottom metrics: Geist Mono for numbers */}
        <div className="flex items-center justify-between mt-1.5 pt-1 border-t border-border/60 text-[10px] text-text-secondary">
          <span className="font-sans text-text-secondary">{sig.event_type}</span>
          <span className="font-mono">Imp {sig.impact_score.toFixed(1)}/10</span>
          <span className={`font-mono ${sig.filtered_by_deadband ? 'text-text-secondary' : isNeg ? 'text-negative font-medium' : 'text-positive font-medium'}`}>
            Sent {sig.sentiment_score > 0 ? '+' : ''}{sig.sentiment_score.toFixed(2)}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col p-4 bg-surface rounded-lg border border-border shadow-xs">
      {/* Column Header: 1 News + plain caption */}
      <div className="flex items-baseline justify-between pb-2.5 mb-2 border-b border-border">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            1 News
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            What people were saying today
          </div>
        </div>
        <span className="text-xs font-mono text-text-secondary">
          <strong className="text-text-primary font-semibold">{drivingSignals.length}</strong> active
          {ignoredSignals.length > 0 && <span className="text-text-secondary/70"> / {signals.length} total</span>}
        </span>
      </div>

      {/* Stream list */}
      <div
        ref={containerRef}
        className="space-y-2 pt-1 pb-1 flex-1"
      >
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
              visibleDrivingSignals.map((sig) => renderCard(sig, false))
            )}

            {/* Expander for remaining driving signals */}
            {hiddenDrivingCount > 0 && (
              <div className="pt-1">
                <button
                  onClick={() => setShowAllDriving(!showAllDriving)}
                  className="w-full py-1.5 px-2 rounded-md text-xs font-mono text-accent hover:bg-blue-50 border border-blue-200 bg-white transition-colors flex items-center justify-center gap-1 shadow-2xs"
                >
                  {showAllDriving ? (
                    <>
                      <ChevronDown className="h-3 w-3 rotate-180" />
                      <span>Show top 3 only</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      <span>Show {hiddenDrivingCount} more</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Ignored (too weak to count) accordion */}
            {ignoredSignals.length > 0 && (
              <div className="pt-2">
                <button
                  onClick={() => setShowIgnored(!showIgnored)}
                  className="w-full flex items-center justify-between p-1.5 rounded-md text-xs text-text-secondary hover:text-text-primary hover:bg-slate-100 transition-colors border border-dashed border-border"
                >
                  <div className="flex items-center gap-1.5 font-mono text-[11px]">
                    {showIgnored ? <ChevronDown className="h-3.5 w-3.5 text-accent" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    <span>Ignored (too weak to count): {ignoredSignals.length}</span>
                  </div>
                  <span className="text-[10px] text-text-muted font-sans">
                    {showIgnored ? 'Collapse' : 'Expand'}
                  </span>
                </button>

                {showIgnored && (
                  <div className="space-y-1.5 mt-1.5 pt-1 border-l-2 border-slate-200 pl-2">
                    {ignoredSignals.map((sig) => renderCard(sig, true))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Aligned column footer note */}
      <div className="pt-2 border-t border-border text-[10px] text-text-secondary font-sans leading-snug">
        Pre-market headlines & social posts ingested before the 21:00 UTC cutoff.
      </div>
    </div>
  );
};
