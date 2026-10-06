"""Unit tests for rules-based event classifier using real financial headlines and synthetic credit fixtures."""

import pytest

from src.common.schema import EventType
from src.nlp.event_classifier import EventClassifier


@pytest.fixture
def classifier():
    return EventClassifier()


def test_real_headline_merger_acquisition_buyout(classifier):
    headline = "PayPal Stock Surges on $53 Billion Stripe-Advent Buyout Bid"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.MERGER_ACQUISITION.value
    assert res["confidence"] >= 0.8
    assert any("buyout" in t.lower() for t in res["matched_triggers"])


def test_real_headline_merger_acquisition_block_suit(classifier):
    headline = "California sues to block $110B Paramount-Warner Bros. merger"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.MERGER_ACQUISITION.value
    assert res["confidence"] >= 0.8
    assert any("merger" in t.lower() for t in res["matched_triggers"])
    assert res["secondary_event"] == EventType.REGULATORY.value


def test_real_headline_geopolitical_sanctions(classifier):
    headline = "UAE central bank imposes strict sanctions on Bank Melli Iran branches"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.GEOPOLITICAL.value
    assert res["confidence"] >= 0.8
    assert any("sanctions" in t.lower() for t in res["matched_triggers"])


def test_real_headline_regulatory_lawsuit(classifier):
    headline = "Apple Faces $32.5 Billion Lawsuit Over Facial Recognition in iPhone Photos App"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.REGULATORY.value
    assert res["confidence"] >= 0.8
    assert any("lawsuit" in t.lower() for t in res["matched_triggers"])


def test_real_headline_regulatory_sue_regulator(classifier):
    headline = "Disney and ABC sue Trump media regulator to stop early licence renewal"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.REGULATORY.value
    assert res["confidence"] >= 0.8
    assert any(term in [t.lower() for t in res["matched_triggers"]] for term in ["sue", "regulator", "licence renewal"])


def test_real_headline_earnings_report(classifier):
    headline = "Goldman Sachs Reports Earnings on July 14. Can Its Investment Banking Surge Keep Going?"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.EARNINGS.value
    assert res["confidence"] >= 0.8
    assert any("reports earnings" in t.lower() or "earnings" in t.lower() for t in res["matched_triggers"])


def test_real_headline_macroeconomic_cpi(classifier):
    headline = "How the market may react to July CPI report, according to JPMorgan"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.MACROECONOMIC.value
    assert res["confidence"] >= 0.8
    assert any("cpi" in t.lower() for t in res["matched_triggers"])


def test_real_headline_product_launch_cybercab(classifier):
    headline = "Tesla's Cybercab had a rocky first month in Austin"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.PRODUCT_LAUNCH.value
    assert res["confidence"] >= 0.8
    assert any("cybercab" in t.lower() for t in res["matched_triggers"])


# ==============================================================================
# SYNTHETIC FIXTURES: Credit Event
# ==============================================================================

def test_synthetic_credit_event_moodys_junk(classifier):
    # SYNTHETIC FIXTURE: Credit rating agency downgrade to junk
    headline = "Moody's downgrades Boeing to junk"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.CREDIT_EVENT.value
    assert res["confidence"] >= 0.8
    assert res["is_analyst_action"] is False


def test_synthetic_credit_event_chapter_11(classifier):
    # SYNTHETIC FIXTURE: Corporate bankruptcy filing
    headline = "Company files for Chapter 11 bankruptcy"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.CREDIT_EVENT.value
    assert res["confidence"] >= 0.8
    assert res["is_analyst_action"] is False


def test_synthetic_credit_event_missed_bond_payment(classifier):
    # SYNTHETIC FIXTURE: Missed bond coupon payment
    headline = "Troubled developer fails to pay bond coupon payment ahead of grace period deadline"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.CREDIT_EVENT.value
    assert res["confidence"] >= 0.8


def test_brokerage_analyst_downgrade_is_earnings_not_credit(classifier):
    """Equity brokerage downgrade is an analyst action in Earnings, NOT a credit event."""
    headline = "JPMORGAN downgrades $NFLX to Neutral and slashes price target in half"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.EARNINGS.value
    assert res["is_analyst_action"] is True
    assert "analyst_action" in res["matched_triggers"]


def test_price_target_upgrade_is_earnings_analyst_action(classifier):
    """Price target upgrades belong to Earnings with analyst_action true."""
    headline = "$KO price target has been upgraded to a high of $72"
    res = classifier.classify(headline)
    assert res["event_type"] == EventType.EARNINGS.value
    assert res["is_analyst_action"] is True
    assert "analyst_action" in res["matched_triggers"]


