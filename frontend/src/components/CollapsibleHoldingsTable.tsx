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
    <div className="mt-6 pt-5 px-6 max-w-[1600px] mx-auto border-t border-border">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 rounded-lg bg-surface hover:bg-surface-secondary text-xs text-text-secondary hover:text-text-primary transition-colors border border-border font-sans shadow-xs cursor-pointer"
      >
        <div className="flex items-center gap-2">
          {isOpen ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-muted" />}
          <Table className="h-3.5 w-3.5 text-accent" />
          <span className="font-semibold text-text-primary">
            Full Holdings Table (14 assets) — {snapshot?.date || 'Historical Snapshot'}
          </span>
          <span className="text-[11px] text-text-secondary">
            • Prev Wt, Current Wt, Change (bps), ACTION
          </span>
        </div>
        <span className="text-[11px] font-medium text-accent">
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
