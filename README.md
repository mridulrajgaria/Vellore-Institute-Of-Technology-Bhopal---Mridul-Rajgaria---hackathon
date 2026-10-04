# AI/NLP Risk Engine

**Candidate Name:** [Your Full Name]  
**College Email ID:** [your_id@college.ac.in]  
**College/Campus:** [Your College Name]  
**Demo Video Link:** [Unlisted YouTube Video Link]  
**Slide Deck Link:** [Link to Slide Deck]  

---

## 1. Project Overview / Problem Statement & Approach

### Problem Statement
Financial institutions and portfolio managers face an overwhelming volume of unstructured real-time data from financial news feeds and social media. Rapidly detecting high-impact market events and quantifying market sentiment into structured, actionable risk signals is essential for tactical rebalancing and strategic portfolio stress testing.

### Approach
This project implements an end-to-end AI/NLP Risk Engine that:
- Ingests unstructured financial news and tweets across multiple public sources (GDELT, NewsAPI, and financial tweet datasets).
- Classifies financial event categories (Geopolitical, Macroeconomic, Earnings, Regulatory, etc.) and predicts sentiment using domain-specific NLP models.
- Generates an explainable impact score (1 to 10) assessing predicted market severity.
- Dispatches structured signals to downstream financial modules:
  - **Module A (Tactical Index Rebalancer):** Dynamically adjusts constituent weights in an S&P stock universe based on inbound sentiment.
  - **Module B (Strategic Stress Testing):** Assesses portfolio vulnerability across wholesale banking assets during severe risk events.

---

## 2. Architecture & Tech Stack

### High-Level Architecture
```
[Unstructured Data Sources]
   ├── GDELT Project (DOC 2.0 API)
   ├── NewsAPI / Live Feeds
   └── Historical Financial Tweets
           │
           ▼
[Data Ingestion & Caching Layer] (Offline-capable)
           │
           ▼
[NLP & Risk Engine Core]
   ├── Sentiment Analysis (FinBERT / NLP Pipeline)
   ├── Event Classifier (Hybrid Rules & Weak Supervision)
   └── Impact Scoring Engine (Component breakdown & explainability)
           │
           ▼
[Structured Signals API & Persistence] (RiskSignal Schema)
           │
           ├──────────────────────────────┐
           ▼                              ▼
[Module A: Index Rebalancer]   [Module B: Stress Testing]
           │                              │
           └──────────────┬───────────────┘
                          ▼
            [Interactive Streamlit Dashboard]
```

### Tech Stack
- **Language & Runtime:** Python 3.11
- **NLP & Modeling:** Hugging Face Transformers, FinBERT, Pydantic
- **Data & Computation:** Pandas, NumPy, PyArrow
- **Market Data:** yfinance
- **Visualization & UI:** Streamlit, Plotly
- **Testing & Quality:** pytest

---

## 3. Dataset Used
All datasets used are public, free, and contain no proprietary or real client information:
- **GDELT DOC 2.0 API:** Global news event themes and sentiment signals.
- **Kaggle Financial News Sentiment Dataset:** Benchmarking and evaluating financial sentiment scores.
- **NewsAPI:** Real-time financial headlines (cached for offline evaluation).
- **Historical Stock Tweets Dataset:** Secondary unstructured text source.
- **Market Price Data (yfinance):** Historical price and volume data for benchmark (SPY) and candidate equities.
- **Statistical Banking Data:** Open banking transaction seeds for synthetic wholesale portfolio generation.

*Note: Raw downloads are stored locally in `data/raw/` (gitignored), while curated test samples (<5 MB) reside in `data/sample/` for offline execution.*

---

## 4. Quickstart & Installation

### Environment Requirements
- **Tested OS:** Windows 10/11, Linux (Ubuntu 22.04)
- **Runtime:** Python 3.11

### Setup Steps
```bash
# 1. Clone repository
git clone <repo-url>
cd <repo-folder>

# 2. Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment keys
cp .env.example .env
# Edit .env with your optional API keys

# 5. Run automated tests
pytest tests/
```

---

## 5. Key Results & Domain Impact
- **Signal Precision & Explainability:** Generates transparent risk signals with bounded sentiment scores and explainable impact scoring breakdowns.
- **Dynamic Portfolio Resilience:** Module A demonstrates risk-adjusted alpha generation and lower drawdowns by rebalancing ahead of headline shocks.
- **Stress Testing Preparedness:** Module B provides institutional risk managers with rapid scenario analytics when extreme geopolitical or credit events are detected.
