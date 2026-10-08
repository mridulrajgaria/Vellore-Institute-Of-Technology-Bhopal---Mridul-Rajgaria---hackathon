"""Evaluate FinBERT sentiment predictions against human hand labels."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from src.nlp.sentiment import FinBertScorer

logger = logging.getLogger("eval_hand_labels")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

LABELS = ["negative", "neutral", "positive"]


def evaluate_hand_labels(
    csv_path: str = "data/sample/sentiment_hand_label_template.csv",
    out_md: str = "docs/sentiment_hand_eval.md",
) -> Dict[str, Any]:
    """Read filled hand label template, compare against FinBERT predictions, and write markdown report."""
    csv_p = Path(csv_path)
    if not csv_p.exists():
        raise FileNotFoundError(f"Hand label file not found at {csv_p}")

    df = pd.read_csv(csv_p, encoding="utf-8")
    if "my_label" not in df.columns:
        raise ValueError("Missing 'my_label' column in hand label file.")

    df_labeled = df[df["my_label"].fillna("").astype(str).str.strip() != ""].copy()
    df_labeled["my_label"] = df_labeled["my_label"].astype(str).str.strip().str.lower()

    valid_mask = df_labeled["my_label"].isin(LABELS)
    df_valid = df_labeled[valid_mask].copy()

    if len(df_valid) == 0:
        logger.warning("No labeled rows found yet in hand label file. Fill 'my_label' with positive/negative/neutral first.")
        return {}

    logger.info(f"Evaluating {len(df_valid)} hand-labeled rows...")

    scorer = FinBertScorer()
    texts = df_valid["text"].fillna("").astype(str).tolist()
    sources = df_valid["source"].fillna("").astype(str).tolist() if "source" in df_valid.columns else None

    results = scorer.score_texts(texts, sources)
    y_pred = [r["sentiment_label"] for r in results]
    y_true = df_valid["my_label"].tolist()

    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    report = classification_report(y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABELS).tolist()

    # Breakdown by source
    by_source_report = {}
    if "source" in df_valid.columns:
        for src, grp in df_valid.groupby("source"):
            grp_indices = grp.index
            s_true = grp["my_label"].tolist()
            s_pred = [y_pred[df_valid.index.get_loc(idx)] for idx in grp_indices]
            s_acc = float(accuracy_score(s_true, s_pred))
            s_f1 = float(f1_score(s_true, s_pred, average="macro", zero_division=0))
            by_source_report[src] = {"n": len(grp), "accuracy": s_acc, "macro_f1": s_f1}

    out_p = Path(out_md)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    source_breakdown_md = "\n".join(
        f"- **{src}:** N={v['n']}, Accuracy={v['accuracy']*100:.1f}%, Macro-F1={v['macro_f1']:.4f}"
        for src, v in by_source_report.items()
    )

    md_content = f"""# FinBERT Human Hand-Label Evaluation Report

## Overview
- **Total Hand-Labeled Rows Evaluated:** {len(df_valid)}
- **Overall Accuracy:** {acc * 100:.2f}%
- **Overall Macro-F1:** {macro_f1:.4f}
- **Overall Weighted-F1:** {weighted_f1:.4f}

## Performance by Text Source
{source_breakdown_md}

---

## Per-Class Breakdown

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Negative** | {report['negative']['precision']:.4f} | {report['negative']['recall']:.4f} | {report['negative']['f1-score']:.4f} | {report['negative']['support']} |
| **Neutral** | {report['neutral']['precision']:.4f} | {report['neutral']['recall']:.4f} | {report['neutral']['f1-score']:.4f} | {report['neutral']['support']} |
| **Positive** | {report['positive']['precision']:.4f} | {report['positive']['recall']:.4f} | {report['positive']['f1-score']:.4f} | {report['positive']['support']} |

---

## Confusion Matrix

```
                     Predicted Negative   Predicted Neutral   Predicted Positive
True Negative:       {cm[0][0]:<20} {cm[0][1]:<19} {cm[0][2]:<19}
True Neutral:        {cm[1][0]:<20} {cm[1][1]:<19} {cm[1][2]:<19}
True Positive:       {cm[2][0]:<20} {cm[2][1]:<19} {cm[2][2]:<19}
```
"""
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"Saved hand label evaluation report to {out_p}")

    # Save structured JSON
    json_path = out_p.with_suffix(".json")
    json_data = {
        "total_evaluated": len(df_valid),
        "accuracy": acc,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "by_source": by_source_report,
        "per_class": {
            cls: {
                "precision": report[cls]["precision"],
                "recall": report[cls]["recall"],
                "f1": report[cls]["f1-score"],
                "support": report[cls]["support"],
            }
            for cls in LABELS
        },
        "confusion_matrix": cm,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    logger.info(f"Saved hand label evaluation JSON to {json_path}")

    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "by_source": by_source_report,
        "confusion_matrix": cm,
    }


if __name__ == "__main__":
    evaluate_hand_labels()
