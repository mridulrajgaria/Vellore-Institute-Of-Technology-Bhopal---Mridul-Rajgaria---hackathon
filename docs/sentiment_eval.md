# FinBERT Sentiment Model Evaluation Report

## Executive Summary & Evaluation Honesty Notice
> [!IMPORTANT]
> **Dataset Origin & Fine-Tuning Overlap:**
> The `ProsusAI/finbert` model was directly fine-tuned on the **Financial PhraseBank** benchmark dataset (Malo et al., 2014). Consequently, the quantitative metrics shown below on Financial PhraseBank are **optimistic** and represent in-domain / training-domain performance. They do NOT reflect how FinBERT performs out-of-the-box on noisy, uncurated social media (tweets) or 2026 real-time breaking financial news feeds.
> An independent 120-row hand-label template (`data/sample/sentiment_hand_label_template.csv`) spanning 40 tweets, 40 NewsAPI headlines, and 40 GDELT headlines has been exported to benchmark true out-of-distribution performance.

---

## Dataset Breakdown: Financial PhraseBank
- **Total Evaluated Rows:** 4,838
- **Class Distribution:**
  - Neutral: 2,872 (59.4%)
  - Positive: 1,362 (28.2%)
  - Negative: 604 (12.5%)

---

## Benchmark Comparison: FinBERT vs. Baselines

| Metric | Majority Baseline (Neutral) | VADER Baseline | FinBERT (`ProsusAI/finbert`) |
| :--- | :--- | :--- | :--- |
| **Accuracy** | 59.36% | 54.34% | **88.92%** |
| **Macro-F1** | 0.2483 | 0.4889 | **0.8821** |
| **Weighted-F1** | 0.4423 | 0.5493 | **0.8904** |
| **Pearson Correlation** | 0.0000 | 0.3161 | **0.8716** |
| **Spearman Correlation** | 0.0000 | 0.3085 | **0.8202** |

---

## Per-Class Breakdown (FinBERT)

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Negative** | 0.8016 | 0.9702 | 0.8779 | 604 |
| **Neutral** | 0.9621 | 0.8572 | 0.9066 | 2,872 |
| **Positive** | 0.8101 | 0.9207 | 0.8619 | 1,362 |

---

## Confusion Matrix (FinBERT)

```
                     Predicted Negative   Predicted Neutral   Predicted Positive
True Negative:       586                  11                  7                  
True Neutral:        123                  2462                287                
True Positive:       22                   86                  1254               
```

Heatmap plot saved to: `docs/sentiment_confusion_matrix.png`
