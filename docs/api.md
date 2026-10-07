# AI/NLP Risk Engine API & File Export Documentation

The Risk Engine serves structured RiskSignals to downstream consumers (such as Module A: Tactical Rebalancer and Module B: Strategic Stress Testing) via a high-performance REST API, a real-time Server-Sent Events (SSE) streaming replay service, and a file export utility.

---

## 1. Quickstart: Starting the API Server

Start the API service locally using the standard runner:

```bash
# Start API on http://127.0.0.1:8000
python -m src.engine.serve

# Optional flags:
python -m src.engine.serve --host 127.0.0.1 --port 8000 --reload
```

The service runs fully offline. By default, it loads from `data/processed/signals.parquet` if present, otherwise falling back automatically to the committed sample `data/sample/signals_sample.parquet`.

Interactive OpenAPI / Swagger documentation is available in your browser at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 2. REST API Endpoints

### A. Service Index & Navigation (`GET /`)
Returns a service overview with direct links to Swagger docs, health, signals, tickers, and stats.

**Curl Example:**
```bash
curl -s http://127.0.0.1:8000/
```

**Response Example (`200 OK`):**
```json
{
  "service": "AI/NLP Risk Engine API",
  "version": "1.0.0",
  "docs": "/docs",
  "redoc": "/redoc",
  "endpoints": {
    "health": "/health",
    "signals": "/signals",
    "latest_signals": "/signals/latest?n=10",
    "tickers": "/tickers",
    "stats": "/stats",
    "replay_stream": "/replay/stream?speed=20"
  }
}
```

---

### B. Health & System Status (`GET /health`)
Returns service status, signal count, the active data source file, and temporal coverage.

**Curl Example:**
```bash
curl -s http://127.0.0.1:8000/health
```

**Response Example (`200 OK`):**
```json
{
  "status": "ok",
  "signals_count": 13893,
  "data_source": "data/processed/signals.parquet",
  "date_range": {
    "min": "2021-09-30T01:16:13+00:00",
    "max": "2026-10-03T19:47:08+00:00"
  }
}
```

---

### B. Query Signals (`GET /signals`)
Query signals with rich filtering and pagination.

