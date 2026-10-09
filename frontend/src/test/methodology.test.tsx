import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MethodologyPage } from '../components/MethodologyPage';
import { MetaMetricsResponse } from '../types';
import sentimentEvalRaw from '../../../docs/sentiment_eval.json';
import sentimentHandRaw from '../../../docs/sentiment_hand_eval.json';
import eventEvalRaw from '../../../docs/event_eval.json';
import validationRaw from '../../../docs/validation.json';
import moduleARaw from '../../../docs/module_a.json';

describe('MethodologyPage Source-to-Render Verification', () => {

  const metricsPayload: MetaMetricsResponse = {
    sentiment_eval: sentimentEvalRaw,
    sentiment_hand_eval: sentimentHandRaw,
    event_eval: eventEvalRaw,
    validation: validationRaw,
    module_a: moduleARaw,
    meta: {
      replay_period: {
        start: '2021-10-01',
        end: '2022-09-30',
        source: 'StockTwits & Kaggle Twitter',
      },
      news_period: {
        start: '2026-03-24',
        end: '2026-03-27',
        source: 'Live NewsAPI & GDELT',
      },
    },
  };

  it('renders all metrics exactly matching the source json values to displayed precision', () => {
    render(<MethodologyPage metrics={metricsPayload} onBack={vi.fn()} />);

    // 1. Financial PhraseBank Public Benchmark
    const expectedPhraseBankAcc = `${(sentimentEvalRaw.finbert.accuracy * 100).toFixed(1)}% Accuracy`;
    const expectedPhraseBankF1 = sentimentEvalRaw.finbert.macro_f1.toFixed(2);
    const expectedPhraseBankN = sentimentEvalRaw.n_samples.toString();

    expect(screen.getByTestId('phrasebank-accuracy')).toHaveTextContent(expectedPhraseBankAcc);
    expect(screen.getByTestId('phrasebank-f1')).toHaveTextContent(expectedPhraseBankF1);
    expect(screen.getByTestId('phrasebank-n')).toHaveTextContent(expectedPhraseBankN);

    // 2. Hand-Labeled Production Test Set
    const expectedHandAcc = `${(sentimentHandRaw.accuracy * 100).toFixed(1)}% Accuracy`;
    const expectedHandF1 = sentimentHandRaw.macro_f1.toFixed(2);
    const expectedHandN = sentimentHandRaw.total_evaluated.toString();

    expect(screen.getByTestId('hand-accuracy')).toHaveTextContent(expectedHandAcc);
    expect(screen.getByTestId('hand-f1')).toHaveTextContent(expectedHandF1);
    expect(screen.getByTestId('hand-n')).toHaveTextContent(expectedHandN);

    // Breakdown by source
    const expectedGdelt = `${(sentimentHandRaw.by_source.gdelt.accuracy * 100).toFixed(1)}%`;
    const expectedNewsApi = `${(sentimentHandRaw.by_source.newsapi.accuracy * 100).toFixed(1)}%`;
    const expectedTwitter = `${(sentimentHandRaw.by_source.twitter_kaggle.accuracy * 100).toFixed(1)}%`;
    expect(screen.getByTestId('hand-gdelt-acc')).toHaveTextContent(expectedGdelt);
    expect(screen.getByTestId('hand-newsapi-acc')).toHaveTextContent(expectedNewsApi);
    expect(screen.getByTestId('hand-twitter-acc')).toHaveTextContent(expectedTwitter);

    // Event model
    const expectedEventF1 = eventEvalRaw.macro_f1.toFixed(2);
    const expectedEventN = eventEvalRaw.total_annotated.toString();
    expect(screen.getByTestId('event-macro-f1')).toHaveTextContent(expectedEventF1);
    expect(screen.getByTestId('event-n')).toHaveTextContent(expectedEventN);

    // 3. Quintiles Breakdown & Price Reaction
    const tweetsVal = validationRaw.tweets_2021_2022;
    const expectedQ1 = `${(tweetsVal.quintiles.breakdown.Q1.mean_abs_ar0 * 100).toFixed(2)}%`;
    const expectedQ5 = `${(tweetsVal.quintiles.breakdown.Q5.mean_abs_ar0 * 100).toFixed(2)}%`;
    expect(screen.getByTestId('quintile-q1-abs')).toHaveTextContent(expectedQ1);
    expect(screen.getByTestId('quintile-q5-abs')).toHaveTextContent(expectedQ5);

    // Quintile spread and 95% CI
    const expectedSpread = `+${(tweetsVal.quintiles.q5_q1_spread * 100).toFixed(2)}%`;
    const expectedCi = `+${(tweetsVal.quintiles.ci_95[0] * 100).toFixed(2)}% to +${(tweetsVal.quintiles.ci_95[1] * 100).toFixed(2)}%`;
    expect(screen.getByTestId('quintile-spread')).toHaveTextContent(expectedSpread);
    expect(screen.getByTestId('quintile-ci')).toHaveTextContent(expectedCi);

    // Spearman Rank Correlation & CI & p-value
    const sp = tweetsVal.spearman.impact_vs_abs_ar0;
    const expectedRho = sp.rho.toFixed(3);
    const expectedPval = sp.p_value.toExponential(2);
    const expectedSpCi = `${sp.ci_95[0].toFixed(3)} to ${sp.ci_95[1].toFixed(3)}`;
    expect(screen.getByTestId('spearman-rho')).toHaveTextContent(expectedRho);
    expect(screen.getByTestId('spearman-pval')).toHaveTextContent(expectedPval);
    expect(screen.getByTestId('spearman-ci')).toHaveTextContent(expectedSpCi);

    // 4. Backtest Numbers & Benchmarks
    const expectedStratCum = `${(moduleARaw.summary.strat_5bps.cum_ret * 100).toFixed(2)}%`;
    const expectedEwCum = `${(moduleARaw.summary.ew_5bps.cum_ret * 100).toFixed(2)}%`;
    const expectedSpyCum = `${(moduleARaw.summary.spy.cum_ret * 100).toFixed(2)}%`;
    const expectedTurnover = `${(moduleARaw.summary.avg_daily_turnover * 100).toFixed(2)}%`;
    const expectedPlaceboPct = `${moduleARaw.placebo.sharpe_percentile.toFixed(1)}th`;

    expect(screen.getByTestId('strat-cum-ret')).toHaveTextContent(expectedStratCum);
    expect(screen.getByTestId('ew-cum-ret')).toHaveTextContent(expectedEwCum);
    expect(screen.getByTestId('spy-cum-ret')).toHaveTextContent(expectedSpyCum);
    expect(screen.getByTestId('strat-turnover')).toHaveTextContent(expectedTurnover);
    expect(screen.getByTestId('placebo-percentile')).toHaveTextContent(expectedPlaceboPct);
  });
});
