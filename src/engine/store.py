"""Thread-safe signal store supporting queries, pagination, and metrics.

Loads signals from `data/processed/signals.parquet` if present; otherwise falls
back gracefully to `data/sample/signals_sample.parquet` for fully offline operation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

PROCESSED_SIGNALS_PATH = Path("data/processed/signals.parquet")
SAMPLE_SIGNALS_PATH = Path("data/sample/signals_sample.parquet")
DEFAULT_CONFIG_PATH = Path("config/default.yaml")


def _sanitize_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert pandas/numpy types to standard JSON-compatible Python primitives."""
    # Matched triggers
    mt = row.get("matched_triggers")
    if isinstance(mt, np.ndarray):
        row["matched_triggers"] = mt.tolist()
    elif mt is None or (isinstance(mt, float) and np.isnan(mt)):
        row["matched_triggers"] = []
    elif not isinstance(mt, list):
        row["matched_triggers"] = list(mt)

    # Secondary event
    sec = row.get("secondary_event")
    if sec is None or (isinstance(sec, float) and np.isnan(sec)):
        row["secondary_event"] = None

    # Timestamp
    ts = row.get("ts")
    if isinstance(ts, pd.Timestamp):
        row["ts"] = ts.isoformat()
    elif isinstance(ts, datetime):
        row["ts"] = ts.isoformat()

    # Numbers
    for k in ["sentiment_score", "impact_score", "confidence", "event_confidence", "attribution_weight"]:
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            row[k] = float(v)

    # Booleans
    row["is_broadcast"] = bool(row.get("is_broadcast", False))
    row["is_analyst_action"] = bool(row.get("is_analyst_action", False))

    return row


