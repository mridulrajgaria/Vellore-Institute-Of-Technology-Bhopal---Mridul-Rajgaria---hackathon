"""Evaluate FinBERT sentiment scorer on Financial PhraseBank with baselines and honesty reporting."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.nlp.sentiment import FinBertScorer

logger = logging.getLogger("eval_sentiment")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

LABEL_TO_NUM = {"negative": -1, "neutral": 0, "positive": 1}
LABELS = ["negative", "neutral", "positive"]


def compute_metrics(y_true: list, y_pred: list, y_scores: list) -> Dict[str, Any]:
    """Compute classification metrics and correlations."""
    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    report = classification_report(y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABELS).tolist()

    y_true_num = [LABEL_TO_NUM[y] for y in y_true]
    p_corr, p_val = pearsonr(y_true_num, y_scores)
    s_corr, s_val = spearmanr(y_true_num, y_scores)

    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "pearson_corr": float(p_corr) if not np.isnan(p_corr) else 0.0,
        "pearson_pvalue": float(p_val) if not np.isnan(p_val) else 1.0,
        "spearman_corr": float(s_corr) if not np.isnan(s_corr) else 0.0,
        "spearman_pvalue": float(s_val) if not np.isnan(s_val) else 1.0,
        "per_class": {
            lbl: {
                "precision": float(report[lbl]["precision"]),
                "recall": float(report[lbl]["recall"]),
                "f1": float(report[lbl]["f1-score"]),
                "support": int(report[lbl]["support"]),
            }
            for lbl in LABELS
        },
        "confusion_matrix": cm,
    }


def plot_confusion_matrix(cm: list, labels: list, out_path: Path, title: str = "FinBERT Confusion Matrix"):
    """Plot and save confusion matrix heatmap."""
    fig, ax = plt.subplots(figsize=(6, 5))
    cm_arr = np.array(cm)
    im = ax.imshow(cm_arr, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    ax.set(
        xticks=np.arange(cm_arr.shape[1]),
        yticks=np.arange(cm_arr.shape[0]),
        xticklabels=labels,
        yticklabels=labels,
        title=title,
        ylabel="True Label",
        xlabel="Predicted Label",
    )

    thresh = cm_arr.max() / 2.0
    for i in range(cm_arr.shape[0]):
        for j in range(cm_arr.shape[1]):
            val = cm_arr[i, j]
            ax.text(
                j,
                i,
                f"{val:,}",
                ha="center",
                va="center",
                color="white" if val > thresh else "black",
                fontweight="bold",
            )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    logger.info(f"Saved confusion matrix plot to {out_path}")


def export_hand_label_template(
    texts_all_path: str = "data/processed/texts_all.parquet",
    out_path: str = "data/sample/sentiment_hand_label_template.csv",
    random_state: int = 42,
):
    """Export 120-row template (40 tweets, 40 NewsAPI titles, 40 GDELT titles, relevant rows only)."""
    df_all = pd.read_parquet(texts_all_path)
    rel_df = df_all[df_all["is_relevant"] == True].copy()

    # 40 tweets
    tw_pool = rel_df[rel_df["source"] == "twitter_kaggle"]
    tw_sample = tw_pool.sample(n=min(40, len(tw_pool)), random_state=random_state)
    tw_rows = pd.DataFrame({
        "text_id": tw_sample["text_id"],
        "source": tw_sample["source"],
        "text": tw_sample["text"],
        "my_label": "",
    })

    # 40 NewsAPI titles
    news_pool = rel_df[rel_df["source"] == "newsapi"]
    news_sample = news_pool.sample(n=min(40, len(news_pool)), random_state=random_state)
    news_rows = pd.DataFrame({
        "text_id": news_sample["text_id"],
        "source": news_sample["source"],
        "text": news_sample["title"].fillna(news_sample["text"]),
        "my_label": "",
    })

    # 40 GDELT titles
    gdelt_pool = rel_df[rel_df["source"] == "gdelt"]
    gdelt_sample = gdelt_pool.sample(n=min(40, len(gdelt_pool)), random_state=random_state)
    gdelt_rows = pd.DataFrame({
        "text_id": gdelt_sample["text_id"],
        "source": gdelt_sample["source"],
        "text": gdelt_sample["title"].fillna(gdelt_sample["text"]),
        "my_label": "",
    })

    template_df = pd.concat([tw_rows, news_rows, gdelt_rows], ignore_index=True)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    template_df.to_csv(out_p, index=False, encoding="utf-8")
    logger.info(f"Exported {len(template_df)} rows to hand-label template at {out_p}")


def run_evaluation(
    texts_all_path: str = "data/processed/texts_all.parquet",
    docs_dir: str = "docs",
) -> Dict[str, Any]:
    """Run evaluation on Financial PhraseBank against baselines and output reports."""
    df_all = pd.read_parquet(texts_all_path)
    fpb_df = df_all[df_all["source"] == "financial_phrasebank"].copy()
    logger.info(f"Loaded {len(fpb_df):,} Financial PhraseBank rows from {texts_all_path}")

    # Ground truth
    y_true = fpb_df["raw_label"].str.lower().tolist()
    texts = fpb_df["text"].tolist()

    # 1. FinBERT evaluation
    scorer = FinBertScorer()
    finbert_results = scorer.score_texts(texts, sources=["financial_phrasebank"] * len(texts))
    y_pred_finbert = [r["sentiment_label"] for r in finbert_results]
    y_scores_finbert = [r["sentiment_score"] for r in finbert_results]

    metrics_finbert = compute_metrics(y_true, y_pred_finbert, y_scores_finbert)

    # 2. Majority Class baseline (neutral)
    y_pred_maj = ["neutral"] * len(y_true)
    y_scores_maj = [0.0] * len(y_true)
    metrics_maj = compute_metrics(y_true, y_pred_maj, y_scores_maj)

    # 3. VADER baseline
    vader = SentimentIntensityAnalyzer()
    y_pred_vader = []
    y_scores_vader = []
    for t in texts:
        score = vader.polarity_scores(t)["compound"]
        y_scores_vader.append(score)
        if score >= 0.05:
            y_pred_vader.append("positive")
        elif score <= -0.05:
            y_pred_vader.append("negative")
        else:
            y_pred_vader.append("neutral")

    metrics_vader = compute_metrics(y_true, y_pred_vader, y_scores_vader)

    # Output docs
    docs_p = Path(docs_dir)
    docs_p.mkdir(parents=True, exist_ok=True)

    # Plot confusion matrix
    cm_plot_path = docs_p / "sentiment_confusion_matrix.png"
    plot_confusion_matrix(metrics_finbert["confusion_matrix"], LABELS, cm_plot_path)

    eval_summary = {
        "dataset": "financial_phrasebank",
        "n_samples": len(fpb_df),
        "finbert": metrics_finbert,
        "majority_baseline": metrics_maj,
        "vader_baseline": metrics_vader,
    }

    # Save JSON
    json_path = docs_p / "sentiment_eval.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)
    logger.info(f"Saved evaluation JSON to {json_path}")

    # Generate Markdown Report
    md_path = docs_p / "sentiment_eval.md"
    md_content = f"""# FinBERT Sentiment Model Evaluation Report

