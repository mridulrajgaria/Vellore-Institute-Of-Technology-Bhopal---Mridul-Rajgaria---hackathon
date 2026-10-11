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

  // Top 9 movers vs all 14 (default to top 9 so card height matches NewsColumn with 4 cards)
  const displayedPositions = showAll ? sortedPositions : sortedPositions.slice(0, 9);

  return (
    <div className="flex flex-col h-full flex-1 p-4 bg-surface rounded-lg border border-border shadow-xs">
      {/* Column Header: 3 Portfolio + plain caption */}
      <div className="flex items-baseline justify-between pb-2.5 mb-2 border-b border-border">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            3 Portfolio
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            What the portfolio did about it
          </div>
        </div>
        <span className="text-xs font-mono text-text-secondary font-medium">
          {positions.length} Assets
        </span>
      </div>

      {/* Labelled Scale above the bars */}
      <div className="mb-2 px-1">
        <div className="flex justify-between items-center text-[10px] font-mono text-text-secondary">
          <span className="w-16 text-left">-{maxBps} bps</span>
          <span className="text-center font-semibold text-text-primary">0 (Base 7.14%)</span>
          <span className="w-16 text-right">+{maxBps} bps</span>
        </div>
        {/* Scale hairline ruler */}
        <div className="relative w-full h-1 mt-0.5 border-b border-border">
          <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-slate-400" />
          <div className="absolute top-0 bottom-0 left-1/4 w-0.5 bg-slate-300" />
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-slate-500" />
          <div className="absolute top-0 bottom-0 left-3/4 w-0.5 bg-slate-300" />
          <div className="absolute top-0 bottom-0 right-0 w-0.5 bg-slate-400" />
        </div>
      </div>

      {/* Asset Rows Container */}
      <div className="space-y-1.5 py-1 flex-1">
        {displayedPositions.map((pos) => {
          const isHighlighted = highlightedTicker === pos.ticker;
          const deltaBps = pos.weight_change_bps;
          const isPositive = deltaBps > 0;
          const absBps = Math.abs(deltaBps);

          // Bar width percentage relative to one half (50%) of the container
          const barWidthHalfPct = Math.min(50, (absBps / maxBps) * 50);

          const oldPct = (pos.prev_weight * 100).toFixed(2);
          const newPct = (pos.weight * 100).toFixed(2);

          return (
            <div
              key={pos.ticker}
              onClick={() => onSelectTicker?.(pos.ticker)}
              className={`py-1.5 px-2 rounded-md transition-all cursor-pointer border ${
                isHighlighted
                  ? 'bg-accent-light border-accent-border shadow-xs'
                  : 'bg-transparent border-transparent hover:bg-surface-secondary'
              }`}
            >
              {/* Row Header: Ticker, Old -> New, and Bps */}
              <div className="flex items-center justify-between text-xs mb-1 font-mono">
                <div className="flex items-center gap-1.5">
                  <span className={`font-bold ${isHighlighted ? 'text-accent' : 'text-text-primary'}`}>
                    {pos.ticker}
                  </span>
                  <span className="text-[10px] text-text-secondary">
                    {oldPct}% → {newPct}%
                  </span>
                </div>
                <span className={`text-[11px] font-semibold ${
                  isPositive ? 'text-positive' : deltaBps < 0 ? 'text-negative' : 'text-text-secondary'
                }`}>
                  {isPositive ? '+' : ''}{deltaBps.toFixed(1)} bps
                </span>
              </div>

              {/* Diverging Bar Container */}
              <div className="relative w-full h-3 bg-bar-track rounded-xs overflow-hidden">
                {/* Thin Zero Axis Line */}
                <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-slate-400 z-10" />

                {/* Bar */}
                {isPositive ? (
                  // Positive extends right from center
                  <div
                    className="absolute top-0 bottom-0 left-1/2 bg-positive rounded-r-xs transition-all duration-300"
                    style={{ width: `${barWidthHalfPct}%` }}
                  />
                ) : (
                  // Negative extends left from center
                  <div
                    className="absolute top-0 bottom-0 bg-negative rounded-l-xs transition-all duration-300"
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

        {/* Expander button: Show all 14 toggle */}
        {sortedPositions.length > 9 && (
          <div className="pt-1">
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full py-1.5 px-2 rounded-md text-xs font-mono text-accent hover:bg-blue-50 border border-blue-200 bg-white transition-colors flex items-center justify-center gap-1 shadow-2xs cursor-pointer"
            >
              {showAll ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  <span>Show top 9 only</span>
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  <span>Show all 14 ({sortedPositions.length - 9} more)</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Aligned column footer note */}
      <div className="pt-2 border-t border-border text-[10px] text-text-secondary font-sans leading-snug">
        Tickers without signals drift slightly because weights re-normalize when others move.
      </div>
    </div>
  );
};
