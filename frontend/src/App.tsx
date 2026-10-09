import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  PortfolioWeight,
  NavPoint,
  PortfolioSnapshot,
  MetaMetricsResponse,
  DrivingSignal,
  HighImpactDay,
} from './types';
import {
  fetchPortfolioWeights,
  fetchPortfolioNav,
  fetchPortfolioSnapshot,
  fetchMetaMetrics,
  fetchHighImpactDays,
} from './api/client';
import { SlimHeader } from './components/SlimHeader';
import { ReplayTimeline } from './components/ReplayTimeline';
import { DayStory } from './components/DayStory';
import { NewsColumn } from './components/NewsColumn';
import { SignalColumn } from './components/SignalColumn';
import { PortfolioReactionColumn } from './components/PortfolioReactionColumn';
import { PerformanceSection } from './components/PerformanceSection';
import { KpiLine } from './components/KpiLine';
import { CollapsibleHoldingsTable } from './components/CollapsibleHoldingsTable';
import { MethodologyPage } from './components/MethodologyPage';

export const App: React.FC = () => {
  const [weightsData, setWeightsData] = useState<PortfolioWeight[]>([]);
  const [navData, setNavData] = useState<NavPoint[]>([]);
  const [metrics, setMetrics] = useState<MetaMetricsResponse | null>(null);
  const [highImpactDays, setHighImpactDays] = useState<HighImpactDay[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('2021-10-01');
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<DrivingSignal | null>(null);
  const [highlightedTicker, setHighlightedTicker] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [view, setView] = useState<'dashboard' | 'methodology'>(() => {
    return window.location.hash === '#/methodology' ? 'methodology' : 'dashboard';
  });

  // Active fetch request ID to cancel stale async snapshot requests
  const activeFetchIdRef = useRef<number>(0);

  // Sync hash routing
  useEffect(() => {
    const handleHash = () => {
      if (window.location.hash === '#/methodology') {
        setView('methodology');
      } else {
        setView('dashboard');
      }
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  // Available trading dates with fallback between weights and nav
  const availableDates = useMemo(() => {
    if (weightsData.length > 0) {
      return Array.from(new Set(weightsData.map((w) => w.date))).sort();
    }
    if (navData.length > 0) {
      return navData.map((n) => n.date).sort();
    }
    return [];
  }, [weightsData, navData]);

  // Initial load
  useEffect(() => {
    async function initData() {
      try {
        setLoading(true);
        const [wRes, nRes, mRes, hRes] = await Promise.allSettled([
          fetchPortfolioWeights(),
          fetchPortfolioNav(),
          fetchMetaMetrics(),
          fetchHighImpactDays(10),
        ]);

        if (wRes.status === 'fulfilled') {
          setWeightsData(wRes.value.data);
          if (wRes.value.data.length > 0) {
            setSelectedDate(wRes.value.data[0].date);
          }
        }
        if (nRes.status === 'fulfilled') {
          setNavData(nRes.value.data);
          if (wRes.status !== 'fulfilled' && nRes.value.data.length > 0) {
            setSelectedDate(nRes.value.data[0].date);
          }
        }
        if (mRes.status === 'fulfilled') {
          setMetrics(mRes.value);
        }
        if (hRes.status === 'fulfilled') {
          setHighImpactDays(hRes.value);
        }
      } catch (err) {
        console.error('Failed to initialize dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    initData();
  }, []);

  // Fetch snapshot whenever selectedDate changes with cancellation token
  useEffect(() => {
    if (!selectedDate) return;
    const fetchId = ++activeFetchIdRef.current;

    fetchPortfolioSnapshot(selectedDate)
      .then((snap) => {
        // Only commit state if this is still the most recent request
        if (fetchId === activeFetchIdRef.current) {
          setSnapshot(snap);

          // Extract all driving signals for today
          const daySignals: DrivingSignal[] = [];
          snap.positions.forEach((p) => {
            if (p.top_driving_signals) {
              daySignals.push(...p.top_driving_signals);
            }
          });

          // Sort by contribution
          daySignals.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

          // Auto-select the top driving signal (or first signal)
          const firstDriving = daySignals.find((s) => !s.filtered_by_deadband) ?? daySignals[0] ?? null;
          setSelectedSignal(firstDriving);
          setHighlightedTicker(firstDriving?.ticker ?? null);
        }
      })
      .catch((err) => {
        if (fetchId === activeFetchIdRef.current) {
          console.error(`Failed to load snapshot for ${selectedDate}:`, err);
        }
      });
  }, [selectedDate]);

  // Auto-replay timeline playback at 800ms per day
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

  // Extract signals for current snapshot
  const currentSignals = useMemo(() => {
    if (!snapshot) return [];
    const all: DrivingSignal[] = [];
    snapshot.positions.forEach((pos) => {
      if (pos.top_driving_signals) {
        all.push(...pos.top_driving_signals);
      }
    });
    return all.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  }, [snapshot]);

  // Position for the selected signal's ticker
  const selectedTickerPosition = useMemo(() => {
    if (!snapshot || !selectedSignal?.ticker) return null;
    return snapshot.positions.find((p) => p.ticker === selectedSignal.ticker) || null;
  }, [snapshot, selectedSignal?.ticker]);

  // Handle signal selection
  const handleSelectSignal = (sig: DrivingSignal) => {
    setSelectedSignal(sig);
    if (sig.ticker) {
      setHighlightedTicker(sig.ticker);
    }
  };

  // Handle ticker selection from portfolio reaction column
  const handleSelectTicker = (ticker: string) => {
    setHighlightedTicker(ticker);
    const match = currentSignals.find((s) => s.ticker === ticker);
    if (match) {
      setSelectedSignal(match);
    }
  };

  if (view === 'methodology') {
    return (
      <MethodologyPage
        metrics={metrics}
        onBack={() => {
          window.location.hash = '#/';
          setView('dashboard');
        }}
      />
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-text-primary flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-text-secondary">Loading Rebalance Engine & Historical Data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-text-primary flex flex-col selection:bg-accent selection:text-background font-sans">
      {/* a. Slim Header with Glossary popover */}
      <SlimHeader meta={metrics?.meta} />

      {/* b. Replay Timeline Scrubber */}
      <ReplayTimeline
        dates={availableDates}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
        isPlaying={isPlaying}
        onTogglePlay={() => setIsPlaying(!isPlaying)}
        highImpactDays={highImpactDays}
      />

      {/* c. Day Story (natural prose, no truncation, company names) */}
      <DayStory snapshot={snapshot} />

      {/* Main Container */}
      <main className="flex-1 w-full max-w-[1600px] mx-auto py-4">
        {/* d. Three Columns Read Left-to-Right as the Pipeline */}
        <div className="px-6 grid grid-cols-1 lg:grid-cols-12 gap-0 mb-6">
          {/* Column 1: NEWS (4 cols) */}
          <div className="lg:col-span-4">
            <NewsColumn
              signals={currentSignals}
              selectedSignal={selectedSignal}
              onSelectSignal={handleSelectSignal}
            />
          </div>

          {/* Column 2: SIGNAL (4 cols) */}
          <div className="lg:col-span-4">
            <SignalColumn
              signal={selectedSignal}
              position={selectedTickerPosition}
            />
          </div>

          {/* Column 3: PORTFOLIO REACTION (4 cols) */}
          <div className="lg:col-span-4">
            <PortfolioReactionColumn
              positions={snapshot?.positions || []}
              highlightedTicker={highlightedTicker}
              onSelectTicker={handleSelectTicker}
            />
          </div>
        </div>

        {/* e. Below: Performance & Weights Over Time Tabs with Playhead */}
        <PerformanceSection
          navData={navData}
          weightsData={weightsData}
          selectedDate={selectedDate}
          onSelectDate={setSelectedDate}
        />

        {/* Collapsible Full Holdings Table */}
        <CollapsibleHoldingsTable
          snapshot={snapshot}
          onSelectTickerSignals={(ticker, signals) => {
            setHighlightedTicker(ticker);
            const topSig = signals?.[0] ?? currentSignals.find((s) => s.ticker === ticker) ?? null;
            if (topSig) {
              setSelectedSignal(topSig);
            }
            const signalCol = document.getElementById('signal-column');
            if (signalCol) {
              signalCol.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }}
        />

        {/* f. KPIs Quiet Line with wired Methodology Link */}
        <KpiLine
          metrics={metrics}
          onOpenMethodology={() => {
            window.location.hash = '#/methodology';
            setView('methodology');
          }}
        />
      </main>
    </div>
  );
};
