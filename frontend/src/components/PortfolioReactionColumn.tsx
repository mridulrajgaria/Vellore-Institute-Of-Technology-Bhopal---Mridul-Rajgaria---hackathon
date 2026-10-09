import React, { useState, useMemo } from 'react';
import { PositionSnapshot } from '../types';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface PortfolioReactionColumnProps {
  positions: PositionSnapshot[];
  highlightedTicker?: string | null;
  onSelectTicker?: (ticker: string) => void;
}

export const PortfolioReactionColumn: React.FC<PortfolioReactionColumnProps> = ({
  positions,
  highlightedTicker,
  onSelectTicker,
}) => {
  const [showAll, setShowAll] = useState<boolean>(false);

  // 1. Sort strictly by absolute weight change so the largest mover is first
  const sortedPositions = useMemo(() => {
    return [...positions].sort(
      (a, b) => Math.abs(b.weight_change_bps) - Math.abs(a.weight_change_bps)
    );
  }, [positions]);

  // Max absolute weight change bps to scale the axis proportionally
  const maxBps = useMemo(() => {
    let maxVal = 50.0;
    positions.forEach((p) => {
      const absVal = Math.abs(p.weight_change_bps);
      if (absVal > maxVal) maxVal = absVal;
    });
    // Round up to nearest 50 for clean scale ticks (e.g., 200 bps)
    return Math.max(100, Math.ceil(maxVal / 50) * 50);
  }, [positions]);

  // Top 6 movers vs all 14
  const displayedPositions = showAll ? sortedPositions : sortedPositions.slice(0, 6);

  return (
    <div className="flex flex-col h-[520px] pl-5">
      {/* Column Header: Quieter small-caps label in secondary text colour */}
      <div className="flex items-baseline justify-between pb-2 mb-2 border-b border-border/30">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
            3. Portfolio Reaction
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            Sorted by absolute weight change
          </div>
        </div>
        <span className="text-xs font-mono text-text-secondary">
          {positions.length} Assets
        </span>
      </div>

      {/* Labelled Scale above the bars */}
      <div className="mb-2 px-1">
        <div className="flex justify-between items-center text-[10px] font-mono text-text-secondary/70">
          <span className="w-16 text-left">-{maxBps} bps</span>
          <span className="text-center font-semibold text-text-primary">0 (Base 7.14%)</span>
          <span className="w-16 text-right">+{maxBps} bps</span>
        </div>
        {/* Scale hairline ruler */}
        <div className="relative w-full h-1 mt-0.5 border-b border-border/40">
          <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-border/60" />
          <div className="absolute top-0 bottom-0 left-1/4 w-0.5 bg-border/30" />
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-text-secondary" />
          <div className="absolute top-0 bottom-0 left-3/4 w-0.5 bg-border/30" />
          <div className="absolute top-0 bottom-0 right-0 w-0.5 bg-border/60" />
        </div>
      </div>

      {/* Bar List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {displayedPositions.map((pos) => {
          const isHighlighted = highlightedTicker === pos.ticker;
          const deltaBps = pos.weight_change_bps;
          const isPositive = deltaBps > 0;
          const absBps = Math.abs(deltaBps);

          // Bar width percentage relative to one half (50%) of the container
          const barWidthHalfPct = Math.min(50, (absBps / maxBps) * 50);

          const oldPct = (pos.prev_weight * 100).toFixed(2);
          const newPct = (pos.weight * 100).toFixed(2);

          const hasHighlightActive = Boolean(highlightedTicker);
          const isDimmed = hasHighlightActive && !isHighlighted;

          return (
            <div
              key={pos.ticker}
              onClick={() => onSelectTicker?.(pos.ticker)}
              className={`py-1 px-1.5 rounded transition-all cursor-pointer border ${
                isHighlighted
                  ? 'border-accent bg-accent/10 shadow-sm'
                  : 'border-transparent hover:bg-surface-secondary/30'
              } ${isDimmed ? 'opacity-40' : 'opacity-100'}`}
            >
              {/* Row Header: Ticker, Old -> New, and Bps */}
              <div className="flex items-center justify-between text-xs mb-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`font-mono font-bold ${
                      isHighlighted ? 'text-accent' : 'text-text-primary'
                    }`}
                  >
                    {pos.ticker}
                  </span>
                  <span className="font-mono text-[10px] text-text-secondary">
                    {oldPct}% → {newPct}%
                  </span>
                </div>

                <span
                  className={`font-mono text-xs font-semibold ${
                    deltaBps > 0
                      ? 'text-positive'
                      : deltaBps < 0
                      ? 'text-negative'
                      : 'text-text-secondary'
                  }`}
                >
                  {deltaBps > 0 ? `+${deltaBps.toFixed(1)}` : deltaBps.toFixed(1)} bps
                </span>
              </div>

              {/* Zero-Centered Diverging Bar Container */}
              <div className="relative w-full h-2 bg-surface-secondary/40 rounded overflow-hidden">
                {/* Thin Zero Axis Line */}
                <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px bg-border z-10" />

                {/* Bar */}
                {isPositive ? (
                  // Positive extends right from center
                  <div
                    className="absolute top-0 bottom-0 left-1/2 bg-positive rounded-r transition-all duration-300"
                    style={{ width: `${barWidthHalfPct}%` }}
                  />
                ) : (
                  // Negative extends left from center
                  <div
                    className="absolute top-0 bottom-0 bg-negative rounded-l transition-all duration-300"
                    style={{
                      right: '50%',
                      width: `${barWidthHalfPct}%`,
                    }}
                  />
                )}
              </div>
            </div>
          );
        })}

        {/* Expander button: "All 14" toggle */}
        {sortedPositions.length > 6 && (
          <div className="pt-1">
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full py-1.5 px-2 rounded border border-border/40 bg-surface hover:bg-surface-secondary/40 text-[11px] font-mono text-text-secondary hover:text-text-primary transition-colors flex items-center justify-center gap-1.5"
            >
              {showAll ? (
                <>
                  <ChevronUp className="h-3.5 w-3.5 text-accent" />
                  <span>Show Top 6 Movers Only</span>
                </>
              ) : (
                <>
                  <ChevronDown className="h-3.5 w-3.5 text-accent" />
                  <span>All 14 Tickers ({sortedPositions.length - 6} more)</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* One-line note at bottom */}
      <div className="pt-2 border-t border-border/30 text-[10px] text-text-secondary font-sans leading-snug">
        Tickers without signals drift slightly because weights re-normalize when others move.
      </div>
    </div>
  );
};
