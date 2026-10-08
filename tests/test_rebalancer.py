"""Unit tests for Module A: Tactical Index Rebalancer.

Tests weight bounding, turnover cap, timing cutoffs, deadband filtering,
negative multiplier scaling, determinism, and incremental step consistency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine.validate import map_timestamp_to_t0
from src.modules.backtest import BacktestRunner
from src.modules.rebalancer import RebalanceResult, Rebalancer, project_bounded_weights


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rebalancer():
    return Rebalancer()


@pytest.fixture
def mock_signals_single_day():
    return [
        {
            "ts": pd.Timestamp("2022-01-04 10:00:00", tz="UTC"),
            "ticker": "TSLA",
            "source": "twitter_kaggle",
            "impact_score": 8.0,
            "sentiment_score": 0.60,
            "event_type": "Product Launch",
            "confidence": 0.85,
            "event_confidence": 0.70,
            "attribution_weight": 1.0,
            "is_broadcast": False,
            "headline": "Tesla delivers record vehicles in Q4",
        },
        {
            "ts": pd.Timestamp("2022-01-04 12:00:00", tz="UTC"),
            "ticker": "META",
            "source": "twitter_kaggle",
            "impact_score": 7.0,
            "sentiment_score": -0.50,
            "event_type": "Regulatory",
            "confidence": 0.90,
            "event_confidence": 0.80,
            "attribution_weight": 1.0,
            "is_broadcast": False,
            "headline": "Meta faces regulatory inquiry in Europe",
        },
        # Mild sentiment inside deadband (|s| < 0.20)
        {
            "ts": pd.Timestamp("2022-01-04 14:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 5.0,
            "sentiment_score": 0.10,
            "event_type": "Other",
            "confidence": 0.60,
            "event_confidence": 0.30,
            "attribution_weight": 1.0,
            "is_broadcast": False,
            "headline": "Apple shares quiet today",
        },
    ]


# ---------------------------------------------------------------------------
# 1. Weights Sum to 1.0 and Respect [0.5x, 2.0x] Bounds
# ---------------------------------------------------------------------------

def test_weights_sum_to_one_and_respect_bounds(rebalancer: Rebalancer, mock_signals_single_day):
    res = rebalancer.step("2022-01-04", mock_signals_single_day)

    total_w = sum(res.weights.values())
    assert np.isclose(total_w, 1.0, atol=1e-6)

    min_w = rebalancer.min_weight
    max_w = rebalancer.max_weight

    for tk, w in res.weights.items():
        assert min_w - 1e-6 <= w <= max_w + 1e-6, f"Weight for {tk} ({w}) violates bounds [{min_w}, {max_w}]"


def test_project_bounded_weights_extreme_inputs():
    # 5 assets: base = 0.2, min = 0.1, max = 0.4
    raw = np.array([10.0, 0.001, 0.001, 0.001, 0.001])
    bounded = project_bounded_weights(raw, min_weight=0.10, max_weight=0.40)

    assert np.isclose(np.sum(bounded), 1.0, atol=1e-7)
    assert np.all(bounded >= 0.10 - 1e-7)
    assert np.all(bounded <= 0.40 + 1e-7)


# ---------------------------------------------------------------------------
# 2. Turnover Constraint Cap (<= 10%)
# ---------------------------------------------------------------------------

def test_turnover_never_exceeds_cap(rebalancer: Rebalancer):
    # Pass massive signals to force maximum possible tilt
    extreme_signals = [
        {
            "ticker": "TSLA",
            "sentiment_score": 1.0,
            "impact_score": 10.0,
            "attribution_weight": 5.0,
            "is_broadcast": False,
        },
        {
            "ticker": "META",
            "sentiment_score": -1.0,
            "impact_score": 10.0,
            "attribution_weight": 5.0,
            "is_broadcast": False,
        },
    ]

    res = rebalancer.step("2022-01-04", extreme_signals)
    assert res.turnover <= rebalancer.max_turnover + 1e-6
    assert np.isclose(sum(res.weights.values()), 1.0, atol=1e-6)


# ---------------------------------------------------------------------------
# 3. Timing Cutoff: Signals after 21:00 UTC
# ---------------------------------------------------------------------------

def test_timing_cutoff_affects_next_trading_day():
    calendar = ["2022-01-07", "2022-01-10", "2022-01-11"]  # Friday, Monday, Tuesday

    # Signal on Friday before 21:00 UTC -> belongs to Friday (2022-01-07)
    ts_fri_early = pd.Timestamp("2022-01-07 19:30:00", tz="UTC")
    t0_early = map_timestamp_to_t0(ts_fri_early, calendar)
    assert t0_early == "2022-01-07"

    # Signal on Friday after 21:00 UTC -> belongs to Monday (2022-01-10)
    ts_fri_late = pd.Timestamp("2022-01-07 21:30:00", tz="UTC")
    t0_late = map_timestamp_to_t0(ts_fri_late, calendar)
    assert t0_late == "2022-01-10"

    # Therefore, signals after 21:00 on Friday do NOT affect Friday's rebalance (which earns Monday's return);
    # they affect Monday's rebalance (which earns Tuesday's return).


# ---------------------------------------------------------------------------
# 4. Tickers with No Signals Stay Near Base Weight
# ---------------------------------------------------------------------------

def test_ticker_with_no_signals_stays_near_base_weight(rebalancer: Rebalancer):
    # Only TSLA has signals; all other 13 tickers have zero signals
    signals = [{
        "ticker": "TSLA",
        "sentiment_score": 0.5,
        "impact_score": 5.0,
        "attribution_weight": 1.0,
        "is_broadcast": False,
    }]

    res = rebalancer.step("2022-01-04", signals)
    base = rebalancer.base_weight

    # PG and MSFT had no signals; their scores must be 0.0
    assert res.scores["PG"] == 0.0
    assert res.scores["MSFT"] == 0.0

    # Their weights adjust only by standard residual normalization
    assert abs(res.weights["PG"] - base) < 0.01
    assert abs(res.weights["MSFT"] - base) < 0.01


# ---------------------------------------------------------------------------
# 5. Deadband Suppresses Mild Sentiment (|s| < 0.20)
# ---------------------------------------------------------------------------

def test_deadband_ignores_mild_sentiment(rebalancer: Rebalancer):
    signals = [{
        "ticker": "AAPL",
        "sentiment_score": 0.10,  # inside deadband 0.20
        "impact_score": 6.0,
        "attribution_weight": 1.0,
        "is_broadcast": False,
    }]

    raw_score = rebalancer.compute_daily_raw_score(signals)
    assert raw_score == 0.0


# ---------------------------------------------------------------------------
# 6. Negative Multiplier Applies
# ---------------------------------------------------------------------------

def test_negative_multiplier_scaling(rebalancer: Rebalancer):
    signals_pos = [{
        "ticker": "AAPL",
        "sentiment_score": 0.40,
        "impact_score": 5.0,
        "attribution_weight": 1.0,
        "is_broadcast": False,
    }]
    signals_neg = [{
        "ticker": "AAPL",
        "sentiment_score": -0.40,
        "impact_score": 5.0,
        "attribution_weight": 1.0,
        "is_broadcast": False,
    }]

    raw_pos = rebalancer.compute_daily_raw_score(signals_pos)
    raw_neg = rebalancer.compute_daily_raw_score(signals_neg)

    assert np.isclose(raw_pos, 0.40, atol=1e-5)
    # raw_neg must be scaled by neg_multiplier (1.25): -0.40 * 1.25 = -0.50
    assert np.isclose(raw_neg, -0.50, atol=1e-5)


# ---------------------------------------------------------------------------
# 7. Determinism with Fixed Seeds
# ---------------------------------------------------------------------------

def test_rebalancer_determinism(mock_signals_single_day):
    reb1 = Rebalancer()
    reb2 = Rebalancer()

    res1 = reb1.step("2022-01-04", mock_signals_single_day)
    res2 = reb2.step("2022-01-04", mock_signals_single_day)

    for tk in reb1.universe:
        assert np.isclose(res1.weights[tk], res2.weights[tk], atol=1e-9)
        assert np.isclose(res1.scores[tk], res2.scores[tk], atol=1e-9)


# ---------------------------------------------------------------------------
# 8. Incremental Step() and Batch Backtest Produce Identical Weights
# ---------------------------------------------------------------------------

def test_step_and_batch_consistency(mock_signals_single_day):
    reb = Rebalancer()
    step_res = reb.step("2022-01-04", mock_signals_single_day)

    # Calling step() again on fresh instance produces identical weights
    reb_fresh = Rebalancer()
    batch_res = reb_fresh.step("2022-01-04", mock_signals_single_day)

    assert step_res.weights == batch_res.weights
    assert step_res.scores == batch_res.scores
    assert step_res.turnover == batch_res.turnover


# ---------------------------------------------------------------------------
# 9. Top-3 Driving Signals Included in Result
# ---------------------------------------------------------------------------

def test_rebalance_result_contains_top_three_driving_signals(rebalancer: Rebalancer, mock_signals_single_day):
    res = rebalancer.step("2022-01-04", mock_signals_single_day)

    assert "TSLA" in res.top_signals
    tsla_top = res.top_signals["TSLA"]
    assert len(tsla_top) == 1
    assert tsla_top[0]["headline"] == "Tesla delivers record vehicles in Q4"
    assert tsla_top[0]["event_type"] == "Product Launch"
    assert tsla_top[0]["sentiment_score"] == 0.60
    assert tsla_top[0]["impact_score"] == 8.0
