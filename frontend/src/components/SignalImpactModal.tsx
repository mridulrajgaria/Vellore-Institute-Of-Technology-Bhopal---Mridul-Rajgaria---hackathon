import React, { useEffect, useState } from 'react';
import { SignalImpactResponse, DrivingSignal } from '../types';
import { fetchSignalImpact } from '../api/client';
import { X, Sparkles, HelpCircle, Loader2 } from 'lucide-react';

interface SignalImpactModalProps {
  signal?: DrivingSignal | null;
  onClose: () => void;
}

export const SignalImpactModal: React.FC<SignalImpactModalProps> = ({
  signal,
  onClose,
}) => {
  const [impactDetails, setImpactDetails] = useState<SignalImpactResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!signal) return;
    setLoading(true);
    fetchSignalImpact(signal.text_id)
      .then((res) => setImpactDetails(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [signal]);

  if (!signal) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-surface p-6 shadow-2xl relative">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1.5 text-text-secondary hover:bg-surface-secondary hover:text-text-primary transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2.5 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 border border-accent/20 text-accent">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-base font-bold text-text-primary">
              Signal Explainability & Attribution Decomposition
            </h3>
            <p className="text-xs text-text-secondary">
              Inspect how NLP detection translates into quantitative portfolio weights
            </p>
          </div>
        </div>

        {/* Headline Card */}
        <div className="rounded-lg border border-border bg-surface-secondary p-3.5 mb-5">
          <div className="flex items-center justify-between text-[11px] text-text-secondary mb-1.5">
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-accent">{signal.event_type}</span>
              <span>•</span>
              <span className="font-mono">{signal.source}</span>
            </div>
            <span className="font-mono text-text-secondary/70">ID: {signal.text_id.slice(0, 8)}...</span>
          </div>
          <p className="text-xs text-text-primary font-medium leading-relaxed">
            "{signal.headline}"
          </p>
        </div>

        {/* Explainability Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <div className="rounded-lg border border-border bg-surface p-3">
            <div className="text-[10px] text-text-secondary">FinBERT Score</div>
            <div className="text-base font-mono font-bold mt-1 text-text-primary">
              {signal.sentiment_score > 0 ? '+' : ''}
              {signal.sentiment_score.toFixed(2)}
            </div>
            <div className="text-[10px] text-text-secondary mt-0.5">
              {signal.filtered_by_deadband ? 'Suppressed (noise)' : 'Active signal'}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-surface p-3">
            <div className="text-[10px] text-text-secondary">Asymmetry Prior</div>
            <div className="text-base font-mono font-bold mt-1 text-accent">
              {signal.sentiment_score < 0 ? '1.25x' : '1.00x'}
            </div>
            <div className="text-[10px] text-text-secondary mt-0.5">
              Negative recall prior
            </div>
          </div>

          <div className="rounded-lg border border-border bg-surface p-3">
            <div className="text-[10px] text-text-secondary">Adjusted Sentiment</div>
            <div className="text-base font-mono font-bold mt-1 text-text-primary">
              {signal.adj_sentiment.toFixed(2)}
            </div>
            <div className="text-[10px] text-text-secondary mt-0.5">
              After prior & deadband
            </div>
          </div>

          <div className="rounded-lg border border-border bg-surface p-3">
            <div className="text-[10px] text-text-secondary">Share of Raw Score</div>
            <div className="text-base font-mono font-bold mt-1 text-positive">
              {signal.contribution.toFixed(4)}
            </div>
            <div className="text-[10px] text-text-secondary mt-0.5">
              Rank #{signal.rank} today
            </div>
          </div>
        </div>

        {/* Plain-English Explanation Callout */}
        <div className="rounded-lg border border-accent/20 bg-accent/5 p-4 mb-5">
          <div className="flex items-start gap-2.5">
            <HelpCircle className="h-4 w-4 text-accent mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-xs font-semibold text-accent">
                  Plain-English Rationale
                </h4>
                {loading && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
              </div>
              <p className="text-xs text-text-primary leading-relaxed">
                {impactDetails?.explanation ||
                  (signal.sentiment_score < 0
                    ? 'Negative sentiment is weighted 1.25x because FinBERT was more reliable on negative text in our hand-labeled test (precision 85%).'
                    : signal.filtered_by_deadband
                    ? 'Mild sentiment score lies within deadband [-0.20, +0.20] and was suppressed to 0.0 to eliminate model noise.'
                    : 'Positive sentiment was retained without extra weighting.')}
              </p>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between text-xs text-text-secondary pt-2 border-t border-border">
          <span>Attribution Weight: <span className="font-mono text-text-primary">{signal.attribution_weight.toFixed(2)}</span></span>
          <span>Impact Factor: <span className="font-mono text-text-primary">{signal.impact_score.toFixed(1)}/10</span></span>
          <button
            onClick={onClose}
            className="rounded bg-surface-secondary border border-border px-3 py-1 text-xs text-text-primary hover:bg-border transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