**Query Parameters:**
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ticker` | `string` | `null` | Filter by ticker symbol (e.g. `TSLA`, `AAPL`, `MARKET`) |
| `since` | `string` | `null` | Start timestamp in ISO-8601 format (inclusive) |
| `until` | `string` | `null` | End timestamp in ISO-8601 format (inclusive) |
| `min_impact` | `float` | `null` | Minimum impact score threshold (1.0 to 10.0) |
| `max_impact` | `float` | `null` | Maximum impact score threshold (1.0 to 10.0) |
| `event_type` | `string` | `null` | Filter by event type (`Earnings`, `Credit Event`, etc.) |
| `source` | `string` | `null` | Filter by source (`twitter_kaggle`, `newsapi`, `gdelt`) |
| `limit` | `integer`| `100` | Number of items to return (1 to 1000) |
| `offset` | `integer`| `0` | Offset for pagination |

**Curl Example:**
```bash
curl -s "http://127.0.0.1:8000/signals?ticker=TSLA&min_impact=5.0&limit=2"
```

**Response Example (`200 OK`):**
```json
[
  {
    "ts": "2021-10-04T12:00:23+00:00",
    "ticker": "TSLA",
    "source": "twitter_kaggle",
    "text_id": "450fa2e897914040",
    "headline": "Tesla $TSLA is on fire. Breaks past key resistance as deliveries hit new record.",
    "sentiment_score": 0.4521,
    "event_type": "Other",
    "impact_score": 5.2104,
    "confidence": 0.825,
    "event_confidence": 0.3,
    "secondary_event": null,
    "attribution_weight": 1.0,
    "matched_triggers": [],
    "impact_components": {
      "severity_contrib": 0.0675,
      "sentiment_contrib": 0.1356,
      "source_contrib": 0.06,
      "volume_contrib": 0.05,
      "raw_severity": 0.15,
      "raw_sentiment_abs": 0.4521,
      "raw_source_weight": 0.4,
      "raw_volume_signal": 0.5
    },
    "is_broadcast": false,
    "is_analyst_action": false
  }
]
```

---

### C. Latest Signals (`GET /signals/latest`)
Quickly retrieve the $N$ most recent signals sorted in descending timestamp order.

**Curl Example:**
```bash
curl -s "http://127.0.0.1:8000/signals/latest?n=5"
```

---

### D. Single Signal Lookup (`GET /signals/{text_id}`)
Retrieve a specific signal by its unique identifier.

**Curl Example:**
```bash
curl -s http://127.0.0.1:8000/signals/450fa2e897914040
```

Returns `404 Not Found` if the signal does not exist:
```json
{
  "detail": "Signal with text_id 'unknown_id' not found."
}
```

---

### E. Ticker Universe & Watchlist (`GET /tickers`)
Lists all tracked symbols, their signal counts, index universe membership, and news-only watchlist flags.

**Curl Example:**
```bash
curl -s http://127.0.0.1:8000/tickers
```

**Response Example (`200 OK`):**
```json
[
  {
    "ticker": "AAPL",
    "count": 1892,
    "is_index_universe": true,
    "is_news_only_watchlist": false
  },
  {
    "ticker": "NVDA",
    "count": 41,
    "is_index_universe": false,
    "is_news_only_watchlist": true
  }
]
```

---

### F. Aggregated Engine Statistics (`GET /stats`)
Provides data distribution summaries across event categories, sources, and impact score histograms.

**Curl Example:**
```bash
curl -s http://127.0.0.1:8000/stats
```

**Response Example (`200 OK`):**
```json
{
  "total_signals": 13893,
  "date_range": {
    "min": "2021-09-30T01:16:13+00:00",
    "max": "2026-10-03T19:47:08+00:00"
  },
  "by_event_type": {
    "Other": 13444,
    "Macroeconomic": 156,
    "Regulatory": 118,
    "Earnings": 94,
    "Product Launch": 41,
    "Merger/Acquisition": 29,
    "Credit Event": 11
  },
  "by_source": {
    "twitter_kaggle": 12910,
    "gdelt": 543,
    "newsapi": 440
  },
  "impact_histogram": {
    "1-2": 32,
    "2-3": 4421,
    "3-4": 5832,
    "4-5": 2187,
    "5-6": 1056,
    "6-7": 284,
    "7-8": 68,
    "8-9": 15,
    "9-10": 0,
    "10+": 0
  }
}
```

---

## 3. Real-Time Server-Sent Events (SSE) Replay Stream

For live interactive dashboards (Streamlit, React, Vue), the API provides a deterministic Server-Sent Events stream that yields signals in chronological order.

**Endpoint:** `GET /replay/stream`

**Query Parameters:**
- `speed` (float, default `20.0`): Replay rate in signals per second (0.1 to 200.0).
- `start` (string, optional): Start timestamp in ISO format to resume from.
- `ticker` (string, optional): Restrict the replay to a single ticker symbol.

**Curl Example:**
```bash
curl -N "http://127.0.0.1:8000/replay/stream?speed=5&ticker=TSLA"
```

**SSE Stream Output:**
```text
data: {"ts": "2021-09-30T03:14:53+00:00", "ticker": "TSLA", "impact_score": 2.6827, ...}

data: {"ts": "2021-09-30T08:25:10+00:00", "ticker": "TSLA", "impact_score": 3.1084, ...}
```

The generator stops cleanly if the client disconnects or aborts the HTTP connection.

---

## 4. File Export CLI

In addition to the REST API, signals can be exported directly to local files in `jsonl`, `csv`, or `parquet` format.

**Command Syntax:**
```bash
python -m src.engine.export --format <jsonl|csv|parquet> --out <filepath> [options]
```

**Options:**
- `--format`: File format (`jsonl`, `csv`, or `parquet`, default: `jsonl`).
- `--out`: Destination file path.
- `--ticker`: Optional ticker filter (e.g. `TSLA`).
- `--since` / `--until`: Optional timestamp bounds.
- `--min-impact` / `--max-impact`: Optional impact score bounds.
- `--event-type`: Filter by event category.
- `--source`: Filter by data source.
- `--limit`: Maximum number of records to export.
- `--sample`: Force loading strictly from `data/sample/signals_sample.parquet`.

**CLI Usage Examples:**
```bash
# 1. Export TSLA signals to JSONL
python -m src.engine.export --format jsonl --out data/exports/tsla_signals.jsonl --ticker TSLA

# 2. Export high-impact signals (impact >= 5.0) to CSV
python -m src.engine.export --format csv --out data/exports/high_impact.csv --min-impact 5.0

# 3. Export all signals to Parquet
python -m src.engine.export --format parquet --out data/exports/signals_backup.parquet
```
