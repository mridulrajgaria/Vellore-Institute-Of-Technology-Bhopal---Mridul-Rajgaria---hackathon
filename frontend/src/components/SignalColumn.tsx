import React, { useEffect, useState } from 'react';
import { DrivingSignal, SignalImpactResponse, PositionSnapshot } from '../types';
import { fetchSignalImpact } from '../api/client';
import { AlertCircle, ArrowRight, ChevronDown, ChevronUp, Calculator } from 'lucide-react';

interface SignalColumnProps {
  signal: DrivingSignal | null;
  position?: PositionSnapshot | null;
}

export const SignalColumn: React.FC<SignalColumnProps> = ({ signal, position }) => {
  const [impactDetail, setImpactDetail] = useState<SignalImpactResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [showMath, setShowMath] = useState<boolean>(false);

  useEffect(() => {
    if (!signal?.text_id) {
      setImpactDetail(null);
      return;
    }

    let isCurrent = true;
    setLoading(true);
    fetchSignalImpact(signal.text_id)
      .then((res) => {
        if (isCurrent) {
          setImpactDetail(res);
        }
      })
      .catch((err) => {
        console.error('Failed to load impact decomposition:', err);
      })
      .finally(() => {
        if (isCurrent) setLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [signal?.text_id]);

  if (!signal) {
    return (
      <div id="signal-column" className="flex flex-col p-4 bg-surface-secondary/80 rounded-lg border border-border shadow-xs">
        <div className="flex items-baseline justify-between pb-2.5 mb-2 border-b border-border">
          <div>
            <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
              2 Signal
            </span>
            <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
              What the AI understood
            </div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center text-xs text-text-secondary font-sans italic text-center p-6">
          Select a headline from the stream to inspect the model's classification, plain-English takeaway, and arithmetic chain.
        </div>
        <div className="pt-2 border-t border-border text-[10px] text-text-secondary font-sans leading-snug">
          Filtered by ±0.20 deadband • Asymmetric 1.25x multiplier on negative news.
        </div>
      </div>
    );
  }

  const eventConfPct = Math.round(signal.event_confidence * 100);
  const isLowEventConfidence = signal.event_confidence < 0.60;
  const isDeadband = signal.filtered_by_deadband;
  const isNegative = signal.sentiment_score < 0;

  // Real sentiment confidence from FinBERT model (via API impact route)
  const sentConf = impactDetail?.sentiment_confidence;
  const sentConfPct = sentConf != null ? Math.round(sentConf * 100) : null;

  // Components of arithmetic chain
  const rawSent = signal.sentiment_score;
  const deadbandPassed = !isDeadband;
  const adjSent = signal.adj_sentiment;
  const weightW = signal.weight_w;
  const finalContrib = signal.contribution;
  const sumWeights = signal.sum_weights_for_ticker ?? impactDetail?.sum_weights_for_ticker ?? weightW;

  // Build plain-English summary from real values
  const intensity = Math.abs(rawSent) >= 0.6 ? 'strongly' : 'mildly';
  const sentimentWord = rawSent >= 0 ? 'positive' : 'negative';
  const scoreFormatted = rawSent > 0 ? `+${rawSent.toFixed(2)}` : rawSent.toFixed(2);
  const strengthClause = deadbandPassed
    ? 'It was strong enough to count (the cut-off is ±0.20)'
    : 'It was too weak to count (the cut-off is ±0.20)';

  let weightActionClause = '';
  if (position) {
    const prevPct = (position.prev_weight * 100).toFixed(2);
    const currPct = (position.weight * 100).toFixed(2);
    if (position.weight > position.prev_weight) {
      weightActionClause = `${signal.ticker}'s weight was raised from ${prevPct}% to ${currPct}%`;
    } else if (position.weight < position.prev_weight) {
      weightActionClause = `${signal.ticker}'s weight was lowered from ${prevPct}% to ${currPct}%`;
    } else {
      weightActionClause = `${signal.ticker}'s weight stayed at ${currPct}%`;
    }
  } else {
    weightActionClause = `${signal.ticker}'s weight was updated based on this signal`;
  }

  const plainEnglishSummary = `The AI read this post as ${intensity} ${sentimentWord} (${scoreFormatted}). ${strengthClause}, so ${weightActionClause}.`;

  return (
    <div id="signal-column" className="flex flex-col p-4 bg-surface-secondary/80 rounded-lg border border-border shadow-xs">
      {/* Column Header: 2 Signal + plain caption */}
      <div className="flex items-baseline justify-between pb-2.5 mb-2 border-b border-border">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            2 Signal
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            What the AI understood
          </div>
        </div>
        {loading && (
          <span className="text-[10px] font-mono text-accent animate-pulse font-medium">
            Loading...
          </span>
        )}
      </div>

      <div className="space-y-2.5 flex-1">
        {/* Headline & Source */}
        <div className="p-3 rounded-lg bg-surface border border-border shadow-xs">
          <div className="flex items-center gap-2 mb-1.5">
            {signal.ticker && (
              <span className="font-mono font-bold text-accent px-2 py-0.5 rounded bg-accent-light border border-accent-border text-xs">
                {signal.ticker}
              </span>
            )}
            <span className="text-[11px] font-sans text-text-secondary font-medium">{signal.source}</span>
          </div>
          <p className="text-xs font-sans text-text-primary leading-relaxed font-semibold">
            "{signal.headline}"
          </p>
        </div>

        {/* Plain-English summary card */}
        <div className="p-3 rounded-lg bg-surface border border-border text-xs font-sans text-text-primary leading-relaxed shadow-xs">
          <p className="text-text-primary">
            {plainEnglishSummary}
          </p>
        </div>

        {/* Model Classification & Confidence (Event vs Sentiment) */}
        <div className="grid grid-cols-2 gap-2.5 pt-1">
          <div className="p-2.5 rounded-lg bg-surface border border-border shadow-xs">
            <span className="text-[10px] font-sans text-text-secondary uppercase tracking-wider block font-medium">Event Classification</span>
            <span className="text-xs font-semibold text-text-primary mt-0.5 block font-sans">
              {signal.event_type}
            </span>
            <span className="text-[10px] font-mono text-text-secondary">
              Event Confidence: {eventConfPct}%
            </span>
          </div>

          <div className="p-2.5 rounded-lg bg-surface border border-border shadow-xs">
            <span className="text-[10px] font-sans text-text-secondary uppercase tracking-wider block font-medium">FinBERT Sentiment</span>
            <span className={`text-xs font-semibold mt-0.5 block font-sans ${isNegative ? 'text-negative' : 'text-positive'}`}>
              {isNegative ? 'Negative' : 'Positive'} ({rawSent > 0 ? '+' : ''}{rawSent.toFixed(2)})
            </span>
            {sentConfPct != null ? (
              <span className="text-[10px] font-mono text-accent font-medium">
                Sentiment Confidence: {sentConfPct}%
              </span>
            ) : (
              <span className="text-[10px] font-mono text-text-secondary">
                Score: {rawSent > 0 ? '+' : ''}{rawSent.toFixed(4)}
              </span>
            )}
          </div>
        </div>

        {/* Confidence note when event confidence < 60% */}
        {isLowEventConfidence && (
          <div className="p-2.5 rounded-lg bg-warning-background border border-amber-200 text-[11px] text-warning-text leading-snug font-sans flex items-start gap-2 shadow-xs">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-warning" />
            <span>
              {sentConfPct != null ? (
                <>
                  Event classification has low confidence (<span className="font-mono font-semibold">{eventConfPct}%</span>), while FinBERT sentiment confidence is <span className="font-mono font-semibold">{sentConfPct}%</span>. Event attribution weighting scales down the contribution accordingly.
                </>
              ) : (
                <>
                  Event classification confidence is low (<span className="font-mono font-semibold">{eventConfPct}%</span>); attribution weighting scales down the signal's contribution accordingly.
                </>
              )}
            </span>
          </div>
        )}

        {/* Impact Score with Component Bar */}
        <div className="p-2.5 rounded-lg bg-surface border border-border shadow-xs">
          <div className="flex items-center justify-between text-[11px] mb-1.5">
            <span className="text-text-secondary font-sans font-medium">Impact Score</span>
            <span className="text-text-primary font-mono font-bold text-xs">{signal.impact_score.toFixed(1)} / 10.0</span>
          </div>
          <div className="w-full h-2 bg-bar-track border border-border rounded-full overflow-hidden">
            <div
              className="h-full bg-accent"
              style={{ width: `${(signal.impact_score / 10) * 100}%` }}
            />
          </div>
        </div>

        {/* "Show the math" Toggle (closed by default) */}
        <div>
          <button
            onClick={() => setShowMath(!showMath)}
            className="w-full flex items-center justify-between p-2.5 rounded-lg bg-surface hover:bg-surface-secondary text-xs text-text-secondary hover:text-text-primary transition-colors border border-border font-mono shadow-xs cursor-pointer"
          >
            <div className="flex items-center gap-1.5">
              <Calculator className="h-3.5 w-3.5 text-accent" />
              <span className="font-medium text-text-primary">Show the math</span>
              <span className="text-[10px] text-text-muted">(5-step propagation chain)</span>
            </div>
            {showMath ? <ChevronUp className="h-3.5 w-3.5 text-accent" /> : <ChevronDown className="h-3.5 w-3.5 text-accent" />}
          </button>

          {showMath && (
            <div className="space-y-1.5 font-mono text-[11px] mt-2 pt-2 border-t border-border">
              {/* Step 1: Raw Sentiment */}
              <div className="flex items-center justify-between p-2 rounded bg-surface border border-border">
                <span className="text-text-secondary font-sans text-[11px]">1. FinBERT Sentiment</span>
                <span className={`font-semibold ${rawSent < 0 ? 'text-negative' : 'text-positive'}`}>
                  {rawSent > 0 ? '+' : ''}{rawSent.toFixed(4)}
                </span>
              </div>

              {/* Step 2: Deadband Check */}
              <div className="flex items-center justify-between p-2 rounded bg-surface border border-border">
                <span className="text-text-secondary font-sans text-[11px]">2. Deadband Check (±0.20)</span>
                <span className={deadbandPassed ? 'text-positive font-semibold' : 'text-text-secondary font-semibold'}>
                  {deadbandPassed ? 'Passed (|s| ≥ 0.20)' : 'Filtered (|s| < 0.20 → 0.0)'}
                </span>
              </div>

              {/* Step 3: Asymmetry Multiplier */}
              <div className="flex items-center justify-between p-2 rounded bg-surface border border-border">
                <span className="text-text-secondary font-sans text-[11px]">3. Negative Weighting</span>
                <span className="text-text-primary font-medium">
                  {isNegative && deadbandPassed ? '1.25x applied' : '1.0x (unscaled)'}
                  <span className="text-text-secondary ml-1">→ {adjSent > 0 ? '+' : ''}{adjSent.toFixed(4)}</span>
                </span>
              </div>

              {/* Step 4: Attribution Weight */}
              <div className="flex items-center justify-between p-2 rounded bg-surface border border-border">
                <span className="text-text-secondary font-sans text-[11px]">4. Weight (Attr × Imp/10)</span>
                <span className="text-text-primary font-semibold">
                  {weightW.toFixed(4)}
                </span>
              </div>

              {/* Step 5: Share of day's signal weight for this ticker */}
              <div className="p-2.5 rounded bg-surface border border-border space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-text-secondary font-sans text-[11px] leading-tight font-medium">
                    5. Share of the day's signal weight for this ticker:
                  </span>
                  <span className="font-mono text-text-primary text-[11px] font-bold">
                    {sumWeights > 0 ? `${((weightW / sumWeights) * 100).toFixed(1)}%` : '0.0%'}
                  </span>
                </div>
                <div className="text-[10px] text-text-secondary font-sans leading-tight">
                  contribution = adj_sentiment × weight / sum of weights for {signal.ticker || 'TICKER'} that day
                </div>
                <div className="flex items-center justify-between text-[11px] pt-1 border-t border-border font-mono text-text-secondary">
                  <span>
                    ({adjSent > 0 ? '+' : ''}{adjSent.toFixed(4)} × {weightW.toFixed(4)}) / <strong className="text-text-primary font-mono">{sumWeights.toFixed(4)}</strong>
                  </span>
                  <span className="text-text-primary font-bold">
                    = {sumWeights > 0 ? ((adjSent * weightW) / sumWeights).toFixed(4) : '0.0000'}
                  </span>
                </div>
              </div>

              {/* Final Contribution */}
              <div className="flex items-center justify-between p-2.5 rounded bg-accent-light border border-accent-border shadow-xs">
                <span className="font-semibold text-text-primary font-sans text-xs flex items-center gap-1">
                  <ArrowRight className="h-3.5 w-3.5 text-accent" />
                  Final Contribution
                </span>
                <span className={`text-xs font-bold ${
                  finalContrib > 0 ? 'text-positive' : finalContrib < 0 ? 'text-negative' : 'text-text-secondary'
                }`}>
                  {finalContrib > 0 ? '+' : ''}{finalContrib.toFixed(4)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Plain language explanation from impact route */}
        {impactDetail?.explanation && (
          <div className="p-2.5 rounded-lg bg-surface border border-border text-[11px] text-text-secondary font-sans leading-relaxed shadow-xs">
            <span className="font-semibold text-text-primary">Rationale: </span>
            {impactDetail.explanation}
          </div>
        )}
      </div>

      {/* Aligned column footer note */}
      <div className="pt-2 border-t border-border text-[10px] text-text-secondary font-sans leading-snug">
        Filtered by ±0.20 deadband • Asymmetric 1.25x multiplier on negative conviction.
      </div>
    </div>
  );
};
