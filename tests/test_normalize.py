"""Unit tests for text normalization pipeline using isolated inline fixtures."""

import io
from pathlib import Path
import pandas as pd
import pytest

from src.ingestion.normalize import (
    clean_tweet_text,
    compute_text_id,
    normalize_tweets,
    normalize_newsapi,
    normalize_financial_news,
    create_deterministic_monthly_tweet_sample,
    create_deterministic_eval_sample,
)


def test_clean_tweet_text_html_unescape_and_rt_strip():
    """Verify HTML entities are decoded and 'RT @user:' prefixes are removed."""
    raw = "RT @elonmusk: Tesla &amp; SpaceX are doing great &gt; legacy auto! Check https://tesla.com"
    cleaned, url = clean_tweet_text(raw)
    assert cleaned == "Tesla & SpaceX are doing great > legacy auto! Check"
    assert url == "https://tesla.com"


def test_clean_tweet_text_preserves_mentions_and_cashtags():
    """Verify @mentions and $cashtags are preserved while collapsing extra whitespace."""
    raw = "Bullish on   $AAPL and  @Apple   today!  \n\n Massive earnings coming."
    cleaned, url = clean_tweet_text(raw)
    assert cleaned == "Bullish on $AAPL and @Apple today! Massive earnings coming."
    assert url is None


def test_compute_text_id_deterministic():
    """Verify text_id is deterministic and exactly 16 hex characters."""
    id1 = compute_text_id("twitter_kaggle", "2022-01-01T00:00:00+00:00", "AAPL", "Apple launches M2 chip")
    id2 = compute_text_id("twitter_kaggle", "2022-01-01T00:00:00+00:00", "AAPL", "Apple launches M2 chip")
    assert id1 == id2
    assert len(id1) == 16
    assert int(id1, 16) >= 0


def test_normalize_tweets_universe_filter_goog_mapping_and_dedupe(tmp_path):
    """Verify filtering non-universe tickers, GOOG -> GOOGL mapping, and dedupe with dup_count."""
    csv_file = tmp_path / "mock_tweets.csv"
    data = [
        # In universe GOOG (should map to GOOGL)
        ("2022-01-02 10:00:00+00:00", "Google cloud growth accelerates significantly today", "GOOG", "Alphabet Inc."),
        # Duplicate of above (earlier timestamp) -> should be kept, dup_count=2
        ("2022-01-02 09:00:00+00:00", "Google cloud growth accelerates significantly today", "GOOG", "Alphabet Inc."),
        # In universe AAPL
        ("2022-01-03 12:00:00+00:00", "Apple announces record holiday quarter revenue numbers", "AAPL", "Apple Inc."),
        # Non-universe NIO -> should be dropped
        ("2022-01-04 14:00:00+00:00", "NIO delivers 10k electric vehicles in December", "NIO", "NIO Inc."),
        # Short text (<3 words) -> should be dropped
        ("2022-01-05 15:00:00+00:00", "Great stock!", "AAPL", "Apple Inc."),
    ]
    df_raw = pd.DataFrame(data, columns=["Date", "Tweet", "Stock Name", "Company Name"])
    df_raw.to_csv(csv_file, index=False)

    universe = ["AAPL", "GOOGL"]
    df_norm, metrics = normalize_tweets(csv_path=str(csv_file), index_universe=universe)

    assert metrics["dropped_non_universe"] == 1
    assert metrics["dropped_short"] == 1
    assert metrics["dropped_dups"] == 1
    assert len(df_norm) == 2

    # Check GOOG mapped to GOOGL
    googl_row = df_norm[df_norm["ticker_hint"] == "GOOGL"].iloc[0]
    assert googl_row["ticker_hint"] == "GOOGL"
    assert googl_row["dup_count"] == 2
    # Kept earliest timestamp
    assert str(googl_row["ts"]).startswith("2022-01-02 09:00:00")
    assert googl_row["ts"].tzinfo is not None  # tz-aware UTC


