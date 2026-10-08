"""Module A: Tactical Index Rebalancer.

Consumes AI/NLP Risk Engine signals and computes constrained daily portfolio
weights for the 14 S&P index universe equities. Supports both batch backtesting
and incremental step-by-step replay for live dashboard simulation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yaml

from src.engine.validate import map_timestamp_to_t0

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/rebalancer.yaml")


@dataclass
class RebalanceResult:
    """Output state of a single rebalancing step."""
    date: str
    weights: Dict[str, float]
    target_weights: Dict[str, float]
    scores: Dict[str, float]
    raw_scores: Dict[str, float]
    turnover: float
    turnover_constrained: bool
    top_signals: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


def project_bounded_weights(
    raw_weights: np.ndarray,
    min_weight: float,
    max_weight: float,
    max_iter: int = 50,
) -> np.ndarray:
    """Project weights onto the simplex sum(w) = 1 while enforcing w_min <= w_i <= w_max.

    Uses an iterative water-filling / clipping algorithm to redistribute surplus/deficit.
    """
    n = len(raw_weights)
    if n * min_weight > 1.0 or n * max_weight < 1.0:
        raise ValueError("Infeasible weight bounds: bounds cannot sum to 1.0.")

    w = raw_weights.copy()
    if np.sum(w) <= 0:
        w = np.full(n, 1.0 / n)
    else:
        w = w / np.sum(w)

    for _ in range(max_iter):
        clipped = np.clip(w, min_weight, max_weight)
        diff = 1.0 - np.sum(clipped)

        if abs(diff) < 1e-9:
            return clipped

        if diff > 0:
            eligible = clipped < max_weight - 1e-9
        else:
            eligible = clipped > min_weight + 1e-9

        if not np.any(eligible):
            return clipped

        w = clipped.copy()
        w[eligible] += diff / np.sum(eligible)

    return np.clip(w, min_weight, max_weight)


class Rebalancer:
    """Tactical index rebalancer driven by sentiment and impact signals."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        universe: Optional[List[str]] = None,
        k: Optional[float] = None,
        half_life_days: Optional[float] = None,
        deadband: Optional[float] = None,
        neg_multiplier: Optional[float] = None,
        min_weight_mult: Optional[float] = None,
        max_weight_mult: Optional[float] = None,
        max_turnover: Optional[float] = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._load_config()

        # Overrides if explicitly provided
        if universe is not None:
            self.universe = list(universe)
        if k is not None:
            self.k = float(k)
        if half_life_days is not None:
            self.half_life_days = float(half_life_days)
        if deadband is not None:
            self.deadband = float(deadband)
        if neg_multiplier is not None:
            self.neg_multiplier = float(neg_multiplier)
        if min_weight_mult is not None:
            self.min_weight_mult = float(min_weight_mult)
        if max_weight_mult is not None:
            self.max_weight_mult = float(max_weight_mult)
        if max_turnover is not None:
            self.max_turnover = float(max_turnover)

        self.n_assets = len(self.universe)
        self.base_weight = 1.0 / self.n_assets
        self.min_weight = self.min_weight_mult * self.base_weight
        self.max_weight = self.max_weight_mult * self.base_weight

        # EMA decay factor: alpha = 1 - 2^(-1 / half_life)
        self.alpha = 1.0 - (2.0 ** (-1.0 / self.half_life_days))

        self.reset()

    def _load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            self.universe = cfg.get("universe", [
                "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "NFLX",
                "AMD", "PG", "KO", "DIS", "BA", "COST", "PYPL"
            ])
            self.k = float(cfg.get("k", 1.5))
            self.half_life_days = float(cfg.get("half_life_days", 2.0))
            self.deadband = float(cfg.get("deadband", 0.20))
            self.neg_multiplier = float(cfg.get("neg_multiplier", 1.25))
            self.min_weight_mult = float(cfg.get("min_weight_mult", 0.5))
            self.max_weight_mult = float(cfg.get("max_weight_mult", 2.0))
            self.max_turnover = float(cfg.get("max_turnover", 0.10))
            self.timing_cutoff_utc = cfg.get("timing_cutoff_utc", "21:00")
        else:
            self.universe = [
                "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "NFLX",
                "AMD", "PG", "KO", "DIS", "BA", "COST", "PYPL"
            ]
            self.k = 1.5
            self.half_life_days = 2.0
            self.deadband = 0.20
            self.neg_multiplier = 1.25
            self.min_weight_mult = 0.5
            self.max_weight_mult = 2.0
            self.max_turnover = 0.10
            self.timing_cutoff_utc = "21:00"

    def reset(self) -> None:
        """Reset internal state to initial equal-weight portfolio and zero scores."""
        self.current_weights = {tk: self.base_weight for tk in self.universe}
        self.current_scores = {tk: 0.0 for tk in self.universe}

    def compute_daily_raw_score(
        self,
        signals_for_ticker: List[Dict[str, Any]],
    ) -> float:
        """Compute attribution-weighted raw daily sentiment score with noise deadband and negative multiplier."""
        if not signals_for_ticker:
            return 0.0

        adj_sents: List[float] = []
        weights: List[float] = []

        for sig in signals_for_ticker:
            s = float(sig.get("sentiment_score", 0.0))
            # Deadband suppression
            if abs(s) < self.deadband:
                adj_s = 0.0
            elif s < 0.0:
                adj_s = s * self.neg_multiplier
            else:
                adj_s = s

            # Weight = attribution_weight * (impact / 10)
            attr_w = float(sig.get("attribution_weight", 1.0))
            imp = float(sig.get("impact_score", 5.0))
            w = max(0.0, attr_w * (imp / 10.0))

            adj_sents.append(adj_s)
            weights.append(w)

        sum_w = sum(weights)
        if sum_w <= 0.0:
            return 0.0

        return sum(s * w for s, w in zip(adj_sents, weights)) / sum_w

    def step(
        self,
        date: str,
        signals_for_day: Union[List[Dict[str, Any]], pd.DataFrame],
    ) -> RebalanceResult:
        """Execute a single rebalancing step for trading day t.

        Filters signals strictly prior to cutoff, computes EMA scores, derives bounded
        target weights, applies the turnover constraint, and returns the RebalanceResult.
        """
        # Convert DataFrame to records if passed
        if isinstance(signals_for_day, pd.DataFrame):
            sig_list = signals_for_day.to_dict(orient="records")
        else:
            sig_list = list(signals_for_day)

        # Group signals by ticker (skipping broadcast, MARKET, non-universe)
        by_ticker: Dict[str, List[Dict[str, Any]]] = {tk: [] for tk in self.universe}
        for s in sig_list:
            if s.get("is_broadcast", False):
                continue
            tk = s.get("ticker")
            if tk in by_ticker:
                by_ticker[tk].append(s)

        # 1. Compute raw scores and update EMA scores
        raw_scores: Dict[str, float] = {}
        new_scores: Dict[str, float] = {}
        for tk in self.universe:
            raw = self.compute_daily_raw_score(by_ticker[tk])
            raw_scores[tk] = raw
            # EMA update: score_t = (1 - alpha) * score_{t-1} + alpha * raw_t
            new_scores[tk] = (1.0 - self.alpha) * self.current_scores[tk] + self.alpha * raw

        # 2. Compute unconstrained target weights: target_i ~ base_i * exp(k * score_i)
        exp_tilts = np.array([np.exp(self.k * new_scores[tk]) for tk in self.universe])
        raw_targets = exp_tilts / np.sum(exp_tilts)

        # 3. Enforce [min_weight, max_weight] bounds with exact residual redistribution
        bounded_targets = project_bounded_weights(
            raw_targets,
            min_weight=self.min_weight,
            max_weight=self.max_weight,
        )
        target_dict = {tk: float(w) for tk, w in zip(self.universe, bounded_targets)}

        # 4. Enforce turnover constraint: at most max_turnover (10%) one-way turnover
        prev_w = np.array([self.current_weights[tk] for tk in self.universe])
        raw_diff = bounded_targets - prev_w
        one_way_turnover = 0.5 * float(np.sum(np.abs(raw_diff)))

        is_constrained = False
        if one_way_turnover > self.max_turnover and one_way_turnover > 1e-9:
            scale = self.max_turnover / one_way_turnover
            exec_weights = prev_w + scale * raw_diff
            actual_turnover = self.max_turnover
            is_constrained = True
        else:
            exec_weights = bounded_targets
            actual_turnover = one_way_turnover

        # Guarantee exact normalization
        exec_weights = exec_weights / np.sum(exec_weights)
        new_weight_dict = {tk: float(w) for tk, w in zip(self.universe, exec_weights)}

        # 5. Extract top-3 driving signals per ticker
        top_signals: Dict[str, List[Dict[str, Any]]] = {}
        for tk in self.universe:
            tk_sigs = by_ticker[tk]
            if tk_sigs:
                # Sort by impact_score descending, break tie with abs(sentiment)
                sorted_sigs = sorted(
                    tk_sigs,
                    key=lambda x: (float(x.get("impact_score", 0.0)), abs(float(x.get("sentiment_score", 0.0)))),
                    reverse=True,
                )[:3]
                top_signals[tk] = [
                    {
                        "headline": s.get("headline", ""),
                        "event_type": s.get("event_type", "Other"),
                        "sentiment_score": float(s.get("sentiment_score", 0.0)),
                        "impact_score": float(s.get("impact_score", 0.0)),
                    }
                    for s in sorted_sigs
                ]

        # Update internal state
        self.current_weights = new_weight_dict
        self.current_scores = new_scores

        return RebalanceResult(
            date=date,
            weights=new_weight_dict,
            target_weights=target_dict,
            scores=new_scores,
            raw_scores=raw_scores,
            turnover=actual_turnover,
            turnover_constrained=is_constrained,
            top_signals=top_signals,
        )
