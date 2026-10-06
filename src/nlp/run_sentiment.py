"""Run FinBERT sentiment scoring pipeline with benchmark, batch inference, and sanity checks."""

import logging
from pathlib import Path
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.nlp.preprocess import clean_for_model
from src.nlp.sentiment import FinBertScorer

logger = logging.getLogger("run_sentiment")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

MAX_SAMPLE_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB safety limit


def benchmark_throughput(scorer: FinBertScorer) -> Tuple[float, float]:
    """Benchmark scoring throughput on news samples and project full run time."""
    gdelt_sample_path = Path("data/sample/gdelt_sample.parquet")
    newsapi_sample_path = Path("data/sample/newsapi_sample.parquet")

    df_gdelt = pd.read_parquet(gdelt_sample_path)
    df_newsapi = pd.read_parquet(newsapi_sample_path)
    df_bench = pd.concat([df_gdelt, df_newsapi], ignore_index=True)

    n_rows = len(df_bench)
    logger.info(f"--- BENCHMARK START: Scoring {n_rows} rows from GDELT & NewsAPI samples ---")

    t0 = time.time()
    _ = scorer.score_dataframe(df_bench, show_progress=False)
    elapsed = time.time() - t0

    throughput = n_rows / max(elapsed, 0.001)
    logger.info(f"--- BENCHMARK RESULT: {n_rows} rows scored in {elapsed:.2f}s ({throughput:.2f} rows/sec) ---")

    texts_all_path = Path("data/processed/texts_all.parquet")
    n_all = len(pd.read_parquet(texts_all_path)) if texts_all_path.exists() else 57653
    projected_seconds = n_all / throughput
    projected_minutes = projected_seconds / 60.0
    logger.info(f"--- PROJECTED FULL CORPUS RUNTIME ({n_all:,} rows): {projected_minutes:.1f} minutes ({projected_seconds:.0f}s) ---")

    return throughput, projected_minutes


def score_and_save_samples(scorer: FinBertScorer) -> Dict[str, pd.DataFrame]:
    """Score all committed sample parquet files, check size limits, and persist."""
    sample_files = [
        "data/sample/gdelt_sample.parquet",
        "data/sample/newsapi_sample.parquet",
        "data/sample/news_labeled_eval_sample.parquet",
        "data/sample/tweets_sample.parquet",
    ]

    scored_samples: Dict[str, pd.DataFrame] = {}

    for sf in sample_files:
        p = Path(sf)
        if not p.exists():
            logger.warning(f"Sample file {p} does not exist, skipping.")
            continue

        df = pd.read_parquet(p)
        logger.info(f"Scoring sample {p.name} ({len(df):,} rows)...")
        df_scored = scorer.score_dataframe(df, text_col="text", source_col="source", show_progress=True)
        df_scored.to_parquet(p, index=False)

        size_bytes = p.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        logger.info(f"Updated {p} ({len(df_scored):,} rows, {size_mb:.2f} MB)")

        if size_bytes > MAX_SAMPLE_FILE_SIZE_BYTES:
            raise RuntimeError(f"FATAL: Sample file {p} exceeded 5 MB limit ({size_mb:.2f} MB)")

        scored_samples[p.name] = df_scored

    return scored_samples


def print_sanity_report(scored_samples: Dict[str, pd.DataFrame], scorer: FinBertScorer):
    """Print sanity statistics, truncation counts, extreme examples, and ticker distributions."""
    print("\n" + "=" * 80)
    print("FINBERT SENTIMENT SCORING SANITY REPORT")
    print("=" * 80)

    # 1. Truncation counts (>128 words before truncation)
    print("\n[1] TRUNCATION CHECK (>128 words in raw text):")
    for name, df in scored_samples.items():
        word_counts = df["text"].fillna("").astype(str).apply(lambda t: len(t.split()))
        n_truncated = int((word_counts > 128).sum())
        pct = (n_truncated / len(df) * 100) if len(df) > 0 else 0
        print(f"  - {name:<35} Total: {len(df):>6,} | >128 words: {n_truncated:>5} ({pct:.2f}%)")

    # 2. Score distributions and mean sentiment per sample
    print("\n[2] SCORE DISTRIBUTIONS & MEAN SENTIMENT:")
    for name, df in scored_samples.items():
        mean_score = df["sentiment_score"].mean()
        std_score = df["sentiment_score"].std()
        counts = df["sentiment_label"].value_counts().to_dict()
        pos = counts.get("positive", 0)
        neg = counts.get("negative", 0)
        neu = counts.get("neutral", 0)
        print(f"  - {name:<35} Mean Score: {mean_score:+.4f} (std: {std_score:.4f}) | Pos: {pos:,} | Neu: {neu:,} | Neg: {neg:,}")

    # 3. 8 Most Positive and 8 Most Negative items for tweets and news
    print("\n[3] EXTREME SENTIMENT EXAMPLES (TWEETS):")
    if "tweets_sample.parquet" in scored_samples:
        df_tw = scored_samples["tweets_sample.parquet"]
        sorted_tw = df_tw.sort_values("sentiment_score", ascending=False)
        print("  Top 4 Most Positive Tweets:")
        for _, row in sorted_tw.head(4).iterrows():
            print(f"    [{row['sentiment_score']:+.4f} | conf: {row['sentiment_confidence']:.2f}] {repr(row['text'][:120])}")
        print("  Top 4 Most Negative Tweets:")
        for _, row in sorted_tw.tail(4).iterrows():
            print(f"    [{row['sentiment_score']:+.4f} | conf: {row['sentiment_confidence']:.2f}] {repr(row['text'][:120])}")

    print("\n[4] EXTREME SENTIMENT EXAMPLES (NEWS - GDELT & NewsAPI):")
    news_dfs = [v for k, v in scored_samples.items() if k in ["gdelt_sample.parquet", "newsapi_sample.parquet"]]
    if news_dfs:
        df_news = pd.concat(news_dfs, ignore_index=True)
        sorted_news = df_news.sort_values("sentiment_score", ascending=False)
        print("  Top 4 Most Positive Headlines:")
        for _, row in sorted_news.head(4).iterrows():
            print(f"    [{row['sentiment_score']:+.4f} | conf: {row['sentiment_confidence']:.2f}] {repr(row['text'][:120])}")
        print("  Top 4 Most Negative Headlines:")
        for _, row in sorted_news.tail(4).iterrows():
            print(f"    [{row['sentiment_score']:+.4f} | conf: {row['sentiment_confidence']:.2f}] {repr(row['text'][:120])}")

    # 4. Ticker-level mean sentiment in tweet sample
    if "tweets_sample.parquet" in scored_samples:
        df_tw = scored_samples["tweets_sample.parquet"]
        print("\n[5] TWEET SAMPLE TICKER-LEVEL SENTIMENT (by ticker_hint):")
        grp = df_tw.groupby("ticker_hint")["sentiment_score"].agg(["count", "mean", "std"]).reset_index()
        grp = grp.sort_values("count", ascending=False)
        for _, r in grp.iterrows():
            print(f"    Ticker: {r['ticker_hint']:<6} | Count: {int(r['count']):>5,} | Mean Sentiment: {r['mean']:+.4f} | Std: {r['std']:.4f}")

    print("\n" + "=" * 80 + "\n")


def main():
    scorer = FinBertScorer()

    # Step 1: Benchmark and project full runtime
    throughput, projected_minutes = benchmark_throughput(scorer)

    # Step 2: Score sample files
    scored_samples = score_and_save_samples(scorer)

    # Step 3: Print Sanity Report
    print_sanity_report(scored_samples, scorer)


if __name__ == "__main__":
    main()
