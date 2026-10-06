"""Unit tests for RiskEngine: emission rules, broadcast attribution, and dataset exclusion."""

from datetime import datetime
import pandas as pd
import pytest

from src.common.schema import EventType
from src.engine.risk_engine import RiskEngine


@pytest.fixture
def engine():
    return RiskEngine()


def test_emission_single_company_signal(engine):
    """Verify single company text emits exactly one RiskSignal with attribution_weight = 1.0."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "single_001",
        "source": "newsapi",
        "text": "Apple reports strong iPhone sales for Q3",
        "primary_ticker": "AAPL",
        "linked_tickers": ["AAPL"],
        "is_relevant": True,
        "is_broadcast": False,
        "sentiment_score": 0.8,
        "sentiment_confidence": 0.9,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 1
    sig = signals[0]
    assert sig.ticker == "AAPL"
    assert sig.attribution_weight == 1.0
    assert not sig.is_broadcast
    assert sig.event_type == EventType.EARNINGS


def test_emission_broadcast_tweet_splits_signals_and_weights(engine):
    """Verify broadcast tweet with 3 linked tickers and high-confidence event emits 3 signals with attribution_weight = 1/3."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "broadcast_001",
        "source": "twitter_kaggle",
        "text": "Quarterly earnings report and guidance released for $AAPL, $MSFT, and $AMZN",
        "primary_ticker": None,
        "linked_tickers": ["AAPL", "MSFT", "AMZN"],
        "is_relevant": True,
        "is_broadcast": True,
        "sentiment_score": 0.6,
        "sentiment_confidence": 0.85,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 3
    tickers = {s.ticker for s in signals}
    assert tickers == {"AAPL", "MSFT", "AMZN"}
    for sig in signals:
        assert pytest.approx(sig.attribution_weight, abs=1e-3) == 1.0 / 3.0
        assert sig.is_broadcast is True
        assert sig.text_id == "broadcast_001"
        assert sig.event_type == EventType.EARNINGS


def test_broadcast_tweet_other_or_low_conf_emits_nothing(engine):
    """Verify broadcast tweet with 6 tickers and Other/low confidence emits 0 signals."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "broadcast_spam_001",
        "source": "twitter_kaggle",
        "text": "Most Anticipated Releases this week ... $AAPL $AMZN $BA $GOOGL $KO $META",
        "primary_ticker": None,
        "linked_tickers": ["AAPL", "AMZN", "BA", "GOOGL", "KO", "META"],
        "is_relevant": True,
        "is_broadcast": True,
        "sentiment_score": 0.1,
        "sentiment_confidence": 0.5,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 0


def test_template_tweet_is_filtered_out(engine):
    """Verify tweets matching template spam patterns (#stickynote, Good morning TRADERS) emit nothing."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "template_001",
        "source": "twitter_kaggle",
        "text": "Good morning TRADERS ... #stickynote pls retweet ... $AAPL $AMZN",
        "primary_ticker": "AAPL",
        "linked_tickers": ["AAPL", "AMZN"],
        "is_relevant": True,
        "is_broadcast": False,
        "sentiment_score": 0.2,
        "sentiment_confidence": 0.8,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 0


def test_scrape_hint_only_emission_rules(engine):
    """Verify scrape hint ticker is only emitted when link_type is hint_only with a single scrape label."""
    # Case 1: single hint_only emits
    df_single = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "hint_001",
        "source": "twitter_kaggle",
        "text": "General discussion about quarterly results without direct company name mention",
        "primary_ticker": None,
        "linked_tickers": [],
        "ticker_hint": "AAPL",
        "ticker_hints": ["AAPL"],
        "link_type": "hint_only",
        "is_relevant": True,
        "is_broadcast": False,
        "sentiment_score": 0.3,
        "sentiment_confidence": 0.8,
    }])
    signals_single = engine.process_texts_to_signals(df_single, fit_volume_history=False)
    assert len(signals_single) == 1
    assert signals_single[0].ticker == "AAPL"

    # Case 2: multiple hints with no text evidence emits nothing
    df_multi = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "hint_002",
        "source": "twitter_kaggle",
        "text": "General discussion without direct company name mention",
        "primary_ticker": None,
        "linked_tickers": [],
        "ticker_hint": "AAPL",
        "ticker_hints": ["AAPL", "MSFT"],
        "link_type": "hint_only",
        "is_relevant": True,
        "is_broadcast": False,
        "sentiment_score": 0.3,
        "sentiment_confidence": 0.8,
    }])
    signals_multi = engine.process_texts_to_signals(df_multi, fit_volume_history=False)
    assert len(signals_multi) == 0


