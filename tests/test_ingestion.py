"""Unit tests for ingestion modules with complete network call mocking."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.ingestion.fetch_prices import (
    normalize_yfinance_dataframe,
    fetch_from_yfinance,
    fetch_from_alpha_vantage,
)
from src.ingestion.fetch_newsapi import (
    sanitize_filename,
    fetch_articles_for_company,
    run_newsapi_fetch,
)
from src.ingestion.fetch_gdelt import (
    build_gdelt_query,
    fetch_gdelt_articles,
    parse_and_save_gdelt_records,
    read_gkg_themes,
)


# ==========================================
# 1. Tests for fetch_prices.py
# ==========================================

def test_normalize_yfinance_multiindex_price_level0():
    """Test normalizing yfinance MultiIndex dataframe where Price is Level 0."""
    dates = pd.date_range("2024-01-01", periods=2)
    cols = pd.MultiIndex.from_tuples([
        ("Close", "AAPL"),
        ("Close", "MSFT"),
        ("Open", "AAPL"),
        ("Open", "MSFT"),
        ("High", "AAPL"),
        ("High", "MSFT"),
        ("Low", "AAPL"),
        ("Low", "MSFT"),
        ("Volume", "AAPL"),
        ("Volume", "MSFT"),
    ])
    data = [
        [150.0, 300.0, 149.0, 298.0, 151.0, 302.0, 148.0, 297.0, 1000, 2000],
        [152.0, 305.0, 150.0, 301.0, 153.0, 306.0, 149.0, 300.0, 1200, 2200],
    ]
    raw_df = pd.DataFrame(data, index=dates, columns=cols)

    norm_df = normalize_yfinance_dataframe(raw_df)
    assert not norm_df.empty
    assert set(norm_df["ticker"].unique()) == {"AAPL", "MSFT"}
    assert list(norm_df.columns) == ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    assert len(norm_df) == 4


def test_normalize_yfinance_multiindex_ticker_level0():
    """Test normalizing yfinance MultiIndex dataframe where Ticker is Level 0."""
    dates = pd.date_range("2024-01-01", periods=2)
    cols = pd.MultiIndex.from_tuples([
        ("AAPL", "Close"),
        ("AAPL", "Open"),
        ("MSFT", "Close"),
        ("MSFT", "Open"),
    ])
    data = [
        [150.0, 149.0, 300.0, 298.0],
        [152.0, 150.0, 305.0, 301.0],
    ]
    raw_df = pd.DataFrame(data, index=dates, columns=cols)

    norm_df = normalize_yfinance_dataframe(raw_df)
    assert not norm_df.empty
    assert set(norm_df["ticker"].unique()) == {"AAPL", "MSFT"}


def test_fetch_from_alpha_vantage_success():
    """Test parsing Alpha Vantage TIME_SERIES_DAILY successful response."""
    mock_payload = {
        "Time Series (Daily)": {
            "2024-01-02": {
                "1. open": "180.0",
                "2. high": "185.0",
                "3. low": "179.0",
                "4. close": "184.0",
                "5. volume": "50000",
            }
        }
    }
    with patch("src.ingestion.fetch_prices.get_resilient_session") as mock_sess_factory:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_payload
        mock_resp.status_code = 200
        mock_session.get.return_value = mock_resp
        mock_sess_factory.return_value = mock_session

        df = fetch_from_alpha_vantage("AAPL", start_date="2024-01-01", api_key="test_key")
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "AAPL"
        assert df.iloc[0]["close"] == 184.0


def test_fetch_from_alpha_vantage_rate_limit_handled():
    """Test Alpha Vantage rate-limit note is handled without crash."""
    mock_payload = {"Note": "Thank you for using Alpha Vantage! Call frequency limit reached."}
    with patch("src.ingestion.fetch_prices.get_resilient_session") as mock_sess_factory:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_payload
        mock_session.get.return_value = mock_resp
        mock_sess_factory.return_value = mock_session

        df = fetch_from_alpha_vantage("AAPL", start_date="2024-01-01", api_key="test_key")
        assert df is None


# ==========================================
# 2. Tests for fetch_newsapi.py
# ==========================================

def test_sanitize_filename():
    """Verify filename sanitization removes unsafe characters."""
    assert sanitize_filename("Apple Inc. / Corporate: Q4?") == "Apple_Inc.___Corporate__Q4_"


def test_newsapi_missing_key_exits_zero(monkeypatch):
    """Verify missing NEWSAPI_KEY cleanly exits 0."""
    monkeypatch.setenv("NEWSAPI_KEY", "")
    with pytest.raises(SystemExit) as excinfo:
        run_newsapi_fetch()
    assert excinfo.value.code == 0


def test_fetch_articles_handles_429_retry(tmp_path):
    """Verify HTTP 429 triggers retry-after wait and succeeds on second attempt."""
    mock_success_payload = {
        "status": "ok",
        "totalResults": 1,
        "articles": [{"title": "Apple launches new M4 chip", "url": "https://example.com/news"}],
    }

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "1"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = mock_success_payload

    with patch("src.ingestion.fetch_newsapi.get_resilient_session") as mock_sess_factory, \
         patch("time.sleep") as mock_sleep:
        mock_session = MagicMock()
        mock_session.get.side_effect = [resp_429, resp_200]
        mock_sess_factory.return_value = mock_session

        result = fetch_articles_for_company(company_name="Apple", api_key="valid_key", output_dir=tmp_path)
        assert result is not None
        assert result["totalResults"] == 1
        assert mock_sleep.called
        # Verify JSON file was written
        cached_files = list(tmp_path.glob("*.json"))
        assert len(cached_files) == 1


# ==========================================
# 3. Tests for fetch_gdelt.py
# ==========================================

def test_build_gdelt_query():
    """Verify GDELT query is OR-grouped with explicit risk keywords."""
    query = build_gdelt_query("Apple", ["tariff", "war"])
    assert query == '"Apple" (tariff OR war) sourcelang:english'


def test_fetch_gdelt_handles_throttled_html_response():
    """Verify GDELT retries when throttled with HTML/empty body."""
    resp_html = MagicMock()
    resp_html.status_code = 200
    resp_html.text = "<html><body>Please slow down your request rate</body></html>"

    resp_json = MagicMock()
    resp_json.status_code = 200
    resp_json.text = json.dumps({
        "articles": [
            {
                "url": "https://example.com/gdelt_art",
                "title": "Trade tariffs impact tech",
                "seendate": "20240101T120000Z",
                "domain": "example.com",
                "language": "English",
            }
        ]
    })

    with patch("src.ingestion.fetch_gdelt.get_resilient_session") as mock_sess_factory, \
         patch("time.sleep") as mock_sleep:
        mock_session = MagicMock()
        mock_session.get.side_effect = [resp_html, resp_json]
        mock_sess_factory.return_value = mock_session

        articles = fetch_gdelt_articles(query="test_query", max_retries=2, backoff_seconds=0.1)
        assert len(articles) == 1
        assert articles[0]["title"] == "Trade tariffs impact tech"
        assert mock_sleep.called


def test_parse_and_save_gdelt_records(tmp_path):
    """Verify GDELT articles are extracted into expected schema and saved."""
    articles = [
        {
            "url": "https://news.com/1",
            "title": "Macro headline",
            "seendate": "20240101T000000Z",
            "domain": "news.com",
            "language": "English",
        }
    ]
    df = parse_and_save_gdelt_records(articles=articles, ticker="MSFT", output_dir=tmp_path)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "MSFT"
    assert list(df.columns) == ["url", "title", "seendate", "domain", "language", "ticker"]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_read_gkg_themes(tmp_path):
    """Verify GKG theme reader handles missing directory and parsed CSV files."""
    # Non-existent directory returns empty dataframe
    empty_df = read_gkg_themes(tmp_path / "non_existent")
    assert empty_df.empty

    # Create dummy tab-separated GKG file
    sample_file = tmp_path / "sample.gkg.csv"
    sample_file.write_text("REC001\t20240101\tNews\tApple\tTAX_TARIFF\n", encoding="utf-8")
    loaded_df = read_gkg_themes(tmp_path)
    assert not loaded_df.empty
    assert len(loaded_df) == 1
