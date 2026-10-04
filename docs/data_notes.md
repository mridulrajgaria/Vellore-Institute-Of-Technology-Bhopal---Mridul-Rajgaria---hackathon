# Manual Dataset Acquisition Notes

This document describes the offline datasets required for the AI/NLP Risk Engine project. Place all downloaded raw datasets in their respective subdirectories within `data/raw/` (which is gitignored). Small benchmark slices (<5 MB) will subsequently be extracted into `data/sample/`.

---

## 1. Sentiment Analysis for Financial News (FinancialPhraseBank)
- **Dataset Title:** *Sentiment Analysis for Financial News* (Malo et al. / FinancialPhraseBank)
- **Kaggle Search:** Search Kaggle for `"Sentiment Analysis for Financial News"` or `"FinancialPhraseBank"`.
- **Expected Files:** `all-data.csv` or `Sentences_50Agree.txt`
- **Target Location:** `data/raw/sentiment_news/all-data.csv`
- **Schema & Content:** Contains ~4,845 financial headlines/sentences annotated with consensus sentiment labels (`positive`, `negative`, `neutral`).
- **Usage:** Benchmark evaluation and zero-shot/FinBERT alignment for sentiment scoring.

---

## 2. Historical Stock Tweets Dataset
- **Dataset Title:** *Stock Market Tweets* / *Stock Tweets for Sentiment Analysis*
- **Kaggle Search:** Search Kaggle for `"Stock Market Tweets Data"` or `"Stock Tweets Sentiment"`.
- **Expected Files:** CSV or JSON files containing columns such as `Date`, `Tweet`, `Stock Name` / `Ticker`, `Company Name`.
- **Target Location:** `data/raw/tweets/` (e.g. `stock_tweets.csv`)
- **Usage:** Secondary unstructured text source to validate social sentiment and retail volume momentum for candidate tickers.

---

## 3. Salad Money Open Banking Dataset
- **Dataset Context:** Anonymized open banking transaction records used for credit scoring and income/expense volatility modeling.
- **Search Recommendation:** Search Kaggle or public repository portals for `"Salad Money Open Banking dataset"`.
- **Target Location:** `data/raw/salad_money/`
- **Usage:** Used strictly as a statistical seed (cash flow volatility, transaction distributions) to generate synthetic wholesale portfolio loan obligations for Module B (Stress Testing). No real client data is utilized.

---

## 4. Financial Transactions Dataset
- **Dataset Context:** Statistical transaction dataset (e.g. Kaggle Financial Transactions / Synthetic Financial Datasets).
- **Search Recommendation:** Search Kaggle for `"Financial Transactions Dataset"` or `"Synthetic Financial Datasets for Banking"`.
- **Target Location:** `data/raw/financial_transactions/`
- **Usage:** Supplementary statistical seed for counterparty exposures, credit lines, and payment frequency modeling in Module B.

---

## Verification Checklist
Once downloaded, confirm files are present in `data/raw/` before running subsequent sample preparation scripts:
- [ ] `data/raw/sentiment_news/`
- [ ] `data/raw/tweets/`
- [ ] `data/raw/salad_money/`
- [ ] `data/raw/financial_transactions/`
