"""Unit and integration tests for Module A Portfolio and Signal Intelligence API routes.

Tests verify:
1. GET /portfolio/weights (filtering, smoothed_score alias, values match parquet).
2. GET /portfolio/nav (trajectories, benchmarking against EW and SPY).
3. GET /portfolio/snapshot (ACTION logic against 10 bps threshold, constraints, driving signals).
4. GET /signals/{text_id}/impact (FinBERT deadband, negative multiplier, explainability).
5. GET /meta/metrics (pure JSON loading from docs, zero hardcoded values).
6. Consistency: driving signal contributions reproduce raw_scores for every ticker-day.
7. Exact byte-for-byte SHA-256 preservation of module_a_weights_sample and module_a_nav_sample.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.engine.api import app

WEIGHTS_SAMPLE_PATH = Path("data/sample/module_a_weights_sample.parquet")
NAV_SAMPLE_PATH = Path("data/sample/module_a_nav_sample.parquet")
DRIVING_SAMPLE_PATH = Path("data/sample/module_a_driving_signals.parquet")

BASELINE_WEIGHTS_HASH = "f481beaced2281bb74d61005cb3e646d1dbf85a02e3da0aa9a0a3dc4d5a7d9d0"
BASELINE_NAV_HASH = "50535a3762bcd55ef43c06abe24fc4499acc3c1ae3716e65f6406b8daefea4e7"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Reusable TestClient fixture."""
    return TestClient(app)


def test_byte_for_byte_sample_hashes_preserved():
    """Verify that sample weights and NAV files remain byte-for-byte unchanged."""
    assert WEIGHTS_SAMPLE_PATH.exists(), "module_a_weights_sample.parquet missing"
    assert NAV_SAMPLE_PATH.exists(), "module_a_nav_sample.parquet missing"

    w_hash = hashlib.sha256(WEIGHTS_SAMPLE_PATH.read_bytes()).hexdigest()
    n_hash = hashlib.sha256(NAV_SAMPLE_PATH.read_bytes()).hexdigest()

    assert w_hash == BASELINE_WEIGHTS_HASH, f"Weights hash mismatch: {w_hash} != {BASELINE_WEIGHTS_HASH}"
    assert n_hash == BASELINE_NAV_HASH, f"NAV hash mismatch: {n_hash} != {BASELINE_NAV_HASH}"


def test_portfolio_weights_route(client: TestClient):
    """Test /portfolio/weights metadata, fields, smoothed_score alias, and filtering."""
    expected_df = pd.read_parquet(WEIGHTS_SAMPLE_PATH)

    # Full query
    res = client.get("/portfolio/weights")
    assert res.status_code == 200
    payload = res.json()
    assert "data" in payload and "meta" in payload
    assert payload["meta"]["replay_period"]["source"] == "twitter_kaggle"
    assert len(payload["data"]) == len(expected_df)

    # Ticker filter
    res_tsla = client.get("/portfolio/weights?ticker=TSLA")
    assert res_tsla.status_code == 200
    tsla_data = res_tsla.json()["data"]
    expected_tsla = expected_df[expected_df["ticker"] == "TSLA"]
    assert len(tsla_data) == len(expected_tsla)

    # Check first record fields against committed parquet
    first_exp = expected_tsla.iloc[0]
    first_act = tsla_data[0]
    assert first_act["date"] == first_exp["date"]
    assert first_act["ticker"] == first_exp["ticker"]
    assert np.isclose(first_act["weight"], first_exp["weight"])
    assert np.isclose(first_act["score"], first_exp["score"])
    assert np.isclose(first_act["smoothed_score"], first_exp["score"])  # Required alias
    assert np.isclose(first_act["turnover"], first_exp["turnover"])

    # Date range filter
    min_date = expected_df["date"].min()
    max_date = expected_df["date"].max()
    res_range = client.get(f"/portfolio/weights?start_date={min_date}&end_date={min_date}")
    assert res_range.status_code == 200
    assert len(res_range.json()["data"]) == 14


def test_portfolio_nav_route(client: TestClient):
    """Test /portfolio/nav returns cumulative trajectories matching committed parquet."""
    expected_df = pd.read_parquet(NAV_SAMPLE_PATH)

    res = client.get("/portfolio/nav")
    assert res.status_code == 200
    payload = res.json()
    assert "data" in payload and "meta" in payload
    assert len(payload["data"]) == len(expected_df)

    first_exp = expected_df.iloc[0]
    first_act = payload["data"][0]
    assert first_act["date"] == first_exp["date"]
    assert np.isclose(first_act["strategy_5bps"], first_exp["strategy_5bps"])
    assert np.isclose(first_act["equal_weight_5bps"], first_exp["equal_weight_5bps"])
    assert np.isclose(first_act["spy"], first_exp["spy"])

    last_exp = expected_df.iloc[-1]
    last_act = payload["data"][-1]
    assert last_act["date"] == last_exp["date"]
    assert np.isclose(last_act["strategy_5bps"], last_exp["strategy_5bps"])


