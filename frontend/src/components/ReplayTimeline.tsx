import React, { useEffect, useRef } from 'react';
import { Play, Pause, ChevronLeft, ChevronRight, Zap } from 'lucide-react';
import { HighImpactDay } from '../types';

interface ReplayTimelineProps {
  dates: string[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  highImpactDays: HighImpactDay[];
}

export const ReplayTimeline: React.FC<ReplayTimelineProps> = ({
  dates,
  selectedDate,
  onSelectDate,
  isPlaying,
  onTogglePlay,
  highImpactDays,
}) => {
  const currentIndex = dates.indexOf(selectedDate);
  const sliderRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcuts: Space (play/pause), Left (prev), Right (next)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is focused on an input or textarea
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        onTogglePlay();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        if (currentIndex > 0) {
          onSelectDate(dates[currentIndex - 1]);
        }
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        if (currentIndex < dates.length - 1) {
          onSelectDate(dates[currentIndex + 1]);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentIndex, dates, onSelectDate, onTogglePlay]);

  const handleStep = (delta: number) => {
    const nextIdx = currentIndex + delta;
    if (nextIdx >= 0 && nextIdx < dates.length) {
      onSelectDate(dates[nextIdx]);
    }
  };

  // Top 5 chips
  const top5Days = highImpactDays.slice(0, 5);

  return (
    <div className="py-3 px-6 max-w-[1600px] mx-auto">
      {/* Top row: Controls, current date, and Quick jump chips */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-2">
        {/* Playhead Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleStep(-1)}
            disabled={currentIndex <= 0}
            className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-secondary disabled:opacity-30 transition-colors"
            title="Previous Trading Day (Left Arrow)"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <button
            onClick={onTogglePlay}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium flex items-center gap-1.5 transition-colors ${
              isPlaying
                ? 'bg-accent text-background font-bold'
                : 'text-text-primary bg-surface-secondary hover:bg-border/60'
            }`}
            title="Toggle Replay (Spacebar)"
          >
            {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            <span>{isPlaying ? 'Pause' : 'Play'}</span>
          </button>

          <button
            onClick={() => handleStep(1)}
            disabled={currentIndex >= dates.length - 1}
            className="p-1 rounded text-text-secondary hover:text-text-primary hover:bg-surface-secondary disabled:opacity-30 transition-colors"
            title="Next Trading Day (Right Arrow)"
          >
            <ChevronRight className="h-4 w-4" />
          </button>

          {/* Active Date Counter */}
          <div className="ml-3 flex items-baseline gap-2 font-mono text-xs">
            <span className="font-bold text-accent">{selectedDate}</span>
            <span className="text-text-secondary text-[11px]">
              ({currentIndex >= 0 ? currentIndex + 1 : 1} of {dates.length > 0 ? dates.length : 252} trading days)
            </span>
          </div>
        </div>

        {/* Top 5 High-Impact "Pick a day" chips */}
        {top5Days.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-[11px] text-text-secondary flex items-center gap-1 font-mono">
              <Zap className="h-3 w-3 text-accent" />
              Top events:
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {top5Days.map((chip) => {
                const isActive = chip.date === selectedDate;
                return (
                  <button
                    key={chip.date}
                    onClick={() => onSelectDate(chip.date)}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors border ${
                      isActive
                        ? 'border-accent bg-accent/15 text-accent font-semibold'
                        : 'border-border/60 bg-surface hover:bg-surface-secondary text-text-secondary hover:text-text-primary'
                    }`}
                    title={`${chip.date}: ${chip.ticker} (${chip.event_type}) - ${chip.headline}`}
                  >
                    <span>{chip.date.slice(5)}</span>
                    <span className="ml-1 text-[10px] text-accent/80 font-semibold">{chip.ticker}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Scrubber slider track with high-impact ticks */}
      <div className="relative pt-1 pb-1">
        {/* Ticks container over the slider */}
        <div className="relative w-full h-3 mb-1 pointer-events-none">
          {highImpactDays.map((d) => {
            const tickIdx = dates.indexOf(d.date);
            if (tickIdx < 0 || dates.length <= 1) return null;
            const pct = (tickIdx / (dates.length - 1)) * 100;
            const isCurrent = d.date === selectedDate;

            return (
              <button
                key={d.date}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectDate(d.date);
                }}
                className="absolute top-0 -translate-x-1/2 pointer-events-auto group focus:outline-none"
                style={{ left: `${pct}%` }}
                title={`Jump to ${d.date}: ${d.ticker} (Impact ${d.impact_score.toFixed(1)}/10)`}
              >
                <div
                  className={`w-1.5 h-2.5 rounded-full transition-all ${
                    isCurrent
                      ? 'bg-accent ring-2 ring-accent/30 scale-125'
                      : 'bg-accent/60 hover:bg-accent hover:scale-125'
                  }`}
                />
              </button>
            );
          })}
        </div>

        {/* Range Slider */}
        <input
          ref={sliderRef}
          type="range"
          min={0}
          max={Math.max(0, dates.length - 1)}
          value={currentIndex >= 0 ? currentIndex : 0}
          onChange={(e) => {
            const idx = Number(e.target.value);
            if (dates[idx]) {
              onSelectDate(dates[idx]);
            }
          }}
          className="w-full accent-accent h-1 bg-surface-secondary rounded cursor-pointer"
        />

        {/* Bottom timeline date limits */}
        <div className="flex justify-between items-center text-[10px] font-mono text-text-secondary/70 mt-1">
          <span>{dates[0]}</span>
          <span className="text-[10px] text-text-secondary/40">Space: play/pause • ←/→: step</span>
          <span>{dates[dates.length - 1]}</span>
        </div>
      </div>
    </div>
  );
};
