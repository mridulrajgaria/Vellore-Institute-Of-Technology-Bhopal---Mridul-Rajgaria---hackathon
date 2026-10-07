# FinBERT Human Hand-Label Evaluation Report

## Overview
- **Total Hand-Labeled Rows Evaluated:** 180
- **Overall Accuracy:** 61.11%
- **Overall Macro-F1:** 0.6036
- **Overall Weighted-F1:** 0.5983

## Performance by Text Source
- **gdelt:** N=50, Accuracy=74.0%, Macro-F1=0.6814
- **newsapi:** N=44, Accuracy=61.4%, Macro-F1=0.5925
- **twitter_kaggle:** N=86, Accuracy=53.5%, Macro-F1=0.5465

---

## Per-Class Breakdown

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Negative** | 0.8462 | 0.7097 | 0.7719 | 62.0 |
| **Neutral** | 0.4369 | 0.9184 | 0.5921 | 49.0 |
| **Positive** | 0.8400 | 0.3043 | 0.4468 | 69.0 |

---

## Confusion Matrix

```
                     Predicted Negative   Predicted Neutral   Predicted Positive
True Negative:       44                   16                  2                  
True Neutral:        2                    45                  2                  
True Positive:       6                    42                  21                 
```