def test_template_spam_detection(classifier):
    """Template and spam tweets are identified with is_template=True."""
    tweet = "Good morning TRADERS ... #stickynote pls retweet ... $AAPL"
    res = classifier.classify(tweet, source="twitter_kaggle")
    assert res["is_template"] is True


def test_hypothetical_tweet_confidence_cap(classifier):
    """Hypothetical or speculative tweets on Twitter have confidence capped at 0.60."""
    tweet = "Pretty sure the next step for $AAPL is bankruptcy."
    res = classifier.classify(tweet, source="twitter_kaggle")
    assert res["confidence"] <= 0.60


def test_real_credit_distress_speculation_jokes_excluded(classifier):
    """Bare bankruptcy in jokes, history, or speculation must not be classified as Credit Event."""
    t1 = "You would think $PYPL is going bankrupt with this pre-mkt action lol"
    assert classifier.classify(t1, source="twitter_kaggle")["event_type"] != EventType.CREDIT_EVENT.value

    t2 = "I think $TSLA will be the largest bankruptcy filing in history"
    assert classifier.classify(t2, source="twitter_kaggle")["event_type"] != EventType.CREDIT_EVENT.value

    t3 = "Elon Musk: America is 1,000% going to go bankrupt"
    assert classifier.classify(t3, source="twitter_kaggle")["event_type"] != EventType.CREDIT_EVENT.value

    t4 = "Gouging at the Boeing credit default swap desk shall be vigorously investigated!"
    assert classifier.classify(t4, source="twitter_kaggle")["event_type"] != EventType.CREDIT_EVENT.value


def test_geopolitical_triggers_and_actor_requirements(classifier):
    """Geopolitical trigger word alone or opinion chatter must not trigger Geopolitical."""
    # Class name alone without event word -> Other
    t1 = "Futures just turned around lower. Must be another Geopolitical headline brewing again. $TSLA"
    assert classifier.classify(t1, source="twitter_kaggle")["event_type"] == EventType.OTHER.value

    # National Security Systems style phrase must not trigger Geopolitical
    t2 = "One competitive advantage PLTR has over SNOW and $GOOG is that they are authorized for Mission Critical National Security Systems (IL5) by the U.S. Department of Defense"
    assert classifier.classify(t2, source="twitter_kaggle")["event_type"] != EventType.GEOPOLITICAL.value

    # Real event words with named actors -> Geopolitical
    t3 = "Russia sanctions Mark Zuckerberg of $FB."
    res3 = classifier.classify(t3, source="twitter_kaggle")
    assert res3["event_type"] == EventType.GEOPOLITICAL.value
    assert res3["confidence"] >= 0.8

    t4 = "UAE central bank imposes strict sanctions on Bank Melli Iran branches"
    res4 = classifier.classify(t4, source="gdelt")
    assert res4["event_type"] == EventType.GEOPOLITICAL.value
    assert res4["confidence"] >= 0.8


def test_calendar_table_list_filter(classifier):
    """Calendar schedules, multi-ticker lists, and growth tables get is_calendar=True."""
    t1 = "Upcoming Earnings Report - Week of October 25th $XOM $AAPL $AMZN $KO $BA"
    assert classifier.classify(t1, source="twitter_kaggle")["is_calendar"] is True

    t2 = "Q4 Revenue Growth, YoY % Change... Exxon $XOM: +86% Tesla $TSLA: +65%"
    assert classifier.classify(t2, source="twitter_kaggle")["is_calendar"] is True

    t3 = "This week: 35% of the SPX is scheduled to report earnings. Largest: $AAPL, $MSFT, $GOOGL"
    assert classifier.classify(t3, source="twitter_kaggle")["is_calendar"] is True

    t4 = "Most Anticipated Releases for the Week Beginning July 25, 2022 $AAPL $AMZN $BA"
    assert classifier.classify(t4, source="twitter_kaggle")["is_calendar"] is True


def test_noisy_tweet_defaults_to_other(classifier):
    """Verify that uninformative casual tweets default to Other with low confidence."""
    tweet = "Nice weather today, thinking about grabbing a coffee before work."
    res = classifier.classify(tweet, source="twitter_kaggle")
    assert res["event_type"] == EventType.OTHER.value
    assert res["confidence"] <= 0.3
    assert res["matched_triggers"] == []
