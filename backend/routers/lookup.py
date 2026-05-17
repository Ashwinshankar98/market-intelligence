import os, json, re
import httpx
import feedparser
from fastapi import APIRouter
from core.analyser import _clean_json
import anthropic

router = APIRouter(prefix="/api", tags=["lookup"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

async def fetch_recent_news(ticker: str, company: str) -> list:
    """Fetch recent news for a specific ticker/company from multiple sources."""
    articles = []

    # Google News RSS
    queries = [
        f"{company} stock",
        f"{ticker} earnings layoffs acquisition",
        f"{company} latest news",
    ]
    for q in queries[:2]:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                articles.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "source":  "google_news",
                    "date":    entry.get("published", ""),
                })
        except Exception:
            pass

    # NewsAPI
    if NEWS_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8) as client_http:
                resp = await client_http.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": f"{ticker} OR {company}",
                        "apiKey": NEWS_API_KEY,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 8,
                    }
                )
                data = resp.json()
                for a in data.get("articles", []):
                    articles.append({
                        "title":   a.get("title", ""),
                        "summary": (a.get("description") or "")[:300],
                        "source":  "newsapi",
                        "date":    a.get("publishedAt", ""),
                    })
        except Exception:
            pass

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen and a["title"]:
            seen.add(a["title"])
            unique.append(a)

    return unique[:12]


@router.post("/lookup")
async def lookup_ticker(body: dict):
    """
    Manual ticker lookup — fetch recent news and get full Claude analysis
    including entry AND exit strategy.
    """
    ticker  = body.get("ticker", "").upper().strip()
    company = body.get("company", ticker)
    context = body.get("context", "")  # optional extra context from user

    if not ticker:
        return {"error": "ticker is required"}

    # Fetch recent news
    articles = await fetch_recent_news(ticker, company)

    if not articles:
        news_text = "No recent news found. Analyse based on general knowledge."
    else:
        news_text = "\n".join([
            f"- [{a['date'][:10]}] {a['title']}: {a['summary']}"
            for a in articles
        ])

    import datetime
    today = datetime.date.today().isoformat()

    prompt = f"""You are a sophisticated event-driven investment analyst. The user wants a full analysis of {ticker} ({company}) including specific options recommendations with complete entry AND exit strategies.

Today's date: {today}
Ticker: {ticker}
Company: {company}
User context: {context if context else 'General analysis requested'}

Recent news:
{news_text}

Your task:
1. Synthesise the recent news into a clear investment thesis
2. Identify the PRIMARY catalyst and direction (bullish/bearish)
3. Recommend specific options plays with FULL entry and exit strategy
4. For every option play include:
   - Exact strike price and expiry date
   - Entry: when and at what price to buy
   - Profit target: exact price or % to sell for profit
   - Stop loss: exact price or % to exit if wrong
   - Time stop: date to exit regardless if thesis hasn't played out
   - IV warning: flag if IV is elevated (e.g. around earnings) — suggest buying AFTER earnings if so
5. Identify ripple tickers that benefit or suffer

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences. Start directly with {{

{{
  "score": 82,
  "event_category": "restructuring",
  "primary_ticker": "{ticker}",
  "sector": "Technology",
  "reasoning_chain": [
    {{"step": "Event", "text": "describe the main catalyst"}},
    {{"step": "1st Order", "text": "immediate market impact"}},
    {{"step": "2nd Order", "text": "downstream effects"}},
    {{"step": "3rd Order", "text": "ripple effects on sector"}},
    {{"step": "Edge", "text": "why market hasn't fully priced this"}}
  ],
  "options_plays": [
    {{
      "ticker": "{ticker}",
      "type": "call",
      "role": "primary",
      "strike_note": "$X (Y% OTM)",
      "expiry_note": "Mon DD YYYY — reason for this expiry",
      "days_out": 45,
      "reasoning": "full reasoning for this play",
      "entry_strategy": "Buy when price is above $X or on a pullback to $Y support",
      "profit_target": "Sell at $Z (representing X% gain) or when stock reaches $W",
      "stop_loss": "Exit if option loses 40% of value or stock breaks below $X",
      "time_stop": "Exit by [date] if thesis hasn't played out regardless of P&L",
      "iv_warning": "IV is currently LOW/HIGH — good/bad time to buy options. Specific advice here."
    }}
  ],
  "act_by_hours": 48,
  "catalyst_date": "YYYY-MM-DD",
  "iv_environment": "low",
  "risk_level": "medium",
  "ripple_tickers": ["TICK1", "TICK2"],
  "summary_one_line": "one line summary of the thesis",
  "news_used": {json.dumps([a['title'][:80] for a in articles[:4]])}
}}"""

    import time
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            result = json.loads(text)
            result["is_manual_lookup"] = True
            result["lookup_ticker"] = ticker
            result["lookup_company"] = company
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            try:
                raw = response.content[0].text
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                    result["is_manual_lookup"] = True
                    return result
            except Exception:
                pass
            return {"error": str(e)[:200], "score": 0}

    return {"error": "max retries exceeded", "score": 0}
