"""File export module and CLI for AI Risk Signals.

Allows exporting filtered signals to JSONL, CSV, or Parquet for downstream
modules and file-based data consumption.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from src.engine.store import SignalStore

logger = logging.getLogger(__name__)


def export_signals(
    out_path: Union[str, Path],
    output_format: str = "jsonl",
    ticker: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    min_impact: Optional[float] = None,
    max_impact: Optional[float] = None,
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    store: Optional[SignalStore] = None,
) -> int:
    """Export filtered risk signals to a file in jsonl, csv, or parquet format.

    Returns the number of rows exported.
    """
    if store is None:
        store = SignalStore()

    target_path = Path(out_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = output_format.lower().strip()

    # Query matching records
    # If limit is None, query up to total_count
    effective_limit = limit if limit is not None else store.total_count
    records = store.query(
        ticker=ticker,
        since=since,
        until=until,
        min_impact=min_impact,
        max_impact=max_impact,
        event_type=event_type,
        source=source,
        limit=effective_limit,
        offset=offset,
    )

    if fmt == "jsonl":
        with open(target_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    elif fmt == "csv":
        df = pd.DataFrame(records)
        if not df.empty:
            # Serialize nested dicts/lists to JSON strings for CSV compatibility
            if "matched_triggers" in df.columns:
                df["matched_triggers"] = df["matched_triggers"].apply(json.dumps)
            if "impact_components" in df.columns:
                df["impact_components"] = df["impact_components"].apply(json.dumps)
        df.to_csv(target_path, index=False, encoding="utf-8")
    elif fmt == "parquet":
        df = pd.DataFrame(records)
        df.to_parquet(target_path, index=False)
    else:
        raise ValueError(f"Unsupported export format: '{output_format}'. Must be jsonl, csv, or parquet.")

    logger.info(f"Exported {len(records):,} signals to {target_path.as_posix()} ({fmt})")
    return len(records)


def main() -> None:
    """CLI entrypoint for exporting risk signals to disk."""
    parser = argparse.ArgumentParser(
        description="Export AI Risk Signals to JSONL, CSV, or Parquet for downstream consumption."
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv", "parquet"],
        default="jsonl",
        help="Target output format (default: jsonl)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Target file path to write exported signals",
    )
    parser.add_argument("--ticker", help="Filter by ticker symbol (e.g. TSLA, AAPL, MARKET)")
    parser.add_argument("--since", help="Filter signals on or after ISO timestamp (YYYY-MM-DD or full ISO)")
    parser.add_argument("--until", help="Filter signals on or before ISO timestamp")
    parser.add_argument("--min-impact", type=float, help="Minimum impact score threshold (1.0 to 10.0)")
    parser.add_argument("--max-impact", type=float, help="Maximum impact score threshold (1.0 to 10.0)")
    parser.add_argument("--event-type", help="Filter by event category (e.g. Earnings, Credit Event)")
    parser.add_argument("--source", help="Filter by source (twitter_kaggle, newsapi, gdelt)")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to export")
    parser.add_argument("--sample", action="store_true", help="Explicitly use data/sample/signals_sample.parquet")

    args = parser.parse_args()

    store = SignalStore(data_path="data/sample/signals_sample.parquet" if args.sample else None)
    n_exported = export_signals(
        out_path=args.out,
        output_format=args.format,
        ticker=args.ticker,
        since=args.since,
        until=args.until,
        min_impact=args.min_impact,
        max_impact=args.max_impact,
        event_type=args.event_type,
        source=args.source,
        limit=args.limit,
        store=store,
    )
    print(f"Successfully exported {n_exported} signals to {args.out} ({args.format})")


if __name__ == "__main__":
    main()
