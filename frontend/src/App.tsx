import React, { useEffect, useState, useMemo } from 'react';
import {
  PortfolioWeight,
  NavPoint,
  PortfolioSnapshot,
  MetaMetricsResponse,
  DrivingSignal,
} from './types';
import {
  fetchPortfolioWeights,
  fetchPortfolioNav,
  fetchPortfolioSnapshot,
  fetchMetaMetrics,
} from './api/client';
import { Header } from './components/Header';
import { KpiStrip } from './components/KpiStrip';
import { WeightsAreaChart } from './components/WeightsAreaChart';
import { PerformanceChart } from './components/PerformanceChart';
import { HoldingsTable } from './components/HoldingsTable';
import { SignalFeed } from './components/SignalFeed';
import { SignalImpactModal } from './components/SignalImpactModal';
import { Play, Pause, SkipBack, SkipForward, Calendar } from 'lucide-react';

export const App: React.FC = () => {
  const [weightsData, setWeightsData] = useState<PortfolioWeight[]>([]);
  const [navData, setNavData] = useState<NavPoint[]>([]);
  const [metrics, setMetrics] = useState<MetaMetricsResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('2021-10-01');
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<DrivingSignal | null>(null);
  const [activeTickerFilter, setActiveTickerFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Available trading dates
  const availableDates = useMemo(() => {
    return Array.from(new Set(weightsData.map((w) => w.date))).sort();
  }, [weightsData]);

  // Initial load
  useEffect(() => {
    async function initData() {
      try {
        setLoading(true);
        const [wRes, nRes, mRes] = await Promise.all([
          fetchPortfolioWeights(),
          fetchPortfolioNav(),
          fetchMetaMetrics(),
        ]);
        setWeightsData(wRes.data);
        setNavData(nRes.data);
        setMetrics(mRes);

        if (wRes.data.length > 0) {
          const initialDate = wRes.data[0].date;
          setSelectedDate(initialDate);
        }
      } catch (err) {
        console.error('Failed to initialize dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    initData();
  }, []);

  // Fetch snapshot whenever selectedDate changes with race condition protection
  useEffect(() => {
    if (!selectedDate) return;
    let isCurrent = true;
    fetchPortfolioSnapshot(selectedDate)
      .then((snap) => {
        if (isCurrent) {
          setSnapshot(snap);
        }
      })
      .catch((err) => console.error(`Failed to load snapshot for ${selectedDate}:`, err));
    return () => {
      isCurrent = false;
    };
  }, [selectedDate]);

  // Auto-replay ticker interval
  useEffect(() => {
    if (!isPlaying || availableDates.length === 0) return;
    const interval = setInterval(() => {
      setSelectedDate((curr) => {
        const currIdx = availableDates.indexOf(curr);
        if (currIdx >= availableDates.length - 1) {
          setIsPlaying(false);
          return curr;
        }
        return availableDates[currIdx + 1];
      });
    }, 800);
    return () => clearInterval(interval);
  }, [isPlaying, availableDates]);

  // Extract signals for current snapshot, optionally filtered by ticker
  const currentSignals = useMemo(() => {
    if (!snapshot) return [];
    let all: DrivingSignal[] = [];
    snapshot.positions.forEach((pos) => {
      if (!activeTickerFilter || pos.ticker === activeTickerFilter) {
        if (pos.top_driving_signals) {
          all = all.concat(pos.top_driving_signals);
        }
      }
    });
    // Sort by absolute contribution descending
    return all.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  }, [snapshot, activeTickerFilter]);

  const currentIndex = availableDates.indexOf(selectedDate);

  const handleStep = (delta: number) => {
    const nextIdx = currentIndex + delta;
    if (nextIdx >= 0 && nextIdx < availableDates.length) {
      setSelectedDate(availableDates[nextIdx]);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-accent">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <span className="text-sm font-medium">Loading Risk Engine & Portfolio Data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col">
      {/* Header */}
      <Header meta={metrics?.meta} selectedDate={selectedDate} />

      {/* Main Container */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto pb-12">
        {/* KPI Strip */}
        <KpiStrip metrics={metrics} />

        {/* Date Timeline Scrubber Bar */}
        <div className="px-6 py-2">
          <div className="rounded-lg border border-border bg-surface p-3 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleStep(-1)}
                disabled={currentIndex <= 0}
                className="p-1.5 rounded bg-surface-secondary border border-border hover:bg-border text-text-secondary hover:text-text-primary disabled:opacity-30"
                title="Previous Trading Day"
              >
                <SkipBack className="h-4 w-4" />
              </button>

              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={`p-1.5 rounded border px-3 flex items-center gap-1.5 text-xs font-medium transition-colors ${
                  isPlaying
                    ? 'bg-accent text-background border-accent'
                    : 'bg-surface-secondary border-border text-text-primary hover:bg-border'
                }`}
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                <span>{isPlaying ? 'Pause Replay' : 'Play Timeline'}</span>
              </button>

              <button
                onClick={() => handleStep(1)}
                disabled={currentIndex >= availableDates.length - 1}
                className="p-1.5 rounded bg-surface-secondary border border-border hover:bg-border text-text-secondary hover:text-text-primary disabled:opacity-30"
                title="Next Trading Day"
              >
                <SkipForward className="h-4 w-4" />
              </button>

              <div className="ml-3 flex items-center gap-2 text-xs">
                <Calendar className="h-4 w-4 text-accent" />
                <span className="text-text-secondary">Day:</span>
                <span className="font-mono font-bold text-accent">{selectedDate}</span>
                <span className="text-text-secondary">({currentIndex + 1} of {availableDates.length})</span>
              </div>
            </div>

            {/* Slider */}
            <div className="flex-1 max-w-md mx-4">
              <input
                type="range"
                min={0}
                max={availableDates.length - 1}
                value={currentIndex >= 0 ? currentIndex : 0}
                onChange={(e) => {
                  const idx = Number(e.target.value);
                  if (availableDates[idx]) setSelectedDate(availableDates[idx]);
                }}
                className="w-full accent-accent h-1.5 bg-surface-secondary rounded-lg cursor-pointer"
              />
            </div>

            {/* Jump shortcuts */}
            <div className="flex items-center gap-2 text-xs">
              <button
                onClick={() => setSelectedDate(availableDates[0])}
                className="text-[11px] text-text-secondary hover:text-text-primary hover:underline"
              >
                Start
              </button>
              <span className="text-border">•</span>
              <button
                onClick={() => setSelectedDate(availableDates[Math.floor(availableDates.length / 2)])}
                className="text-[11px] text-text-secondary hover:text-text-primary hover:underline"
              >
                Mid
              </button>
              <span className="text-border">•</span>
              <button
                onClick={() => setSelectedDate(availableDates[availableDates.length - 1])}
                className="text-[11px] text-text-secondary hover:text-text-primary hover:underline"
              >
                End
              </button>
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6 pt-3">
          {/* Main Visual: 14-Asset Weights Area Chart */}
          <WeightsAreaChart
            weightsData={weightsData}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />

          {/* Cumulative Performance Chart */}
          <PerformanceChart
            navData={navData}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />
        </div>

        {/* Bottom Section: Holdings Table & Risk Signal Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 px-6">
          {/* Holdings Snapshot Table (7 Cols) */}
          <div className="lg:col-span-7">
            <HoldingsTable
              snapshot={snapshot}
              onSelectSignal={setSelectedSignal}
              onSelectTickerSignals={(tk) => {
                setActiveTickerFilter(activeTickerFilter === tk ? null : tk);
              }}
            />
          </div>

          {/* Signal Feed (5 Cols) */}
          <div className="lg:col-span-5">
            <SignalFeed
              signals={currentSignals}
              activeTicker={activeTickerFilter}
              onSelectSignal={setSelectedSignal}
              onClearFilter={() => setActiveTickerFilter(null)}
            />
          </div>
        </div>
      </main>

      {/* Signal Explainability Decomposition Modal */}
      <SignalImpactModal
        signal={selectedSignal}
        onClose={() => setSelectedSignal(null)}
      />
    </div>
  );
};