def test_normalize_newsapi_filtering_and_char_strip(tmp_path):
    """Verify NewsAPI drops [Removed], strips [+N chars], deduplicates URLs, and maps tickers."""
    # Create mock companies.yaml
    companies_yaml = tmp_path / "companies.yaml"
    companies_yaml.write_text(
        """companies:
  AAPL:
    legal_name: "Apple Inc."
    aliases:
      - "Apple"
""",
        encoding="utf-8",
    )

    newsapi_dir = tmp_path / "newsapi"
    newsapi_dir.mkdir()

    # Create mock NewsAPI file Apple_20261005_010000.json
    mock_payload = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": None, "name": "Reuters"},
                "author": "John Doe",
                "title": "Apple unveils AI features",
                "description": "New AI models on iPhone [+123 chars]",
                "url": "https://reuters.com/article/1",
                "publishedAt": "2026-10-04T12:00:00Z",
                "content": "Full story [+456 chars]",
            },
            # Duplicate URL of article 1
            {
                "source": {"id": None, "name": "Yahoo"},
                "author": "Jane Doe",
                "title": "Apple unveils AI features (repost)",
                "description": "New AI models on iPhone",
                "url": "https://reuters.com/article/1",
                "publishedAt": "2026-10-04T13:00:00Z",
                "content": "Full story",
            },
            # Article with title "[Removed]"
            {
                "source": {"id": None, "name": "Spam News"},
                "author": None,
                "title": "[Removed]",
                "description": "[Removed]",
                "url": "https://spam.com/article/2",
                "publishedAt": "2026-10-04T14:00:00Z",
                "content": "[Removed]",
            },
        ],
    }
    json_file = newsapi_dir / "Apple_20261005_010000.json"
    json_file.write_text(pd.Series([mock_payload]).to_json(orient="records")[1:-1], encoding="utf-8")

    df_norm, metrics = normalize_newsapi(newsapi_dir=str(newsapi_dir), companies_yaml_path=str(companies_yaml))

    assert metrics["dropped_removed_or_empty"] == 1
    assert metrics["dropped_dups"] == 1
    assert len(df_norm) == 1

    row = df_norm.iloc[0]
    assert row["ticker_hint"] == "AAPL"
    assert row["author_or_domain"] == "Reuters"
    assert "[+123 chars]" not in row["text"]
    assert row["dup_count"] == 2
    assert row["ts"].tzinfo is not None  # tz-aware UTC


def test_normalize_financial_news_latin1_and_dedupe(tmp_path):
    """Verify headerless latin-1 financial news parsing and deduplication."""
    csv_file = tmp_path / "all-data.csv"
    content = (
        'neutral,"Operating profit rose to EUR 15.5 mn from EUR 10.2 mn in 2008 ."\n'
        'neutral,"Operating profit rose to EUR 15.5 mn from EUR 10.2 mn in 2008 ."\n'  # exact duplicate
        'positive,"Sales increased by 20% in Scandinavia during the fourth quarter ."\n'
    )
    csv_file.write_bytes(content.encode("latin-1"))

    df_norm, metrics = normalize_financial_news(csv_path=str(csv_file))

    assert metrics["raw_count"] == 3
    assert metrics["dropped_dups"] == 1
    assert len(df_norm) == 2

    assert df_norm.iloc[0]["source"] == "financial_phrasebank"
    assert df_norm.iloc[0]["raw_label"] in ["neutral", "positive"]
    assert df_norm.iloc[0]["ts"] is None
    assert df_norm.iloc[0]["ticker_hint"] is None


def test_deterministic_sampling_idempotence():
    """Verify that sampling functions produce 100% identical outputs on multiple runs."""
    dates = pd.date_range("2022-01-01", periods=100, freq="D", tz="UTC")
    data = []
    for i in range(100):
        data.append({
            "text_id": f"id_{i:04d}",
            "ts": dates[i],
            "ticker_hint": "TSLA",
            "text": f"Sample tweet content text {i}",
            "source": "twitter_kaggle",
            "title": None,
            "url": None,
            "author_or_domain": "twitter.com",
            "raw_label": None,
            "dup_count": 1,
        })
    df_tweets = pd.DataFrame(data)

    sample1 = create_deterministic_monthly_tweet_sample(df_tweets, target_per_ticker=50, random_state=42)
    sample2 = create_deterministic_monthly_tweet_sample(df_tweets, target_per_ticker=50, random_state=42)

    pd.testing.assert_frame_equal(sample1, sample2)
    assert len(sample1) == 50
