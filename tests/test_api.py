"""Unit tests for FastAPI endpoints, SSE streaming replay, and export CLI.

Uses FastAPI TestClient strictly on committed data/sample/signals_sample.parquet
without external network calls or heavy models.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.engine.api import app, set_store
from src.engine.export import export_signals
from src.engine.store import SignalStore

SAMPLE_PATH = Path("data/sample/signals_sample.parquet")


@pytest.fixture(autouse=True)
def setup_sample_store():
    """Ensure tests run strictly against the committed sample parquet file."""
    sample_store = SignalStore(data_path=SAMPLE_PATH)
    set_store(sample_store)
    yield
    # reset store
    set_store(SignalStore(data_path=SAMPLE_PATH))


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Health & Metadata Endpoints
# ---------------------------------------------------------------------------

def test_get_root(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert "docs" in data
    assert "endpoints" in data
    assert data["endpoints"]["health"] == "/health"


def test_get_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["signals_count"] == 5000
    assert "signals_sample.parquet" in data["data_source"]
    assert data["date_range"]["min"] is not None
    assert data["date_range"]["max"] is not None


def test_get_tickers(client: TestClient):
    resp = client.get("/tickers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check structure
    first = data[0]
    assert "ticker" in first
    assert "count" in first
    assert "is_index_universe" in first
    assert "is_news_only_watchlist" in first


def test_get_stats(client: TestClient):
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_signals"] == 5000
    assert "by_event_type" in data
    assert "by_source" in data
    assert "impact_histogram" in data
    assert sum(data["by_source"].values()) == 5000


# ---------------------------------------------------------------------------
# 2. Signals Querying, Filters & Pagination
# ---------------------------------------------------------------------------

def test_query_signals_ticker_filter(client: TestClient):
    resp = client.get("/signals?ticker=TSLA&limit=5")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) == 5
    for sig in signals:
        assert sig["ticker"] == "TSLA"
        assert "impact_score" in sig
        assert "sentiment_score" in sig
        assert "event_confidence" in sig
        assert "attribution_weight" in sig
        assert "matched_triggers" in sig
        assert "impact_components" in sig


def test_query_signals_impact_range(client: TestClient):
    resp = client.get("/signals?min_impact=5.0&max_impact=8.0&limit=10")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) > 0
    for sig in signals:
        assert 5.0 <= sig["impact_score"] <= 8.0


def test_query_signals_pagination(client: TestClient):
    resp_page1 = client.get("/signals?ticker=AAPL&limit=5&offset=0")
    resp_page2 = client.get("/signals?ticker=AAPL&limit=5&offset=5")
    assert resp_page1.status_code == 200
    assert resp_page2.status_code == 200
    ids_1 = [s["text_id"] for s in resp_page1.json()]
    ids_2 = [s["text_id"] for s in resp_page2.json()]
    # Pages should not overlap
    assert set(ids_1).isdisjoint(set(ids_2))


def test_pagination_max_limit_validation(client: TestClient):
    # limit > 1000 violates validation constraint
    resp = client.get("/signals?limit=1001")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Error Handling (400 and 404)
# ---------------------------------------------------------------------------

def test_bad_date_returns_400(client: TestClient):
    resp = client.get("/signals?since=invalid-date-format")
    assert resp.status_code == 400
    assert "Invalid 'since' ISO timestamp format" in resp.json()["detail"]

    resp2 = client.get("/signals?until=2021-99-99")
    assert resp2.status_code == 400
    assert "Invalid 'until' ISO timestamp format" in resp2.json()["detail"]


def test_inverted_impact_range_returns_400(client: TestClient):
    resp = client.get("/signals?min_impact=7.0&max_impact=3.0")
    assert resp.status_code == 400
    assert "min_impact cannot be greater than max_impact" in resp.json()["detail"]


def test_get_by_id_success_and_404(client: TestClient):
    # Get a real ID from query
    all_sigs = client.get("/signals?limit=1").json()
    assert len(all_sigs) == 1
    real_id = all_sigs[0]["text_id"]

    # Valid ID lookup
    resp_found = client.get(f"/signals/{real_id}")
    assert resp_found.status_code == 200
    assert resp_found.json()["text_id"] == real_id

    # Unknown ID lookup
    resp_missing = client.get("/signals/non_existent_text_id_xyz_123")
    assert resp_missing.status_code == 404
    assert "not found" in resp_missing.json()["detail"]


def test_get_latest_signals(client: TestClient):
    resp = client.get("/signals/latest?n=5")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) == 5
    # Must be sorted descending by timestamp
    for i in range(len(signals) - 1):
        assert signals[i]["ts"] >= signals[i + 1]["ts"]


# ---------------------------------------------------------------------------
# 4. Server-Sent Events (SSE) Replay Stream
# ---------------------------------------------------------------------------

def test_replay_stream_order(client: TestClient):
    """Test that SSE stream delivers events in non-decreasing timestamp order."""
    with client.stream("GET", "/replay/stream?speed=100.0&ticker=TSLA") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        received_events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                received_events.append(payload)
                if len(received_events) >= 10:
                    break

        assert len(received_events) == 10
        # Verify non-decreasing timestamp ordering
        for i in range(len(received_events) - 1):
            t_curr = received_events[i]["ts"]
            t_next = received_events[i + 1]["ts"]
            assert t_curr <= t_next


# ---------------------------------------------------------------------------
# 5. Export CLI & File Export Logic
# ---------------------------------------------------------------------------

def test_export_signals_python_api(tmp_path: Path):
    store = SignalStore(data_path=SAMPLE_PATH)

    # 1. JSONL export
    out_jsonl = tmp_path / "out.jsonl"
    n_jsonl = export_signals(out_jsonl, output_format="jsonl", ticker="AAPL", limit=15, store=store)
    assert n_jsonl == 15
    assert out_jsonl.exists()
    with open(out_jsonl, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 15
    first_obj = json.loads(lines[0])
    assert first_obj["ticker"] == "AAPL"

    # 2. CSV export
    out_csv = tmp_path / "out.csv"
    n_csv = export_signals(out_csv, output_format="csv", ticker="TSLA", limit=10, store=store)
    assert n_csv == 10
    assert out_csv.exists()

    # 3. Parquet export
    out_pq = tmp_path / "out.parquet"
    n_pq = export_signals(out_pq, output_format="parquet", ticker="MSFT", limit=8, store=store)
    assert n_pq == 8
    assert out_pq.exists()


def test_export_cli_subprocess(tmp_path: Path):
    out_file = tmp_path / "cli_exported.jsonl"
    cmd = [
        sys.executable,
        "-m",
        "src.engine.export",
        "--format",
        "jsonl",
        "--out",
        str(out_file),
        "--ticker",
        "AMZN",
        "--limit",
        "12",
        "--sample",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 12
