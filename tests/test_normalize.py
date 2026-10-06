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
    normalize_gdelt,
    normalize_financial_news,
    create_deterministic_monthly_tweet_sample,
    create_deterministic_eval_sample,
)
from src.nlp.entity_linking import EntityLinker, enrich_dataframe


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


def test_normalize_gdelt(tmp_path):
    """Verify GDELT seendate parsing, prefix ticker hint, URL and syndicated title deduplication."""
    import json
    gdelt_dir = tmp_path / "gdelt"
    gdelt_dir.mkdir()

    # SPY file: SPY should map to MARKET
    spy_items = [
        {
            "url": "https://reuters.com/article/1",
            "title": "Federal Reserve maintains current interest rate levels",
            "seendate": "20260714T134500Z",
            "domain": "reuters.com",
            "language": "English",
        },
        # Duplicate URL of article 1
        {
            "url": "https://reuters.com/article/1",
            "title": "Federal Reserve maintains current interest rate levels (copy)",
            "seendate": "20260714T140000Z",
            "domain": "reuters.com",
            "language": "English",
        },
        # Syndicated duplicate title with different URL and punctuation
        {
            "url": "https://bloomberg.com/article/2",
            "title": "Federal Reserve maintains current interest rate levels!",
            "seendate": "20260714T150000Z",
            "domain": "bloomberg.com",
            "language": "English",
        },
        # Short title (< 3 words) -> dropped
        {
            "url": "https://news.com/short",
            "title": "Fed rates",
            "seendate": "20260714T160000Z",
            "domain": "news.com",
            "language": "English",
        },
    ]
    spy_file = gdelt_dir / "SPY_20261005_120000.json"
    spy_file.write_text(json.dumps(spy_items), encoding="utf-8")

    df_gdelt, metrics = normalize_gdelt(gdelt_dir=str(gdelt_dir))
    assert len(df_gdelt) == 1
    row = df_gdelt.iloc[0]
    assert row["source"] == "gdelt"
    assert row["ticker_hint"] == "MARKET"
    assert row["ts"].tzinfo is not None
    assert str(row["ts"]).startswith("2026-07-14 13:45:00")
    assert row["dup_count"] == 2


def test_cross_hint_dedupe_and_hint_resolution(tmp_path):
    """Verify cross-hint deduplication and ticker_hint resolution from linked_tickers or alphabetical fallback."""
    csv_file = tmp_path / "cross_hint_tweets.csv"
    data = [
        # Fixture 1: Repeated under PG, MSFT, AMZN with $AMZN in text
        ("2022-01-01 12:00:00+00:00", "Strong quarterly performance reported by $AMZN today", "PG", "Procter & Gamble"),
        ("2022-01-01 12:00:00+00:00", "Strong quarterly performance reported by $AMZN today", "MSFT", "Microsoft"),
        ("2022-01-01 12:00:00+00:00", "Strong quarterly performance reported by $AMZN today", "AMZN", "Amazon"),
        # Fixture 2: Repeated under PG, MSFT, AMZN with no ticker in text
        ("2022-01-02 12:00:00+00:00", "Market sentiment remains cautious amid macro conditions", "PG", "Procter & Gamble"),
        ("2022-01-02 12:00:00+00:00", "Market sentiment remains cautious amid macro conditions", "MSFT", "Microsoft"),
        ("2022-01-02 12:00:00+00:00", "Market sentiment remains cautious amid macro conditions", "AMZN", "Amazon"),
    ]
    df_raw = pd.DataFrame(data, columns=["Date", "Tweet", "Stock Name", "Company Name"])
    df_raw.to_csv(csv_file, index=False)

    universe = ["AMZN", "MSFT", "PG"]
    df_norm, metrics = normalize_tweets(csv_path=str(csv_file), index_universe=universe)

    assert len(df_norm) == 2
    assert metrics["dropped_cross_hint_dups"] == 4

    linker = EntityLinker()
    df_enriched = enrich_dataframe(df_norm, linker)

    # Fixture 1 checks: exactly one row, ticker_hints ['AMZN', 'MSFT', 'PG'], dup_count 3, ticker_hint is AMZN
    row1 = df_enriched[df_enriched["text"].str.contains("Strong quarterly")].iloc[0]
    assert row1["ticker_hints"] == ["AMZN", "MSFT", "PG"]
    assert row1["dup_count"] == 3
    assert row1["ticker_hint"] == "AMZN"
    assert "AMZN" in row1["linked_tickers"]

    # Fixture 2 checks: exactly one row, ticker_hints ['AMZN', 'MSFT', 'PG'], dup_count 3, ticker_hint is AMZN (alphabetical fallback)
    row2 = df_enriched[df_enriched["text"].str.contains("Market sentiment")].iloc[0]
    assert row2["ticker_hints"] == ["AMZN", "MSFT", "PG"]
    assert row2["dup_count"] == 3
    assert row2["ticker_hint"] == "AMZN"

