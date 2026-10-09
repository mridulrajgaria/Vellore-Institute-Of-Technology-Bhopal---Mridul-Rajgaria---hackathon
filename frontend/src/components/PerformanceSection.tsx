import React, { useState, useMemo } from 'react';
import { NavPoint, PortfolioWeight } from '../types';
import { PerformanceChart } from './PerformanceChart';
import { WeightsAreaChart } from './WeightsAreaChart';

interface PerformanceSectionProps {
  navData: NavPoint[];
  weightsData: PortfolioWeight[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
}

export const PerformanceSection: React.FC<PerformanceSectionProps> = ({
  navData,
  weightsData,
  selectedDate,
  onSelectDate,
}) => {
  const [activeTab, setActiveTab] = useState<'perf' | 'weights'>('perf');

  // Day's returns for the selected date
  const dayNav = useMemo(() => {
    return navData.find((d) => d.date === selectedDate) ?? null;
  }, [navData, selectedDate]);

  return (
    <div className="border-t border-border/40 pt-4 px-6 max-w-[1600px] mx-auto">
      {/* Tab bar & Day's return strip */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-border/30">
        <div className="flex items-center gap-1 font-mono text-xs">
          <button
            onClick={() => setActiveTab('perf')}
            className={`px-3 py-1.5 rounded transition-colors ${
              activeTab === 'perf'
                ? 'bg-surface-secondary text-text-primary font-bold border border-border/60'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Cumulative Performance
          </button>
          <button
            onClick={() => setActiveTab('weights')}
            className={`px-3 py-1.5 rounded transition-colors ${
              activeTab === 'weights'
                ? 'bg-surface-secondary text-text-primary font-bold border border-border/60'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Weights Over Time
          </button>
        </div>

        {/* Selected Day's daily returns */}
        {dayNav && (
          <div className="flex items-center gap-3 font-mono text-xs">
            <span className="text-text-secondary text-[11px]">{selectedDate} returns:</span>
            <span className="flex items-center gap-1">
              <span className="text-text-secondary">Strategy:</span>
              <span className={`font-semibold ${dayNav.strat_ret_5bps >= 0 ? 'text-positive' : 'text-negative'}`}>
                {dayNav.strat_ret_5bps >= 0 ? '+' : ''}{(dayNav.strat_ret_5bps * 100).toFixed(2)}%
              </span>
            </span>
            <span className="text-border/60">•</span>
            <span className="flex items-center gap-1">
              <span className="text-text-secondary">EW:</span>
              <span className={`font-semibold ${dayNav.ew_ret_5bps >= 0 ? 'text-positive' : 'text-negative'}`}>
                {dayNav.ew_ret_5bps >= 0 ? '+' : ''}{(dayNav.ew_ret_5bps * 100).toFixed(2)}%
              </span>
            </span>
            <span className="text-border/60">•</span>
            <span className="flex items-center gap-1">
              <span className="text-text-secondary">SPY:</span>
              <span className={`font-semibold ${dayNav.spy_ret >= 0 ? 'text-positive' : 'text-negative'}`}>
                {dayNav.spy_ret >= 0 ? '+' : ''}{(dayNav.spy_ret * 100).toFixed(2)}%
              </span>
            </span>
          </div>
        )}
      </div>

      {/* Tab content */}
      <div className="pt-2">
        {activeTab === 'perf' ? (
          <PerformanceChart
            navData={navData}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
          />
        ) : (
          <WeightsAreaChart
            weightsData={weightsData}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
          />
        )}
      </div>
    </div>
  );
};
