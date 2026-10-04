"""Fetch news and risk events from GDELT DOC 2.0 API and parse GKG theme files."""

from datetime import datetime
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional
import pandas as pd
import requests

from src.common.config import load_companies_config
from src.common.http_client import get_resilient_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fetch_gdelt")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
OUTPUT_DIR = Path("data/raw/gdelt")
GKG_DIR = Path("data/raw/gdelt_gkg")

RISK_KEYWORDS = ["sanctions", "default", "merger", "tariff", "inflation", "war", "lawsuit"]


def build_gdelt_query(company_name: str, keywords: List[str] = RISK_KEYWORDS) -> str:
    """Build GDELT DOC 2.0 query string grouping company name and risk keywords.
    
    Example: "Apple" (sanctions OR default OR merger OR tariff OR inflation OR war OR lawsuit) sourcelang:english
    """
    keyword_clause = " OR ".join(keywords)
    return f'"{company_name}" ({keyword_clause}) sourcelang:english'


def fetch_gdelt_articles(
    query: str,
    max_records: int = 250,
    timespan: str = "3m",
    max_retries: int = 3,
    backoff_seconds: float = 6.0,
) -> List[Dict[str, Any]]:
    """Query GDELT DOC 2.0 API in artlist mode with throttle resilience and backoff."""
    session = get_resilient_session(retries=1, backoff_factor=1.0)
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "timespan": timespan,
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(GDELT_DOC_API, params=params, timeout=20)
            text_body = resp.text.strip()

            if resp.status_code != 200 or not text_body:
                logger.warning(
                    f"GDELT returned HTTP {resp.status_code} with {len(text_body)} bytes on attempt {attempt}. Backing off {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)
                backoff_seconds *= 1.5
                continue

            # GDELT occasionally returns HTML error pages or non-JSON throttled responses
            if text_body.startswith("<") or not text_body.startswith("{"):
                logger.warning(
                    f"GDELT returned non-JSON/HTML response (likely throttle block). Attempt {attempt}/{max_retries}. Backing off {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)
                backoff_seconds *= 1.5
                continue

            data = json.loads(text_body)
            articles = data.get("articles", [])
            logger.info(f"Successfully retrieved {len(articles)} articles from GDELT for query: {query[:40]}...")
            return articles

        except json.JSONDecodeError as jde:
            logger.warning(f"Failed to parse GDELT JSON on attempt {attempt}: {jde}. Backing off {backoff_seconds}s...")
            time.sleep(backoff_seconds)
            backoff_seconds *= 1.5
        except Exception as e:
            logger.warning(f"Error during GDELT request on attempt {attempt}: {e}. Backing off {backoff_seconds}s...")
            time.sleep(backoff_seconds)
            backoff_seconds *= 1.5

    logger.error(f"Failed to retrieve GDELT articles after {max_retries} attempts.")
    return []


def parse_and_save_gdelt_records(articles: List[Dict[str, Any]], ticker: str, output_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    """Extract standard schema fields and save records to local parquet/JSON in data/raw/gdelt/."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not articles:
        return pd.DataFrame(columns=["url", "title", "seendate", "domain", "language", "ticker"])

    records = []
    for art in articles:
        records.append({
            "url": art.get("url", ""),
            "title": art.get("title", ""),
            "seendate": art.get("seendate", ""),
            "domain": art.get("domain", ""),
            "language": art.get("language", "English"),
            "ticker": ticker.upper(),
        })

    df = pd.DataFrame(records)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{ticker.upper()}_{ts_str}.json"
    df.to_json(output_file, orient="records", indent=2)
    logger.info(f"Saved {len(df)} GDELT records to {output_file}")
    return df


def read_gkg_themes(gkg_dir: Path = GKG_DIR) -> pd.DataFrame:
    """Optional reader for GDELT Global Knowledge Graph (GKG) theme files if present."""
    if not gkg_dir.exists():
        logger.info(f"GKG directory {gkg_dir} does not exist. Returning empty dataframe.")
        return pd.DataFrame()

    files = sorted(set(gkg_dir.glob("*.csv")).union(gkg_dir.glob("*.tsv")))
    if not files:
        logger.info(f"No GKG theme files found in {gkg_dir}.")
        return pd.DataFrame()

    dfs = []
    for file_path in files:
        logger.info(f"Reading GKG theme file: {file_path.name}")
        try:
            # GKG files are tab-delimited
            df = pd.read_csv(file_path, sep="\t", header=None, low_memory=False)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Could not parse GKG file {file_path}: {e}")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Successfully loaded {len(combined)} records from {len(dfs)} GKG files.")
    return combined


def run_gdelt_fetch() -> None:
    """Main execution loop querying GDELT DOC 2.0 API with respectful throttle delays."""
    companies_cfg = load_companies_config()
    companies = companies_cfg.get("companies", {})

    logger.info(f"Initiating GDELT fetch for {len(companies)} configured entities.")
    for ticker, info in companies.items():
        if ticker.upper() == "SPY":
            company_search = "S&P 500"
        else:
            aliases = info.get("aliases", [])
            company_search = aliases[0] if aliases else info.get("legal_name", ticker)

        query = build_gdelt_query(company_name=company_search)
        logger.info(f"Querying GDELT for {ticker}: {query}")

        articles = fetch_gdelt_articles(query=query)
        parse_and_save_gdelt_records(articles=articles, ticker=ticker)

        # Enforce GDELT throttle rule (sleep at least 5 seconds between calls)
        logger.info("Sleeping 5.5s to respect GDELT DOC 2.0 rate limits...")
        time.sleep(5.5)

    logger.info("GDELT fetch completed.")


if __name__ == "__main__":
    run_gdelt_fetch()
