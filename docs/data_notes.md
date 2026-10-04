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


## Final Index Universe (14 Tickers)

The tactical index universe for Module A is restricted to 14 liquid S&P 100 constituent tickers with robust social media and news coverage:
- **Tickers:** `TSLA`, `AAPL`, `MSFT`, `AMZN`, `META`, `GOOGL`, `NFLX`, `AMD`, `PG`, `KO`, `DIS`, `BA`, `COST`, `PYPL`.
- *Note:* Historical tweets labeled `GOOG` are canonicalized to `GOOGL`. Non-universe tickers from the raw tweet corpus are excluded from the index universe.

## Committed Sample Datasets (`data/sample/`, <5 MB each)

To allow the entire repository and test suite to run offline without external downloads:
1. `data/sample/prices.parquet` (1.21 MB): Daily OHLCV price histories from 2021-01-01 to present for all 21 watchlist equities and benchmark SPY.
2. `data/sample/tweets_sample.parquet` (3.50 MB): 25,454 cleaned tweets covering the 14 universe tickers (up to 3,000 tweets per ticker, distributed evenly across calendar months).
3. `data/sample/newsapi_sample.parquet` (0.32 MB): 994 deduplicated news articles across the 21 watchlist companies and SPY.
4. `data/sample/news_labeled_eval_sample.parquet` (0.06 MB): 500 ground-truth labeled financial headlines stratified across sentiment classes (`positive`, `negative`, `neutral`) for offline FinBERT evaluation.
