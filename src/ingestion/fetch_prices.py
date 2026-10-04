"""Fetch historical daily OHLCV price data via yfinance with Alpha Vantage fallback."""

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from dotenv import load_dotenv
import yfinance as yf

from src.common.config import load_default_config
from src.common.http_client import get_resilient_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fetch_prices")

CACHE_DIR = Path("data/raw/prices_cache")
OUTPUT_PATH = Path("data/sample/prices.parquet")


def normalize_yfinance_dataframe(df: pd.DataFrame, default_ticker: Optional[str] = None) -> pd.DataFrame:
    """Normalize yfinance single or multi-ticker dataframe to standardized long format.
    
    Columns: date, ticker, open, high, low, close, adj_close, volume.
    """
    if df.empty:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])

    records: List[pd.DataFrame] = []

    # Case 1: MultiIndex columns (as returned by yf.download with multiple tickers)
    if isinstance(df.columns, pd.MultiIndex):
        level_0_names = df.columns.get_level_values(0).unique()
        level_1_names = df.columns.get_level_values(1).unique()

        # Check whether Price or Ticker is at level 0
        price_cols = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
        is_price_level_0 = any(c in price_cols for c in level_0_names)

        tickers = level_1_names if is_price_level_0 else level_0_names

        for t in tickers:
            try:
                sub_df = df.xs(t, axis=1, level=1 if is_price_level_0 else 0).copy()
                sub_norm = _normalize_single_ticker_df(sub_df, ticker=str(t))
                if not sub_norm.empty:
                    records.append(sub_norm)
            except KeyError:
                continue

        if records:
            return pd.concat(records, ignore_index=True)
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])

    # Case 2: Single ticker
    return _normalize_single_ticker_df(df, ticker=default_ticker or "UNKNOWN")


def _normalize_single_ticker_df(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Helper to standardize column names and format for a single ticker dataframe."""
    work_df = df.copy()

    # Reset date index if Date is index
    if isinstance(work_df.index, (pd.DatetimeIndex, pd.Index)) and work_df.index.name in ["Date", "Datetime", None]:
        work_df = work_df.reset_index()

    col_map = {}
    for c in work_df.columns:
        c_str = str(c).strip().lower()
        if c_str in ["date", "datetime"]:
            col_map[c] = "date"
        elif c_str == "open":
            col_map[c] = "open"
        elif c_str == "high":
            col_map[c] = "high"
        elif c_str == "low":
            col_map[c] = "low"
        elif c_str == "close":
            col_map[c] = "close"
        elif c_str in ["adj close", "adjclose", "adjusted_close"]:
            col_map[c] = "adj_close"
        elif c_str == "volume":
            col_map[c] = "volume"

    work_df = work_df.rename(columns=col_map)

    # Ensure required columns exist
    if "date" not in work_df.columns and not work_df.empty:
        work_df["date"] = pd.date_range(end=datetime.now(), periods=len(work_df)).date

    if "adj_close" not in work_df.columns and "close" in work_df.columns:
        work_df["adj_close"] = work_df["close"]

    target_cols = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    available_cols = [c for c in target_cols if c in work_df.columns]
    work_df = work_df[available_cols].copy()

    # Standardize types
    work_df["date"] = pd.to_datetime(work_df["date"]).dt.strftime("%Y-%m-%d")
    work_df["ticker"] = str(ticker).upper()

    for num_col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if num_col in work_df.columns:
            work_df[num_col] = pd.to_numeric(work_df[num_col], errors="coerce")

    work_df = work_df.dropna(subset=["date", "close"])
    ordered = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    return work_df.reindex(columns=ordered)


def fetch_from_yfinance(ticker: str, start_date: str) -> Optional[pd.DataFrame]:
    """Download daily historical data from yfinance for a single ticker."""
    try:
        raw = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
        if raw is not None and not raw.empty:
            df = normalize_yfinance_dataframe(raw, default_ticker=ticker)
            if not df.empty:
                logger.info(f"Successfully fetched {ticker} from yfinance ({len(df)} rows)")
                return df
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
    return None


def fetch_from_alpha_vantage(ticker: str, start_date: str, api_key: str) -> Optional[pd.DataFrame]:
    """Fallback fetch from Alpha Vantage TIME_SERIES_DAILY."""
    if not api_key:
        logger.warning(f"No ALPHAVANTAGE_KEY available for {ticker} fallback.")
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
        "apikey": api_key,
    }

    session = get_resilient_session(retries=2, backoff_factor=1.5)
    try:
        resp = session.get(url, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        logger.warning(f"Alpha Vantage request failed for {ticker}: {e}")
        return None

    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information")
        logger.warning(f"Alpha Vantage limit reached or note received for {ticker}: {msg}")
        return None

    ts_data = data.get("Time Series (Daily)")
    if not ts_data:
        logger.warning(f"Alpha Vantage returned no daily data for {ticker}")
        return None

    rows = []
    for dt_str, values in ts_data.items():
        if dt_str >= start_date:
            rows.append({
                "date": dt_str,
                "ticker": ticker.upper(),
                "open": float(values.get("1. open", np.nan)),
                "high": float(values.get("2. high", np.nan)),
                "low": float(values.get("3. low", np.nan)),
                "close": float(values.get("4. close", np.nan)),
                "adj_close": float(values.get("4. close", np.nan)),
                "volume": float(values.get("5. volume", 0)),
            })

    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    logger.info(f"Successfully fetched {ticker} from alpha_vantage ({len(df)} rows)")
    return df


def fetch_all_prices() -> pd.DataFrame:
    """Fetch prices for all configured tickers and benchmark, utilizing cache and fallbacks."""
    load_dotenv()
    alpha_key = os.getenv("ALPHAVANTAGE_KEY", "").strip()

    config = load_default_config()
    tickers = list(config.get("tickers", []))
    benchmark = config.get("benchmark", "SPY")
    if benchmark and benchmark not in tickers:
        tickers.append(benchmark)

    start_date = config.get("price_start_date", "2021-01-01")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_dfs: List[pd.DataFrame] = []

    for ticker in tickers:
        cache_file = CACHE_DIR / f"{ticker.upper()}.parquet"
        if cache_file.exists():
            logger.info(f"Loaded {ticker} from cache: {cache_file}")
            df = pd.read_parquet(cache_file)
            all_dfs.append(df)
            continue

        # Try yfinance
        df = fetch_from_yfinance(ticker, start_date)
        source = "yfinance"

        # Fallback to Alpha Vantage if needed
        if df is None or df.empty:
            logger.info(f"Attempting Alpha Vantage fallback for {ticker}")
            df = fetch_from_alpha_vantage(ticker, start_date, alpha_key)
            source = "alpha_vantage"

        if df is not None and not df.empty:
            df.to_parquet(cache_file, index=False)
            logger.info(f"Cached {ticker} ({source}) to {cache_file}")
            all_dfs.append(df)
        else:
            logger.error(f"Could not retrieve price data for {ticker} from any source.")

    if not all_dfs:
        logger.warning("No price data was collected.")
        empty_df = pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])
        return empty_df

    combined_df = pd.concat(all_dfs, ignore_index=True)
    combined_df = combined_df.sort_values(["ticker", "date"]).reset_index(drop=True)
    combined_df.to_parquet(OUTPUT_PATH, index=False)

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    logger.info(f"Saved consolidated prices to {OUTPUT_PATH} ({len(combined_df)} rows, {size_kb:.2f} KB)")
    return combined_df


if __name__ == "__main__":
    fetch_all_prices()
