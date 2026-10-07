# Event Classification Evaluation Report

- **Total Annotated Rows:** 180
- **Macro-F1:** 0.6884
- **Weighted-F1:** 0.6389

## Share of Rows Classified as 'Other' per Source
- **gdelt:** 23/50 (46.0% Other)
- **newsapi:** 39/44 (88.6% Other)
- **twitter_kaggle:** 47/86 (54.7% Other)

## Per-Class Performance

| Event Type | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| Geopolitical | 0.6364 | 0.6364 | 0.6364 | 11.0 |
| Macroeconomic | 0.7857 | 0.5000 | 0.6111 | 22.0 |
| Credit Event | 1.0000 | 1.0000 | 1.0000 | 2.0 |
| Merger/Acquisition | 0.8462 | 0.8462 | 0.8462 | 13.0 |
| Product Launch | 0.7778 | 0.4118 | 0.5385 | 17.0 |
| Regulatory | 1.0000 | 0.6818 | 0.8108 | 22.0 |
| Earnings | 1.0000 | 0.2333 | 0.3784 | 30.0 |
| Other | 0.5413 | 0.9365 | 0.6860 | 63.0 |

## Confusion Matrix
```
Classes: ['Geopolitical', 'Macroeconomic', 'Credit Event', 'Merger/Acquisition', 'Product Launch', 'Regulatory', 'Earnings', 'Other']
[[ 7  1  0  0  0  0  0  3]
 [ 0 11  0  0  0  0  0 11]
 [ 0  0  2  0  0  0  0  0]
 [ 0  0  0 11  0  0  0  2]
 [ 2  0  0  0  7  0  0  8]
 [ 2  0  0  0  0 15  0  5]
 [ 0  1  0  1  0  0  7 21]
 [ 0  1  0  1  2  0  0 59]]
```