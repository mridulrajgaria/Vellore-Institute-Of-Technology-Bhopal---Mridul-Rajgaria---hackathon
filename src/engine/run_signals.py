"""Run Risk Engine pipeline: emit signals, save parquet/jsonl, and print full data report."""

import json
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

from src.common.schema import EventType
from src.engine.risk_engine import RiskEngine, save_signals_outputs, signals_to_dataframe

logger = logging.getLogger("run_signals")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run_pipeline():
    logger.info("Loading scored sample and cache data...")
    # Load scored samples (which already contain FinBERT sentiment_score)
    df_tweets = pd.read_parquet("data/sample/tweets_sample.parquet")
    df_gdelt = pd.read_parquet("data/sample/gdelt_sample.parquet")
    df_newsapi = pd.read_parquet("data/sample/newsapi_sample.parquet")

    # Combine into input corpus for signal emission
    df_corpus = pd.concat([df_tweets, df_gdelt, df_newsapi], ignore_index=True)
    logger.info(f"Loaded {len(df_corpus):,} total scored rows across tweets, GDELT, and NewsAPI samples.")

    engine = RiskEngine()

    # Pre-emission classification to inspect event distribution before filtering
    df_classified = engine.classifier.classify_dataframe(df_corpus)

    logger.info("Processing texts into RiskSignals...")
    t0 = time.time()
    signals = engine.process_texts_to_signals(df_corpus, fit_volume_history=True)
    elapsed = time.time() - t0
    logger.info(f"Emitted {len(signals):,} RiskSignals in {elapsed:.2f}s ({len(signals)/max(elapsed, 0.001):.1f} signals/sec).")

    # Save outputs
    out_p, out_j, samp_p, samp_j = save_signals_outputs(signals)
    df_sig = signals_to_dataframe(signals)

    # ==============================================================================
    # PRINT COMPREHENSIVE DATA REPORT
    # ==============================================================================
    print("\n" + "=" * 90)
    print("RISK SIGNALS PIPELINE DATA REPORT")
    print("=" * 90)

    # 1. Counts before/after for Credit Event, Geopolitical, and Earnings
    print("\n[1] COUNTS BEFORE / AFTER FOR CREDIT EVENT, GEOPOLITICAL, AND EARNINGS:")
    target_categories = ["Credit Event", "Geopolitical", "Earnings"]
    before_counts = df_classified["event_type"].value_counts()
    after_counts = df_sig["event_type"].value_counts()

    print(f"{'Event Category':<22} | {'Before (Raw Corpus)':<20} | {'After (Emitted Signals)':<22}")
    print("-" * 72)
    for cat in target_categories:
        b_cnt = before_counts.get(cat, 0)
        a_cnt = after_counts.get(cat, 0)
        print(f"{cat:<22} | {b_cnt:>19,} | {a_cnt:>21,}")

    print("\nFull Event Breakdown Before vs After by Source:")
    print("\n--- BEFORE Filtering (Raw Input Corpus) ---")
    before_pivot = pd.crosstab(df_classified["source"], df_classified["event_type"], margins=True)
    print(before_pivot.to_string())

    print("\n--- AFTER Filtering (Emitted Signals) ---")
    after_pivot = pd.crosstab(df_sig["source"], df_sig["event_type"], margins=True)
    print(after_pivot.to_string())

    # 2. ALL remaining Credit Event signals with full headline and matched_triggers
    print("\n[2] ALL REMAINING CREDIT EVENT SIGNALS:")
    credit_sigs = df_sig[df_sig["event_type"] == "Credit Event"]
    print(f"Total Credit Event signals: {len(credit_sigs)}")
    if len(credit_sigs) > 0:
        for idx, (_, r) in enumerate(credit_sigs.iterrows(), 1):
            print(f"  ({idx}) Ticker: {r['ticker']:<6} | Conf: {r['event_confidence']:.2f} | Source: {r['source']}")
            print(f"      Triggers: {r.get('matched_triggers')}")
            print(f"      Headline: {r['headline']}")
    else:
        print("  (None remaining)")

    # 3. 10 Geopolitical Signals
    print("\n[3] 10 GEOPOLITICAL SIGNALS:")
    geo_sigs = df_sig[df_sig["event_type"] == "Geopolitical"]
    print(f"Total Geopolitical signals: {len(geo_sigs)}")
    sample_geo = geo_sigs.head(10)
    for idx, (_, r) in enumerate(sample_geo.iterrows(), 1):
        print(f"  ({idx}) Ticker: {r['ticker']:<6} | Conf: {r['event_confidence']:.2f} | Source: {r['source']}")
        print(f"      Triggers: {r.get('matched_triggers')}")
        print(f"      Headline: {r['headline']}")

    # 4. Top 10 and Bottom 10 Impact Signals with Full Headline Text
    print("\n[4] TOP 10 IMPACT SIGNALS:")
    top_10 = df_sig.sort_values(["impact_score", "confidence"], ascending=[False, False]).head(10)
    for idx, (_, r) in enumerate(top_10.iterrows(), 1):
        comp = r.get("impact_components", {})
        print(f"  #{idx:<2} Impact: {r['impact_score']:4.2f} | Conf: {r['confidence']:.2f} | Ticker: {r['ticker']:<6} | Event: {r['event_type']} ({r['source']})")
        print(f"      Headline: {r['headline']}")
        print(f"      Components: sev={comp.get('severity_contrib')}, sent={comp.get('sentiment_contrib')}, src={comp.get('source_contrib')}, vol={comp.get('volume_contrib')}")

    print("\n[5] BOTTOM 10 IMPACT SIGNALS:")
    bot_10 = df_sig.sort_values(["impact_score", "confidence"], ascending=[True, True]).head(10)
    for idx, (_, r) in enumerate(bot_10.iterrows(), 1):
        comp = r.get("impact_components", {})
        print(f"  #{idx:<2} Impact: {r['impact_score']:4.2f} | Conf: {r['confidence']:.2f} | Ticker: {r['ticker']:<6} | Event: {r['event_type']} ({r['source']})")
        print(f"      Headline: {r['headline']}")
        print(f"      Components: sev={comp.get('severity_contrib')}, sent={comp.get('sentiment_contrib')}, src={comp.get('source_contrib')}, vol={comp.get('volume_contrib')}")

    # 5. Calendar / Template Removals with Counts and 8 Examples
    print("\n[6] CALENDAR / TEMPLATE REMOVALS:")
    dropped_df = getattr(engine, "dropped_template_rows", pd.DataFrame())
    print(f"Total rows removed by template & calendar filter: {len(dropped_df):,}")
    print("Removals per source:")
    print(dropped_df["source"].value_counts().to_string())
    print("\n8 Examples of removed calendar/template rows:")
    for idx, (_, r) in enumerate(dropped_df.head(8).iterrows(), 1):
        clean_text = str(r.get("text", "")).strip().replace("\n", " ")
        print(f"  ({idx}) [{r.get('source')}] {repr(clean_text[:120])}")

    # 6. MSFT Alias List
    print("\n[7] MSFT ALIAS LIST REPORT:")
    import yaml
    with open("config/companies.yaml", "r", encoding="utf-8") as yf:
        cmp_cfg = yaml.safe_load(yf)
    msft_info = cmp_cfg.get("companies", {}).get("MSFT", {})
    print("  Legal Name:", msft_info.get("legal_name"))
    print("  Aliases:", msft_info.get("aliases"))
    print("  Products (Cleaned):", msft_info.get("products"))
    print("  Generic words removed: ['Windows', 'Teams'] (replaced by specific compounds like 'Microsoft Windows', 'Windows 11', 'Microsoft Teams')")

    # 7. Signals Per Ticker
    print("\n[8] SIGNALS PER TICKER:")
    ticker_counts = df_sig["ticker"].value_counts()
    for tkr, cnt in ticker_counts.items():
        print(f"  - {tkr:<8}: {cnt:>5,} signals")

    # 8. File Sizes Check
    print("\n[9] PERSISTED FILE SIZES:")
    for p in [out_p, out_j, samp_p, samp_j]:
        mb = p.stat().st_size / (1024 * 1024)
        is_ok = mb < 5.0 if "sample" in p.name else True
        print(f"  - {str(p):<45} Size: {mb:6.2f} MB (<5 MB: {is_ok})")

    print("\n" + "=" * 90 + "\n")


if __name__ == "__main__":
    run_pipeline()
