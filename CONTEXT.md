PROJECT
An AI/NLP Risk Engine that ingests real-time unstructured text from at least 2 different sources (news + tweets) and, for a given company or event, outputs structured signals:
- sentiment_score: -1.0 to 1.0
- event_type: Geopolitical, Macroeconomic, Credit Event, Merger/Acquisition, Product Launch, Regulatory, Earnings, Other
- impact_score: 1 to 10 (predicted market-impact severity)
Signals must be available to downstream apps via a simple API and by writing to a file.

DOWNSTREAM MODULES (engine + at least ONE required; plan: Module A first, Module B as stretch)
- Module A: Tactical index rebalancer. Mock index of 10-20 S&P 100 stocks. Subscribes to sentiment score: positive raises a stock's weight, negative lowers it. Dashboard showing weights over time.
- Module B: Strategic stress testing. Synthetic wholesale-banking portfolio (loans, bonds, derivatives). Subscribes to event type + impact score. High-impact events (e.g. Geopolitical with impact > 7) trigger a simplified stress test (e.g. -10% equities, +2% rates). Dashboard showing portfolio value before vs after.

DATA SOURCES (all free/public; no proprietary or real S&P/Crisil client data)
- GDELT (news events/themes, DOC 2.0 API, no key)
- Kaggle "Sentiment Analysis for Financial News" (labeled; for evaluating sentiment)
- NewsAPI (live news; key in .env; free tier is limited, so cache results)
- Kaggle historical stock tweets (second text source)
- yfinance for prices, Alpha Vantage as fallback
- Salad Money open banking transactions and Kaggle Financial Transactions dataset: used only as statistical seeds for a SYNTHETIC wholesale portfolio
Manual downloads go into data/raw/ (gitignored). Small samples (<5 MB each) go into data/sample/ and are committed.

TICKERS (candidate list; confirm after checking tweet coverage): AAPL, MSFT, AMZN, GOOGL, META, NVDA, TSLA, JPM, BAC, GS, XOM, JNJ, PG, WMT, KO, benchmark SPY.

DELIVERABLES / REPO RULES
- Public GitHub repo named <college>-<candidate-name>-hackathon containing: README.md, requirements.txt, LICENSE (MIT), .env.example, src/, data/, docs/presentation.pdf (5-7 slides), docs/architecture.png.
- README must follow this template: header fields (Candidate Name, College Email ID, College/Campus, Demo Video Link, Slide Deck Link), then 1 Project Overview / Problem Statement & Approach, 2 Architecture & Tech Stack, 3 Dataset Used, 4 Quickstart & Installation (runtime, OS tested, exact commands), 5 Key Results & Domain Impact.
- All data used (including synthetic) must be in /data. Keep the repo free of large binary or data dumps.
- Demo video: short end-to-end walkthrough, YouTube unlisted. Reviewers must be able to run the project from the README commands.
- Evaluation: working prototype, architecture, code quality, innovation/efficiency, presentation, domain understanding, documentation clarity. Incremental commits are expected, because one giant commit is penalized.

ENGINEERING RULES
- Python 3.11, minimal pinned dependencies, runnable in Docker (python:3.11-slim) and on Windows.
- Structure: src/{ingestion,nlp,engine,modules,dashboard,common}, tests/, config/ (YAML for parameters), data/{sample,raw}, docs/.
- Never hardcode API keys; use .env plus .env.example. Missing keys must be handled gracefully. The whole app must run OFFLINE from cached data in data/sample/.
- Small, readable modules with docstrings, type hints, and pytest tests for core logic. Use logging, not print.
- Dashboards in Streamlit with Plotly.
- Sentiment: FinBERT (ProsusAI/finbert) on CPU. Event classification: hybrid of keyword rules, GDELT weak labels and zero-shot. The impact score must be explainable, with a component breakdown and all constants in config.
- Honesty: never claim results the code doesn't produce, and document limitations.

HOW YOU MUST WORK
- Begin every task with a short plan and wait for my OK. Work in small steps, one task at a time.
- NEVER run git commit or git push. I commit myself after reviewing diffs.
- Do not guess file formats or column names: inspect real files in data/raw/ first.
- Don't add extra files, services or heavy dependencies without asking.
- After each task, tell me how to verify it and give a suggested commit message.
