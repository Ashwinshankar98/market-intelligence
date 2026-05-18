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

    # Fetch current price
    import yfinance as yf
    current_price = None
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if not hist.empty:
            current_price = round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    price_str = f"Current live price: ${current_price}" if current_price else "Current price: fetch from market"

    prompt = f"""You are a sophisticated event-driven investment analyst. Analyse {ticker} ({company}) with the latest available information.

Today: {today}
Ticker: {ticker}
{price_str}
User context: {context if context else 'General analysis requested'}
{pos_note}

Recent news:
{news_text}

Tasks:
1. Buy/Hold/Sell with TWO sections: analyst_facts (cite actual news/analyst opinions from news provided) and claude_opinion (your own view)
2. Reason through event chain (1st/2nd/3rd order)
3. For each option play: use the live price for strike, include entry, profit target, stop loss, time stop, IV warning, risk_reward_score (1-10, 10=best), max_loss_pct, confidence
4. If held: ADD/HOLD/REDUCE with analyst_facts AND claude_rationale separately
5. Complete all fields fully, no truncation

IMPORTANT: Raw JSON only. No markdown. Start with open brace.

{{"score": 82, "event_category": "earnings", "primary_ticker": "{ticker}", "sector": "Technology",
"current_price": {current_price or 0},
"buy_hold_sell": {{
  "recommendation": "BUY",
  "analyst_facts": "cite actual analyst upgrades, price targets, news facts",
  "claude_opinion": "separate claude assessment"
}},
"reasoning_chain": [
  {{"step": "Event", "text": "full description"}},
  {{"step": "1st Order", "text": "immediate impact"}},
  {{"step": "2nd Order", "text": "downstream effects"}},
  {{"step": "Edge", "text": "why not fully priced"}}
],
"portfolio_impact": {{
  "held_positions": [{{"ticker": "{ticker}", "action": "ADD", "analyst_facts": "news-based reason", "claude_rationale": "claude view", "current_equity": 0}}],
  "correlation_alerts": [],
  "hedge_suggestion": null
}},
"options_plays": [
  {{
    "ticker": "{ticker}", "type": "call", "role": "primary",
    "current_price": {current_price or 0},
    "strike_note": "use live price to calculate OTM strike",
    "expiry_note": "Month DD YYYY — reason for expiry",
    "days_out": 45,
    "reasoning": "complete reasoning without truncation",
    "entry_strategy": "complete entry instructions",
    "profit_target": "exact target with price levels",
    "stop_loss": "exact stop with price levels",
    "time_stop": "exit date if thesis fails",
    "iv_warning": "IV environment and whether good time to buy",
    "risk_reward_score": 7,
    "max_loss_pct": 40,
    "confidence": 75
  }}
],
"act_by_hours": 48,
"catalyst_date": "{today}",
"iv_environment": "normal",
"risk_level": "medium",
"ripple_tickers": [],
"summary_one_line": "complete one-line thesis",
"news_used": {json.dumps([a['title'][:80] for a in articles[:4]])}
}}"""

    import time
    response = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=5000,
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