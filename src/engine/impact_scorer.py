"""Explainable market-impact scoring with component breakdown and trailing volume analysis."""

import logging
from math import exp, log
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

from src.common.config import load_engine_config

logger = logging.getLogger("impact_scorer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def sigmoid(z: float) -> float:
    """Standard sigmoid function bounded between 0 and 1."""
    if z < -20:
        return 0.0
    if z > 20:
        return 1.0
    return 1.0 / (1.0 + exp(-z))


class ImpactScorer:
    """Computes explainable market impact score (1.0 to 10.0) with component attribution."""

    def __init__(self, config_path: str = "config/engine.yaml"):
        self.config = load_engine_config(config_path)
        impact_cfg = self.config.get("impact_scoring", {})

        # Load and validate weights
        weights = impact_cfg.get("weights", {})
        self.w_sev = float(weights.get("w_sev", 0.45))
        self.w_sent = float(weights.get("w_sent", 0.30))
        self.w_src = float(weights.get("w_src", 0.15))
        self.w_vol = float(weights.get("w_vol", 0.10))

        total_weight = self.w_sev + self.w_sent + self.w_src + self.w_vol
        if abs(total_weight - 1.0) > 1e-5:
            raise ValueError(f"Impact weights must sum to 1.0, found sum = {total_weight:.6f}")

        # Severities
        self.severity_map = {
            "Credit Event": 0.90,
            "Geopolitical": 0.85,
            "Macroeconomic": 0.70,
            "Regulatory": 0.65,
            "Merger/Acquisition": 0.60,
            "Earnings": 0.50,
            "Product Launch": 0.35,
            "Other": 0.15,
        }
        self.severity_map.update(impact_cfg.get("severity", {}))

        # Source weights
        self.source_weights = {
            "newsapi": 0.9,
            "gdelt": 0.7,
            "twitter_kaggle": 0.4,
            "unknown": 0.5,
        }
        self.source_weights.update(impact_cfg.get("source_weights", {}))

        # Volume parameters
        vol_params = impact_cfg.get("volume_parameters", {})
        self.tweet_trailing_days = int(vol_params.get("tweet_trailing_days", 30))
        self.min_history_days = int(vol_params.get("min_history_days", 7))
        self.fallback_volume_signal = float(vol_params.get("fallback_volume_signal", 0.5))
        self.news_dup_norm_base = float(vol_params.get("news_dup_norm_base", 10.0))

        # Cache for ticker daily counts if precomputed
        self.daily_counts_by_ticker: Dict[str, pd.Series] = {}

    def fit_tweet_volume_history(self, tweets_df: pd.DataFrame, ticker_col: str = "ticker_hint", ts_col: str = "ts") -> None:
        """Precompute daily tweet counts per ticker for trailing volume z-score calculations."""
        df_valid = tweets_df.dropna(subset=[ts_col]).copy()
        df_valid["date"] = pd.to_datetime(df_valid[ts_col], utc=True).dt.date

        self.daily_counts_by_ticker = {}
        for ticker, grp in df_valid.groupby(ticker_col):
            if not ticker or pd.isna(ticker):
                continue
            counts = grp.groupby("date").size()
            counts.index = pd.to_datetime(counts.index)
            self.daily_counts_by_ticker[str(ticker)] = counts.sort_index()

    def compute_volume_signal(
        self,
        source: str,
        dup_count: int = 1,
        ticker: Optional[str] = None,
        ts: Optional[Union[pd.Timestamp, str]] = None,
    ) -> float:
        """Compute volume signal in [0.0, 1.0].

        - Tweets: trailing-only z-score of ticker daily volume vs prior 30 days (sigmoid squashed).
        - NewsAPI / GDELT: log(1 + dup_count) / log(1 + 10) capped at 1.0.
        """
        src = (source or "").lower()

        if src in ["twitter", "twitter_kaggle"]:
            # NEVER use dup_count for tweets
            if not ticker or ts is None or ticker not in self.daily_counts_by_ticker:
                return self.fallback_volume_signal

            try:
                current_dt = pd.to_datetime(ts, utc=True)
                current_date = current_dt.floor("D").tz_localize(None)
            except Exception:
                return self.fallback_volume_signal

            ticker_series = self.daily_counts_by_ticker.get(ticker)
            if ticker_series is None or len(ticker_series) == 0:
                return self.fallback_volume_signal

            # Strict trailing window: [current_date - 30 days, current_date - 1 day]
            start_date = current_date - pd.Timedelta(days=self.tweet_trailing_days)
            end_date = current_date - pd.Timedelta(days=1)

            trailing_slice = ticker_series.loc[start_date:end_date]
            if len(trailing_slice) < self.min_history_days:
                return self.fallback_volume_signal

            mean_vol = trailing_slice.mean()
            std_vol = trailing_slice.std()

            # Current day count
            current_vol = float(ticker_series.get(current_date, 0.0))

            if std_vol == 0 or np.isnan(std_vol):
                if current_vol > mean_vol:
                    return 1.0
                elif current_vol < mean_vol:
                    return 0.0
                else:
                    return self.fallback_volume_signal

            z_score = (current_vol - mean_vol) / std_vol
            return float(sigmoid(z_score))

        else:
            # News sources: syndication depth via dup_count
            dc = max(1, int(dup_count) if dup_count and not np.isnan(dup_count) else 1)
            norm_factor = log(1.0 + self.news_dup_norm_base)
            norm_val = log(1.0 + dc) / norm_factor
            return float(min(1.0, max(0.0, norm_val)))

    def compute_impact(
        self,
        event_type: str,
        sentiment_score: float,
        source: str,
        dup_count: int = 1,
        ticker: Optional[str] = None,
        ts: Optional[Union[pd.Timestamp, str]] = None,
        volume_signal: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compute impact score and component breakdown."""
        sev_val = float(self.severity_map.get(event_type, self.severity_map["Other"]))
        sent_val = float(abs(sentiment_score))
        src_val = float(self.source_weights.get((source or "").lower(), self.source_weights["unknown"]))

        if volume_signal is None:
            vol_val = self.compute_volume_signal(source, dup_count=dup_count, ticker=ticker, ts=ts)
        else:
            vol_val = float(min(1.0, max(0.0, volume_signal)))

        sev_contrib = self.w_sev * sev_val
        sent_contrib = self.w_sent * sent_val
        src_contrib = self.w_src * src_val
        vol_contrib = self.w_vol * vol_val

        weighted_sum = sev_contrib + sent_contrib + src_contrib + vol_contrib
        raw_score = 1.0 + 9.0 * weighted_sum
        clipped_score = float(min(10.0, max(1.0, raw_score)))

        components = {
            "severity_contrib": round(sev_contrib, 4),
            "sentiment_contrib": round(sent_contrib, 4),
            "source_contrib": round(src_contrib, 4),
            "volume_contrib": round(vol_contrib, 4),
            "raw_severity": round(sev_val, 4),
            "raw_sentiment_abs": round(sent_val, 4),
            "raw_source_weight": round(src_val, 4),
            "raw_volume_signal": round(vol_val, 4),
        }

        return {
            "impact_score": round(clipped_score, 4),
            "impact_components": components,
        }
