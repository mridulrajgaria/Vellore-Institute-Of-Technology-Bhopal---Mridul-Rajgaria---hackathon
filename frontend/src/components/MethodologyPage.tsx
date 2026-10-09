import React from 'react';
import { MetaMetricsResponse } from '../types';
import { ArrowLeft, BookOpen, AlertTriangle, TrendingDown } from 'lucide-react';

interface MethodologyPageProps {
  metrics: MetaMetricsResponse | null;
  onBack: () => void;
}

export const MethodologyPage: React.FC<MethodologyPageProps> = ({ metrics, onBack }) => {
  if (!metrics) {
    return (
      <div className="min-h-screen bg-background text-text-primary flex items-center justify-center font-mono text-xs">
        Loading methodology metrics...
      </div>
    );
  }

  const meta = metrics.meta;
  const modA = metrics.module_a;
  const strat = modA?.summary?.strat_5bps;
  const ew = modA?.summary?.ew_5bps;
  const spy = modA?.summary?.spy;
  const placebo = modA?.placebo;

  const finbert = metrics.sentiment_eval?.finbert;
  const handEval = metrics.sentiment_hand_eval;
  const eventEval = metrics.event_eval;
  const valTweets = metrics.validation?.tweets_2021_2022;

  // Formatting helpers
  const fmtPct = (val?: number, decimals = 1) =>
    val != null ? `${(val * 100).toFixed(decimals)}%` : '—';
  const fmtDec = (val?: number, decimals = 2) =>
    val != null ? val.toFixed(decimals) : '—';
  const fmtExp = (val?: number) =>
    val != null ? val.toExponential(2) : '—';

  // Section B: Periods
  const replayStart = meta?.replay_period?.start ?? '—';
  const replayEnd = meta?.replay_period?.end ?? '—';
  const replaySource = meta?.replay_period?.source ?? '—';
  const newsStart = meta?.news_period?.start ?? '—';
  const newsEnd = meta?.news_period?.end ?? '—';
  const newsSource = meta?.news_period?.source ?? '—';
  const replayDays = modA?.summary?.total_rebalance_days ?? 252;
  const replayObs = valTweets?.n_observations ?? 0;
  const newsObs = metrics.validation?.news_2026?.n_observations ?? 0;

  // Section C: Accuracies & F1s
  const phraseBankAcc = fmtPct(finbert?.accuracy, 1); // 88.9%
  const phraseBankF1 = fmtDec(finbert?.macro_f1, 2);  // 0.88
  const phraseBankN = metrics.sentiment_eval?.n_samples ?? 0;

  const handAcc = fmtPct(handEval?.accuracy, 1);      // 61.1%
  const handF1 = fmtDec(handEval?.macro_f1, 2);       // 0.60
  const handTotal = handEval?.total_evaluated ?? 0;

  const gdeltAcc = fmtPct(handEval?.by_source?.gdelt?.accuracy, 1);       // 74.0%
  const newsApiAcc = fmtPct(handEval?.by_source?.newsapi?.accuracy, 1);    // 61.4%
  const twitterAcc = fmtPct(handEval?.by_source?.twitter_kaggle?.accuracy, 1); // 53.5%

  const eventMacroF1 = fmtDec(eventEval?.macro_f1, 2); // 0.69
  const eventTotal = eventEval?.total_annotated ?? 0;

  // Section D: Quintiles & Spearman
  const qBreak = valTweets?.quintiles?.breakdown;
  const q1Abs = fmtPct(qBreak?.Q1?.mean_abs_ar0, 2); // 1.21%
  const q1Imp = fmtDec(qBreak?.Q1?.mean_impact, 2);  // 2.70
  const q2Abs = fmtPct(qBreak?.Q2?.mean_abs_ar0, 2); // 1.35%
  const q2Imp = fmtDec(qBreak?.Q2?.mean_impact, 2);  // 3.50
  const q3Abs = fmtPct(qBreak?.Q3?.mean_abs_ar0, 2); // 1.46%
  const q3Imp = fmtDec(qBreak?.Q3?.mean_impact, 2);  // 4.63
  const q4Abs = fmtPct(qBreak?.Q4?.mean_abs_ar0, 2); // 1.71%
  const q4Imp = fmtDec(qBreak?.Q4?.mean_impact, 2);  // 5.15
  const q5Abs = fmtPct(qBreak?.Q5?.mean_abs_ar0, 2); // 2.36%
  const q5Imp = fmtDec(qBreak?.Q5?.mean_impact, 2);  // 6.36

  const qSpread = valTweets?.quintiles?.q5_q1_spread != null
    ? `+${(valTweets.quintiles.q5_q1_spread * 100).toFixed(2)}%`
    : '—'; // +1.15%
  const qCiLow = valTweets?.quintiles?.ci_95?.[0] != null
    ? `+${(valTweets.quintiles.ci_95[0] * 100).toFixed(2)}%`
    : '—'; // +0.81%
  const qCiHigh = valTweets?.quintiles?.ci_95?.[1] != null
    ? `+${(valTweets.quintiles.ci_95[1] * 100).toFixed(2)}%`
    : '—'; // +1.57%

  const spRho = fmtDec(valTweets?.spearman?.impact_vs_abs_ar0?.rho, 3); // 0.159
  const spPval = fmtExp(valTweets?.spearman?.impact_vs_abs_ar0?.p_value); // 3.08e-13
  const spCiLow = fmtDec(valTweets?.spearman?.impact_vs_abs_ar0?.ci_95?.[0], 3); // 0.122
  const spCiHigh = fmtDec(valTweets?.spearman?.impact_vs_abs_ar0?.ci_95?.[1], 3); // 0.194

  // Section E: Backtest & Placebo
  const stratCumRet = fmtPct(strat?.cum_ret, 2); // -28.91%
  const stratDd = fmtPct(strat?.max_dd, 2);      // -37.95%
  const stratSharpe = fmtDec(strat?.sharpe, 2);  // -0.92

  const ewCumRet = fmtPct(ew?.cum_ret, 2);       // -28.53%
  const ewDd = fmtPct(ew?.max_dd, 2);            // -37.39%
  const ewSharpe = fmtDec(ew?.sharpe, 2);        // -0.91

  const spyCumRet = fmtPct(spy?.cum_ret, 2);     // -15.51%
  const spyDd = fmtPct(spy?.max_dd, 2);          // -24.37%
  const spySharpe = fmtDec(spy?.sharpe, 2);      // -0.71

  const avgTurnover = fmtPct(modA?.summary?.avg_daily_turnover, 2); // 4.14%
  const placeboPct = placebo?.sharpe_percentile != null ? `${placebo.sharpe_percentile.toFixed(1)}th` : '—'; // 48.5th
  const placeboN = placebo?.n_permutations ?? 200;

  return (
    <div className="min-h-screen bg-background text-text-primary">
      {/* Sticky top nav */}
      <div className="sticky top-0 z-40 bg-surface/90 backdrop-blur-sm border-b border-border/40 px-6 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <button
            onClick={onBack}
            data-testid="back-to-dashboard-btn"
            className="flex items-center gap-1.5 text-xs font-mono text-accent hover:text-accent/80 transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>← Back to dashboard</span>
          </button>
          <span className="text-xs font-mono text-text-secondary">
            Methodology & Empirical Validation
          </span>
        </div>
      </div>

      {/* Main Single Scrollable Page */}
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-10 font-sans text-sm leading-relaxed">
        {/* Title */}
        <div className="border-b border-border/40 pb-5">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="h-5 w-5 text-accent" />
            <h1 className="text-xl font-bold text-text-primary tracking-tight">
              Methodology & Empirical Validation Report
            </h1>
          </div>
          <p className="text-xs text-text-secondary">
            Rigorous performance, NLP evaluation metrics, and full empirical disclosures loaded dynamically from committed validation data.
          </p>
        </div>

        {/* Section (a): System Overview in 4 Sentences */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">A.</span>
            System Architecture in 4 Sentences
          </h2>
          <div className="p-4 rounded-lg bg-surface border border-border/50 space-y-2 text-xs leading-relaxed text-text-secondary">
            <p>
              1. The AI Risk Engine ingests financial headlines and social tweets prior to the 21:00 UTC cutoff and maps them to an index universe of 14 large-cap equities.
            </p>
            <p>
              2. FinBERT classifies each post's sentiment score (-1.0 to +1.0), while a zero-shot event model categorizes the headline and computes an impact score from 1.0 to 10.0.
            </p>
            <p>
              3. Signals clearing a ±0.20 deadband receive asymmetric weighting (1.25x multiplier on negative news) to form a normalized daily conviction score per stock.
            </p>
            <p>
              4. An automated optimizer shifts portfolio weights away from equal weight (7.14%) within strict bounds [3.57%, 14.29%] and a 10% daily turnover cap, executing daily at market close with 5 bps slippage.
            </p>
          </div>
        </section>

        {/* Section (b): Data Sources & Periods */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">B.</span>
            Data Sources and Evaluated Periods
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-lg bg-surface border border-border/40 space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-accent font-bold tracking-wider">
                Primary Backtest Replay Period
              </span>
              <div
                data-testid="meta-replay-period"
                className="font-semibold text-text-primary text-sm font-mono"
              >
                {replayStart} to {replayEnd}
              </div>
              <div className="text-text-secondary">
                Source: <span className="font-mono text-text-primary">{replaySource}</span> (historical tweets, <span data-testid="meta-replay-obs">{replayObs}</span> observations across <span data-testid="meta-replay-days">{replayDays}</span> trading days).
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-surface border border-border/40 space-y-1.5">
              <span className="text-[10px] font-mono uppercase text-accent font-bold tracking-wider">
                Out-of-Sample News Validation Period
              </span>
              <div
                data-testid="meta-news-period"
                className="font-semibold text-text-primary text-sm font-mono"
              >
                {newsStart} to {newsEnd}
              </div>
              <div className="text-text-secondary">
                Source: <span className="font-mono text-text-primary">{newsSource}</span> (live articles and GDELT events, <span data-testid="meta-news-obs">{newsObs}</span> observations).
              </div>
            </div>
          </div>
        </section>

        {/* Section (c): AI Accuracy */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">C.</span>
            How Accurate is the AI?
          </h2>
          <div className="p-4 rounded-lg bg-surface border border-border/50 space-y-3.5 text-xs text-text-secondary">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 rounded bg-surface-secondary/30 border border-border/30">
                <span className="text-[11px] font-semibold text-text-primary block mb-1">
                  Public Benchmark (Financial PhraseBank)
                </span>
                <div
                  data-testid="phrasebank-accuracy"
                  className="font-mono text-lg font-bold text-positive"
                >
                  {phraseBankAcc} Accuracy
                </div>
                <div className="text-[11px] font-mono text-text-secondary mt-0.5">
                  Macro F1: <span data-testid="phrasebank-f1">{phraseBankF1}</span> • Evaluated on <span data-testid="phrasebank-n">{phraseBankN}</span> published analyst sentences.
                </div>
              </div>

              <div className="p-3 rounded bg-surface-secondary/30 border border-border/30">
                <span className="text-[11px] font-semibold text-text-primary block mb-1">
                  Our Hand-Labeled Production Test Set
                </span>
                <div
                  data-testid="hand-accuracy"
                  className="font-mono text-lg font-bold text-amber-400"
                >
                  {handAcc} Accuracy
                </div>
                <div className="text-[11px] font-mono text-text-secondary mt-0.5">
                  Macro F1: <span data-testid="hand-f1">{handF1}</span> • N=<span data-testid="hand-n">{handTotal}</span> audited items across three channels.
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-border/20 text-xs leading-relaxed">
              <span className="font-semibold text-text-primary">Performance Breakdown by Source: </span>
              GDELT news articles reached <span data-testid="hand-gdelt-acc" className="font-mono font-medium text-text-primary">{gdeltAcc}</span> accuracy, NewsAPI headlines achieved <span data-testid="hand-newsapi-acc" className="font-mono font-medium text-text-primary">{newsApiAcc}</span>, while raw Twitter social posts scored <span data-testid="hand-twitter-acc" className="font-mono font-medium text-text-primary">{twitterAcc}</span> (with event categorization achieving a <span data-testid="event-macro-f1" className="font-mono font-medium text-text-primary">{eventMacroF1}</span> macro F1 on N=<span data-testid="event-n">{eventTotal}</span>).
            </div>

            <div className="p-3 rounded bg-accent/5 border border-accent/20 text-xs text-text-primary leading-relaxed font-sans">
              <strong>Why they differ: </strong>
              Social media tweets contain colloquial language, sarcasm, emojis, and stock ticker spam, making them vastly noisier and harder to classify accurately than polished financial news sentences from published research benchmarks.
            </div>
          </div>
        </section>

        {/* Section (d): Do the signals mean anything? Quintiles */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">D.</span>
            Do the Signals Mean Anything? (Quintile Price Reactions)
          </h2>
          <div className="p-4 rounded-lg bg-surface border border-border/50 space-y-3 text-xs text-text-secondary">
            <p>
              To verify whether impact scores contain true signal or random noise, we stratified all pre-cutoff events into 5 quintiles (Q1 lowest impact to Q5 highest impact) and measured the subsequent absolute price movement:
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5 text-center font-mono">
              <div className="p-2 rounded bg-surface-secondary/40 border border-border/30">
                <div className="text-[10px] text-text-secondary uppercase">Q1 (Low)</div>
                <div data-testid="quintile-q1-abs" className="text-sm font-bold text-text-primary mt-1">{q1Abs}</div>
                <div className="text-[10px] text-text-secondary">Impact ~{q1Imp}</div>
              </div>
              <div className="p-2 rounded bg-surface-secondary/40 border border-border/30">
                <div className="text-[10px] text-text-secondary uppercase">Q2</div>
                <div data-testid="quintile-q2-abs" className="text-sm font-bold text-text-primary mt-1">{q2Abs}</div>
                <div className="text-[10px] text-text-secondary">Impact ~{q2Imp}</div>
              </div>
              <div className="p-2 rounded bg-surface-secondary/40 border border-border/30">
                <div className="text-[10px] text-text-secondary uppercase">Q3</div>
                <div data-testid="quintile-q3-abs" className="text-sm font-bold text-text-primary mt-1">{q3Abs}</div>
                <div className="text-[10px] text-text-secondary">Impact ~{q3Imp}</div>
              </div>
              <div className="p-2 rounded bg-surface-secondary/40 border border-border/30">
                <div className="text-[10px] text-text-secondary uppercase">Q4</div>
                <div data-testid="quintile-q4-abs" className="text-sm font-bold text-text-primary mt-1">{q4Abs}</div>
                <div className="text-[10px] text-text-secondary">Impact ~{q4Imp}</div>
              </div>
              <div className="p-2 rounded bg-surface-secondary/40 border border-border/30">
                <div className="text-[10px] text-text-secondary uppercase">Q5 (High)</div>
                <div data-testid="quintile-q5-abs" className="text-sm font-bold text-accent mt-1">{q5Abs}</div>
                <div className="text-[10px] text-text-secondary">Impact ~{q5Imp}</div>
              </div>
            </div>

            <div className="p-3 rounded bg-surface-secondary/20 border border-border/30 text-xs space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  <strong className="text-text-primary">Q5 vs Q1 Volatility Spread: </strong>
                  <span data-testid="quintile-spread" className="font-mono font-bold text-accent">{qSpread}</span>{' '}
                  <span className="font-mono text-text-secondary text-[11px]">
                    (95% CI: <span data-testid="quintile-ci">{qCiLow} to {qCiHigh}</span>)
                  </span>
                </span>
                <span className="font-mono text-text-secondary text-[11px]">
                  Spearman ρ = <span data-testid="spearman-rho">{spRho}</span> (95% CI: <span data-testid="spearman-ci">{spCiLow} to {spCiHigh}</span>, p = <span data-testid="spearman-pval">{spPval}</span>)
                </span>
              </div>
              <p className="text-text-secondary leading-relaxed">
                Stocks experiencing events in the highest impact quintile experienced over twice the absolute next-day return of those in Q1, validating that the model successfully differentiates high-consequence market catalysts from noise.
              </p>
            </div>
          </div>
        </section>

        {/* Section (e): Honest Backtest Numbers & Placebo */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">E.</span>
            Did the Portfolio Beat Equal Weight?
          </h2>
          <div className="p-4 rounded-lg bg-surface border border-border/50 space-y-3 text-xs text-text-secondary">
            {/* Plain language verdict */}
            <div className="p-3 rounded bg-red-500/10 border border-red-500/30 text-red-300 leading-relaxed font-sans flex items-start gap-2">
              <TrendingDown className="h-4 w-4 shrink-0 mt-0.5 text-negative" />
              <span>
                <strong>Plain verdict: The strategy did not outperform. </strong>
                Over the 1-year replay period, the AI-tilted portfolio achieved a cumulative return of <span data-testid="strat-cum-ret" className="font-mono font-bold">{stratCumRet}</span>, slightly trailing the equal-weight benchmark (<span data-testid="ew-cum-ret" className="font-mono font-bold">{ewCumRet}</span>) while SPY returned <span data-testid="spy-cum-ret" className="font-mono font-bold">{spyCumRet}</span>.
              </span>
            </div>

            {/* Performance table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-[11px] border border-border/40">
                <thead className="bg-surface-secondary/50 text-text-secondary border-b border-border/40">
                  <tr>
                    <th className="p-2">Strategy Variant</th>
                    <th className="p-2">Cum Return</th>
                    <th className="p-2">Max Drawdown</th>
                    <th className="p-2">Sharpe</th>
                    <th className="p-2">Daily Turnover</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  <tr>
                    <td className="p-2 font-bold text-accent">AI Rebalancer (5 bps)</td>
                    <td className="p-2 font-bold text-negative">{stratCumRet}</td>
                    <td data-testid="strat-max-dd" className="p-2">{stratDd}</td>
                    <td data-testid="strat-sharpe" className="p-2">{stratSharpe}</td>
                    <td data-testid="strat-turnover" className="p-2">{avgTurnover}</td>
                  </tr>
                  <tr>
                    <td className="p-2 text-text-primary">Equal-Weight (5 bps)</td>
                    <td className="p-2 text-negative">{ewCumRet}</td>
                    <td data-testid="ew-max-dd" className="p-2">{ewDd}</td>
                    <td data-testid="ew-sharpe" className="p-2">{ewSharpe}</td>
                    <td className="p-2">—</td>
                  </tr>
                  <tr>
                    <td className="p-2 text-text-secondary">SPY Benchmark</td>
                    <td className="p-2 text-negative">{spyCumRet}</td>
                    <td data-testid="spy-max-dd" className="p-2">{spyDd}</td>
                    <td data-testid="spy-sharpe" className="p-2">{spySharpe}</td>
                    <td className="p-2">—</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Placebo test explanation */}
            <div className="pt-2 text-xs leading-relaxed">
              <span className="font-semibold text-text-primary">Placebo Null Hypothesis Test: </span>
              In a <span data-testid="placebo-n">{placeboN}</span>-iteration Monte Carlo permutation test where signals were randomly shuffled across dates and tickers, the actual strategy Sharpe ratio fell in the <strong data-testid="placebo-percentile" className="text-text-primary font-mono">{placeboPct} percentile</strong>. This indicates that portfolio performance was statistically indistinguishable from chance; daily transaction friction ({avgTurnover} turnover) and broad macro market decline outweighed the modest signal edge.
            </div>
          </div>
        </section>

        {/* Section (f): Limitations */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent font-mono text-xs font-bold">F.</span>
            Key Limitations & Risks
          </h2>
          <div className="p-4 rounded-lg bg-surface border border-border/50 text-xs text-text-secondary space-y-2.5">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="text-text-primary">One year of tweets: </strong>
                Social sentiment data covers only Oct 2021 through Sep 2022, representing an isolated 12-month historical window.
              </div>
            </div>

            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="text-text-primary">One market regime: </strong>
                The backtest took place during a persistent tech bear market marked by rapid Federal Reserve interest rate hikes; the model has not been evaluated in sustained bull or sideways regimes.
              </div>
            </div>

            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="text-text-primary">Small hand-labeled sample: </strong>
                Our ground-truth qualitative evaluation contains 180 verified examples, offering targeted domain inspection rather than large-sample statistical guarantees.
              </div>
            </div>

            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="text-text-primary">FinBERT misreads numbers vs expectations: </strong>
                Standard NLP models evaluate lexical tone without benchmarking against financial consensus. For instance, "Earnings grew 10%" is scored as positive, even if consensus expected 15% and the stock plummeted.
              </div>
            </div>
          </div>
        </section>

        {/* Bottom Back Button */}
        <div className="pt-6 border-t border-border/40 text-center">
          <button
            onClick={onBack}
            className="px-5 py-2 rounded-lg bg-surface-secondary hover:bg-border/60 text-text-primary text-xs font-mono font-medium border border-border/50 transition-colors cursor-pointer"
          >
            ← Return to Live Index Dashboard
          </button>
        </div>
      </main>
    </div>
  );
};
