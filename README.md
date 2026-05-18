# Market Intelligence

An AI-powered event-driven market intelligence system that scans global news, SEC filings, Reddit sentiment, insider activity, and hedge fund moves to generate personalized, actionable options trading signals — tailored to your portfolio.

## Live URLs
- **Dashboard**: https://market-intelligence-gold-phi.vercel.app
- **API**: https://market-intelligence-production-a8db.up.railway.app

## What it does

- Scans 1,000+ news sources every hour for market-moving events
- Tracks 25+ famous investors and hedge funds (Ackman, Cathie Wood, Buffett, Druckenmiller, Burry, and more)
- Monitors SEC EDGAR for insider buys (Form 4) and material events (8-K)
- Tracks Reddit sentiment spikes across WSB, r/stocks, r/investing, r/semiconductors
- Reasons through full event chains (1st → 2nd → 3rd order effects)
- Generates specific options plays with exact strike prices, expiry dates, entry strategy, profit target, stop loss, and time stop
- Portfolio-aware — knows your holdings, flags correlation alerts, says ADD/HOLD/REDUCE on positions you own
- Sends Telegram alerts to a dedicated intelligence group
- Dashboard with 7D / 30D / ALL time filters, MY SECTORS view, and manual ticker lookup
- Self-improving — every Sunday Claude reviews the week and adjusts keyword weights intelligently

## Signal types

- Corporate restructuring (layoffs → EPS beat thesis)
- M&A, acquisitions, and strategic investments
- Hedge fund portfolio moves (13F filings, position changes)
- Famous investor buys/sells (Ackman exits Google → buy Microsoft logic)
- Earnings beats and misses (portfolio tickers only)
- Insider buying activity (CEO/CFO personal purchases)
- Regulatory actions and antitrust
- Macro policy changes (tariffs, CHIPS Act, export restrictions)
- AI and GPU infrastructure deals
- Quantum computing breakthroughs
- Space launch contracts
- Optoelectronics and photonics news
- Rare earth and critical minerals

## Stack

- **Backend**: FastAPI (Python) — hosted on Railway
- **Database**: SQLite with active_weights table for self-improvement
- **Dashboard**: React — hosted on Vercel
- **LLM**: Claude Sonnet 4.6 (4-tier analysis pipeline)
- **Alerts**: Telegram (dedicated intelligence group)
- **Data**: Reuters RSS, Google News RSS, SEC EDGAR, NewsAPI, Reddit, Yahoo Finance RSS

## Project Structure

```
market-intelligence/
├── backend/
│   ├── main.py                  # FastAPI app + APScheduler
│   ├── database.py              # DB schema with active_weights for self-improvement
│   ├── requirements.txt
│   ├── core/
│   │   ├── analyser.py          # All 4 Claude tiers + weight-aware scoring
│   │   ├── orchestrator.py      # Full pipeline with dedup and cost controls
│   │   ├── tripwire.py          # Zero-cost keyword filter (ticker-gated)
│   │   ├── notifier.py          # Telegram alerts with portfolio impact section
│   │   └── portfolio.py         # Your holdings, correlations, sector priorities
│   ├── scanners/
│   │   ├── news_scanner.py      # RSS + NewsAPI with hedge fund specific feeds
│   │   ├── sec_scanner.py       # EDGAR Form 4 insider + 8-K material events
│   │   └── reddit_scanner.py    # WSB + r/stocks + r/semiconductors
│   └── routers/
│       ├── api.py               # Signals, stats, weights endpoints
│       └── lookup.py            # Manual ticker lookup with exit strategy
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx              # Full responsive dashboard
        └── main.jsx
```

## How the 4-tier pipeline works

| Tier | Frequency | Claude cost | What it does |
|------|-----------|-------------|--------------|
| Tier 1 — Tripwire | Every 15 min | **$0** | Keyword regex. Generic events only pass if a watchlist ticker is mentioned. Famous investor and sector-wide events always pass. |
| Tier 2 — Quick score | Hourly on Tier 1 hits | ~$0.001/call | Fast Claude score 0–100. Applies active category weights so high-performing categories score higher. |
| Tier 3 — Deep analysis | On score ≥ 72 | ~$0.02/call | Full options recommendation with entry, profit target, stop loss, time stop, IV warning, portfolio impact, correlation alerts. |
| Tier 4 — Weekly synthesis | Every Sunday 8pm ET | ~$0.10 | Claude reviews the week, adjusts category weights up AND down intelligently with hard constraints. Triggers cleanup. |

## Breaking scan vs full scan

**Full scan** (every 60 min): Hits all sources → Tier 1 → Tier 2 → Tier 3.

