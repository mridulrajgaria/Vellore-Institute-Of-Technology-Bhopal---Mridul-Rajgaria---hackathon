"""Unit tests for ImpactScorer: bounds, weights validation, monotonicity, and volume signal rules."""

import pandas as pd
import pytest

from src.engine.impact_scorer import ImpactScorer


@pytest.fixture
def scorer():
    return ImpactScorer()


def test_impact_score_bounds(scorer):
    """Verify that impact score is always bounded strictly between 1.0 and 10.0."""
    # Extreme low
    res_low = scorer.compute_impact("Other", sentiment_score=0.0, source="twitter_kaggle", volume_signal=0.0)
    assert 1.0 <= res_low["impact_score"] <= 10.0
    assert res_low["impact_score"] >= 1.0

    # Extreme high
    res_high = scorer.compute_impact("Credit Event", sentiment_score=-1.0, source="newsapi", volume_signal=1.0)
    assert 1.0 <= res_high["impact_score"] <= 10.0
    assert res_high["impact_score"] <= 10.0


def test_weights_sum_validation(tmp_path):
    """Verify that weights not summing to 1.0 raise a ValueError upon initialization."""
    bad_cfg = tmp_path / "bad_engine.yaml"
    bad_cfg.write_text(
        """
impact_scoring:
  weights:
    w_sev: 0.50
    w_sent: 0.50
    w_src: 0.20
    w_vol: 0.10
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Impact weights must sum to 1.0"):
        ImpactScorer(config_path=str(bad_cfg))


def test_monotonicity_in_severity(scorer):
    """Higher event severity must yield higher or equal impact score."""
    res_other = scorer.compute_impact("Other", sentiment_score=0.5, source="newsapi", volume_signal=0.5)
    res_earn = scorer.compute_impact("Earnings", sentiment_score=0.5, source="newsapi", volume_signal=0.5)
    res_credit = scorer.compute_impact("Credit Event", sentiment_score=0.5, source="newsapi", volume_signal=0.5)

    assert res_other["impact_score"] < res_earn["impact_score"]
    assert res_earn["impact_score"] < res_credit["impact_score"]


def test_monotonicity_in_sentiment_extremity(scorer):
    """Higher absolute sentiment must yield higher or equal impact score."""
    res_neu = scorer.compute_impact("Regulatory", sentiment_score=0.0, source="newsapi", volume_signal=0.5)
    res_mid = scorer.compute_impact("Regulatory", sentiment_score=-0.5, source="newsapi", volume_signal=0.5)
    res_ext = scorer.compute_impact("Regulatory", sentiment_score=1.0, source="newsapi", volume_signal=0.5)

    assert res_neu["impact_score"] < res_mid["impact_score"]
    assert res_mid["impact_score"] < res_ext["impact_score"]


def test_monotonicity_in_source_weight(scorer):
    """Higher source credibility must yield higher or equal impact score."""
    res_tw = scorer.compute_impact("Geopolitical", sentiment_score=0.5, source="twitter_kaggle", volume_signal=0.5)
    res_gd = scorer.compute_impact("Geopolitical", sentiment_score=0.5, source="gdelt", volume_signal=0.5)
    res_news = scorer.compute_impact("Geopolitical", sentiment_score=0.5, source="newsapi", volume_signal=0.5)

    assert res_tw["impact_score"] < res_gd["impact_score"]
    assert res_gd["impact_score"] < res_news["impact_score"]


def test_tweet_volume_signal_trailing_only_and_no_dup_count(scorer):
    """Verify that tweet volume uses only prior trailing days, ignores dup_count, and falls back when < 7 days."""
    # Synthetic tweet history spanning 40 days
    dates = pd.date_range("2026-01-01", periods=40, freq="D", tz="UTC")
    # Base 10 tweets per day
    history_records = []
    for d in dates:
        # Day 39 has a massive spike of 100 tweets
        count = 100 if d == dates[39] else 10
        for _ in range(count):
            history_records.append({"ticker_hint": "TSLA", "ts": d})

    df_hist = pd.DataFrame(history_records)
    scorer.fit_tweet_volume_history(df_hist)

    # 1. Fallback when less than 7 days of trailing history available
    early_ts = dates[3]
    vol_early = scorer.compute_volume_signal("twitter_kaggle", dup_count=50, ticker="TSLA", ts=early_ts)
    assert vol_early == 0.5  # < 7 days history triggers 0.5 fallback

    # 2. Strict trailing: on spike day (dates[39]), volume signal should be high (> 0.5)
    spike_ts = dates[39]
    vol_spike = scorer.compute_volume_signal("twitter_kaggle", dup_count=1, ticker="TSLA", ts=spike_ts)
    assert vol_spike > 0.8

    # 3. dup_count is strictly ignored for tweets: varying dup_count produces identical volume_signal
    vol_dup1 = scorer.compute_volume_signal("twitter_kaggle", dup_count=1, ticker="TSLA", ts=spike_ts)
    vol_dup99 = scorer.compute_volume_signal("twitter_kaggle", dup_count=99, ticker="TSLA", ts=spike_ts)
    assert vol_dup1 == vol_dup99
