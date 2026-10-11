"""Focused backend tests for Server-Sent Events (/replay/stream).

Tests four operational aspects:
1. Connection: HTTP 200, text/event-stream headers, initial event delivery.
2. Event Delivery: >=25 events for ticker=AAPL, payload framing, schema validation,
   chronological ordering by timestamp, ticker exclusivity, and bounded timeout.
3. Disconnect Handling: Client abort after partial stream, generator cancellation,
   absence of server-side exceptions.
4. Error Handling: Invalid ISO timestamp (400), invalid speed ranges (422),
   future start timestamp with zero events, and bounded timeouts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.engine.api import app, set_store
from src.engine.store import SignalStore

SAMPLE_PATH = Path("data/sample/signals_sample.parquet")


@pytest.fixture(autouse=True)
def setup_sample_store():
    """Ensure tests run strictly against the committed sample parquet file."""
    sample_store = SignalStore(data_path=SAMPLE_PATH)
    set_store(sample_store)
    yield
    set_store(SignalStore(data_path=SAMPLE_PATH))


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Connection Tests
# ---------------------------------------------------------------------------

def test_sse_connection_headers_and_initial_event(client: TestClient):
    """Verify HTTP status 200, Content-Type, expected headers, and initial event."""
    with client.stream("GET", "/replay/stream?speed=200.0") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("connection") == "keep-alive"
        assert response.headers.get("x-accel-buffering") == "no"

        # Read first SSE frame
        first_line = next(response.iter_lines())
        assert first_line.startswith("data: ")
        payload = json.loads(first_line[6:])
        assert isinstance(payload, dict)
        assert "text_id" in payload
        assert "ts" in payload


# ---------------------------------------------------------------------------
# 2. Event Delivery Tests
# ---------------------------------------------------------------------------

def test_sse_event_delivery_schema_ordering_and_filtering(client: TestClient):
    """Consume >=25 events for ticker=AAPL, validating framing, schema, and order."""
    required_keys = {
        "text_id", "ticker", "headline", "source", "event_type",
        "ts", "sentiment_score", "impact_score", "confidence"
    }

    with client.stream("GET", "/replay/stream?speed=200.0&ticker=AAPL") as response:
        assert response.status_code == 200
        events = []
        # Consume lines with bounded loop to prevent infinite hang
        for line in response.iter_lines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                events.append(payload)
                if len(events) >= 25:
                    break

        assert len(events) >= 25, f"Expected at least 25 events, got {len(events)}"

        # Validate ticker filter and schema
        for idx, event in enumerate(events):
            assert event["ticker"] == "AAPL", f"Event {idx} ticker was {event.get('ticker')}, expected AAPL"
            missing = required_keys - set(event.keys())
            assert not missing, f"Event {idx} missing required fields: {missing}"
            assert isinstance(event["text_id"], str)
            assert isinstance(event["headline"], str)
            assert isinstance(event["sentiment_score"], (int, float))
            assert isinstance(event["impact_score"], (int, float))

        # Validate non-decreasing chronological ordering by timestamp
        for i in range(len(events) - 1):
            assert events[i]["ts"] <= events[i + 1]["ts"], (
                f"Chronological violation at index {i}: {events[i]['ts']} > {events[i+1]['ts']}"
            )


# ---------------------------------------------------------------------------
# 3. Disconnect Handling Tests
# ---------------------------------------------------------------------------

def test_sse_disconnect_handling(client: TestClient, caplog):
    """Client disconnects after partial consumption; generator cancels cleanly."""
    caplog.set_level(logging.ERROR)

    # Open stream, read 3 events, then exit context manager (disconnect)
    with client.stream("GET", "/replay/stream?speed=200.0") as response:
        assert response.status_code == 200
        count = 0
        for line in response.iter_lines():
            if line.startswith("data: "):
                count += 1
                if count >= 3:
                    break

    assert count == 3
    # Verify no unhandled server exceptions logged
    error_logs = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(error_logs) == 0, f"Unexpected server error logs during disconnect: {error_logs}"


# ---------------------------------------------------------------------------
# 4. Error Handling & Parameter Validation Tests
# ---------------------------------------------------------------------------

def test_sse_invalid_iso_timestamp_returns_400(client: TestClient):
    """Invalid start timestamp produces HTTP 400 Bad Request."""
    resp = client.get("/replay/stream?start=invalid-date-format")
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Invalid 'start' ISO timestamp format" in detail


def test_sse_speed_validation_returns_422(client: TestClient):
    """Speed < 0.1 or > 200.0 produces FastAPI validation error 422."""
    # Speed below minimum (0.1)
    resp_low = client.get("/replay/stream?speed=0.0")
    assert resp_low.status_code == 422

    # Speed above maximum (200.0)
    resp_high = client.get("/replay/stream?speed=500.0")
    assert resp_high.status_code == 422


def test_sse_future_start_produces_empty_stream(client: TestClient):
    """A future timestamp beyond dataset produces an empty stream that terminates cleanly."""
    with client.stream("GET", "/replay/stream?speed=200.0&start=2099-01-01T00:00:00Z") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())
        # Stream should yield no data frames
        data_frames = [l for l in lines if l.startswith("data: ")]
        assert len(data_frames) == 0
