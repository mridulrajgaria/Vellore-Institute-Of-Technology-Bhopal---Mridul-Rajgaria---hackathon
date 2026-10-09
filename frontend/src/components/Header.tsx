import React from 'react';
import { Activity, Calendar } from 'lucide-react';
import { MetaPayload } from '../types';

interface HeaderProps {
  meta?: MetaPayload;
  selectedDate: string;
}

export const Header: React.FC<HeaderProps> = ({ meta: _meta, selectedDate }) => {
  return (
    <header className="border-b border-border bg-surface px-6 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 border border-accent/20 text-accent">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-text-primary">
                AI Risk Signal Index Rebalancer
              </h1>
              <p className="text-xs text-text-secondary mt-0.5">
                Module A: Tactical Mega-Cap Index Rebalancing driven by FinBERT Sentiment & Event Attribution
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Replay Period Badge required */}
          <div className="flex items-center gap-2 rounded-md border border-accent/30 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent">
            <Calendar className="h-3.5 w-3.5" />
            <span>Replay: Oct 2021 – Sep 2022 • historical tweets, not live</span>
          </div>

          {/* Active Date Indicator */}
          <div className="flex items-center gap-2 rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-xs font-mono text-text-primary">
            <span className="text-text-secondary">Snapshot Date:</span>
            <span className="font-semibold text-accent">{selectedDate}</span>
          </div>

          {/* Engine Status */}
          <div className="flex items-center gap-2 rounded-md border border-border bg-surface-secondary px-2.5 py-1.5 text-xs text-text-secondary">
            <span className="h-2 w-2 rounded-full bg-positive animate-pulse" />
            <span className="text-text-primary font-medium">Engine API Online</span>
          </div>
        </div>
      </div>
    </header>
  );
};
