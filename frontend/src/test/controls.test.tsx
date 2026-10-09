import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HoldingsTable } from '../components/HoldingsTable';
import { KpiLine } from '../components/KpiLine';
import { SlimHeader } from '../components/SlimHeader';
import { MethodologyPage } from '../components/MethodologyPage';
import { PortfolioSnapshot, DrivingSignal } from '../types';

describe('Interactive Controls & Dead Controls Verification', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  const mockDrivingSignal: DrivingSignal = {
    ticker: 'AMD',
    rank: 1,
    text_id: 'sig-amd-01',
    headline: 'AMD expands server cloud partnership',
    source: 'twitter_kaggle',
    event_type: 'Other',
    sentiment_score: 0.92,
    impact_score: 5.1,
    event_confidence: 0.8,
    attribution_weight: 1.0,
    adj_sentiment: 0.92,
    weight_w: 0.51,
    sum_weights_for_ticker: 1.88,
    weight_share: 0.27,
    contribution: 0.25,
    filtered_by_deadband: false,
  };

  const mockSnapshot: PortfolioSnapshot = {
    date: '2021-10-01',
    turnover: 0.041,
    turnover_constrained: false,
    bounds_constrained: false,
    hold_threshold_bps: 10,
    positions: [
      {
        ticker: 'AMD',
        base_weight: 0.0714,
        prev_weight: 0.0714,
        weight: 0.0875,
        target_weight: 0.0875,
        weight_change_bps: 160.6,
        action: 'INCREASE',
        score: 0.49,
        smoothed_score: 0.49,
        raw_score: 0.49,
        bounds_constrained: false,
        top_driving_signals: [mockDrivingSignal],
      },
      {
        ticker: 'TSLA',
        base_weight: 0.0714,
        prev_weight: 0.0714,
        weight: 0.0691,
        target_weight: 0.0691,
        weight_change_bps: -23.0,
        action: 'REDUCE',
        score: -0.15,
        smoothed_score: -0.15,
        raw_score: 0.0,
        bounds_constrained: false,
        top_driving_signals: [], // No active signals today
      },
    ],
    meta: {
      replay_period: { start: '2021-10-01', end: '2022-09-30', source: 'twitter_kaggle' },
      news_period: { start: '2026-07-07', end: '2026-10-03', source: 'newsapi and gdelt' },
    },
  };

  it('(1a) HoldingsTable "N Signals" button wires to select ticker driving signals; disabled "no signals" for tickers with none', () => {
    const onSelectTickerSignals = vi.fn();

    render(
      <HoldingsTable
        snapshot={mockSnapshot}
        onSelectTickerSignals={onSelectTickerSignals}
      />
    );

    // 1. Ticker with driving signals (AMD)
    const amdBtn = screen.getByTestId('signals-btn-AMD');
    expect(amdBtn).not.toBeDisabled();
    expect(amdBtn).toHaveTextContent('1 Signals');

    // Click AMD signals button
    fireEvent.click(amdBtn);
    expect(onSelectTickerSignals).toHaveBeenCalledTimes(1);
    expect(onSelectTickerSignals).toHaveBeenCalledWith('AMD', [mockDrivingSignal]);

    // 2. Ticker with no driving signals (TSLA)
    const tslaBtn = screen.getByTestId('signals-btn-TSLA');
    expect(tslaBtn).toBeDisabled();
    expect(tslaBtn).toHaveTextContent('no signals');

    // Clicking disabled button should do nothing
    fireEvent.click(tslaBtn);
    expect(onSelectTickerSignals).toHaveBeenCalledTimes(1);
  });

  it('(1b) "See Methodology & Empirical Validation ->" routes to Methodology page, and "Back to dashboard" routes back', () => {
    const onOpenMethodology = vi.fn();

    // 1. Click See Methodology button in KpiLine
    const { unmount } = render(<KpiLine metrics={null} onOpenMethodology={onOpenMethodology} />);
    const linkBtn = screen.getByTestId('see-methodology-btn');
    expect(linkBtn).toHaveTextContent('See Methodology & Empirical Validation →');

    fireEvent.click(linkBtn);
    expect(onOpenMethodology).toHaveBeenCalledTimes(1);
    unmount();

    // 2. Render MethodologyPage and click Back to dashboard button
    const onBack = vi.fn();
    const mockMetrics: any = {
      meta: {},
      module_a: { summary: {}, placebo: {} },
      sentiment_eval: { finbert: {} },
      sentiment_hand_eval: { by_source: {} },
      event_eval: {},
      validation: { tweets_2021_2022: { quintiles: { breakdown: {} }, spearman: { impact_vs_abs_ar0: {} } } },
    };
    render(<MethodologyPage metrics={mockMetrics} onBack={onBack} />);

    expect(screen.getByText('Methodology & Empirical Validation Report')).toBeInTheDocument();
    expect(screen.getByText(/System Architecture in 4 Sentences/i)).toBeInTheDocument();
    expect(screen.getByText(/Did the portfolio beat equal weight\?/i)).toBeInTheDocument();
    expect(screen.getByText(/Key Limitations & Risks/i)).toBeInTheDocument();

    const backBtn = screen.getByTestId('back-to-dashboard-btn');
    expect(backBtn).toHaveTextContent('← Back to dashboard');
    fireEvent.click(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('(5) Glossary popover opens with 7 definitions and remembers dismissal in localStorage', () => {
    // First visit: should be open by default
    const { rerender } = render(<SlimHeader />);
    expect(screen.getByText('What do these terms mean?')).toBeInTheDocument();

    // Check that all 7 required terms are defined in the document
    expect(screen.getByText(/^Sentiment:/i)).toBeInTheDocument();
    expect(screen.getByText(/^Impact score:/i)).toBeInTheDocument();
    expect(screen.getByText(/^Confidence:/i)).toBeInTheDocument();
    expect(screen.getByText(/^Cut-off \(deadband\):/i)).toBeInTheDocument();
    expect(screen.getByText(/^Weight:/i)).toBeInTheDocument();
    expect(screen.getByText(/^Base weight:/i)).toBeInTheDocument();
    expect(screen.getByText(/^Overweight \/ Underweight:/i)).toBeInTheDocument();

    // Dismiss the guide
    const dismissBtn = screen.getByTestId('dismiss-guide-btn');
    fireEvent.click(dismissBtn);

    expect(localStorage.getItem('glossary_dismissed')).toBe('true');
    expect(screen.queryByText('What do these terms mean?')).not.toBeInTheDocument();

    // Re-render: should stay closed because localStorage remembers dismissal
    rerender(<SlimHeader />);
    expect(screen.queryByText('What do these terms mean?')).not.toBeInTheDocument();

    // Click toggle to reopen
    const toggleBtn = screen.getByTestId('how-to-read-toggle');
    fireEvent.click(toggleBtn);
    expect(screen.getByText('What do these terms mean?')).toBeInTheDocument();
  });
});