**Breaking scan** (every 15 min): Hits RSS only → Tier 1 only → **zero Claude cost**. Only escalates directly to Tier 3 if score_boost ≥ 40 (e.g. Ackman + your ticker, bankruptcy of held stock). Everything else waits for the next full scan.

## Self-improvement system

Every Sunday at 8pm ET, Tier 4 runs:
1. Reviews all signals from the past 7 days
2. Calculates per-category stats (signal count, avg score, actionable options count)
3. Claude recommends weight adjustments UP and DOWN with reasoning
4. Weights applied with hard constraints:
   - Range: 0.5 (minimum) to 2.0 (maximum)
   - Max change per week: ±0.3
   - `hedge_fund`, `portfolio_move`: never below 1.0
   - Core sectors (semiconductor, quantum, space, etc.): never below 0.8
5. Weekly cleanup runs at 8:30pm ET

## Portfolio-aware alerts

Every signal includes:
- **Position action**: ADD / HOLD / REDUCE on stocks you own
- **Correlation alerts**: NVDA news → flags your AMD, SMCI, CRWV, IREN positions
- **Hedge suggestions**: Bearish signal on a heavy position → suggests hedge
- **Sector filtering**: Priority sectors alert at score ≥ 72. Everything else only alerts at score ≥ 90

## Hedge funds and investors tracked

Ackman (Pershing Square), Cathie Wood (ARK), Buffett (Berkshire), Druckenmiller, Soros, Michael Burry, Dalio (Bridgewater), Ken Griffin (Citadel), Steve Cohen (Point72), Chase Coleman (Tiger Global), Philippe Laffont (Coatue), Dan Sundheim (D1), David Einhorn (Greenlight), Dan Loeb (Third Point), Carl Icahn, Paul Singer (Elliott), Jim Simons (Renaissance), Masayoshi Son (SoftBank), KKR, Apollo, Blackstone, BlackRock, Vanguard, Fidelity, a16z, Sequoia.

## Manual ticker lookup

Type any ticker + optional context in the dashboard. Claude fetches recent news in parallel and returns a full analysis in 12–18 seconds including entry strategy, profit target, stop loss, time stop, and IV warning.

## Data TTL and cleanup

Every Sunday 8:30pm ET:
- Non-priority sector signals older than 7 days with score < 80 → deleted
- Any signal older than 30 days with score < 72 → deleted
- Manual lookups, high conviction signals (≥80), weekly synthesis → kept forever
- Old dedup cache entries (>30 days) → cleared

## Dashboard features

- **7D / 30D / ALL** time range toggle (top right)
- **MY SECTORS** filter — priority sectors + score ≥ 90 only
- **HIGH CONVICTION** filter — score ≥ 80 only
- **LOOKUPS** tab — all your manual analyses
- Full reasoning chain, options plays with entry/exit strategy in detail panel
- Mobile responsive — tap to expand, back button to return
- Auto-refreshes every 30 seconds

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
```

Required keys:
- `ANTHROPIC_API_KEY` — from platform.anthropic.com
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — intelligence group chat ID (negative number)
- `NEWS_API_KEY` — from newsapi.org (free tier)

Optional tuning:
- `QUICK_SCORE_THRESHOLD` — default 65
- `DEEP_SCORE_THRESHOLD` — default 72
- `BREAKING_CRITICAL_THRESHOLD` — default 40
- `SCAN_INTERVAL_MINUTES` — default 60
- `BREAKING_SCAN_MINUTES` — default 15

### 3. Run locally

```bash
uvicorn main:app --port 8001
```

### 4. Key endpoints

```
GET  /api/signals?days=7&limit=200   # Signals with time filter
GET  /api/stats                       # Today's summary
GET  /api/weights                     # Current category weights
POST /api/lookup                      # Manual ticker analysis
POST /api/scan/trigger                # Manually trigger a scan
GET  /health                          # Health + scheduled jobs
GET  /docs                            # Interactive API docs
```

## Deployment

- **Backend** → Railway (second service, covered by existing $5/mo plan)
- **Frontend** → Vercel (free tier, set `VITE_API_URL` to Railway URL)

## Estimated monthly cost

| Item | Cost |
|------|------|
| Railway (backend 24/7) | $0 (covered by existing plan) |
| Vercel (dashboard) | Free |
| Claude API (all tiers) | ~$3–5/month |
| NewsAPI | Free |
| SEC EDGAR + Reddit | Free |
| **Total** | **~$3–5/month** |

Cost controls built in: startup scan skipped on redeploy if last scan < 50 min ago · breaking scan never calls Claude unless score_boost ≥ 40 · Tier 2→3 threshold at 72 · generic events require watchlist ticker at Tier 1.