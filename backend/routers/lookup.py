import os, json, re, asyncio
import httpx
import feedparser
from fastapi import APIRouter
from core.analyser import _clean_json
from core.portfolio import get_holdings_summary, get_position_context, HOLDINGS
import anthropic

router = APIRouter(prefix="/api", tags=["lookup"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

async def fetch_news_fast(ticker: str, company: str) -> list:
    """Fetch news from multiple sources in parallel with short timeouts."""
    articles = []

    async def fetch_rss(query: str):
        try:
            url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            return [{"title": e.get("title",""), "summary": (e.get("summary","") or "")[:200], "date": e.get("published","")} for e in feed.entries[:5]]
        except Exception:
            return []

    async def fetch_newsapi():
        if not NEWS_API_KEY:
            return []
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get("https://newsapi.org/v2/everything", params={
                    "q": f"{ticker} {company}", "apiKey": NEWS_API_KEY,
                    "language": "en", "sortBy": "publishedAt", "pageSize": 5,
                })
                return [{"title": a.get("title",""), "summary": (a.get("description") or "")[:200], "date": a.get("publishedAt","")} for a in resp.json().get("articles", [])]
        except Exception:
            return []

    # Run all fetches in parallel with 8 second total timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                fetch_rss(f"{ticker} stock news"),
                fetch_rss(f"{company} latest"),
                fetch_newsapi(),
                return_exceptions=True
            ),
            timeout=8.0
        )
        for r in results:
            if isinstance(r, list):
                articles.extend(r)
    except asyncio.TimeoutError:
        print(f"[Lookup] News fetch timed out for {ticker} — proceeding with what we have")

    # Deduplicate
    seen, unique = set(), []
    for a in articles:
        if a["title"] and a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:10]


def _salvage_json(raw: str) -> dict:
    """Try multiple strategies to extract valid JSON from a truncated response."""
    raw = _clean_json(raw)

    # Strategy 1 — find last complete closing brace
    try:
        depth = 0
        last_valid = 0
        for i, ch in enumerate(raw):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_valid = i + 1
        if last_valid:
            return json.loads(raw[:last_valid])
    except Exception:
        pass

    # Strategy 2 — regex extraction
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    # Strategy 3 — try fixing truncated string by closing open brackets
    try:
        fixed = raw
        open_braces   = raw.count('{') - raw.count('}')
        open_brackets = raw.count('[') - raw.count(']')
        # Close any open string first
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += ']' * max(0, open_brackets)
        fixed += '}' * max(0, open_braces)
        return json.loads(fixed)
    except Exception:
        pass

    return {}


@router.post("/lookup")
async def lookup_ticker(body: dict):
    ticker  = body.get("ticker", "").upper().strip()
    company = body.get("company", ticker)
    context = body.get("context", "")

    if not ticker:
        return {"error": "ticker is required"}

    # Fetch news with fast parallel fetching
    articles = await fetch_news_fast(ticker, company)

    news_text = "\n".join([
        f"- [{a.get('date','')[:10]}] {a['title']}: {a['summary']}"
        for a in articles
    ]) if articles else "No recent news found. Analyse based on general market knowledge."

    # Get portfolio context
    pos_ctx   = get_position_context([ticker])
    portfolio = get_holdings_summary()

    import datetime
    today = datetime.date.today().isoformat()

    # Build position note
    pos_note = ""
    if ticker in HOLDINGS:
        h = HOLDINGS[ticker]
        pos_note = f"\nYOU HOLD {ticker}: {h['shares']} shares, ${h['equity']:,} equity, avg cost ${h['avg_cost']}"

    prompt = f"""You are a sophisticated event-driven investment analyst managing a personal tech/AI/quantum/space focused portfolio. Analyse {ticker} ({company}) and provide a complete investment analysis with specific options recommendations including full entry AND exit strategy.

Today: {today}
Ticker: {ticker}
User context: {context if context else 'General analysis requested'}
{pos_note}

Recent news:
{news_text}

Your task:
1. Synthesise news into a clear investment thesis (bullish/bearish/neutral)
2. Reason through event chain if there is a catalyst
3. For each options play include exact strike, expiry, entry strategy, profit target, stop loss, time stop, and IV warning
4. If the user holds the stock say ADD, HOLD, or REDUCE
5. List ripple tickers that are affected

CRITICAL: Keep your response concise. Maximum 2 options plays. Keep reasoning_chain to 4 steps max. Keep all text fields under 150 characters. This ensures the response fits within token limits.

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences. Start directly with open brace.

{{"score": 82, "event_category": "earnings", "primary_ticker": "{ticker}", "sector": "Technology",
"reasoning_chain": [
  {{"step": "Event", "text": "what happened in 100 chars or less"}},
  {{"step": "Impact", "text": "immediate market impact in 100 chars or less"}},
  {{"step": "Catalyst", "text": "next catalyst in 100 chars or less"}},
  {{"step": "Edge", "text": "why not fully priced in 100 chars or less"}}
],
"portfolio_impact": {{
  "held_positions": [{{"ticker": "{ticker}", "action": "ADD", "rationale": "brief reason", "current_equity": 0}}],
  "correlation_alerts": [],
  "hedge_suggestion": null
}},
"options_plays": [
  {{
    "ticker": "{ticker}",
    "type": "call",
    "role": "primary",
    "strike_note": "$X (Y% OTM)",
    "expiry_note": "Month DD YYYY",
    "days_out": 45,
    "reasoning": "why this play in 120 chars",
    "entry_strategy": "when and where to enter in 120 chars",
    "profit_target": "exact price or percent to take profit",
    "stop_loss": "exact price or percent to cut loss",
    "time_stop": "exit by this date if thesis fails",
    "iv_warning": "current IV assessment in 100 chars"
  }}
],
"act_by_hours": 48,
"catalyst_date": "{today}",
"iv_environment": "normal",
"risk_level": "medium",
"ripple_tickers": ["TICK1", "TICK2"],
"summary_one_line": "one line thesis under 120 chars",
"news_used": {json.dumps([a['title'][:80] for a in articles[:4]])}
}}"""

    import time
    response = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            text   = _clean_json(response.content[0].text)
            result = json.loads(text)
            result["is_manual_lookup"] = True
            result["lookup_ticker"]    = ticker
            result["lookup_company"]   = company
            return result

        except json.JSONDecodeError:
            # Try to salvage truncated JSON
            try:
                raw    = response.content[0].text if response else ""
                result = _salvage_json(raw)
                if result and result.get("primary_ticker"):
                    result["is_manual_lookup"] = True
                    result["lookup_ticker"]    = ticker
                    result["lookup_company"]   = company
                    return result
            except Exception:
                pass
            if attempt < 2:
                time.sleep(1)
                continue

        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            # Last resort salvage
            try:
                if response:
                    result = _salvage_json(response.content[0].text)
                    if result:
                        result["is_manual_lookup"] = True
                        result["lookup_ticker"]    = ticker
                        return result
            except Exception:
                pass
            return {"error": f"Analysis failed: {str(e)[:100]}", "score": 0, "is_manual_lookup": True}

    return {"error": "Max retries exceeded", "score": 0, "is_manual_lookup": True}