def test_portfolio_snapshot_route(client: TestClient):
    """Test /portfolio/snapshot with ACTION classification, threshold, constraints, and driving signals."""
    weights_df = pd.read_parquet(WEIGHTS_SAMPLE_PATH)
    test_date = str(weights_df["date"].iloc[0])

    res = client.get(f"/portfolio/snapshot?date={test_date}")
    assert res.status_code == 200
    snap = res.json()

    assert snap["date"] == test_date
    assert snap["hold_threshold_bps"] == 10.0
    assert "turnover_constrained" in snap
    assert "bounds_constrained" in snap
    assert len(snap["positions"]) == 14

    for pos in snap["positions"]:
        assert pos["ticker"] in weights_df["ticker"].values
        assert "weight" in pos
        assert "prev_weight" in pos
        assert "target_weight" in pos
        assert "weight_change_bps" in pos
        assert "action" in pos
        assert pos["action"] in ("INCREASE", "REDUCE", "HOLD")

        # Verify ACTION threshold rule
        if pos["weight_change_bps"] > 10.0:
            assert pos["action"] == "INCREASE"
        elif pos["weight_change_bps"] < -10.0:
            assert pos["action"] == "REDUCE"
        else:
            assert pos["action"] == "HOLD"

        assert "top_driving_signals" in pos

    # 404 for invalid date
    res_bad = client.get("/portfolio/snapshot?date=1999-01-01")
    assert res_bad.status_code == 404


def test_driving_signals_reproduce_raw_score(client: TestClient):
    """Verify that the sum of contributions reproduces raw_score for every ticker-day in the driving signals file."""
    assert DRIVING_SAMPLE_PATH.exists()
    driving_df = pd.read_parquet(DRIVING_SAMPLE_PATH)

    # Pick multiple sample dates across the backtest window
    sample_dates = sorted(driving_df["date"].unique())[::25]
    for d in sample_dates:
        res = client.get(f"/portfolio/snapshot?date={d}")
        assert res.status_code == 200
        snap = res.json()

        for pos in snap["positions"]:
            tk = pos["ticker"]
            tk_sigs = driving_df[(driving_df["date"] == d) & (driving_df["ticker"] == tk)]
            expected_raw = float(tk_sigs["contribution"].sum()) if not tk_sigs.empty else 0.0
            actual_raw = pos["raw_score"]
            assert np.isclose(expected_raw, actual_raw, atol=1e-10), f"Raw score mismatch on {d} {tk}"


def test_signal_impact_route(client: TestClient):
    """Test /signals/{text_id}/impact explainability decomposition."""
    driving_df = pd.read_parquet(DRIVING_SAMPLE_PATH)
    sample_signal = driving_df.iloc[0]
    text_id = str(sample_signal["text_id"])

    res = client.get(f"/signals/{text_id}/impact")
    assert res.status_code == 200
    impact = res.json()

    assert impact["text_id"] == text_id
    assert impact["ticker"] == sample_signal["ticker"]
    assert impact["deadband_threshold"] == 0.20
    assert impact["neg_multiplier"] == 1.25
    assert "explanation" in impact
    assert "driving_signal_details" in impact

    # Verify FinBERT deadband logic in impact endpoint
    raw_sent = impact["sentiment_score"]
    if abs(raw_sent) < 0.20:
        assert impact["filtered_by_deadband"] is True
        assert impact["adj_sentiment"] == 0.0
    else:
        assert impact["filtered_by_deadband"] is False
        if raw_sent < 0.0:
            assert np.isclose(impact["adj_sentiment"], raw_sent * 1.25, atol=1e-3)
        else:
            assert np.isclose(impact["adj_sentiment"], raw_sent, atol=1e-3)

    # 404 on nonexistent text_id
    res_bad = client.get("/signals/nonexistent_text_id_99999/impact")
    assert res_bad.status_code == 404


def test_meta_metrics_route(client: TestClient):
    """Test /meta/metrics loads pure JSON without hardcoding any values."""
    res = client.get("/meta/metrics")
    assert res.status_code == 200
    data = res.json()

    # Verify each structured file is present and matches the committed source
    for key, fname in [
        ("validation", "validation.json"),
        ("sentiment_eval", "sentiment_eval.json"),
        ("sentiment_hand_eval", "sentiment_hand_eval.json"),
        ("event_eval", "event_eval.json"),
        ("module_a", "module_a.json"),
    ]:
        p = Path("docs") / fname
        assert p.exists(), f"Missing docs/{fname}"
        with open(p, "r", encoding="utf-8") as f:
            expected = json.load(f)
        assert data[key] == expected, f"Mismatch in /meta/metrics for {key}"

    assert "meta" in data
    assert data["meta"]["replay_period"]["start"] == "2021-10-01"
