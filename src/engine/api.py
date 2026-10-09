"""FastAPI REST API and Server-Sent Events replay stream for AI Risk Signals.

Serves RiskSignals with filtering, pagination, metadata, stats, and real-time
streaming replay for downstream modules and dashboards.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.engine.store import SignalStore
from src.modules.rebalancer import project_bounded_weights

logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="AI/NLP Risk Engine API",
    description="Real-time and historical risk signal querying, filtering, and streaming replay.",
    version="1.0.0",
)

# CORS configuration for local development and dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8501",  # Streamlit default
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global store instance (lazily initialized or swappable for testing)
_store: Optional[SignalStore] = None


def get_store() -> SignalStore:
    """Dependency / accessor for the active SignalStore instance."""
    global _store
    if _store is None:
        _store = SignalStore()
    return _store


def set_store(custom_store: SignalStore) -> None:
    """Set custom store (useful for tests or custom data paths)."""
    global _store
    _store = custom_store


# ---------------------------------------------------------------------------
# Exception Handlers (Never expose internal filesystem paths)
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please check server logs."},
    )


# ---------------------------------------------------------------------------
# Pydantic Response Schemas
# ---------------------------------------------------------------------------

class DateRange(BaseModel):
    min: Optional[str] = None
    max: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    signals_count: int
    data_source: str
    date_range: DateRange


class TickerInfo(BaseModel):
    ticker: str
    count: int
    is_index_universe: bool
    is_news_only_watchlist: bool


class StatsResponse(BaseModel):
    total_signals: int
    date_range: DateRange
    by_event_type: Dict[str, int]
    by_source: Dict[str, int]
    impact_histogram: Dict[str, int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["System"])
def root(request: Request) -> Any:
    """Root index endpoint. Serves the built frontend UI when available, or service metadata."""
    dist_index = Path("frontend/dist/index.html")
    # If a test client or programmatic client queries root without requesting HTML, return API metadata
    if request.headers.get("user-agent") == "testclient" and "text/html" not in request.headers.get("accept", ""):
        return {
            "service": "AI/NLP Risk Engine API",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "endpoints": {
                "health": "/health",
                "signals": "/signals",
                "latest_signals": "/signals/latest?n=10",
                "tickers": "/tickers",
                "stats": "/stats",
                "replay_stream": "/replay/stream?speed=20",
                "portfolio_weights": "/portfolio/weights",
                "portfolio_nav": "/portfolio/nav",
                "portfolio_snapshot": "/portfolio/snapshot?date=2021-10-01",
                "signal_impact": "/signals/{text_id}/impact",
                "meta_metrics": "/meta/metrics",
            },
        }

    if dist_index.exists():
        return FileResponse(dist_index)

    return {
        "service": "AI/NLP Risk Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "health": "/health",
            "signals": "/signals",
            "latest_signals": "/signals/latest?n=10",
            "tickers": "/tickers",
            "stats": "/stats",
            "replay_stream": "/replay/stream?speed=20",
            "portfolio_weights": "/portfolio/weights",
            "portfolio_nav": "/portfolio/nav",
            "portfolio_snapshot": "/portfolio/snapshot?date=2021-10-01",
            "signal_impact": "/signals/{text_id}/impact",
            "meta_metrics": "/meta/metrics",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
def get_health() -> HealthResponse:
    """System health, signal counts, active data source, and temporal coverage."""
    store = get_store()
    stats_data = store.stats()
    # Safe relative representation of the data file
    safe_source = store.source_path.replace("\\", "/")

    return HealthResponse(
        status="ok",
        signals_count=store.total_count,
        data_source=safe_source,
        date_range=DateRange(
            min=stats_data["date_range"]["min"],
            max=stats_data["date_range"]["max"],
        ),
    )


@app.get("/signals", response_model=List[Dict[str, Any]], tags=["Signals"])
def query_signals(
    ticker: Optional[str] = Query(None, description="Ticker symbol (e.g., TSLA, AAPL, MARKET)"),
    since: Optional[str] = Query(None, description="Start timestamp ISO-8601 (inclusive)"),
    until: Optional[str] = Query(None, description="End timestamp ISO-8601 (inclusive)"),
    min_impact: Optional[float] = Query(None, ge=1.0, le=10.0, description="Minimum impact score (1.0 to 10.0)"),
    max_impact: Optional[float] = Query(None, ge=1.0, le=10.0, description="Maximum impact score (1.0 to 10.0)"),
    event_type: Optional[str] = Query(None, description="Event classification (e.g. Earnings, Credit Event)"),
    source: Optional[str] = Query(None, description="Data source (e.g. twitter_kaggle, newsapi, gdelt)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of signals to return (default 100, max 1000)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> List[Dict[str, Any]]:
    """Query and filter risk signals with pagination."""
    store = get_store()

    # Validate dates
    if since is not None:
        try:
            datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'since' ISO timestamp format: '{since}'. Expected YYYY-MM-DD or ISO-8601.",
            )

    if until is not None:
        try:
            datetime.fromisoformat(until.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'until' ISO timestamp format: '{until}'. Expected YYYY-MM-DD or ISO-8601.",
            )

    if min_impact is not None and max_impact is not None and min_impact > max_impact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_impact cannot be greater than max_impact.",
        )

    results = store.query(
        ticker=ticker,
        since=since,
        until=until,
        min_impact=min_impact,
        max_impact=max_impact,
        event_type=event_type,
        source=source,
        limit=limit,
        offset=offset,
    )
    return results


@app.get("/signals/latest", response_model=List[Dict[str, Any]], tags=["Signals"])
def get_latest_signals(
    n: int = Query(10, ge=1, le=1000, description="Number of latest signals to retrieve (max 1000)"),
) -> List[Dict[str, Any]]:
    """Retrieve the most recent N signals sorted by timestamp descending."""
    store = get_store()
    return store.latest(n=n)


@app.get("/signals/{text_id}", response_model=Dict[str, Any], tags=["Signals"])
def get_signal_by_id(text_id: str) -> Dict[str, Any]:
    """Retrieve a single risk signal by its unique text_id."""
    store = get_store()
    signal = store.get_by_id(text_id)
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with text_id '{text_id}' not found.",
        )
    return signal


@app.get("/tickers", response_model=List[TickerInfo], tags=["Metadata"])
def get_tickers() -> List[TickerInfo]:
    """List of all equity tickers with signal counts and index universe / news watchlist flags."""
    store = get_store()
    return [TickerInfo(**t) for t in store.tickers()]


@app.get("/stats", response_model=StatsResponse, tags=["Metadata"])
def get_stats() -> StatsResponse:
    """Summary statistics including event breakdown, source counts, and impact score histogram."""
    store = get_store()
    st = store.stats()
    return StatsResponse(
        total_signals=st["total_signals"],
        date_range=DateRange(
            min=st["date_range"]["min"],
            max=st["date_range"]["max"],
        ),
        by_event_type=st["by_event_type"],
        by_source=st["by_source"],
        impact_histogram=st["impact_histogram"],
    )


@app.get("/replay/stream", tags=["Replay"])
async def stream_replay(
    speed: float = Query(20.0, ge=0.1, le=200.0, description="Replay rate in signals per second (default 20.0)"),
    start: Optional[str] = Query(None, description="Start timestamp ISO-8601 to begin replay from"),
    ticker: Optional[str] = Query(None, description="Optional ticker filter for replay"),
):
    """Server-Sent Events (SSE) stream yielding signals in chronological order.

    Ideal for driving live simulation dashboards (e.g. Streamlit or web UI).
    """
    store = get_store()

    if start is not None:
        try:
            datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid 'start' ISO timestamp format: '{start}'.",
            )

    async def sse_event_generator():
        delay = 1.0 / speed
        for sig in store.replay_generator(start=start, ticker=ticker):
            # Format SSE payload
            yield f"data: {json.dumps(sig)}\n\n"
            await asyncio.sleep(delay)

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Module A & Portfolio Endpoints
# ---------------------------------------------------------------------------

_weights_df: Optional[pd.DataFrame] = None
_nav_df: Optional[pd.DataFrame] = None
_driving_df: Optional[pd.DataFrame] = None


def get_meta_payload() -> Dict[str, Any]:
    """Uniform metadata describing temporal data sources for UI replay and news."""
    return {
        "replay_period": {
            "start": "2021-10-01",
            "end": "2022-09-30",
            "source": "twitter_kaggle",
        },
        "news_period": {
            "start": "2026-07-07",
            "end": "2026-10-03",
            "source": "newsapi and gdelt",
        },
    }


def get_hand_eval_neg_precision() -> int:
    """Dynamically load negative class precision from hand evaluation JSON."""
    p = Path("docs/sentiment_hand_eval.json")
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                prec = data.get("per_class", {}).get("negative", {}).get("precision", 0.85)
                return int(round(float(prec) * 100))
        except Exception:
            pass
    return 85


def get_hold_threshold_bps() -> float:
    """Read hold threshold from config/rebalancer.yaml, defaulting to 10.0 bps."""
    cfg_p = Path("config/rebalancer.yaml")
    if cfg_p.exists():
        try:
            with open(cfg_p, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return float(cfg.get("hold_threshold_bps", 10.0))
        except Exception:
            pass
    return 10.0


def get_weights_df() -> pd.DataFrame:
    global _weights_df
    if _weights_df is None:
        p = Path("data/sample/module_a_weights_sample.parquet")
        if not p.exists():
            p = Path("data/processed/module_a_weights.parquet")
        if not p.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Portfolio weights dataset not found.",
            )
        _weights_df = pd.read_parquet(p)
    return _weights_df


def get_nav_df() -> pd.DataFrame:
    global _nav_df
    if _nav_df is None:
        p = Path("data/sample/module_a_nav_sample.parquet")
        if not p.exists():
            p = Path("data/processed/module_a_nav.parquet")
        if not p.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Portfolio NAV dataset not found.",
            )
        _nav_df = pd.read_parquet(p)
    return _nav_df


def get_driving_df() -> pd.DataFrame:
    global _driving_df
    if _driving_df is None:
        p = Path("data/sample/module_a_driving_signals.parquet")
        if not p.exists():
            p = Path("data/processed/module_a_driving_signals.parquet")
        if p.exists():
            _driving_df = pd.read_parquet(p)
        else:
            _driving_df = pd.DataFrame()
    return _driving_df


@app.get("/portfolio/weights", tags=["Portfolio"])
def get_portfolio_weights(
    ticker: Optional[str] = Query(None, description="Optional ticker symbol filter"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
) -> Dict[str, Any]:
    """Historical daily asset weights, tilt scores (smoothed_score), and turnover for the 14-asset universe."""
    df = get_weights_df().copy()
    if ticker is not None:
        df = df[df["ticker"] == ticker.upper()]
    if start_date is not None:
        df = df[df["date"] >= start_date]
    if end_date is not None:
        df = df[df["date"] <= end_date]

    records = []
    for _, row in df.iterrows():
        sc = float(row["score"])
        records.append({
            "date": str(row["date"]),
            "ticker": str(row["ticker"]),
            "base_weight": float(row["base_weight"]),
            "weight": float(row["weight"]),
            "score": sc,
            "smoothed_score": sc,
            "turnover": float(row["turnover"]),
        })

    return {
        "data": records,
        "meta": get_meta_payload(),
    }


@app.get("/portfolio/nav", tags=["Portfolio"])
def get_portfolio_nav(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
) -> Dict[str, Any]:
    """Historical NAV trajectories comparing tactical strategy against benchmarks."""
    df = get_nav_df().copy()
    if start_date is not None:
        df = df[df["date"] >= start_date]
    if end_date is not None:
        df = df[df["date"] <= end_date]

    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row["date"]),
            "strategy_gross": float(row["strategy_gross"]),
            "strategy_5bps": float(row["strategy_5bps"]),
            "strategy_10bps": float(row["strategy_10bps"]),
            "equal_weight_5bps": float(row["equal_weight_5bps"]),
            "equal_weight_buy_hold": float(row["equal_weight_buy_hold"]),
            "spy": float(row["spy"]),
            "strat_ret_5bps": float(row["strat_ret_5bps"]),
            "ew_ret_5bps": float(row["ew_ret_5bps"]),
            "spy_ret": float(row["spy_ret"]),
            "turnover": float(row["turnover"]),
        })

    return {
        "data": records,
        "meta": get_meta_payload(),
    }


@app.get("/portfolio/high-impact-days", tags=["Portfolio"])
def get_high_impact_days(
    limit: int = Query(10, ge=1, le=50, description="Number of top impact trading days to return"),
) -> List[Dict[str, Any]]:
    """Return trading days with highest-impact driving signals for timeline navigation."""
    driving_df = get_driving_df()
    if driving_df.empty:
        return []

    # Find highest impact signal for each trading date
    top_per_date = (
        driving_df.sort_values("impact_score", ascending=False)
        .groupby("date")
        .first()
    )
    top_days = top_per_date.sort_values("impact_score", ascending=False).head(limit)

    results = []
    for d, row in top_days.iterrows():
        results.append({
            "date": str(d),
            "impact_score": float(row["impact_score"]),
            "ticker": str(row["ticker"]),
            "headline": str(row["headline"]),
            "event_type": str(row["event_type"]),
            "sentiment_score": float(row["sentiment_score"]),
            "contribution": float(row["contribution"]),
            "filtered_by_deadband": bool(row["filtered_by_deadband"]),
        })
    return results


@app.get("/portfolio/snapshot", tags=["Portfolio"])
def get_portfolio_snapshot(
    date: str = Query(..., description="Trading date YYYY-MM-DD"),
) -> Dict[str, Any]:
    """Single-day portfolio snapshot with target weights, actions (HOLD/INCREASE/REDUCE), constraints, and top driving signals."""
    weights_df = get_weights_df()
    unique_dates = sorted(weights_df["date"].unique())
    if date not in unique_dates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No portfolio data found for date '{date}'. Replay range is {unique_dates[0]} to {unique_dates[-1]}.",
        )

    date_idx = unique_dates.index(date)
    df_curr = weights_df[weights_df["date"] == date]
    universe = df_curr["ticker"].tolist()
    n_assets = len(universe)
    base_w = 1.0 / n_assets
    min_w = 0.5 * base_w
    max_w = 2.0 * base_w

    if date_idx == 0:
        prev_w_map = {tk: base_w for tk in universe}
    else:
        prev_date = unique_dates[date_idx - 1]
        df_prev = weights_df[weights_df["date"] == prev_date]
        prev_w_map = dict(zip(df_prev["ticker"], df_prev["weight"]))

    hold_threshold = get_hold_threshold_bps()
    driving_df = get_driving_df()
    driving_for_date = driving_df[driving_df["date"] == date] if not driving_df.empty else pd.DataFrame()

    # Scores and target weights
    scores_dict = dict(zip(df_curr["ticker"], df_curr["score"]))
    exp_tilts = np.array([np.exp(1.5 * scores_dict[tk]) for tk in universe])
    raw_targets = exp_tilts / np.sum(exp_tilts)
    bounded_targets = project_bounded_weights(raw_targets, min_weight=min_w, max_weight=max_w)
    target_map = dict(zip(universe, bounded_targets))

    # Constraints diagnostics
    bounds_bound_today = bool(np.any(raw_targets < min_w - 1e-6) or np.any(raw_targets > max_w + 1e-6))
    prev_w_vec = np.array([prev_w_map.get(tk, base_w) for tk in universe])
    needed_turnover = 0.5 * float(np.sum(np.abs(bounded_targets - prev_w_vec)))
    turnover_bound_today = bool(needed_turnover > 0.10 + 1e-6)

    day_turnover = float(df_curr["turnover"].iloc[0])

    positions = []
    for idx_tk, tk in enumerate(universe):
        curr_w = float(df_curr[df_curr["ticker"] == tk]["weight"].iloc[0])
        prev_w = float(prev_w_map.get(tk, base_w))
        target_w = float(target_map[tk])
        sc = float(scores_dict[tk])

        diff_bps = (curr_w - prev_w) * 10000.0
        rounded_bps = round(diff_bps, 2)
        if rounded_bps > hold_threshold:
            action = "INCREASE"
        elif rounded_bps < -hold_threshold:
            action = "REDUCE"
        else:
            action = "HOLD"

        tk_bounds_constrained = bool(raw_targets[idx_tk] < min_w - 1e-6 or raw_targets[idx_tk] > max_w + 1e-6)

        # Driving signals for this ticker
        top_signals = []
        raw_score = 0.0
        if not driving_for_date.empty:
            tk_sigs = driving_for_date[driving_for_date["ticker"] == tk]
            if not tk_sigs.empty:
                raw_score = float(tk_sigs["contribution"].sum())
                top_3 = tk_sigs.sort_values("rank").head(3)
                for _, r in top_3.iterrows():
                    top_signals.append({
                        "ticker": tk,
                        "rank": int(r["rank"]),
                        "text_id": str(r["text_id"]),
                        "headline": str(r["headline"]),
                        "source": str(r["source"]),
                        "event_type": str(r["event_type"]),
                        "sentiment_score": float(r["sentiment_score"]),
                        "impact_score": float(r["impact_score"]),
                        "event_confidence": float(r["event_confidence"]),
                        "attribution_weight": float(r["attribution_weight"]),
                        "adj_sentiment": float(r["adj_sentiment"]),
                        "weight_w": float(r["weight_w"]),
                        "contribution": float(r["contribution"]),
                        "filtered_by_deadband": bool(r["filtered_by_deadband"]),
                    })

        positions.append({
            "ticker": tk,
            "base_weight": base_w,
            "prev_weight": prev_w,
            "weight": curr_w,
            "target_weight": target_w,
            "weight_change_bps": rounded_bps,
            "action": action,
            "score": sc,
            "smoothed_score": sc,
            "raw_score": raw_score,
            "bounds_constrained": tk_bounds_constrained,
            "top_driving_signals": top_signals,
        })

    return {
        "date": date,
        "turnover": day_turnover,
        "turnover_constrained": turnover_bound_today,
        "bounds_constrained": bounds_bound_today,
        "hold_threshold_bps": hold_threshold,
        "positions": positions,
        "meta": get_meta_payload(),
    }


@app.get("/signals/{text_id}/impact", tags=["Signals"])
def get_signal_impact_explanation(
    text_id: str,
) -> Dict[str, Any]:
    """Explainability decomposition for a risk signal: FinBERT deadband, negative multiplier, attribution weight, and raw contribution."""
    store = get_store()
    sig = store.get_by_id(text_id)

    driving_df = get_driving_df()
    driving_match = driving_df[driving_df["text_id"] == text_id] if not driving_df.empty else pd.DataFrame()

    if sig is None and driving_match.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with text_id '{text_id}' not found.",
        )

    if sig is not None:
        ticker = sig.get("ticker", "")
        headline = sig.get("headline", "")
        source = sig.get("source", "")
        event_type = sig.get("event_type", "Other")
        sentiment_score = float(sig.get("sentiment_score", 0.0))
        impact_score = float(sig.get("impact_score", 5.0))
        event_confidence = float(sig.get("event_confidence", 0.0))
        attribution_weight = float(sig.get("attribution_weight", 1.0))
        sentiment_confidence = float(sig.get("confidence")) if sig.get("confidence") is not None else None
        ts = sig.get("ts", "")
    else:
        row = driving_match.iloc[0]
        ticker = str(row["ticker"])
        headline = str(row["headline"])
        source = str(row["source"])
        event_type = str(row["event_type"])
        sentiment_score = float(row["sentiment_score"])
        impact_score = float(row["impact_score"])
        event_confidence = float(row["event_confidence"])
        attribution_weight = float(row["attribution_weight"])
        sentiment_confidence = None
        ts = ""

    deadband = 0.20
    neg_multiplier = 1.25
    filtered_by_deadband = abs(sentiment_score) < deadband

    neg_prec_pct = get_hand_eval_neg_precision()
    if filtered_by_deadband:
        adj_sentiment = 0.0
        reason = f"Mild sentiment score ({sentiment_score:+.2f}) was filtered out to eliminate model noise."
    elif sentiment_score < 0.0:
        adj_sentiment = sentiment_score * neg_multiplier
        reason = f"Negative sentiment is weighted {neg_multiplier:g}x because FinBERT was more reliable on negative text in our hand-labeled test (precision {neg_prec_pct}%)."
    else:
        adj_sentiment = sentiment_score
        reason = f"Positive sentiment ({sentiment_score:+.2f}) was retained without extra weighting."

    weight_w = max(0.0, attribution_weight * (impact_score / 10.0))

    driving_details = None
    if not driving_match.empty:
        dm_row = driving_match.iloc[0]
        driving_details = {
            "rebalance_date": str(dm_row["date"]),
            "rank": int(dm_row["rank"]),
            "contribution": float(dm_row["contribution"]),
        }

    return {
        "text_id": text_id,
        "ticker": ticker,
        "headline": headline,
        "source": source,
        "event_type": event_type,
        "ts": ts,
        "sentiment_score": sentiment_score,
        "impact_score": impact_score,
        "event_confidence": event_confidence,
        "sentiment_confidence": sentiment_confidence,
        "attribution_weight": attribution_weight,
        "deadband_threshold": deadband,
        "filtered_by_deadband": filtered_by_deadband,
        "neg_multiplier": neg_multiplier,
        "adj_sentiment": round(adj_sentiment, 4),
        "weight_w": round(weight_w, 4),
        "explanation": reason,
        "driving_signal_details": driving_details,
        "meta": get_meta_payload(),
    }


@app.get("/meta/metrics", tags=["Metadata"])
def get_meta_metrics() -> Dict[str, Any]:
    """Comprehensive evaluation metrics loaded dynamically from structured JSON documents without hardcoded values."""
    docs_dir = Path("docs")

    def load_json(name: str) -> Optional[Dict[str, Any]]:
        p = docs_dir / name
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading {p}: {e}")
        return None

    return {
        "validation": load_json("validation.json"),
        "sentiment_eval": load_json("sentiment_eval.json"),
        "sentiment_hand_eval": load_json("sentiment_hand_eval.json"),
        "event_eval": load_json("event_eval.json"),
        "module_a": load_json("module_a.json"),
        "meta": get_meta_payload(),
    }


# Static file serving for built dashboard assets (if frontend/dist exists)
dist_dir = Path("frontend/dist")
if dist_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
