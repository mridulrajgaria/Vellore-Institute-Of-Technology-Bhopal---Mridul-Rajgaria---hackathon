"""Risk Engine for transforming scored multi-source texts into validated RiskSignals."""

from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.common.config import load_engine_config
from src.common.schema import EventType, RiskSignal
from src.engine.impact_scorer import ImpactScorer
from src.nlp.event_classifier import EventClassifier
from src.nlp.preprocess import clean_for_model
from src.nlp.sentiment import FinBertScorer

logger = logging.getLogger("risk_engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

MAX_SAMPLE_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB safety limit


class RiskEngine:
    """End-to-end Risk Engine orchestrating Event Classification, Impact Scoring, and Signal Emission."""

    def __init__(self, config_path: str = "config/engine.yaml"):
        self.config_path = config_path
        self.classifier = EventClassifier(config_path=config_path)
        self.impact_scorer = ImpactScorer(config_path=config_path)

    def process_texts_to_signals(
        self,
        df: pd.DataFrame,
        fit_volume_history: bool = True,
    ) -> List[RiskSignal]:
        """Convert a dataframe of scored/relevant texts into individual RiskSignal records.

        Follows strict emission rules:
        - Excludes financial_phrasebank rows.
        - Rows where primary_ticker == 'MARKET' or ticker_hint == 'MARKET' emit ticker 'MARKET' (weight 1.0).
        - Broadcast tweets (primary_ticker is null or is_broadcast is True) emit one signal per linked company ticker (weight 1/n).
        - Single company rows emit one signal with attribution_weight = 1.0.
        """
        # Exclude financial_phrasebank completely
        valid_df = df[(df["is_relevant"] == True) & (df["source"] != "financial_phrasebank")].copy()

        if fit_volume_history and "source" in valid_df.columns:
            tw_mask = valid_df["source"].isin(["twitter", "twitter_kaggle"])
            if tw_mask.sum() > 0:
                self.impact_scorer.fit_tweet_volume_history(valid_df[tw_mask])

        # Step 1: Run event classification if not already present
        if "event_type" not in valid_df.columns or "is_calendar" not in valid_df.columns:
            valid_df = self.classifier.classify_dataframe(valid_df)

        # Step 1b: Template / Spam / Calendar Filter
        cal_mask = valid_df.get("is_calendar", pd.Series(False, index=valid_df.index)) == True
        templ_mask = valid_df.get("is_template", pd.Series(False, index=valid_df.index)) == True
        drop_mask = cal_mask | templ_mask
        self.dropped_template_rows = valid_df[drop_mask].copy()
        self.dropped_template_count = len(self.dropped_template_rows)
        self.dropped_calendar_rows = valid_df[cal_mask].copy()
        self.dropped_calendar_count = len(self.dropped_calendar_rows)
        valid_df = valid_df[~drop_mask].copy()

        # Step 1c: Generic dictionary word invalidation for MSFT (e.g. "windows", "teams")
        generic_msft_words = {"windows", "window", "teams"}
        if "matched_term" in valid_df.columns:
            invalid_term_mask = valid_df["matched_term"].astype(str).str.lower().isin(generic_msft_words)
            for idx in valid_df[invalid_term_mask].index:
                t_str = str(valid_df.at[idx, "text"] or "") + " " + str(valid_df.at[idx, "title"] or "")
                if not re.search(r"\b(?:microsoft|msft)\b", t_str, re.IGNORECASE):
                    curr_links = valid_df.at[idx, "linked_tickers"]
                    if isinstance(curr_links, (list, np.ndarray)):
                        cleaned_links = [t for t in curr_links if t != "MSFT"]
                        valid_df.at[idx, "linked_tickers"] = cleaned_links
                    if valid_df.at[idx, "primary_ticker"] == "MSFT":
                        valid_df.at[idx, "primary_ticker"] = None
                    valid_df.at[idx, "link_type"] = None

        signals: List[RiskSignal] = []

        # Iterate through rows and emit signals according to attribution
        for _, row in valid_df.iterrows():
            ts_raw = row.get("ts")
            if pd.isnull(ts_raw) or ts_raw is None:
                dt_obj = datetime.now()
            elif isinstance(ts_raw, pd.Timestamp):
                dt_obj = ts_raw.to_pydatetime()
            elif isinstance(ts_raw, datetime):
                dt_obj = ts_raw
            else:
                try:
                    dt_obj = pd.to_datetime(ts_raw, utc=True).to_pydatetime()
                except Exception:
                    dt_obj = datetime.now()

            text_str = str(row.get("text", "")).strip()
            headline = str(row.get("title") or text_str)[:200]
            source_str = str(row.get("source", "unknown"))
            text_id_str = str(row.get("text_id", ""))

            sent_score = float(row.get("sentiment_score", 0.0))
            sent_conf = float(row.get("sentiment_confidence", 0.8))

            event_cat_str = str(row.get("event_type", EventType.OTHER.value))
            event_conf = float(row.get("event_confidence", 0.5))
            secondary_cat_str = row.get("secondary_event")
            matched_trigs = row.get("matched_triggers", [])
            if isinstance(matched_trigs, np.ndarray):
                matched_trigs = matched_trigs.tolist()
            is_analyst = bool(row.get("is_analyst_action", False))

            dup_cnt = int(row.get("dup_count", 1)) if not pd.isna(row.get("dup_count", 1)) else 1

            # Determine emission targets
            primary_ticker = row.get("primary_ticker")
            ticker_hint = row.get("ticker_hint")
            ticker_hints = row.get("ticker_hints", [])
            if not isinstance(ticker_hints, (list, np.ndarray)):
                ticker_hints = [ticker_hint] if ticker_hint else []
            link_type = row.get("link_type", "")
            is_broad = bool(row.get("is_broadcast", False))
            linked_tickers_raw = row.get("linked_tickers")

            if isinstance(linked_tickers_raw, list):
                linked_tickers = [t for t in linked_tickers_raw if t and t != "MARKET"]
            elif isinstance(linked_tickers_raw, np.ndarray):
                linked_tickers = [t for t in linked_tickers_raw.tolist() if t and t != "MARKET"]
            else:
                linked_tickers = []

            # Check broadcast tweet condition:
            # 3 or more real tickers OR explicitly marked as broadcast
            if is_broad or (len(linked_tickers) >= 3):
                # Broadcast tweets emit signals ONLY when event_type is not Other AND event_confidence >= 0.8
                if event_cat_str == EventType.OTHER.value or event_conf < 0.8:
                    continue  # Emit nothing!

                n_tickers = len(linked_tickers) if len(linked_tickers) > 0 else 1
                w = 1.0 / n_tickers
                target_tickers = [(t, w, True) for t in linked_tickers]

            # Rule 1: MARKET item
            elif primary_ticker == "MARKET" or ticker_hint == "MARKET":
                target_tickers = [("MARKET", 1.0, False)]

            # Rule 2: Real linked company ticker
            elif linked_tickers:
                target_t = primary_ticker if (primary_ticker and primary_ticker in linked_tickers) else linked_tickers[0]
                target_tickers = [(target_t, 1.0, False)]

            # Rule 3: Single scrape hint fallback (only if link_type is hint_only and exactly 1 scrape label)
            elif link_type == "hint_only" and len(ticker_hints) <= 1 and ticker_hint and ticker_hint != "MARKET":
                if source_str in ["twitter", "twitter_kaggle"]:
                    target_tickers = [(ticker_hint, 1.0, False)]
                else:
                    target_tickers = [("MARKET", 1.0, False)]

            # Rule 4: MARKET fallback for macroeconomic text without company link
            elif not linked_tickers and primary_ticker is None and ticker_hint is None:
                target_tickers = [("MARKET", 1.0, False)]

            else:
                # Scrape hint only with multiple hints or unverified text -> emit nothing
                continue

            for ticker_symbol, attr_w, broadcast_flag in target_tickers:
                # Compute explainable impact score
                impact_res = self.impact_scorer.compute_impact(
                    event_type=event_cat_str,
                    sentiment_score=sent_score,
                    source=source_str,
                    dup_count=dup_cnt,
                    ticker=ticker_symbol,
                    ts=dt_obj,
                )
                imp_raw = impact_res["impact_score"]
                imp_components = dict(impact_res["impact_components"])

                # When broadcast tweet emits: impact = 1 + (impact_raw - 1) * attribution_weight
                if broadcast_flag and attr_w < 1.0:
                    imp_score = 1.0 + (imp_raw - 1.0) * attr_w
                    for k in ["severity_contrib", "sentiment_contrib", "source_contrib", "volume_contrib"]:
                        if k in imp_components:
                            imp_components[k] = round(imp_components[k] * attr_w, 4)
                else:
                    imp_score = imp_raw

                combined_conf = float(min(1.0, max(0.0, 0.5 * sent_conf + 0.5 * event_conf)))

                # Construct validated RiskSignal
                signal = RiskSignal(
                    ts=dt_obj,
                    ticker=str(ticker_symbol),
                    source=source_str,
                    text_id=text_id_str,
                    headline=headline,
                    sentiment_score=round(sent_score, 4),
                    event_type=EventType(event_cat_str),
                    impact_score=round(float(min(10.0, max(1.0, imp_score))), 4),
                    confidence=round(combined_conf, 4),
                    event_confidence=round(event_conf, 4),
                    secondary_event=EventType(secondary_cat_str) if (secondary_cat_str and pd.notna(secondary_cat_str)) else None,
                    attribution_weight=round(attr_w, 4),
                    matched_triggers=matched_trigs,
                    impact_components=imp_components,
                    is_broadcast=broadcast_flag,
                    is_analyst_action=is_analyst,
                )
                signals.append(signal)

        return signals


def signals_to_dataframe(signals: List[RiskSignal]) -> pd.DataFrame:
    """Convert a list of RiskSignal objects into a pandas DataFrame."""
    records = []
    for s in signals:
        rec = s.model_dump()
        rec["event_type"] = s.event_type.value
        if s.secondary_event:
            rec["secondary_event"] = s.secondary_event.value
        records.append(rec)
    return pd.DataFrame(records)


def save_signals_outputs(
    signals: List[RiskSignal],
    processed_dir: Path = Path("data/processed"),
    sample_dir: Path = Path("data/sample"),
) -> Tuple[Path, Path, Path, Path]:
    """Save signals to processed parquet/jsonl and sample parquet/jsonl."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    df_signals = signals_to_dataframe(signals)

    # 1. Full processed outputs
    out_parquet = processed_dir / "signals.parquet"
    out_jsonl = processed_dir / "signals.jsonl"
    df_signals.to_parquet(out_parquet, index=False)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for s in signals:
            f.write(json.dumps(s.model_dump(), default=str) + "\n")

    logger.info(f"Saved full signals: {out_parquet} ({len(df_signals):,} rows, {out_parquet.stat().st_size / (1024*1024):.2f} MB)")
    logger.info(f"Saved full signals JSONL: {out_jsonl} ({out_jsonl.stat().st_size / (1024*1024):.2f} MB)")

    # 2. Committed sample outputs (< 5 MB)
    sample_parquet = sample_dir / "signals_sample.parquet"
    sample_jsonl = sample_dir / "signals_sample.jsonl"

    # Deterministic sampling: up to 5,000 signals for parquet (< 5 MB)
    if len(df_signals) > 5000:
        df_sample_p = df_signals.sample(n=5000, random_state=42).sort_values("ts")
    else:
        df_sample_p = df_signals
    df_sample_p.to_parquet(sample_parquet, index=False)

    # Deterministic 500-row demo extract for jsonl (< 5 MB)
    # Include every Credit Event, Geopolitical, and Regulatory row that survives (up to 500 cap)
    rare_events = ["Credit Event", "Geopolitical", "Regulatory"]
    rare_mask = df_signals["event_type"].isin(rare_events)
    df_rare = df_signals[rare_mask]

    target_n = min(500, len(df_signals))
    if len(df_rare) >= target_n:
        df_sample_j = df_rare.sample(n=target_n, random_state=42).sort_values("ts")
    else:
        needed = target_n - len(df_rare)
        df_remaining = df_signals[~rare_mask]
        if len(df_remaining) > needed:
            strata = df_remaining.groupby(["source", "event_type"], group_keys=False)
            df_sampled_rem = strata.apply(
                lambda g: g.sample(
                    n=max(1, int(np.round(len(g) / len(df_remaining) * needed))),
                    random_state=42,
                ) if len(g) > 0 else g
            )
            if len(df_sampled_rem) > needed:
                df_sampled_rem = df_sampled_rem.sample(n=needed, random_state=42)
            elif len(df_sampled_rem) < needed:
                deficit = needed - len(df_sampled_rem)
                filler = df_remaining[~df_remaining.index.isin(df_sampled_rem.index)]
                if len(filler) > 0:
                    df_sampled_rem = pd.concat([
                        df_sampled_rem,
                        filler.sample(n=min(deficit, len(filler)), random_state=42),
                    ])
        else:
            df_sampled_rem = df_remaining

        df_sample_j = pd.concat([df_rare, df_sampled_rem]).sort_values("ts")
        if len(df_sample_j) > target_n:
            df_sample_j = df_sample_j.iloc[:target_n]

    with open(sample_jsonl, "w", encoding="utf-8") as f:
        for _, r in df_sample_j.iterrows():
            f.write(json.dumps(r.to_dict(), default=str) + "\n")

    p_size = sample_parquet.stat().st_size
    j_size = sample_jsonl.stat().st_size

    if p_size > MAX_SAMPLE_FILE_SIZE_BYTES:
        raise RuntimeError(f"Sample parquet {sample_parquet} exceeds 5 MB limit ({p_size / 1024**2:.2f} MB)")
    if j_size > MAX_SAMPLE_FILE_SIZE_BYTES:
        raise RuntimeError(f"Sample jsonl {sample_jsonl} exceeds 5 MB limit ({j_size / 1024**2:.2f} MB)")

    logger.info(f"Saved sample parquet: {sample_parquet} ({len(df_sample_p):,} rows, {p_size / (1024*1024):.2f} MB)")
    logger.info(f"Saved sample jsonl demo: {sample_jsonl} ({len(df_sample_j):,} rows, {j_size / (1024*1024):.2f} MB)")

    return out_parquet, out_jsonl, sample_parquet, sample_jsonl
