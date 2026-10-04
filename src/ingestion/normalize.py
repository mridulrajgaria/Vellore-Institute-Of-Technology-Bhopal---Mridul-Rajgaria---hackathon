"""Normalize and clean raw text sources into unified schema and parquet outputs."""

from datetime import datetime
import hashlib
import html
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from src.common.config import load_companies_config, load_default_config
from src.ingestion.fetch_newsapi import sanitize_filename

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("normalize")

PROCESSED_DIR = Path("data/processed")
SAMPLE_DIR = Path("data/sample")

MAX_SAMPLE_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB safety limit


def compute_text_id(source: str, ts_str: Optional[str], ticker_hint: Optional[str], text: str) -> str:
    """Generate 16-hex char sha1 hash for unique deduplication and tracking."""
    ts_val = ts_str or ""
    ticker_val = ticker_hint or ""
    key = f"{source}|{ts_val}|{ticker_val}|{text}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:16]


def clean_tweet_text(raw_text: str) -> Tuple[str, Optional[str]]:
    """Clean tweet text: unescape HTML, strip RT prefix, extract 1st URL, collapse spaces.
    
    Returns (cleaned_text, first_extracted_url).
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return "", None

    # 1. HTML unescape
    text = html.unescape(raw_text)

    # 2. Remove RT @user: prefix
    text = re.sub(r"^RT\s+@\w+:\s*", "", text, flags=re.IGNORECASE)

    # 3. Extract first URL and remove all URLs from text
    url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    first_url_match = url_pattern.search(text)
    first_url = first_url_match.group(0) if first_url_match else None
    text = url_pattern.sub("", text)

    # 4. Collapse whitespace and newlines (preserve @mentions and $cashtags)
    text = re.sub(r"\s+", " ", text).strip()

    return text, first_url


def normalize_tweets(
    csv_path: str = "data/raw/tweets/stock_tweets.csv",
    index_universe: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean and normalize stock_tweets.csv into unified schema."""
    logger.info(f"Loading tweets from {csv_path}...")
    df_raw = pd.read_csv(csv_path, encoding="utf-8")
    raw_count = len(df_raw)

    if index_universe is None:
        cfg = load_default_config()
        index_universe = cfg.get("index_universe", [])

    universe_set = set(index_universe)

    # Map GOOG -> GOOGL
    stock_names = df_raw["Stock Name"].astype(str).str.upper().replace({"GOOG": "GOOGL"})
    df_raw["ticker_hint"] = stock_names

    # Filter by index_universe
    in_universe_mask = df_raw["ticker_hint"].isin(universe_set)
    df_filtered = df_raw[in_universe_mask].copy()
    dropped_non_universe = raw_count - len(df_filtered)

    # Clean text and extract URLs
    cleaned_texts = []
    extracted_urls = []
    for raw_t in df_filtered["Tweet"]:
        c_text, c_url = clean_tweet_text(raw_t)
        cleaned_texts.append(c_text)
        extracted_urls.append(c_url)

    df_filtered["text"] = cleaned_texts
    df_filtered["url"] = extracted_urls

    # Drop empty or fewer than 3 words
    word_counts = df_filtered["text"].apply(lambda t: len(t.split()) if t else 0)
    valid_length_mask = word_counts >= 3
    df_valid = df_filtered[valid_length_mask].copy()
    dropped_short = len(df_filtered) - len(df_valid)

    # Parse UTC tz-aware timestamp
    df_valid["ts"] = pd.to_datetime(df_valid["Date"], utc=True)

    # Deduplicate by (cleaned text, ticker_hint), keep earliest ts, compute dup_count
    logger.info("Deduplicating tweets by (text, ticker_hint)...")
    # Sort by ts ascending so first is earliest
    df_valid = df_valid.sort_values("ts", ascending=True)

    # Group counts
    dup_counts = df_valid.groupby(["text", "ticker_hint"])["Date"].transform("count")
    df_valid["dup_count"] = dup_counts

    df_deduped = df_valid.drop_duplicates(subset=["text", "ticker_hint"], keep="first").copy()
    dropped_dups = len(df_valid) - len(df_deduped)

    # Complete schema
    df_deduped["source"] = "twitter_kaggle"
    df_deduped["title"] = None
    df_deduped["author_or_domain"] = "twitter.com"
    df_deduped["raw_label"] = None

    # Compute text_id
    text_ids = [
        compute_text_id("twitter_kaggle", ts.isoformat() if pd.notnull(ts) else "", ticker, text)
        for ts, ticker, text in zip(df_deduped["ts"], df_deduped["ticker_hint"], df_deduped["text"])
    ]
    df_deduped["text_id"] = text_ids

    cols = ["text_id", "ts", "source", "ticker_hint", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_deduped[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_non_universe": dropped_non_universe,
        "dropped_short": dropped_short,
        "dropped_dups": dropped_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def build_newsapi_query_mapping(companies_yaml_path: str = "config/companies.yaml") -> Dict[str, str]:
    """Map sanitized query strings used by fetch_newsapi to ticker symbols.
    
    Fails loudly if any company cannot be mapped.
    """
    cfg = load_companies_config(companies_yaml_path)
    companies = cfg.get("companies", {})
    mapping: Dict[str, str] = {}

    for ticker, info in companies.items():
        legal_name = info.get("legal_name", "")
        aliases = info.get("aliases", [])
        
        # Primary query used by fetch_newsapi
        primary_query = aliases[0] if aliases else legal_name
        sanitized_primary = sanitize_filename(primary_query)
        mapping[sanitized_primary] = ticker

        # Also map legal name and all aliases for robust fallback
        if legal_name:
            mapping[sanitize_filename(legal_name)] = ticker
        for alias in aliases:
            mapping[sanitize_filename(alias)] = ticker

    return mapping


def normalize_newsapi(
    newsapi_dir: str = "data/raw/newsapi",
    companies_yaml_path: str = "config/companies.yaml",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Flatten and normalize NewsAPI JSON files into unified schema."""
    logger.info(f"Loading NewsAPI files from {newsapi_dir}...")
    query_to_ticker = build_newsapi_query_mapping(companies_yaml_path)

    path = Path(newsapi_dir)
    json_files = sorted(list(path.glob("*.json")))

    raw_articles: List[Dict[str, Any]] = []
    file_ticker_map: Dict[str, str] = {}

    for jf in json_files:
        # Match pattern: <clean_name>_<YYYYMMDD_HHMMSS>.json
        match = re.match(r"^(.*)_\d{8}_\d{6}\.json$", jf.name)
        if not match:
            raise ValueError(f"Unrecognized NewsAPI file naming format: {jf.name}")

        query_name = match.group(1)
        if query_name not in query_to_ticker:
            raise ValueError(f"Cannot map NewsAPI query name '{query_name}' in file '{jf.name}' to any known ticker!")

        ticker = query_to_ticker[query_name]
        file_ticker_map[jf.name] = ticker

        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
            articles = data.get("articles", [])
            for art in articles:
                art_copy = dict(art)
                art_copy["_file_ticker"] = ticker
                raw_articles.append(art_copy)

    raw_count = len(raw_articles)
    if not raw_articles:
        return pd.DataFrame(columns=["text_id", "ts", "source", "ticker_hint", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]), {}

    df = pd.DataFrame(raw_articles)

    # Drop [Removed] or empty title/text
    title_series = df["title"].fillna("").astype(str)
    desc_series = df["description"].fillna("").astype(str)

    # Strip trailing [+N chars] pattern from description/content if present
    char_strip_pat = re.compile(r"\s*\[\+\d+\s+chars\]", re.IGNORECASE)
    cleaned_desc = [char_strip_pat.sub("", d).strip() for d in desc_series]

    combined_text = []
    for t, d in zip(title_series, cleaned_desc):
        if d:
            combined_text.append(f"{t.strip()}. {d}")
        else:
            combined_text.append(t.strip())

    df["text"] = combined_text

    is_removed = title_series.str.strip().str.lower() == "[removed]"
    is_empty_text = df["text"].str.strip().str.len() == 0
    valid_mask = (~is_removed) & (~is_empty_text)
    df_valid = df[valid_mask].copy()
    dropped_removed_or_empty = raw_count - len(df_valid)

    # Parse publishedAt to tz-aware UTC
    df_valid["ts"] = pd.to_datetime(df_valid["publishedAt"], utc=True)

    # Author or domain
    author_or_domain = []
    for src_obj, url in zip(df_valid["source"], df_valid["url"]):
        name = src_obj.get("name") if isinstance(src_obj, dict) else None
        if name and name.strip():
            author_or_domain.append(name.strip())
        elif url and isinstance(url, str):
            try:
                author_or_domain.append(urlparse(url).netloc)
            except Exception:
                author_or_domain.append(None)
        else:
            author_or_domain.append(None)
    df_valid["author_or_domain"] = author_or_domain

    # Deduplicate by URL
    df_valid["dup_count"] = df_valid.groupby("url")["title"].transform("count")
    df_deduped = df_valid.drop_duplicates(subset=["url"], keep="first").copy()
    dropped_dups = len(df_valid) - len(df_deduped)

    df_deduped["source"] = "newsapi"
    df_deduped["ticker_hint"] = df_deduped["_file_ticker"]
    df_deduped["raw_label"] = None

    text_ids = [
        compute_text_id("newsapi", ts.isoformat() if pd.notnull(ts) else "", ticker, text)
        for ts, ticker, text in zip(df_deduped["ts"], df_deduped["ticker_hint"], df_deduped["text"])
    ]
    df_deduped["text_id"] = text_ids

    cols = ["text_id", "ts", "source", "ticker_hint", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_deduped[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_removed_or_empty": dropped_removed_or_empty,
        "dropped_dups": dropped_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def normalize_financial_news(
    csv_path: str = "data/raw/financial_news/all-data.csv",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean and normalize financial_news/all-data.csv."""
    logger.info(f"Loading financial news from {csv_path}...")
    df_raw = pd.read_csv(csv_path, encoding="latin-1", header=None)
    raw_count = len(df_raw)

    df_raw.columns = ["raw_label", "text"]
    df_raw["raw_label"] = df_raw["raw_label"].astype(str).str.strip().str.lower()
    df_raw["text"] = df_raw["text"].astype(str).str.strip()

    # Deduplicate by headline text
    dup_counts = df_raw.groupby("text")["raw_label"].transform("count")
    df_raw["dup_count"] = dup_counts

    df_deduped = df_raw.drop_duplicates(subset=["text"], keep="first").copy()
    dropped_dups = raw_count - len(df_deduped)

    df_deduped["text_id"] = [
        compute_text_id("financial_phrasebank", "", "", text)
        for text in df_deduped["text"]
    ]
    df_deduped["ts"] = None
    df_deduped["source"] = "financial_phrasebank"
    df_deduped["ticker_hint"] = None
    df_deduped["title"] = None
    df_deduped["url"] = None
    df_deduped["author_or_domain"] = "financial_phrasebank"

    cols = ["text_id", "ts", "source", "ticker_hint", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_deduped[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_dups": dropped_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def create_deterministic_monthly_tweet_sample(
    df_tweets: pd.DataFrame,
    target_per_ticker: int = 3000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Sample at most target_per_ticker tweets per ticker, distributed evenly across calendar months.
    
    Residual quota is filled from high-volume months. Entirely deterministic and idempotent.
    """
    sampled_records: List[pd.DataFrame] = []

    for ticker, ticker_group in df_tweets.groupby("ticker_hint"):
        total_avail = len(ticker_group)
        if total_avail <= target_per_ticker:
            sampled_records.append(ticker_group)
            continue

        work_df = ticker_group.copy()
        work_df["year_month"] = work_df["ts"].dt.strftime("%Y-%m")
        months = sorted(work_df["year_month"].unique())
        month_counts = {m: len(work_df[work_df["year_month"] == m]) for m in months}

        # Iteratively distribute quota
        remaining_quota = target_per_ticker
        remaining_months = list(months)
        allocations: Dict[str, int] = {}

        while remaining_quota > 0 and remaining_months:
            fair_share = remaining_quota // len(remaining_months)
            # Find months that cannot satisfy fair_share
            small_months = [m for m in remaining_months if month_counts[m] <= fair_share]

            if small_months:
                for sm in small_months:
                    allocations[sm] = month_counts[sm]
                    remaining_quota -= month_counts[sm]
                    remaining_months.remove(sm)
            else:
                # All remaining months have >= fair_share
                remainder = remaining_quota % len(remaining_months)
                for idx, rm in enumerate(remaining_months):
                    allocations[rm] = fair_share + (1 if idx < remainder else 0)
                remaining_quota = 0
                remaining_months = []

        ticker_samples = []
        for m in months:
            m_df = work_df[work_df["year_month"] == m]
            alloc = allocations.get(m, 0)
            if alloc > 0:
                # Deterministic sampling: sort by text_id first then sample with fixed seed
                sorted_m = m_df.sort_values("text_id")
                sampled_m = sorted_m.sample(n=min(alloc, len(sorted_m)), random_state=random_state)
                ticker_samples.append(sampled_m)

        ticker_sampled_df = pd.concat(ticker_samples, ignore_index=True)
        # Drop temporary year_month column
        ticker_sampled_df = ticker_sampled_df.drop(columns=["year_month"])
        sampled_records.append(ticker_sampled_df)

    if not sampled_records:
        return pd.DataFrame(columns=df_tweets.columns)

    final_sample = pd.concat(sampled_records, ignore_index=True)
    # Sort deterministically
    final_sample = final_sample.sort_values(["ticker_hint", "ts", "text_id"]).reset_index(drop=True)
    return final_sample


def create_deterministic_eval_sample(
    df_labeled: pd.DataFrame,
    target_total: int = 500,
    random_state: int = 42,
) -> pd.DataFrame:
    """Stratified sample of 500 rows across raw_label (positive, negative, neutral)."""
    samples = []
    label_counts = df_labeled["raw_label"].value_counts(normalize=True)

    for label, group in df_labeled.groupby("raw_label"):
        prop = label_counts[label]
        target_n = round(prop * target_total)
        sorted_group = group.sort_values("text_id")
        sample_group = sorted_group.sample(n=min(target_n, len(sorted_group)), random_state=random_state)
        samples.append(sample_group)

    combined = pd.concat(samples, ignore_index=True)
    if len(combined) > target_total:
        combined = combined.sort_values("text_id").head(target_total)
    elif len(combined) < target_total:
        deficit = target_total - len(combined)
        remaining = df_labeled[~df_labeled["text_id"].isin(combined["text_id"])].sort_values("text_id")
        combined = pd.concat([combined, remaining.head(deficit)], ignore_index=True)

    return combined.sort_values(["raw_label", "text_id"]).reset_index(drop=True)


def check_and_save_parquet(df: pd.DataFrame, path: Path, max_bytes: int = MAX_SAMPLE_FILE_SIZE_BYTES) -> int:
    """Save dataframe to parquet and verify file size constraint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    logger.info(f"Saved {path} ({len(df):,} rows, {size_mb:.2f} MB)")

    if size_bytes > max_bytes:
        raise ValueError(
            f"FILE SIZE EXCEEDED: {path} is {size_mb:.2f} MB ({size_bytes} bytes), which exceeds the limit of 5.0 MB!"
        )
    return size_bytes


def run_normalization() -> Dict[str, Any]:
    """Execute complete normalization pipeline, write processed & sample files."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Normalize Tweets
    df_tweets, tweet_metrics = normalize_tweets()

    # 2. Normalize NewsAPI
    df_newsapi, newsapi_metrics = normalize_newsapi()

    # 3. Normalize Financial News
    df_finnews, finnews_metrics = normalize_financial_news()

    # 4. Save combined full dataset to data/processed/texts_all.parquet (gitignored)
    all_texts_df = pd.concat([df_tweets, df_newsapi, df_finnews], ignore_index=True)
    all_texts_df = all_texts_df.sort_values(["source", "text_id"]).reset_index(drop=True)
    all_parquet_path = PROCESSED_DIR / "texts_all.parquet"
    all_texts_df.to_parquet(all_parquet_path, index=False)
    all_size_mb = all_parquet_path.stat().st_size / (1024 * 1024)
    logger.info(f"Saved combined dataset to {all_parquet_path} ({len(all_texts_df):,} rows, {all_size_mb:.2f} MB)")

    # 5. Generate and save sample datasets (deterministic)
    tweets_sample_path = SAMPLE_DIR / "tweets_sample.parquet"
    df_tweets_sample = create_deterministic_monthly_tweet_sample(df_tweets, target_per_ticker=3000, random_state=42)
    check_and_save_parquet(df_tweets_sample, tweets_sample_path)

    newsapi_sample_path = SAMPLE_DIR / "newsapi_sample.parquet"
    df_newsapi_sample = df_newsapi.sort_values(["ticker_hint", "ts", "text_id"]).reset_index(drop=True)
    check_and_save_parquet(df_newsapi_sample, newsapi_sample_path)

    finnews_sample_path = SAMPLE_DIR / "news_labeled_eval_sample.parquet"
    df_finnews_sample = create_deterministic_eval_sample(df_finnews, target_total=500, random_state=42)
    check_and_save_parquet(df_finnews_sample, finnews_sample_path)

    return {
        "tweet_metrics": tweet_metrics,
        "newsapi_metrics": newsapi_metrics,
        "finnews_metrics": finnews_metrics,
        "df_tweets": df_tweets,
        "df_tweets_sample": df_tweets_sample,
        "df_newsapi": df_newsapi,
        "df_finnews": df_finnews,
        "df_finnews_sample": df_finnews_sample,
    }


if __name__ == "__main__":
    run_normalization()