class SignalStore:
    """In-memory searchable store for AI risk signals with disk backing."""

    def __init__(self, data_path: Optional[Union[str, Path]] = None, config_path: Optional[Union[str, Path]] = None) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._load_universe_config()
        self._load_data(data_path)

    def _load_universe_config(self) -> None:
        """Load ticker universe and news-only watchlist metadata."""
        self.all_tickers: List[str] = []
        self.index_universe: List[str] = []
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                self.all_tickers = cfg.get("tickers", [])
                self.index_universe = cfg.get("index_universe", [])
            except Exception as e:
                logger.warning(f"Could not load universe config from {self.config_path}: {e}")

    def _load_data(self, explicit_path: Optional[Union[str, Path]] = None) -> None:
        """Load parquet signals from explicit path, processed, or sample fallback."""
        if explicit_path:
            target = Path(explicit_path)
            if not target.exists():
                raise FileNotFoundError(f"Signal file not found: {target}")
            self.active_path = target
        elif PROCESSED_SIGNALS_PATH.exists():
            self.active_path = PROCESSED_SIGNALS_PATH
        elif SAMPLE_SIGNALS_PATH.exists():
            self.active_path = SAMPLE_SIGNALS_PATH
        else:
            raise FileNotFoundError("Neither processed signals nor sample signals parquet file was found.")

        logger.info(f"SignalStore loaded signals from: {self.active_path.as_posix()}")
        self._df = pd.read_parquet(self.active_path)

        # Ensure ts is datetime
        if not pd.api.types.is_datetime64_any_dtype(self._df["ts"]):
            self._df["ts"] = pd.to_datetime(self._df["ts"], utc=True)
        elif self._df["ts"].dt.tz is None:
            self._df["ts"] = self._df["ts"].dt.tz_localize("UTC")

        # Sort by timestamp ascending for deterministic queries and replay
        self._df = self._df.sort_values("ts", ascending=True).reset_index(drop=True)

        # Build fast text_id index
        self._id_index: Dict[str, int] = {}
        for idx, tid in enumerate(self._df["text_id"]):
            if tid and tid not in self._id_index:
                self._id_index[tid] = idx

    @property
    def total_count(self) -> int:
        return len(self._df)

    @property
    def source_path(self) -> str:
        return self.active_path.as_posix()

    def get_by_id(self, text_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a single signal by text_id."""
        idx = self._id_index.get(text_id)
        if idx is None:
            return None
        row = self._df.iloc[idx].to_dict()
        return _sanitize_record(row)

    def latest(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent N signals sorted by timestamp descending."""
        n = max(1, min(n, 1000))
        sub = self._df.tail(n).iloc[::-1]
        return [_sanitize_record(r) for r in sub.to_dict(orient="records")]

    def query(
        self,
        ticker: Optional[str] = None,
        since: Optional[Union[str, datetime]] = None,
        until: Optional[Union[str, datetime]] = None,
        min_impact: Optional[float] = None,
        max_impact: Optional[float] = None,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Filter signals with pagination and returns standardized signal dicts."""
        mask = pd.Series(True, index=self._df.index)

        if ticker:
            tk_upper = ticker.strip().upper()
            mask &= self._df["ticker"] == tk_upper

        if since is not None:
            since_ts = pd.to_datetime(since, utc=True)
            mask &= self._df["ts"] >= since_ts

        if until is not None:
            until_ts = pd.to_datetime(until, utc=True)
            mask &= self._df["ts"] <= until_ts

        if min_impact is not None:
            mask &= self._df["impact_score"] >= float(min_impact)

        if max_impact is not None:
            mask &= self._df["impact_score"] <= float(max_impact)

        if event_type:
            ev_clean = event_type.strip()
            mask &= self._df["event_type"].str.lower() == ev_clean.lower()

        if source:
            src_clean = source.strip()
            mask &= self._df["source"].str.lower() == src_clean.lower()

        # Apply pagination (offset + limit)
        matched_indices = np.where(mask.values)[0]
        start_idx = max(0, offset)
        end_idx = start_idx + max(1, min(limit, 1000))
        selected_indices = matched_indices[start_idx:end_idx]

        if len(selected_indices) == 0:
            return []

        sub = self._df.iloc[selected_indices]
        return [_sanitize_record(r) for r in sub.to_dict(orient="records")]

    def tickers(self) -> List[Dict[str, Any]]:
        """Return all tickers present in data and config with counts and watchlist flags."""
        counts = self._df["ticker"].value_counts().to_dict()

        # Collect union of config tickers and data tickers
        all_symbols = sorted(set(self.all_tickers) | set(counts.keys()))
        results = []
        for sym in all_symbols:
            count = int(counts.get(sym, 0))
            is_index = sym in self.index_universe
            # News-only watchlist: in configured tickers or data, but not in core index universe
            is_watchlist = (sym in self.all_tickers) and (not is_index)
            results.append({
                "ticker": sym,
                "count": count,
                "is_index_universe": is_index,
                "is_news_only_watchlist": is_watchlist,
            })
        return results

    def stats(self) -> Dict[str, Any]:
        """Summary statistics across the current signal dataset."""
        if self._df.empty:
            return {
                "total_signals": 0,
                "date_range": {"min": None, "max": None},
                "by_event_type": {},
                "by_source": {},
                "impact_histogram": {},
            }

        min_ts = self._df["ts"].min().isoformat()
        max_ts = self._df["ts"].max().isoformat()

        ev_counts = {str(k): int(v) for k, v in self._df["event_type"].value_counts().items()}
        src_counts = {str(k): int(v) for k, v in self._df["source"].value_counts().items()}

        # Impact score histogram (1-10 integer bins)
        bins = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        labels = ["1-2", "2-3", "3-4", "4-5", "5-6", "6-7", "7-8", "8-9", "9-10", "10+"]
        binned = pd.cut(self._df["impact_score"], bins=bins, labels=labels, right=False)
        hist_counts = {str(lbl): int((binned == lbl).sum()) for lbl in labels}

        return {
            "total_signals": len(self._df),
            "date_range": {"min": min_ts, "max": max_ts},
            "by_event_type": ev_counts,
            "by_source": src_counts,
            "impact_histogram": hist_counts,
        }

    def replay_generator(
        self,
        start: Optional[Union[str, datetime]] = None,
        ticker: Optional[str] = None,
    ):
        """Yield signals one-by-one in non-decreasing timestamp order for SSE replay."""
        sub = self._df
        if start is not None:
            start_ts = pd.to_datetime(start, utc=True)
            sub = sub[sub["ts"] >= start_ts]

        if ticker:
            tk_upper = ticker.strip().upper()
            sub = sub[sub["ticker"] == tk_upper]

        for _, row in sub.iterrows():
            yield _sanitize_record(row.to_dict())
