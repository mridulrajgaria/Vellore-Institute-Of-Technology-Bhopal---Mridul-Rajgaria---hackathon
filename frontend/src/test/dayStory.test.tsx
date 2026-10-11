import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DayStory, cleanHeadlineText } from '../components/DayStory';
import { PortfolioSnapshot, DrivingSignal } from '../types';

describe('DayStory Component Redesign', () => {
  const mockSignal1: DrivingSignal = {
    ticker: 'AMD',
    rank: 1,
    text_id: 'sig-01',
    headline: '$AMD expanding partnership with $GOOGL Cloud to "deliver faster application performance" with EPYC processors and enterprise artificial intelligence scale',
    source: 'twitter_kaggle',
    event_type: 'Other',
    sentiment_score: 0.9248,
    impact_score: 5.09,
    event_confidence: 0.8,
    attribution_weight: 1.0,
    adj_sentiment: 0.9248,
    weight_w: 0.51,
    sum_weights_for_ticker: 1.88,
    weight_share: 0.27,
    contribution: 0.25,
    filtered_by_deadband: false,
  };

  const mockSignal2: DrivingSignal = {
    ticker: 'AMD',
    rank: 2,
    text_id: 'sig-02',
    headline: 'AMD Expands Collaboration With Google Cloud to Deliver Faster Application Performance',
    source: 'twitter_kaggle',
    event_type: 'Other',
    sentiment_score: 0.906,
    impact_score: 5.04,
    event_confidence: 0.8,
    attribution_weight: 1.0,
    adj_sentiment: 0.906,
    weight_w: 0.50,
    sum_weights_for_ticker: 1.88,
    weight_share: 0.26,
    contribution: 0.24,
    filtered_by_deadband: false,
  };

  const mockDeadbandSignal: DrivingSignal = {
    ticker: 'AMD',
    rank: 3,
    text_id: 'sig-03',
    headline: 'AMD energy efficiency report announcement',
    source: 'twitter_kaggle',
    event_type: 'Other',
    sentiment_score: 0.14,
    impact_score: 2.99,
    event_confidence: 0.2,
    attribution_weight: 1.0,
    adj_sentiment: 0.0,
    weight_w: 0.30,
    filtered_by_deadband: true,
    contribution: 0.0,
  };

  const mockPositiveSnapshot: PortfolioSnapshot = {
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
        top_driving_signals: [mockSignal1, mockSignal2, mockDeadbandSignal],
      },
      {
        ticker: 'AAPL',
        base_weight: 0.0714,
        prev_weight: 0.0714,
        weight: 0.0684,
        target_weight: 0.0684,
        weight_change_bps: -30.3,
        action: 'REDUCE',
        score: -0.15,
        smoothed_score: -0.15,
        raw_score: -0.15,
        bounds_constrained: false,
        top_driving_signals: [],
      },
    ],
    meta: {
      replay_period: { start: '2021-10-01', end: '2021-12-31', source: 'test' },
      news_period: { start: '2021-10-01', end: '2021-12-31', source: 'test' },
    },
  };

  it('renders section label, dynamic headline, and three key metrics accurately', () => {
    render(<DayStory snapshot={mockPositiveSnapshot} />);

    // Section label
    expect(screen.getByText('Day Summary')).toBeInTheDocument();

    // Headline
    expect(screen.getByText('AMD had the largest portfolio weight increase today.')).toBeInTheDocument();

    // Metric 1: Posts Analysed
    expect(screen.getByText('Posts Analysed')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Metric 2: Posts Above Threshold (2 active, 1 deadband)
    expect(screen.getByText('Posts Above Threshold')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    // Metric 3: Largest Weight Change
    expect(screen.getByText('Largest Weight Change')).toBeInTheDocument();
    expect(screen.getByText('AMD +1.61 percentage points')).toBeInTheDocument();

    // Section D: Portfolio Weight transition
    expect(screen.getByText('7.14%')).toBeInTheDocument();
    expect(screen.getByText('8.75%')).toBeInTheDocument();
  });

  it('handles multiple contributing signals with expandable drawer and full headline toggle', () => {
    render(<DayStory snapshot={mockPositiveSnapshot} />);

    // Multi-signal attribution text
    expect(screen.getByText(/2 signals/i)).toBeInTheDocument();
    expect(screen.getByText(/contributed to this change under the rebalancing model/i)).toBeInTheDocument();

    // Toggle for long headline
    const fullHeadlineBtn = screen.getByRole('button', { name: /view full headline/i });
    expect(fullHeadlineBtn).toBeInTheDocument();
    fireEvent.click(fullHeadlineBtn);
    expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument();

    // Toggle for viewing all contributing signals
    const viewAllSignalsBtn = screen.getByRole('button', { name: /view all 2 contributing signals/i });
    expect(viewAllSignalsBtn).toBeInTheDocument();
    fireEvent.click(viewAllSignalsBtn);
    expect(screen.getByText(/AMD Expands Collaboration With Google Cloud/i)).toBeInTheDocument();
  });

  it('renders negative weight change accurately', () => {
    const mockNegativeSnapshot: PortfolioSnapshot = {
      ...mockPositiveSnapshot,
      positions: [
        {
          ticker: 'TSLA',
          base_weight: 0.0714,
          prev_weight: 0.0714,
          weight: 0.0550,
          target_weight: 0.0550,
          weight_change_bps: -164.0,
          action: 'REDUCE',
          score: -0.55,
          smoothed_score: -0.55,
          raw_score: -0.55,
          bounds_constrained: false,
          top_driving_signals: [
            {
              ...mockSignal1,
              ticker: 'TSLA',
              sentiment_score: -0.75,
              headline: '$TSLA faces unexpected production downtime in key manufacturing facility',
              filtered_by_deadband: false,
            },
          ],
        },
      ],
    };

    render(<DayStory snapshot={mockNegativeSnapshot} />);

    expect(screen.getByText('TSLA had the largest portfolio weight decrease today.')).toBeInTheDocument();
    expect(screen.getByText('TSLA -1.64 percentage points')).toBeInTheDocument();
    expect(screen.getByText('7.14%')).toBeInTheDocument();
    expect(screen.getByText('5.50%')).toBeInTheDocument();
  });

  it('handles empty states gracefully: null snapshot', () => {
    render(<DayStory snapshot={null} />);
    expect(screen.getByText(/select a date on the timeline/i)).toBeInTheDocument();
  });

  it('handles empty states gracefully: zero signals / no change', () => {
    const emptySnapshot: PortfolioSnapshot = {
      ...mockPositiveSnapshot,
      positions: [
        {
          ticker: 'AMD',
          base_weight: 0.0714,
          prev_weight: 0.0714,
          weight: 0.0714,
          target_weight: 0.0714,
          weight_change_bps: 0,
          action: 'HOLD',
          score: 0,
          smoothed_score: 0,
          raw_score: 0,
          bounds_constrained: false,
          top_driving_signals: [],
        },
      ],
    };

    render(<DayStory snapshot={emptySnapshot} />);
    expect(screen.getByText('No market posts received today; weights remained unchanged.')).toBeInTheDocument();
    expect(screen.getByText('None (0.00 percentage points)')).toBeInTheDocument();
  });

  it('cleans headline text without stripping natural prose', () => {
    expect(cleanHeadlineText('$AMD expands server operations')).toBe('expands server operations');
    expect(cleanHeadlineText('Just regular text')).toBe('Just regular text');
    expect(cleanHeadlineText('')).toBe('');
  });
});
