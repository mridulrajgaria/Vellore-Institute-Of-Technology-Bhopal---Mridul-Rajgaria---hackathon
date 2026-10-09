import React, { useEffect, useState } from 'react';
import { DrivingSignal, SignalImpactResponse } from '../types';
import { fetchSignalImpact } from '../api/client';
import { AlertCircle, ArrowRight } from 'lucide-react';

interface SignalColumnProps {
  signal: DrivingSignal | null;
}

export const SignalColumn: React.FC<SignalColumnProps> = ({ signal }) => {
  const [impactDetail, setImpactDetail] = useState<SignalImpactResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

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
      <div className="flex flex-col h-[520px] px-5 border-r border-border/30">
        <div className="pb-2 mb-2 border-b border-border/30">
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            2. Signal & Arithmetic Chain
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            Model scoring & explainability decomposition
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center text-xs text-text-secondary font-sans italic text-center p-6">
          Select a headline from the stream to inspect the model's classification, impact breakdown, and arithmetic chain.
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

  return (
    <div className="flex flex-col h-[520px] px-5 border-r border-border/30 overflow-y-auto">
      {/* Column Header: Quieter small-caps label in secondary text colour */}
      <div className="flex items-baseline justify-between pb-2 mb-2 border-b border-border/30">
        <div>
          <span className="text-xs font-semibold text-text-secondary tracking-wider uppercase font-sans">
            2. Signal & Arithmetic Chain
          </span>
          <div className="text-[11px] text-text-secondary mt-0.5 font-sans">
            FinBERT sentiment & event attribution decomposition
          </div>
        </div>
        {loading && (
          <span className="text-[10px] font-mono text-accent animate-pulse">
            Loading...
          </span>
        )}
      </div>

      <div className="space-y-3.5 text-xs">
        {/* Headline & Source: Inter font for headline */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            {signal.ticker && (
              <span className="font-mono font-bold text-accent px-1.5 py-0.5 rounded bg-accent/10 border border-accent/20 text-xs">
                {signal.ticker}
              </span>
            )}
            <span className="text-[11px] font-sans text-text-secondary">{signal.source}</span>
          </div>
          <p className="text-xs font-sans text-text-primary leading-relaxed font-medium">
            "{signal.headline}"
          </p>
        </div>

        {/* Model Classification & Confidence (Event vs Sentiment) */}
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/20">
          <div>
            <span className="text-[10px] font-sans text-text-secondary block">Event Classification</span>
            <span className="text-xs font-semibold text-text-primary mt-0.5 block font-sans">
              {signal.event_type}
            </span>
            <span className="text-[10px] font-mono text-text-secondary">
              Confidence: {eventConfPct}%
            </span>
          </div>

          <div>
            <span className="text-[10px] font-sans text-text-secondary block">FinBERT Sentiment</span>
            <span className={`text-xs font-semibold mt-0.5 block font-sans ${isNegative ? 'text-negative' : 'text-positive'}`}>
              {isNegative ? 'Negative' : 'Positive'} ({rawSent > 0 ? '+' : ''}{rawSent.toFixed(2)})
            </span>
            {sentConfPct != null ? (
              <span className="text-[10px] font-mono text-accent">
                Confidence: {sentConfPct}%
              </span>
            ) : (
              <span className="text-[10px] font-mono text-text-secondary/60">
                Score: {rawSent > 0 ? '+' : ''}{rawSent.toFixed(4)}
              </span>
            )}
          </div>
        </div>

        {/* Confidence note when event confidence < 60% */}
        {isLowEventConfidence && (
          <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 leading-snug font-sans flex items-start gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span>
              {sentConfPct != null ? (
                <>
                  Event classification has low confidence (<span className="font-mono">{eventConfPct}%</span>), while FinBERT sentiment confidence is <span className="font-mono">{sentConfPct}%</span>. Event attribution weighting scales down the contribution accordingly.
                </>
              ) : (
                <>
                  Event classification confidence is low (<span className="font-mono">{eventConfPct}%</span>); attribution weighting scales down the signal's contribution accordingly.
                </>
              )}
            </span>
          </div>
        )}

        {/* Impact Score with Component Bar */}
        <div className="pt-2 border-t border-border/20">
          <div className="flex items-center justify-between text-[11px] mb-1">
            <span className="text-text-secondary font-sans">Impact Score</span>
            <span className="text-text-primary font-mono font-bold">{signal.impact_score.toFixed(1)} / 10.0</span>
          </div>
          <div className="w-full h-1.5 bg-surface-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-accent"
              style={{ width: `${(signal.impact_score / 10) * 100}%` }}
            />
          </div>
        </div>

        {/* Arithmetic Chain: Sentiment -> Deadband -> 1.25x Multiplier -> Contribution */}
        <div className="pt-2 border-t border-border/20">
          <span className="text-[10px] uppercase font-sans text-text-secondary font-semibold tracking-wider block mb-2">
            Arithmetic Signal Propagation Chain
          </span>
          <div className="space-y-1.5 font-mono text-[11px]">
            {/* Step 1: Raw Sentiment */}
            <div className="flex items-center justify-between p-1.5 rounded bg-surface-secondary/30">
              <span className="text-text-secondary font-sans text-[11px]">1. FinBERT Sentiment</span>
              <span className={`font-semibold ${rawSent < 0 ? 'text-negative' : 'text-positive'}`}>
                {rawSent > 0 ? '+' : ''}{rawSent.toFixed(4)}
              </span>
            </div>

            {/* Step 2: Deadband Check */}
            <div className="flex items-center justify-between p-1.5 rounded bg-surface-secondary/30">
              <span className="text-text-secondary font-sans text-[11px]">2. Deadband Check (±0.20)</span>
              <span className={deadbandPassed ? 'text-positive font-semibold' : 'text-text-secondary font-semibold'}>
                {deadbandPassed ? 'Passed (|s| ≥ 0.20)' : 'Filtered (|s| < 0.20 → 0.0)'}
              </span>
            </div>

            {/* Step 3: Asymmetry Multiplier */}
            <div className="flex items-center justify-between p-1.5 rounded bg-surface-secondary/30">
              <span className="text-text-secondary font-sans text-[11px]">3. Negative Weighting</span>
              <span className="text-text-primary">
                {isNegative && deadbandPassed ? '1.25x applied' : '1.0x (unscaled)'}
                <span className="text-text-secondary ml-1">→ {adjSent > 0 ? '+' : ''}{adjSent.toFixed(4)}</span>
              </span>
            </div>

            {/* Step 4: Attribution Weight */}
            <div className="flex items-center justify-between p-1.5 rounded bg-surface-secondary/30">
              <span className="text-text-secondary font-sans text-[11px]">4. Weight (Attr × Imp/10)</span>
              <span className="text-text-primary">
                {weightW.toFixed(4)}
              </span>
            </div>

            {/* Step 5: Final Contribution */}
            <div className="flex items-center justify-between p-2 rounded bg-surface-secondary border border-border/50">
              <span className="font-semibold text-text-primary font-sans text-xs flex items-center gap-1">
                <ArrowRight className="h-3 w-3 text-accent" />
                Final Contribution
              </span>
              <span className={`text-xs font-bold ${
                finalContrib > 0 ? 'text-positive' : finalContrib < 0 ? 'text-negative' : 'text-text-secondary'
              }`}>
                {finalContrib > 0 ? '+' : ''}{finalContrib.toFixed(4)}
              </span>
            </div>
          </div>
        </div>

        {/* Plain language explanation from impact route */}
        {impactDetail?.explanation && (
          <div className="pt-2 border-t border-border/20 text-[11px] text-text-secondary font-sans leading-relaxed">
            <span className="font-semibold text-text-primary">Rationale: </span>
            {impactDetail.explanation}
          </div>
        )}
      </div>
    </div>
  );
};