def test_emission_market_row_emits_market_ticker(engine):
    """Verify MARKET row emits ticker 'MARKET' with attribution_weight = 1.0."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "market_001",
        "source": "gdelt",
        "text": "Federal Reserve leaves benchmark interest rates unchanged following FOMC meeting",
        "primary_ticker": "MARKET",
        "linked_tickers": ["MARKET"],
        "is_relevant": True,
        "is_broadcast": False,
        "sentiment_score": 0.0,
        "sentiment_confidence": 0.9,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 1
    sig = signals[0]
    assert sig.ticker == "MARKET"
    assert sig.attribution_weight == 1.0
    assert not sig.is_broadcast
    assert sig.event_type == EventType.MACROECONOMIC


def test_financial_phrasebank_strictly_excluded(engine):
    """Verify rows from financial_phrasebank are never emitted as RiskSignals."""
    df = pd.DataFrame([
        {
            "ts": datetime.now(),
            "text_id": "fpb_001",
            "source": "financial_phrasebank",
            "text": "Operating profit increased by 15%",
            "primary_ticker": "AAPL",
            "linked_tickers": ["AAPL"],
            "is_relevant": True,
            "sentiment_score": 0.7,
        },
        {
            "ts": datetime.now(),
            "text_id": "news_001",
            "source": "newsapi",
            "text": "Tesla announces new factory expansion",
            "primary_ticker": "TSLA",
            "linked_tickers": ["TSLA"],
            "is_relevant": True,
            "sentiment_score": 0.5,
        },
    ])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 1
    assert signals[0].text_id == "news_001"
    assert signals[0].source == "newsapi"


def test_judge_allows_lawsuit_over_united_window_seat_no_msft_link(engine):
    """Verify headline with generic 'window/windows' word is not linked or emitted for MSFT."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "window_001",
        "source": "gdelt",
        "title": "Judge Allows Lawsuit Over United Window Seat Without Windows To Proceed",
        "text": "Judge Allows Lawsuit Over United Window Seat Without Windows To Proceed",
        "primary_ticker": None,
        "linked_tickers": [],
        "ticker_hint": "BA",
        "is_relevant": True,
        "sentiment_score": -0.5,
        "sentiment_confidence": 0.8,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    # Must NOT emit any MSFT signal
    assert all(s.ticker != "MSFT" for s in signals)


def test_calendar_schedule_emits_nothing(engine):
    """Verify that multi-ticker earnings calendar tweets emit zero signals even with high confidence."""
    df = pd.DataFrame([{
        "ts": datetime.now(),
        "text_id": "cal_001",
        "source": "twitter_kaggle",
        "text": "Upcoming Earnings Report - Week of October 25th $XOM $AAPL $AMZN $KO $BA $MSFT",
        "primary_ticker": None,
        "linked_tickers": ["XOM", "AAPL", "AMZN", "KO", "BA", "MSFT"],
        "is_relevant": True,
        "is_broadcast": True,
        "sentiment_score": 0.5,
        "sentiment_confidence": 0.9,
    }])

    signals = engine.process_texts_to_signals(df, fit_volume_history=False)
    assert len(signals) == 0
