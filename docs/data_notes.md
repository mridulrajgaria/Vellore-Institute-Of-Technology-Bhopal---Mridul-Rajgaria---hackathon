# Data Sources and Notes

This document lists every data source used by the AI/NLP Risk Engine, where it comes from, and where it lives locally. Large raw files stay in `data/raw/` (gitignored). Small samples (<5 MB) are committed to `data/sample/` so the project runs without any downloads.

## Fetched automatically (scripts in `src/ingestion/`)

| Source | Script | Output | Notes |
|---|---|---|---|
| Yahoo Finance via `yfinance` | `fetch_prices.py` | `data/sample/prices.parquet` | Daily OHLCV for the configured tickers plus SPY, from 2021-01-01. Alpha Vantage is a fallback and was not needed. |
| NewsAPI (newsapi.org) | `fetch_newsapi.py` | `data/raw/newsapi/*.json` | Needs `NEWSAPI_KEY` in `.env`. Free tier returns only recent articles, so it serves as the live-demo feed. |
| GDELT DOC 2.0 API | `fetch_gdelt.py` | `data/raw/gdelt/` | The fetcher and tests are included, but the API was unreachable from the author's network (connection reset), so no GDELT data is used. An optional reader for local GKG files exists. |

## Manual downloads (Kaggle, free account required)

### 1. Sentiment Analysis for Financial News
- Kaggle dataset by Ankur Sinha, derived from FinancialPhraseBank.
- Location: `data/raw/financial_news/all-data.csv`
- Content: 4,846 financial news headlines with a sentiment label (positive / negative / neutral), no dates or tickers. The file is not UTF-8 and must be read with `latin-1` encoding.
- Use: evaluating the sentiment model (FinBERT) against human labels.

### 2. Stock Tweets for Sentiment Analysis and Prediction
- Kaggle dataset by Hanna Yukhymenko (CC0: Public Domain): https://www.kaggle.com/datasets/equinxx/stock-tweets-for-sentiment-analysis-and-prediction
- Location: `data/raw/tweets/stock_tweets.csv` and `data/raw/tweets/stock_yfinance_data.csv`
- Content: 80,793 tweets for the top 25 most-watched Yahoo Finance tickers, 2021-09-30 to 2022-09-30. Columns: `Date`, `Tweet`, `Stock Name`, `Company Name`. The second file has matching price and volume data.
- Notes: tweets contain multi-line text, URLs, @mentions and HTML entities, so they are cleaned during normalization.
- Use: second text source for the engine and the historical replay for the Module A backtest.

### 3. Financial Transactions Dataset (planned, for Module B)
- Not yet downloaded. Search Kaggle for "Financial Transactions Dataset".
- Location: `data/raw/financial_transactions/`
- Use: statistical seed only (amount and category distributions) for a synthetic wholesale portfolio. No real client data.

### 4. Salad Money open banking data (optional, not acquired)
- A reliable public source has not been confirmed. This dataset is optional and will be skipped if unavailable.

## Local folder checklist
- [x] `data/raw/financial_news/`
- [x] `data/raw/tweets/`
- [x] `data/raw/newsapi/`
- [ ] `data/raw/financial_transactions/` (Module B)
- [ ] `data/raw/salad_money/` (optional)