## Executive Summary & Evaluation Honesty Notice
> [!IMPORTANT]
> **Dataset Origin & Fine-Tuning Overlap:**
> The `ProsusAI/finbert` model was directly fine-tuned on the **Financial PhraseBank** benchmark dataset (Malo et al., 2014). Consequently, the quantitative metrics shown below on Financial PhraseBank are **optimistic** and represent in-domain / training-domain performance. They do NOT reflect how FinBERT performs out-of-the-box on noisy, uncurated social media (tweets) or 2026 real-time breaking financial news feeds.
> An independent 120-row hand-label template (`data/sample/sentiment_hand_label_template.csv`) spanning 40 tweets, 40 NewsAPI headlines, and 40 GDELT headlines has been exported to benchmark true out-of-distribution performance.

---

## Dataset Breakdown: Financial PhraseBank
- **Total Evaluated Rows:** {len(fpb_df):,}
- **Class Distribution:**
  - Neutral: {sum(1 for y in y_true if y == 'neutral'):,} ({sum(1 for y in y_true if y == 'neutral') / len(y_true) * 100:.1f}%)
  - Positive: {sum(1 for y in y_true if y == 'positive'):,} ({sum(1 for y in y_true if y == 'positive') / len(y_true) * 100:.1f}%)
  - Negative: {sum(1 for y in y_true if y == 'negative'):,} ({sum(1 for y in y_true if y == 'negative') / len(y_true) * 100:.1f}%)

