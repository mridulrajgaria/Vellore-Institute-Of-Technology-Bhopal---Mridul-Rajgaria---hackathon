"""FastAPI REST API and Server-Sent Events replay stream for AI Risk Signals.

Serves RiskSignals with filtering, pagination, metadata, stats, and real-time
streaming replay for downstream modules and dashboards.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.engine.store import SignalStore

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
def root() -> Dict[str, Any]:
    """Root index endpoint providing service overview and route links."""
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
