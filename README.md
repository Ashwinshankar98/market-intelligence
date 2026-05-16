# Market Intelligence

An AI-powered event-driven market intelligence system that scans global news, SEC filings, Reddit sentiment, and insider activity to generate actionable options trading signals.

## What it does

- Scans 1,000+ news sources every hour for market-moving events
- Monitors SEC EDGAR for insider buys and material 8-K filings
- Tracks Reddit sentiment spikes across WSB, r/stocks, r/investing
- Uses Claude AI to reason through event chains and generate specific options recommendations
- Sends Telegram alerts with strike prices, expiry dates, and full reasoning
- Dashboard showing all signals, scores, and options plays in real time

## Signal types

- Corporate restructuring (layoffs → EPS beat thesis)
- M&A and acquisitions
- Strategic partnerships and investments
- Earnings beats and misses
- Insider buying activity
- Regulatory actions and antitrust
- Macro policy changes (tariffs, subsidies, sanctions)
- Quantum and AI tech deals

## Stack

- **Backend**: FastAPI (Python) — hosted on Railway
- **Database**: SQLite
- **Dashboard**: React — hosted on Vercel
- **LLM**: Claude Sonnet 4.6 (3-tier analysis pipeline)
- **Alerts**: Telegram
- **Data**: Reuters RSS, Google News RSS, SEC EDGAR, NewsAPI, Reddit

## Project Structure

```
market-intelligence/
├── backend/
│   ├── main.py              # FastAPI app + scheduler
│   ├── database.py          # DB setup with dedup tables
│   ├── requirements.txt
│   ├── core/
│   │   ├── analyser.py      # Claude Tier 1/2/3 analysis
│   │   ├── orchestrator.py  # Full scan pipeline with dedup
│   │   ├── tripwire.py      # Zero-cost keyword filter
│   │   └── notifier.py      # Telegram alerts
│   ├── scanners/
│   │   ├── news_scanner.py  # RSS + NewsAPI
│   │   ├── sec_scanner.py   # EDGAR insider + 8-K
│   │   └── reddit_scanner.py
│   └── routers/
│       └── api.py           # Dashboard API endpoints
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx          # Full dashboard
        └── main.jsx
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Ashwinshankar98/market-intelligence.git
cd market-intelligence/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp ../.env.example .env
# Fill in your API keys in .env
```

Required keys:
- `ANTHROPIC_API_KEY` — from platform.anthropic.com
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — your intelligence group chat ID (negative number)
- `NEWS_API_KEY` — from newsapi.org (free tier)

### 3. Run locally

```bash
uvicorn main:app --port 8001
```

### 4. Trigger a manual scan

```
http://localhost:8001/api/scan/trigger
```

### 5. View signals

```
http://localhost:8001/api/signals
http://localhost:8001/docs
```

## How the 3-tier pipeline works

| Tier | Frequency | Cost | What it does |
|------|-----------|------|--------------|
| Tier 1 — Tripwire | Every 15 min | $0 | Keyword regex filter, no Claude |
| Tier 2 — Quick score | Hourly on hits | ~$0.001/event | Fast Claude score 0-100 |
| Tier 3 — Deep analysis | On score ≥ 65 | ~$0.02/signal | Full options recommendation |
| Tier 4 — Weekly synthesis | Every Sunday | ~$0.10/week | Strategy review and adjustment |

## Estimated cost

~$3-5/month total in Claude API calls at normal news volume.

## Deployment

- Backend → Railway (add as second service to existing project)
- Frontend → Vercel (set `VITE_API_URL` to your Railway URL)
