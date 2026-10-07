"""Unit tests for signal validation and event study module (src/engine/validate.py).

Tests market timing mapping, no look-ahead return computations, ticker-day
aggregation, confound controls, and statistical estimation.
"""

from __future__ import annotations

from datetime import datetime, time
import numpy as np
import pandas as pd
import pytest

from src.engine.validate import (
    align_signals_with_calendar,
    aggregate_to_ticker_day,
    block_bootstrap_ci,
    build_trading_calendar,
    compute_stock_returns,
    map_timestamp_to_t0,
    partial_spearman_corr,
    run_evaluation_suite,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_calendar() -> list[str]:
    # Two weeks of trading days: Mon-Fri for 2022-01-03 to 2022-01-14
    return [
        "2022-01-03", "2022-01-04", "2022-01-05", "2022-01-06", "2022-01-07",  # Week 1
        "2022-01-10", "2022-01-11", "2022-01-12", "2022-01-13", "2022-01-14",  # Week 2
    ]


@pytest.fixture
def mock_prices_df(mock_calendar: list[str]) -> pd.DataFrame:
    records = []
    # SPY: steady 1% daily gain
    spy_p = 100.0
    for d in mock_calendar:
        records.append({
            "date": d,
            "ticker": "SPY",
            "open": spy_p,
            "high": spy_p * 1.01,
            "low": spy_p * 0.99,
            "close": spy_p,
            "adj_close": spy_p,
            "volume": 1000000,
        })
        spy_p *= 1.01

    # AAPL: alternating +3% and -1%
    aapl_p = 150.0
    for i, d in enumerate(mock_calendar):
        records.append({
            "date": d,
            "ticker": "AAPL",
            "open": aapl_p,
            "high": aapl_p * 1.02,
            "low": aapl_p * 0.98,
            "close": aapl_p,
            "adj_close": aapl_p,
            "volume": 500000,
        })
        factor = 1.03 if i % 2 == 0 else 0.99
        aapl_p *= factor

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 1. Timing & Calendar Tests
# ---------------------------------------------------------------------------

def test_build_trading_calendar(mock_prices_df: pd.DataFrame, mock_calendar: list[str]) -> None:
    cal = build_trading_calendar(mock_prices_df)
    assert cal == mock_calendar
    assert len(cal) == 10
    assert cal[0] == "2022-01-03"


def test_map_timestamp_to_t0(mock_calendar: list[str]) -> None:
    # Friday 2022-01-07 at 15:00 UTC -> before 21:00 UTC -> Friday 2022-01-07
    ts1 = pd.Timestamp("2022-01-07 15:00:00", tz="UTC")
    assert map_timestamp_to_t0(ts1, mock_calendar) == "2022-01-07"

    # Friday 2022-01-07 at 21:30 UTC -> after 21:00 UTC -> Saturday -> next trading day is Monday 2022-01-10
    ts2 = pd.Timestamp("2022-01-07 21:30:00", tz="UTC")
    assert map_timestamp_to_t0(ts2, mock_calendar) == "2022-01-10"

    # Saturday 2022-01-08 at 12:00 UTC -> weekend -> Monday 2022-01-10
    ts3 = pd.Timestamp("2022-01-08 12:00:00", tz="UTC")
    assert map_timestamp_to_t0(ts3, mock_calendar) == "2022-01-10"

    # Sunday 2022-01-09 at 22:00 UTC -> after 21:00 UTC -> Monday 2022-01-10
    ts4 = pd.Timestamp("2022-01-09 22:00:00", tz="UTC")
    assert map_timestamp_to_t0(ts4, mock_calendar) == "2022-01-10"

    # Wednesday 2022-01-05 at 20:59:59 UTC -> Wednesday 2022-01-05
    ts5 = pd.Timestamp("2022-01-05 20:59:59", tz="UTC")
    assert map_timestamp_to_t0(ts5, mock_calendar) == "2022-01-05"

    # Wednesday 2022-01-05 at 21:00:00 UTC -> Thursday 2022-01-06
    ts6 = pd.Timestamp("2022-01-05 21:00:00", tz="UTC")
    assert map_timestamp_to_t0(ts6, mock_calendar) == "2022-01-06"

    # Timestamp after the end of the calendar returns None
    ts_future = pd.Timestamp("2022-01-20 10:00:00", tz="UTC")
    assert map_timestamp_to_t0(ts_future, mock_calendar) is None


# ---------------------------------------------------------------------------
# 2. Return Calculation & No Look-Ahead Guarantee
# ---------------------------------------------------------------------------

def test_compute_stock_returns_simple_and_no_lookahead(mock_prices_df: pd.DataFrame) -> None:
    returns_df = compute_stock_returns(mock_prices_df)

    # Check columns
    assert "ret" in returns_df.columns
    assert "spy_ret" in returns_df.columns
    assert "ar" in returns_df.columns
    assert "trailing_vol_20" in returns_df.columns

    # Check simple return formula for day 2: (P1 - P0) / P0
    spy_day0 = mock_prices_df[(mock_prices_df["ticker"] == "SPY") & (mock_prices_df["date"] == "2022-01-03")]["adj_close"].values[0]
    spy_day1 = mock_prices_df[(mock_prices_df["ticker"] == "SPY") & (mock_prices_df["date"] == "2022-01-04")]["adj_close"].values[0]
    expected_spy_ret = (spy_day1 - spy_day0) / spy_day0

    calc_spy_ret = returns_df[(returns_df["ticker"] == "SPY") & (returns_df["date"] == "2022-01-04")]["ret"].values[0]
    assert np.isclose(calc_spy_ret, expected_spy_ret, atol=1e-6)

    # Check abnormal return definition: AR = R_i - R_spy
    aapl_ret = returns_df[(returns_df["ticker"] == "AAPL") & (returns_df["date"] == "2022-01-04")]["ret"].values[0]
    aapl_spy_ret = returns_df[(returns_df["ticker"] == "AAPL") & (returns_df["date"] == "2022-01-04")]["spy_ret"].values[0]
    aapl_ar = returns_df[(returns_df["ticker"] == "AAPL") & (returns_df["date"] == "2022-01-04")]["ar"].values[0]
    assert np.isclose(aapl_ar, aapl_ret - aapl_spy_ret, atol=1e-6)

    # No look-ahead test: verify that changing the price on date t does NOT change trailing_vol_20 on date t
    modified_prices = mock_prices_df.copy()
    row_idx = (modified_prices["ticker"] == "AAPL") & (modified_prices["date"] == "2022-01-07")
    orig_vol = returns_df.loc[(returns_df["ticker"] == "AAPL") & (returns_df["date"] == "2022-01-07"), "trailing_vol_20"].values[0]

    # Extreme price spike on day t
    modified_prices.loc[row_idx, "adj_close"] *= 5.0
    new_returns_df = compute_stock_returns(modified_prices)
    new_vol = new_returns_df.loc[(new_returns_df["ticker"] == "AAPL") & (new_returns_df["date"] == "2022-01-07"), "trailing_vol_20"].values[0]

    # Because trailing_vol_20 strictly uses shift(1), day t price modification must NOT alter day t trailing vol
    if not np.isnan(orig_vol):
        assert np.isclose(orig_vol, new_vol, atol=1e-7)


# ---------------------------------------------------------------------------
# 3. Signal Filtering & Window Availability
# ---------------------------------------------------------------------------

def test_align_signals_with_calendar_forward_window(mock_calendar: list[str]) -> None:
    # 10 trading days: index 0 to 9. Max valid t0_idx for 3-day window [t0, t0+1, t0+2] is 7 (2022-01-12)
    # Day 8 (2022-01-13) only has t0+1 (2022-01-14), missing t0+2 -> must be dropped
    # Day 9 (2022-01-14) lacks both t0+1 and t0+2 -> must be dropped
    signals = pd.DataFrame([
        {
            "ts": pd.Timestamp("2022-01-04 14:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 4.5,
            "sentiment_score": 0.5,
            "event_type": "Earnings",
            "confidence": 0.8,
            "event_confidence": 0.6,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
        # Broadcast signal -> excluded
        {
            "ts": pd.Timestamp("2022-01-04 14:30:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 5.0,
            "sentiment_score": -0.2,
            "event_type": "Other",
            "confidence": 0.7,
            "event_confidence": 0.5,
            "attribution_weight": 1.0,
            "is_broadcast": True,
        },
        # MARKET signal -> excluded from stock analysis
        {
            "ts": pd.Timestamp("2022-01-04 15:00:00", tz="UTC"),
            "ticker": "MARKET",
            "source": "gdelt",
            "impact_score": 6.0,
            "sentiment_score": -0.4,
            "event_type": "Macroeconomic",
            "confidence": 0.8,
            "event_confidence": 0.7,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
        # Valid signal on 2022-01-12 (index 7: forward window 7, 8, 9 is fully in calendar)
        {
            "ts": pd.Timestamp("2022-01-12 10:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 3.8,
            "sentiment_score": -0.6,
            "event_type": "Regulatory",
            "confidence": 0.85,
            "event_confidence": 0.7,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
        # Incomplete forward window signal on 2022-01-13 (index 8: missing t0+2) -> dropped
        {
            "ts": pd.Timestamp("2022-01-13 10:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 4.0,
            "sentiment_score": 0.1,
            "event_type": "Other",
            "confidence": 0.6,
            "event_confidence": 0.4,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
    ])

    aligned, audit = align_signals_with_calendar(signals, mock_calendar)

    assert audit["total_raw_signals"] == 5
    assert audit["broadcast_excluded"] == 1
    assert audit["market_excluded"] == 1
    assert audit["stock_signals_evaluated"] == 3
    assert audit["dropped_missing_fwd_window"] == 1
    assert audit["retained_signals"] == 2
    assert len(aligned) == 2


# ---------------------------------------------------------------------------
# 4. Ticker-Day Aggregation Logic
# ---------------------------------------------------------------------------

def test_aggregate_to_ticker_day(mock_prices_df: pd.DataFrame, mock_calendar: list[str]) -> None:
    returns_df = compute_stock_returns(mock_prices_df)

    # 3 signals for AAPL on the same day (2022-01-04)
    signals = pd.DataFrame([
        {
            "ts": pd.Timestamp("2022-01-04 10:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 3.0,
            "sentiment_score": -0.8,
            "event_type": "Earnings",
            "confidence": 0.9,
            "event_confidence": 0.8,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
        {
            "ts": pd.Timestamp("2022-01-04 12:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "twitter_kaggle",
            "impact_score": 7.5,
            "sentiment_score": -0.4,
            "event_type": "Earnings",
            "confidence": 0.8,
            "event_confidence": 0.6,
            "attribution_weight": 2.0,
            "is_broadcast": False,
        },
        {
            "ts": pd.Timestamp("2022-01-04 14:00:00", tz="UTC"),
            "ticker": "AAPL",
            "source": "newsapi",
            "impact_score": 5.2,
            "sentiment_score": 0.2,
            "event_type": "Other",
            "confidence": 0.7,
            "event_confidence": 0.4,
            "attribution_weight": 1.0,
            "is_broadcast": False,
        },
    ])

    aligned, _ = align_signals_with_calendar(signals, mock_calendar)
    td = aggregate_to_ticker_day(aligned, returns_df, mock_calendar)

    assert len(td) == 1
    row = td.iloc[0]

    # Max impact must be 7.5
    assert row["max_impact_score"] == 7.5

    # Attribution-weighted mean sentiment:
    # weights: 1.0, 2.0, 1.0 (sum = 4.0)
    # (-0.8 * 1.0 + -0.4 * 2.0 + 0.2 * 1.0) / 4.0 = (-0.8 - 0.8 + 0.2) / 4.0 = -1.4 / 4.0 = -0.35
    assert np.isclose(row["mean_sentiment_score"], -0.35, atol=1e-5)

    # Dominant event must be Earnings (2 vs 1)
    assert row["dominant_event_type"] == "Earnings"
    assert row["signal_count"] == 3
    assert "newsapi" in row["sources"] and "twitter_kaggle" in row["sources"]

    # Sentiment bucket must be Negative (< -0.2)
    assert row["sent_bucket"] == "Negative"

    # CAR(0, 2) must equal AR0 + AR1 + AR2
    assert np.isclose(row["car_0_2"], row["ar0"] + row["ar1"] + row["ar2"], atol=1e-6)


# ---------------------------------------------------------------------------
# 5. Statistical Estimation & Bootstrap
# ---------------------------------------------------------------------------

def test_partial_spearman_corr() -> None:
    # Create x, y driven by z (confounder)
    rng = np.random.default_rng(42)
    z = rng.standard_normal(200)
    x = 0.8 * z + 0.2 * rng.standard_normal(200)
    y = 0.8 * z + 0.2 * rng.standard_normal(200)

    # Raw correlation between x and y is high
    from scipy import stats
    raw_rho = stats.spearmanr(x, y)[0]
    assert raw_rho > 0.5

    # Partial correlation controlling for z removes spurious link
    part_rho = partial_spearman_corr(x, y, z)
    assert abs(part_rho) < 0.2


def test_block_bootstrap_ci() -> None:
    df = pd.DataFrame({
        "week": ["W1"] * 50 + ["W2"] * 50 + ["W3"] * 50 + ["W4"] * 50,
        "val": np.linspace(10.0, 20.0, 200),
    })

    def mean_fn(d: pd.DataFrame) -> float:
        return float(d["val"].mean())

    point, low, high = block_bootstrap_ci(df, mean_fn, block_col="week", n_boot=500, seed=42)
    assert low <= point <= high
    assert 10.0 <= low <= 20.0
    assert 10.0 <= high <= 20.0


def test_run_evaluation_suite_placebo() -> None:
    # Synthetic ticker-day dataset
    rng = np.random.default_rng(123)
    n = 100
    df = pd.DataFrame({
        "ticker": ["AAPL"] * 50 + ["MSFT"] * 50,
        "t0": ["2022-01-04"] * 50 + ["2022-01-05"] * 50,
        "week": ["2022-01"] * 100,
        "max_impact_score": rng.uniform(1.0, 9.0, n),
        "mean_sentiment_score": rng.uniform(-0.8, 0.8, n),
        "weighted_sentiment_confidence": rng.uniform(0.6, 0.95, n),
        "dominant_event_type": rng.choice(["Earnings", "Other", "Regulatory"], n),
        "ar0": rng.normal(0, 0.02, n),
        "abs_ar0": rng.uniform(0.005, 0.05, n),
        "ar1": rng.normal(0, 0.02, n),
        "car_0_2": rng.normal(0, 0.04, n),
        "abs_car_0_2": rng.uniform(0.01, 0.08, n),
        "trailing_vol_20": rng.uniform(0.01, 0.03, n),
        "sent_bucket": rng.choice(["Negative", "Neutral", "Positive"], n),
    })

    res = run_evaluation_suite(df, "synthetic_test", n_boot=200, seed=42)

    assert res["n_observations"] == 100
    assert "spearman" in res
    assert "quintiles" in res
    assert "sentiment_direction" in res
    assert "placebo_test" in res
    assert res["placebo_test"]["n_permutations"] == 1000
    assert 0.0 <= res["placebo_test"]["empirical_p_value"] <= 1.0
