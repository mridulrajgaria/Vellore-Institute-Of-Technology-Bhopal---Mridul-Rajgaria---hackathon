"""Fetch recent news articles via NewsAPI with rate-limit handling and JSON caching."""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from src.common.config import load_companies_config
from src.common.http_client import get_resilient_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fetch_newsapi")

OUTPUT_DIR = Path("data/raw/newsapi")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"


def sanitize_filename(name: str) -> str:
    """Sanitize query string to produce Windows-safe filename."""
    return re.sub(r'[^\w\-_.]', '_', name)


def fetch_articles_for_company(
    company_name: str,
    api_key: str,
    output_dir: Path = OUTPUT_DIR,
) -> Optional[Dict[str, Any]]:
    """Query NewsAPI for recent articles mentioning a company and cache the raw JSON response."""
    output_dir.mkdir(parents=True, exist_ok=True)
    session = get_resilient_session(retries=2, backoff_factor=2.0)

    params = {
        "q": f'"{company_name}"',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 50,
        "apiKey": api_key,
    }

    try:
        resp = session.get(NEWSAPI_ENDPOINT, params=params, timeout=15)
        
        # Handle 429 rate limit
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait_sec = int(retry_after) if retry_after and retry_after.isdigit() else 5
            logger.warning(f"NewsAPI rate limit reached (HTTP 429). Retry-After: {wait_sec}s. Backing off...")
            time.sleep(wait_sec)
            resp = session.get(NEWSAPI_ENDPOINT, params=params, timeout=15)

        if resp.status_code != 200:
            logger.warning(f"NewsAPI returned status {resp.status_code} for query '{company_name}': {resp.text}")
            return None

        data = resp.json()
    except Exception as e:
        logger.warning(f"Error querying NewsAPI for '{company_name}': {e}")
        return None

    articles = data.get("articles", [])
    total_results = data.get("totalResults", len(articles))
    logger.info(f"Retrieved {len(articles)} articles (total reported: {total_results}) for '{company_name}'")

    # Cache raw JSON
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = sanitize_filename(company_name)
    cache_path = output_dir / f"{clean_name}_{ts_str}.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Cached raw NewsAPI JSON to {cache_path}")
    return data


def run_newsapi_fetch() -> None:
    """Entry point to fetch NewsAPI articles across configured companies."""
    load_dotenv()
    api_key = os.getenv("NEWSAPI_KEY", "").strip()

    if not api_key or api_key == "your_newsapi_key_here":
        logger.info("NEWSAPI_KEY is missing or unconfigured in .env. Exiting gracefully with code 0.")
        sys.exit(0)

    companies_cfg = load_companies_config()
    companies = companies_cfg.get("companies", {})

    logger.info(f"Starting NewsAPI fetch for {len(companies)} company configurations.")
    for ticker, info in companies.items():
        # Prefer primary alias or legal name for news headline query
        aliases = info.get("aliases", [])
        primary_query = aliases[0] if aliases else info.get("legal_name", ticker)

        logger.info(f"Fetching news for {ticker} using query: '{primary_query}'")
        fetch_articles_for_company(company_name=primary_query, api_key=api_key)
        # Sleep slightly to respect rate limit
        time.sleep(1.0)

    logger.info("NewsAPI fetch completed.")


if __name__ == "__main__":
    run_newsapi_fetch()