---

## Benchmark Comparison: FinBERT vs. Baselines

| Metric | Majority Baseline (Neutral) | VADER Baseline | FinBERT (`ProsusAI/finbert`) |
| :--- | :--- | :--- | :--- |
| **Accuracy** | {metrics_maj['accuracy'] * 100:.2f}% | {metrics_vader['accuracy'] * 100:.2f}% | **{metrics_finbert['accuracy'] * 100:.2f}%** |
| **Macro-F1** | {metrics_maj['macro_f1']:.4f} | {metrics_vader['macro_f1']:.4f} | **{metrics_finbert['macro_f1']:.4f}** |
| **Weighted-F1** | {metrics_maj['weighted_f1']:.4f} | {metrics_vader['weighted_f1']:.4f} | **{metrics_finbert['weighted_f1']:.4f}** |
| **Pearson Correlation** | {metrics_maj['pearson_corr']:.4f} | {metrics_vader['pearson_corr']:.4f} | **{metrics_finbert['pearson_corr']:.4f}** |
| **Spearman Correlation** | {metrics_maj['spearman_corr']:.4f} | {metrics_vader['spearman_corr']:.4f} | **{metrics_finbert['spearman_corr']:.4f}** |

---

## Per-Class Breakdown (FinBERT)

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Negative** | {metrics_finbert['per_class']['negative']['precision']:.4f} | {metrics_finbert['per_class']['negative']['recall']:.4f} | {metrics_finbert['per_class']['negative']['f1']:.4f} | {metrics_finbert['per_class']['negative']['support']:,} |
| **Neutral** | {metrics_finbert['per_class']['neutral']['precision']:.4f} | {metrics_finbert['per_class']['neutral']['recall']:.4f} | {metrics_finbert['per_class']['neutral']['f1']:.4f} | {metrics_finbert['per_class']['neutral']['support']:,} |
| **Positive** | {metrics_finbert['per_class']['positive']['precision']:.4f} | {metrics_finbert['per_class']['positive']['recall']:.4f} | {metrics_finbert['per_class']['positive']['f1']:.4f} | {metrics_finbert['per_class']['positive']['support']:,} |

---

## Confusion Matrix (FinBERT)

```
                     Predicted Negative   Predicted Neutral   Predicted Positive
True Negative:       {metrics_finbert['confusion_matrix'][0][0]:<20} {metrics_finbert['confusion_matrix'][0][1]:<19} {metrics_finbert['confusion_matrix'][0][2]:<19}
True Neutral:        {metrics_finbert['confusion_matrix'][1][0]:<20} {metrics_finbert['confusion_matrix'][1][1]:<19} {metrics_finbert['confusion_matrix'][1][2]:<19}
True Positive:       {metrics_finbert['confusion_matrix'][2][0]:<20} {metrics_finbert['confusion_matrix'][2][1]:<19} {metrics_finbert['confusion_matrix'][2][2]:<19}
```

Heatmap plot saved to: `docs/sentiment_confusion_matrix.png`
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"Saved evaluation Markdown report to {md_path}")

    # Export hand label template
    export_hand_label_template(texts_all_path=texts_all_path)

    return eval_summary


if __name__ == "__main__":
    run_evaluation()
