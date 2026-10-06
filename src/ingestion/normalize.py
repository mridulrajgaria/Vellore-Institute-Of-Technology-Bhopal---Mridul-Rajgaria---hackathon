"""Normalize and clean raw text sources into unified schema, enrich with entity links, and generate parquet outputs."""

from datetime import datetime
import hashlib
import html
import json
import logging
from pathlib import Path
import re
import string
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from src.common.config import load_companies_config, load_default_config
from src.ingestion.fetch_newsapi import sanitize_filename
from src.nlp.entity_linking import EntityLinker, enrich_dataframe
from src.nlp.preprocess import fix_token_spacing

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
    """Clean tweet text: unescape HTML, strip RT prefix, extract 1st URL, collapse spaces."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        return "", None

    text = html.unescape(raw_text)
    text = re.sub(r"^RT\s+@\w+:\s*", "", text, flags=re.IGNORECASE)

    url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    first_url_match = url_pattern.search(text)
    first_url = first_url_match.group(0) if first_url_match else None
    text = url_pattern.sub("", text)
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

    in_universe_mask = df_raw["ticker_hint"].isin(universe_set)
    df_filtered = df_raw[in_universe_mask].copy()
    dropped_non_universe = raw_count - len(df_filtered)

    cleaned_texts = []
    extracted_urls = []
    for raw_t in df_filtered["Tweet"]:
        c_text, c_url = clean_tweet_text(raw_t)
        cleaned_texts.append(c_text)
        extracted_urls.append(c_url)

    df_filtered["text"] = cleaned_texts
    df_filtered["url"] = extracted_urls

    word_counts = df_filtered["text"].apply(lambda t: len(t.split()) if t else 0)
    valid_length_mask = word_counts >= 3
    df_valid = df_filtered[valid_length_mask].copy()
    dropped_short = len(df_filtered) - len(df_valid)

    df_valid["ts"] = pd.to_datetime(df_valid["Date"], utc=True)
    df_valid = df_valid.sort_values("ts", ascending=True)

    # 1. Existing per-hint dedupe
    dup_counts = df_valid.groupby(["text", "ticker_hint"])["Date"].transform("count")
    df_valid["dup_count"] = dup_counts

    df_per_hint = df_valid.drop_duplicates(subset=["text", "ticker_hint"], keep="first").copy()
    dropped_per_hint_dups = len(df_valid) - len(df_per_hint)

    # 2. Cross-hint dedupe on (cleaned text, ts)
    agg_df = df_per_hint.groupby(["text", "ts"]).agg(
        ticker_hints=("ticker_hint", lambda s: sorted(list(set(s)))),
        tot_dup=("dup_count", "sum")
    ).reset_index()

    df_cross = df_per_hint.drop_duplicates(subset=["text", "ts"], keep="first").copy()
    df_cross = df_cross.drop(columns=["ticker_hint", "dup_count"]).merge(agg_df, on=["text", "ts"], how="left")
    df_cross = df_cross.rename(columns={"tot_dup": "dup_count"})
    dropped_cross_hint_dups = len(df_per_hint) - len(df_cross)

    df_cross["source"] = "twitter_kaggle"
    df_cross["title"] = None
    df_cross["author_or_domain"] = "twitter.com"
    df_cross["raw_label"] = None
    df_cross["ticker_hint"] = df_cross["ticker_hints"].apply(lambda h: sorted(h)[0])

    text_ids = [
        compute_text_id("twitter_kaggle", ts.isoformat() if pd.notnull(ts) else "", ticker, text)
        for ts, ticker, text in zip(df_cross["ts"], df_cross["ticker_hint"], df_cross["text"])
    ]
    df_cross["text_id"] = text_ids

    cols = ["text_id", "ts", "source", "ticker_hint", "ticker_hints", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_cross[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_non_universe": dropped_non_universe,
        "dropped_short": dropped_short,
        "dropped_dups": dropped_per_hint_dups + dropped_cross_hint_dups,
        "dropped_per_hint_dups": dropped_per_hint_dups,
        "dropped_cross_hint_dups": dropped_cross_hint_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def build_newsapi_query_mapping(companies_yaml_path: str = "config/companies.yaml") -> Dict[str, str]:
    """Map sanitized query strings used by fetch_newsapi to ticker symbols."""
    cfg = load_companies_config(companies_yaml_path)
    companies = cfg.get("companies", {})
    mapping: Dict[str, str] = {}

    for ticker, info in companies.items():
        legal_name = info.get("legal_name", "")
        aliases = info.get("aliases", [])
        primary_query = aliases[0] if aliases else legal_name
        mapping[sanitize_filename(ticker)] = ticker
        sanitized_primary = sanitize_filename(primary_query)
        mapping[sanitized_primary] = ticker

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

    for jf in json_files:
        match = re.match(r"^(.*)_\d{8}_\d{6}\.json$", jf.name)
        if not match:
            raise ValueError(f"Unrecognized NewsAPI file naming format: {jf.name}")

        query_name = match.group(1)
        if query_name not in query_to_ticker:
            raise ValueError(f"Cannot map NewsAPI query name '{query_name}' in file '{jf.name}' to any known ticker!")

        ticker = query_to_ticker[query_name]
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
    title_series = df["title"].fillna("").astype(str).apply(fix_token_spacing)
    desc_series = df["description"].fillna("").astype(str)

    char_strip_pat = re.compile(r"\s*\[\+\d+\s+chars\]", re.IGNORECASE)
    cleaned_desc = [fix_token_spacing(char_strip_pat.sub("", d).strip()) for d in desc_series]

    combined_text = []
    for t, d in zip(title_series, cleaned_desc):
        if d:
            combined_text.append(f"{t.strip()}. {d}")
        else:
            combined_text.append(t.strip())

    df["title"] = title_series
    df["text"] = combined_text

    is_removed = title_series.str.strip().str.lower() == "[removed]"
    is_empty_text = df["text"].str.strip().str.len() == 0
    valid_mask = (~is_removed) & (~is_empty_text)
    df_valid = df[valid_mask].copy()
    dropped_removed_or_empty = raw_count - len(df_valid)

    df_valid["ts"] = pd.to_datetime(df_valid["publishedAt"], utc=True)

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

    df_valid["dup_count"] = df_valid.groupby("url")["title"].transform("count")
    df_deduped = df_valid.drop_duplicates(subset=["url"], keep="first").copy()
    dropped_dups = len(df_valid) - len(df_deduped)

    df_deduped["source"] = "newsapi"
    df_deduped["ticker_hint"] = df_deduped["_file_ticker"]
    df_deduped["ticker_hints"] = [[t] if t else [] for t in df_deduped["ticker_hint"]]
    df_deduped["raw_label"] = None

    text_ids = [
        compute_text_id("newsapi", ts.isoformat() if pd.notnull(ts) else "", ticker, text)
        for ts, ticker, text in zip(df_deduped["ts"], df_deduped["ticker_hint"], df_deduped["text"])
    ]
    df_deduped["text_id"] = text_ids

    cols = ["text_id", "ts", "source", "ticker_hint", "ticker_hints", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_deduped[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_removed_or_empty": dropped_removed_or_empty,
        "dropped_dups": dropped_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def normalize_gdelt(
    gdelt_dir: str = "data/raw/gdelt",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean and normalize GDELT DOC API JSON files into unified schema."""
    logger.info(f"Loading GDELT files from {gdelt_dir}...")
    path = Path(gdelt_dir)
    json_files = sorted(list(path.glob("*.json")))

    file_metrics: Dict[str, Dict[str, int]] = {}
    all_records: List[Dict[str, Any]] = []

    punct_translator = str.maketrans("", "", string.punctuation)

    for jf in json_files:
        match = re.match(r"^([A-Za-z0-9_]+)_\d{8}_\d{6}\.json$", jf.name)
        file_prefix = match.group(1).upper() if match else jf.stem.split("_")[0].upper()
        ticker_hint = "MARKET" if file_prefix == "SPY" else file_prefix

        with open(jf, "r", encoding="utf-8") as f:
            items = json.load(f)

        raw_n = len(items)
        if raw_n == 0:
            file_metrics[jf.name] = {"raw": 0, "after_url_dedupe": 0, "after_title_dedupe": 0}
            continue

        df_file = pd.DataFrame(items)
        # Parse timestamp: GDELT seendate format: %Y%m%dT%H%M%SZ
        df_file["ts"] = pd.to_datetime(df_file["seendate"], format="%Y%m%dT%H%M%SZ", utc=True, errors="coerce")

        # Drop empty or short titles (< 3 words) after spacing fixes
        title_str = df_file["title"].fillna("").astype(str).apply(fix_token_spacing).str.strip()
        df_file["title"] = title_str
        word_counts = title_str.apply(lambda t: len(t.split()))
        df_file = df_file[word_counts >= 3].copy()

        # Step 1: URL Dedupe
        df_file["dup_count"] = df_file.groupby("url")["title"].transform("count")
        df_url_deduped = df_file.drop_duplicates(subset=["url"], keep="first").copy()
        after_url_n = len(df_url_deduped)

        # Step 2: Title Dedupe (normalize: lowercase, strip punctuation, collapse whitespace)
        norm_titles = (
            df_url_deduped["title"]
            .astype(str)
            .str.lower()
            .apply(lambda t: t.translate(punct_translator))
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        df_url_deduped["norm_title"] = norm_titles
        df_title_deduped = df_url_deduped.drop_duplicates(subset=["norm_title"], keep="first").copy()
        after_title_n = len(df_title_deduped)

        file_metrics[jf.name] = {
            "raw": raw_n,
            "after_url_dedupe": after_url_n,
            "after_title_dedupe": after_title_n,
        }

        for _, row in df_title_deduped.iterrows():
            title_text = str(row["title"]).strip()
            all_records.append({
                "ts": row["ts"],
                "source": "gdelt",
                "ticker_hint": ticker_hint,
                "ticker_hints": [ticker_hint] if ticker_hint else [],
                "title": title_text,
                "text": title_text,
                "url": str(row["url"]),
                "author_or_domain": str(row.get("domain", "")),
                "raw_label": None,
                "dup_count": int(row["dup_count"]),
            })

    if not all_records:
        return pd.DataFrame(columns=["text_id", "ts", "source", "ticker_hint", "ticker_hints", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]), file_metrics

    df_gdelt = pd.DataFrame(all_records)
    text_ids = [
        compute_text_id("gdelt", ts.isoformat() if pd.notnull(ts) else "", ticker, text)
        for ts, ticker, text in zip(df_gdelt["ts"], df_gdelt["ticker_hint"], df_gdelt["text"])
    ]
    df_gdelt["text_id"] = text_ids

    cols = ["text_id", "ts", "source", "ticker_hint", "ticker_hints", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    df_gdelt = df_gdelt[cols].reset_index(drop=True)
    return df_gdelt, file_metrics


def normalize_financial_news(
    csv_path: str = "data/raw/financial_news/all-data.csv",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean and normalize financial_news/all-data.csv."""
    logger.info(f"Loading financial news from {csv_path}...")
    df_raw = pd.read_csv(csv_path, encoding="latin-1", header=None)
    raw_count = len(df_raw)

    df_raw.columns = ["raw_label", "text"]
    df_raw["raw_label"] = df_raw["raw_label"].astype(str).str.strip().str.lower()
    df_raw["text"] = df_raw["text"].astype(str).apply(fix_token_spacing).str.strip()

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
    df_deduped["ticker_hints"] = [[] for _ in range(len(df_deduped))]
    df_deduped["title"] = None
    df_deduped["url"] = None
    df_deduped["author_or_domain"] = "financial_phrasebank"

    cols = ["text_id", "ts", "source", "ticker_hint", "ticker_hints", "title", "text", "url", "author_or_domain", "raw_label", "dup_count"]
    result_df = df_deduped[cols].reset_index(drop=True)

    metrics = {
        "raw_count": raw_count,
        "dropped_dups": dropped_dups,
        "final_count": len(result_df),
    }
    return result_df, metrics


def dedupe_cross_file_by_url(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Deduplicate records by URL across files/queries, merging linked_tickers, summing dup_count, keeping earliest ts."""
    has_url_mask = df["url"].notnull() & (df["url"].astype(str).str.strip() != "")
    df_with_url = df[has_url_mask].copy()
    df_no_url = df[~has_url_mask].copy()

    orig_with_url_count = len(df_with_url)
    if orig_with_url_count == 0:
        return df, 0

    # Group by URL
    deduped_rows = []
    for url, group in df_with_url.groupby("url"):
        # Sort by timestamp ascending to keep earliest
        group_sorted = group.sort_values("ts", ascending=True)
        primary_row = group_sorted.iloc[0].to_dict()

        # Merge linked_tickers as a union
        all_linked: Set[str] = set()
        for t_list in group["linked_tickers"]:
            if isinstance(t_list, (list, tuple, set, np.ndarray)):
                all_linked.update(t_list)
        primary_row["linked_tickers"] = sorted(list(all_linked))

        # Merge other_cashtags as a union
        all_other: Set[str] = set()
        if "other_cashtags" in group.columns:
            for ot_list in group["other_cashtags"]:
                if isinstance(ot_list, (list, tuple, set, np.ndarray)):
                    all_other.update(ot_list)
        primary_row["other_cashtags"] = sorted(list(all_other))

        # Merge ticker_hints as a union
        all_hints: Set[str] = set()
        if "ticker_hints" in group.columns:
            for th_list in group["ticker_hints"]:
                if isinstance(th_list, (list, tuple, set, np.ndarray)):
                    all_hints.update(th_list)
        primary_row["ticker_hints"] = sorted(list(all_hints))

        # Recalculate n_linked_tickers and is_broadcast
        comp_tickers = [t for t in primary_row["linked_tickers"] if t != "MARKET"]
        primary_row["n_linked_tickers"] = len(comp_tickers)
        primary_row["is_broadcast"] = len(comp_tickers) >= 3
        if len(comp_tickers) >= 3:
            primary_row["primary_ticker"] = None
        if len(comp_tickers) > 0:
            primary_row["attribution_weight"] = round(1.0 / len(comp_tickers), 4)
        else:
            primary_row["attribution_weight"] = 1.0

        # Sum dup_count
        primary_row["dup_count"] = int(group["dup_count"].sum())

        # If any copy was relevant, the merged row is relevant
        primary_row["is_relevant"] = bool(group["is_relevant"].any())

        deduped_rows.append(primary_row)

    df_deduped_url = pd.DataFrame(deduped_rows)
    removed_count = orig_with_url_count - len(df_deduped_url)

    combined = pd.concat([df_deduped_url, df_no_url], ignore_index=True)
    return combined, removed_count


def create_deterministic_monthly_tweet_sample(
    df_tweets: pd.DataFrame,
    target_per_ticker: int = 3000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Sample at most target_per_ticker tweets per ticker_hint, distributed evenly across calendar months."""
    sampled_records: List[pd.DataFrame] = []

    work_base = df_tweets.copy()

    for ticker_name, ticker_group in work_base.groupby("ticker_hint"):
        total_avail = len(ticker_group)
        if total_avail <= target_per_ticker:
            sampled_records.append(ticker_group)
            continue

        work_df = ticker_group.copy()
        work_df["year_month"] = work_df["ts"].dt.strftime("%Y-%m")
        months = sorted(work_df["year_month"].unique())
        month_counts = {m: len(work_df[work_df["year_month"] == m]) for m in months}

        remaining_quota = target_per_ticker
        remaining_months = list(months)
        allocations: Dict[str, int] = {}

        while remaining_quota > 0 and remaining_months:
            fair_share = remaining_quota // len(remaining_months)
            small_months = [m for m in remaining_months if month_counts[m] <= fair_share]

            if small_months:
                for sm in small_months:
                    allocations[sm] = month_counts[sm]
                    remaining_quota -= month_counts[sm]
                    remaining_months.remove(sm)
            else:
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
                sorted_m = m_df.sort_values("text_id")
                sampled_m = sorted_m.sample(n=min(alloc, len(sorted_m)), random_state=random_state)
                ticker_samples.append(sampled_m)

        ticker_sampled_df = pd.concat(ticker_samples, ignore_index=True)
        ticker_sampled_df = ticker_sampled_df.drop(columns=["year_month"])
        sampled_records.append(ticker_sampled_df)

    if not sampled_records:
        return pd.DataFrame(columns=df_tweets.columns)

    final_sample = pd.concat(sampled_records, ignore_index=True)
    sort_col = "primary_ticker" if "primary_ticker" in final_sample.columns else "ticker_hint"
    final_sample["_temp_sort"] = final_sample[sort_col].fillna("ZZZ")
    final_sample = final_sample.sort_values(["_temp_sort", "ts", "text_id"]).drop(columns=["_temp_sort"]).reset_index(drop=True)
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
    """Execute complete normalization, enrichment, and sampling pipeline."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    linker = EntityLinker()

    # 1. Normalize each source
    df_tweets, tweet_metrics = normalize_tweets()
    df_newsapi, newsapi_metrics = normalize_newsapi()
    df_gdelt, gdelt_file_metrics = normalize_gdelt()
    df_finnews, finnews_metrics = normalize_financial_news()

    # 2. Enrich with Entity Linking BEFORE sampling
    logger.info("Enriching tweets with entity linker...")
    df_tweets_enriched = enrich_dataframe(df_tweets, linker)
    # Recompute text_id with the resolved ticker_hint
    df_tweets_enriched["text_id"] = [
        compute_text_id("twitter_kaggle", ts.isoformat() if pd.notnull(ts) else "", hint, text)
        for ts, hint, text in zip(df_tweets_enriched["ts"], df_tweets_enriched["ticker_hint"], df_tweets_enriched["text"])
    ]

    logger.info("Enriching NewsAPI articles with entity linker...")
    df_newsapi_enriched = enrich_dataframe(df_newsapi, linker)

    logger.info("Enriching GDELT articles with entity linker...")
    df_gdelt_enriched = enrich_dataframe(df_gdelt, linker)

    logger.info("Enriching Financial News with entity linker...")
    df_finnews_enriched = enrich_dataframe(df_finnews, linker)

    # 3. Cross-file URL deduplication for NewsAPI and GDELT
    df_newsapi_deduped, newsapi_cross_removed = dedupe_cross_file_by_url(df_newsapi_enriched)
    logger.info(f"NewsAPI cross-file dedupe removed {newsapi_cross_removed} duplicate URL rows.")

    df_gdelt_deduped, gdelt_cross_removed = dedupe_cross_file_by_url(df_gdelt_enriched)
    logger.info(f"GDELT cross-file dedupe removed {gdelt_cross_removed} duplicate URL rows.")

    # 4. Save combined full dataset to data/processed/texts_all.parquet (gitignored)
    all_texts_df = pd.concat([df_tweets_enriched, df_newsapi_deduped, df_gdelt_deduped, df_finnews_enriched], ignore_index=True)
    all_texts_df = all_texts_df.sort_values(["source", "text_id"]).reset_index(drop=True)
    all_parquet_path = PROCESSED_DIR / "texts_all.parquet"
    all_texts_df.to_parquet(all_parquet_path, index=False)
    all_size_mb = all_parquet_path.stat().st_size / (1024 * 1024)
    logger.info(f"Saved combined dataset to {all_parquet_path} ({len(all_texts_df):,} rows, {all_size_mb:.2f} MB)")

    # 5. Build committed samples in data/sample/ (RELEVANT ROWS ONLY for NewsAPI & GDELT)
    # A. Tweets sample: up to 3,000 per primary_ticker across calendar months
    tweets_sample_path = SAMPLE_DIR / "tweets_sample.parquet"
    df_tweets_sample = create_deterministic_monthly_tweet_sample(df_tweets_enriched, target_per_ticker=3000, random_state=42)
    check_and_save_parquet(df_tweets_sample, tweets_sample_path)

    # B. NewsAPI sample: RELEVANT ROWS ONLY
    newsapi_sample_path = SAMPLE_DIR / "newsapi_sample.parquet"
    df_newsapi_rel = df_newsapi_deduped[df_newsapi_deduped["is_relevant"]].copy()
    df_newsapi_sample = df_newsapi_rel.sort_values(["primary_ticker", "ts", "text_id"]).reset_index(drop=True)
    check_and_save_parquet(df_newsapi_sample, newsapi_sample_path)

    # C. GDELT sample: RELEVANT ROWS ONLY (NEW!)
    gdelt_sample_path = SAMPLE_DIR / "gdelt_sample.parquet"
    df_gdelt_rel = df_gdelt_deduped[df_gdelt_deduped["is_relevant"]].copy()
    df_gdelt_sample = df_gdelt_rel.sort_values(["primary_ticker", "ts", "text_id"]).reset_index(drop=True)
    check_and_save_parquet(df_gdelt_sample, gdelt_sample_path)

    # D. Financial news eval sample: 500 rows stratified by raw_label
    finnews_sample_path = SAMPLE_DIR / "news_labeled_eval_sample.parquet"
    df_finnews_sample = create_deterministic_eval_sample(df_finnews_enriched, target_total=500, random_state=42)
    check_and_save_parquet(df_finnews_sample, finnews_sample_path)

    return {
        "tweet_metrics": tweet_metrics,
        "newsapi_metrics": newsapi_metrics,
        "gdelt_file_metrics": gdelt_file_metrics,
        "finnews_metrics": finnews_metrics,
        "newsapi_cross_removed": newsapi_cross_removed,
        "gdelt_cross_removed": gdelt_cross_removed,
        "df_tweets_enriched": df_tweets_enriched,
        "df_newsapi_deduped": df_newsapi_deduped,
        "df_gdelt_deduped": df_gdelt_deduped,
        "df_finnews_enriched": df_finnews_enriched,
        "df_tweets_sample": df_tweets_sample,
        "df_newsapi_sample": df_newsapi_sample,
        "df_gdelt_sample": df_gdelt_sample,
        "df_finnews_sample": df_finnews_sample,
        "all_texts_df": all_texts_df,
    }


if __name__ == "__main__":
    run_normalization()
