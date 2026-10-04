"""Inspection script for raw datasets in data/raw/."""

import glob
import json
from pathlib import Path
import re
from typing import Dict, Any, List
import pandas as pd


def inspect_tweets(csv_path: str = "data/raw/tweets/stock_tweets.csv") -> pd.DataFrame:
    print("=" * 80)
    print("1. INSPECTING: stock_tweets.csv")
    print("=" * 80)

    path = Path(csv_path)
    if not path.is_file():
        print(f"File not found: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(path, encoding="utf-8")
    print(f"Shape: {df.shape[0]:,} rows, {df.shape[1]} columns")
    print("\nColumns and dtypes:")
    print(df.dtypes)

    print("\nNull counts:")
    print(df.isnull().sum())

    duplicate_rows = df.duplicated().sum()
    duplicate_tweets = df["Tweet"].duplicated().sum() if "Tweet" in df.columns else 0
    print(f"\nExact duplicate rows: {duplicate_rows}")
    print(f"Duplicate tweet texts: {duplicate_tweets}")

    print("\n3 Sample rows:")
    print(df.head(3).to_dict(orient="records"))

    if "Date" in df.columns:
        dt_series = pd.to_datetime(df["Date"], errors="coerce", utc=True)
        print(f"\nDate range: {dt_series.min()} to {dt_series.max()} (Null dates: {dt_series.isnull().sum()})")
        
        monthly_counts = dt_series.dt.to_period("M").value_counts().sort_index()
        print("\nTweets per Month:")
        print(monthly_counts.to_string())

    if "Stock Name" in df.columns:
        stock_counts = df["Stock Name"].value_counts()
        print(f"\nTotal unique Stock Names: {len(stock_counts)}")
        print("\nTweets per Stock Name:")
        print(stock_counts.to_string())

    if "Tweet" in df.columns:
        tweet_strs = df["Tweet"].astype(str)
        char_lengths = tweet_strs.str.len()
        word_lengths = tweet_strs.str.split().str.len()

        print("\nTweet character length stats:")
        print(char_lengths.describe().to_string())

        print("\nTweet word count stats:")
        print(word_lengths.describe().to_string())

        url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        mention_pattern = re.compile(r"@\w+")
        html_entity_pattern = re.compile(r"&\w+;|&#\d+;")

        has_url = tweet_strs.apply(lambda t: bool(url_pattern.search(t))).sum()
        has_mention = tweet_strs.apply(lambda t: bool(mention_pattern.search(t))).sum()
        has_html = tweet_strs.apply(lambda t: bool(html_entity_pattern.search(t))).sum()

        print("\nPattern counts in tweets:")
        print(f"Tweets containing URLs: {has_url:,} ({has_url / len(df) * 100:.1f}%)")
        print(f"Tweets containing @mentions: {has_mention:,} ({has_mention / len(df) * 100:.1f}%)")
        print(f"Tweets containing HTML entities: {has_html:,} ({has_html / len(df) * 100:.1f}%)")

    return df


def inspect_tweets_price_data(csv_path: str = "data/raw/tweets/stock_yfinance_data.csv") -> None:
    print("\n" + "=" * 80)
    print("2. INSPECTING: stock_yfinance_data.csv")
    print("=" * 80)

    path = Path(csv_path)
    if not path.is_file():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(path, encoding="utf-8")
    print(f"Shape: {df.shape[0]:,} rows, {df.shape[1]} columns")
    print("\nColumns and dtypes:")
    print(df.dtypes)

    if "Stock Name" in df.columns:
        print(f"\nTickers covered: {df['Stock Name'].unique().tolist()}")
    if "Date" in df.columns:
        dt = pd.to_datetime(df["Date"], errors="coerce")
        print(f"Date range: {dt.min()} to {dt.max()}")


def inspect_financial_news(csv_path: str = "data/raw/financial_news/all-data.csv") -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("3. INSPECTING: financial_news/all-data.csv")
    print("=" * 80)

    path = Path(csv_path)
    if not path.is_file():
        print(f"File not found: {csv_path}")
        return pd.DataFrame()

    # Read first 5 raw lines to check headers
    with open(path, "r", encoding="latin-1") as f:
        first_lines = [f.readline().strip() for _ in range(5)]
    print("First 5 raw lines in file:")
    for idx, line in enumerate(first_lines, 1):
        print(f"  [{idx}] {line[:100]}...")

    # Load with pandas header=None
    df = pd.read_csv(path, encoding="latin-1", header=None)
    print(f"\nLoaded shape (header=None): {df.shape[0]:,} rows, {df.shape[1]} columns")
    print(f"Column 0 name/sample: {df[0].iloc[0]}")
    print(f"Column 1 name/sample: {df[1].iloc[0][:60]}...")

    df.columns = ["label", "headline"]
    print("\nColumns and dtypes:")
    print(df.dtypes)

    print("\nNull counts:")
    print(df.isnull().sum())

    print(f"\nDuplicate headline counts: {df['headline'].duplicated().sum()}")

    print("\nLabel distribution:")
    print(df["label"].value_counts(dropna=False).to_string())

    print("\n3 Sample rows:")
    print(df.head(3).to_dict(orient="records"))

    return df


def inspect_newsapi(newsapi_dir: str = "data/raw/newsapi") -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("4. INSPECTING: NewsAPI cached JSON files")
    print("=" * 80)

    path = Path(newsapi_dir)
    json_files = sorted(list(path.glob("*.json")))
    print(f"Found {len(json_files)} JSON files in {newsapi_dir}")

    all_articles: List[Dict[str, Any]] = []
    file_stats = []

    for f in json_files:
        try:
            with open(f, "r", encoding="utf-8") as jf:
                data = json.load(jf)
                arts = data.get("articles", [])
                file_stats.append((f.name, len(arts), data.get("status", "unknown")))
                all_articles.extend(arts)
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    print(f"Total articles extracted across all files: {len(all_articles):,}")
    if not all_articles:
        return pd.DataFrame()

    df = pd.DataFrame(all_articles)
    print(f"\nArticles DataFrame shape: {df.shape[0]:,} rows, {df.shape[1]} columns")
    print("\nColumns and dtypes:")
    print(df.dtypes)

    print("\nNull counts per column:")
    print(df.isnull().sum())

    print(f"\nDuplicate URLs: {df['url'].duplicated().sum() if 'url' in df.columns else 0}")
    print(f"Duplicate titles: {df['title'].duplicated().sum() if 'title' in df.columns else 0}")

    if "publishedAt" in df.columns:
        pub_dt = pd.to_datetime(df["publishedAt"], errors="coerce", utc=True)
        print(f"\npublishedAt date range: {pub_dt.min()} to {pub_dt.max()} (Nulls: {pub_dt.isnull().sum()})")

    print("\nAvailable keys in sample article:")
    sample_art = all_articles[0]
    for k, v in sample_art.items():
        v_str = str(v)[:80]
        print(f"  - {k}: {v_str}")

    print("\n3 Sample rows:")
    sample_display = df[["title", "publishedAt", "url"]].head(3) if "title" in df.columns else df.head(3)
    print(sample_display.to_dict(orient="records"))

    return df


def main():
    inspect_tweets()
    inspect_tweets_price_data()
    inspect_financial_news()
    inspect_newsapi()


if __name__ == "__main__":
    main()
