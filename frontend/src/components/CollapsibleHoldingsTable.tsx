import React, { useState } from 'react';
import { PortfolioSnapshot, DrivingSignal } from '../types';
import { ChevronDown, ChevronRight, Table } from 'lucide-react';
import { HoldingsTable } from './HoldingsTable';

interface CollapsibleHoldingsTableProps {
  snapshot?: PortfolioSnapshot | null;
  onSelectTickerSignals?: (ticker: string, signals: DrivingSignal[]) => void;
}

export const CollapsibleHoldingsTable: React.FC<CollapsibleHoldingsTableProps> = ({
  snapshot,
  onSelectTickerSignals,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <div className="py-2 px-6 max-w-[1600px] mx-auto border-t border-border/30">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-2.5 rounded bg-surface/50 hover:bg-surface-secondary text-xs text-text-secondary hover:text-text-primary transition-colors border border-border/40 font-mono"
      >
        <div className="flex items-center gap-2">
          {isOpen ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4" />}
          <Table className="h-3.5 w-3.5 text-accent" />
          <span className="font-semibold text-text-primary">
            Full Holdings Table (14 assets) — {snapshot?.date || 'Historical Snapshot'}
          </span>
          <span className="text-[11px] text-text-secondary/70">
            • Prev Wt, Current Wt, Change (bps), ACTION
          </span>
        </div>
        <span className="text-[11px] text-text-secondary">
          {isOpen ? 'Click to hide table' : 'Click to expand full table'}
        </span>
      </button>

      {isOpen && (
        <div className="mt-3">
          <HoldingsTable
            snapshot={snapshot}
            onSelectTickerSignals={onSelectTickerSignals || (() => {})}
          />
        </div>
      )}
    </div>
  );
};
