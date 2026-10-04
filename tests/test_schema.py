"""Tests for schema validation of RiskSignal and EventType."""

from datetime import datetime
import pytest
from pydantic import ValidationError

from src.common.schema import EventType, RiskSignal


def test_valid_risk_signal():
    """Verify that a valid RiskSignal object is created properly."""
    signal = RiskSignal(
        ts=datetime.now(),
        ticker="AAPL",
        source="GDELT",
        text_id="test_001",
        headline="Apple reports record earnings for Q4",
        sentiment_score=0.85,
        event_type=EventType.EARNINGS,
        impact_score=7.5,
        confidence=0.92,
    )
    assert signal.ticker == "AAPL"
    assert signal.sentiment_score == 0.85
    assert signal.event_type == EventType.EARNINGS
    assert signal.impact_score == 7.5
    assert signal.confidence == 0.92


@pytest.mark.parametrize("invalid_sentiment", [-1.5, 1.01, -2.0, 5.0])
def test_sentiment_score_range_validation(invalid_sentiment):
    """Verify sentiment_score is strictly bounded in [-1.0, 1.0]."""
    with pytest.raises(ValidationError):
        RiskSignal(
            ts=datetime.now(),
            ticker="AAPL",
            source="NewsAPI",
            text_id="test_002",
            headline="Sample headline",
            sentiment_score=invalid_sentiment,
            event_type=EventType.MACROECONOMIC,
            impact_score=5.0,
            confidence=0.8,
        )


@pytest.mark.parametrize("invalid_impact", [0.9, 0.0, -1.0, 10.1, 15.0])
def test_impact_score_range_validation(invalid_impact):
    """Verify impact_score is strictly bounded in [1.0, 10.0]."""
    with pytest.raises(ValidationError):
        RiskSignal(
            ts=datetime.now(),
            ticker="AAPL",
            source="NewsAPI",
            text_id="test_003",
            headline="Sample headline",
            sentiment_score=0.0,
            event_type=EventType.MACROECONOMIC,
            impact_score=invalid_impact,
            confidence=0.8,
        )


@pytest.mark.parametrize("invalid_confidence", [-0.1, 1.05, 2.0])
def test_confidence_range_validation(invalid_confidence):
    """Verify confidence is strictly bounded in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        RiskSignal(
            ts=datetime.now(),
            ticker="AAPL",
            source="NewsAPI",
            text_id="test_004",
            headline="Sample headline",
            sentiment_score=0.0,
            event_type=EventType.MACROECONOMIC,
            impact_score=5.0,
            confidence=invalid_confidence,
        )


def test_invalid_event_type():
    """Verify invalid event_type strings are rejected."""
    with pytest.raises(ValidationError):
        RiskSignal(
            ts=datetime.now(),
            ticker="AAPL",
            source="NewsAPI",
            text_id="test_005",
            headline="Sample headline",
            sentiment_score=0.0,
            event_type="InvalidEventCategory",  # type: ignore
            impact_score=5.0,
            confidence=0.8,
        )
