"""Evaluates event classification performance against human-annotated event labels."""

import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from src.common.schema import EventType
from src.nlp.event_classifier import EventClassifier

logger = logging.getLogger("eval_events")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

EVENT_CLASSES = [e.value for e in EventType]


def evaluate_event_labels(
    csv_path: str = "data/sample/sentiment_hand_label_template.csv",
    out_md: str = "docs/event_eval.md",
) -> Dict[str, Any]:
    """Evaluate predicted event classifications against human hand labels in my_event column."""
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Template file not found at {p}")

    df = pd.read_csv(p, encoding="utf-8")
    if "my_event" not in df.columns:
        raise ValueError("Missing 'my_event' column in template CSV.")

    # Filter to annotated rows
    df_annotated = df[df["my_event"].fillna("").astype(str).str.strip() != ""].copy()
    df_annotated["my_event"] = df_annotated["my_event"].astype(str).str.strip()

    valid_mask = df_annotated["my_event"].isin(EVENT_CLASSES)
    df_valid = df_annotated[valid_mask].copy()

    if len(df_valid) == 0:
        logger.warning("No labeled event rows found yet in template. Fill 'my_event' first.")
        return {}

    logger.info(f"Evaluating {len(df_valid)} hand-annotated event rows...")

    classifier = EventClassifier()
    predictions = []
    for _, row in df_valid.iterrows():
        txt = str(row["text"])
        src = str(row.get("source", ""))
        res = classifier.classify(txt, source=src)
        predictions.append(res["event_type"])

    y_true = df_valid["my_event"].tolist()
    y_pred = predictions

    macro_f1 = float(f1_score(y_true, y_pred, labels=EVENT_CLASSES, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, labels=EVENT_CLASSES, average="weighted", zero_division=0))
    report = classification_report(y_true, y_pred, labels=EVENT_CLASSES, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=EVENT_CLASSES).tolist()

    # Share of rows classified as Other per source
    df_valid["pred_event"] = y_pred
    other_share_by_source = {}
    for src, grp in df_valid.groupby("source"):
        other_cnt = (grp["pred_event"] == EventType.OTHER.value).sum()
        other_share_by_source[src] = {
            "total": len(grp),
            "other_count": int(other_cnt),
            "other_pct": float(other_cnt / len(grp) * 100),
        }

    # Generate Markdown Report
    out_p = Path(out_md)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Event Classification Evaluation Report",
        "",
        f"- **Total Annotated Rows:** {len(df_valid)}",
        f"- **Macro-F1:** {macro_f1:.4f}",
        f"- **Weighted-F1:** {weighted_f1:.4f}",
        "",
        "## Share of Rows Classified as 'Other' per Source",
    ]
    for src, info in other_share_by_source.items():
        lines.append(f"- **{src}:** {info['other_count']}/{info['total']} ({info['other_pct']:.1f}% Other)")

    lines.extend([
        "",
        "## Per-Class Performance",
        "",
        "| Event Type | Precision | Recall | F1-Score | Support |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ])
    for cat in EVENT_CLASSES:
        if cat in report:
            lines.append(
                f"| {cat} | {report[cat]['precision']:.4f} | {report[cat]['recall']:.4f} | {report[cat]['f1-score']:.4f} | {report[cat]['support']} |"
            )

    lines.extend([
        "",
        "## Confusion Matrix",
        "```",
        f"Classes: {EVENT_CLASSES}",
        str(np.array(cm)),
        "```",
    ])

    with open(out_p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Saved event evaluation report to {out_p}")
    return {
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "other_share_by_source": other_share_by_source,
        "confusion_matrix": cm,
    }


if __name__ == "__main__":
    evaluate_event_labels()
