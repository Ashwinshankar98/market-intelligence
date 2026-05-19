import os, json, re, asyncio, time
import httpx
import feedparser
from fastapi import APIRouter
from core.analyser import _clean_json, _salvage_json
from core.portfolio import get_holdings_summary, get_position_context, HOLDINGS
import anthropic

router = APIRouter(prefix="/api", tags=["lookup"])

client      = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL       = "claude-sonnet-4-6"
NEWS_API_KEY= os.getenv("NEWS_API_KEY", "")

def _get_price(ticker: str) -> float | None:
    """Fetch latest price from yfinance with timeout protection."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None

async def fetch_news_fast(ticker: str, company: str) -> list:
    articles = []

    async def fetch_rss(query: str):
        try:
            url  = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
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
        pass

    seen, unique = set(), []
    for a in articles:
        if a["title"] and a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:10]


@router.post("/lookup")
async def lookup_ticker(body: dict):
    try:
        return await asyncio.wait_for(_do_lookup(body), timeout=60.0)
    except asyncio.TimeoutError:
        return {"error": "Analysis timed out — try again", "score": 0, "is_manual_lookup": True}

async def _do_lookup(body: dict):
    ticker  = body.get("ticker", "").upper().strip()
    company = body.get("company", ticker)
    context = body.get("context", "")

    if not ticker:
        return {"error": "ticker is required"}

    # Fetch news and price in parallel
    articles      = await fetch_news_fast(ticker, company)
    current_price = _get_price(ticker)

    news_text = "\n".join([
        f"- [{a.get('date','')[:10]}] {a['title']}: {a['summary']}"
        for a in articles
    ]) if articles else "No recent news found. Analyse based on general market knowledge."

    pos_ctx  = get_position_context([ticker])
    pos_note = ""
    if ticker in HOLDINGS:
        h = HOLDINGS[ticker]
        pos_note = f"\nYOU HOLD {ticker}: {h['shares']} shares, ${h['equity']:,} equity, avg cost ${h['avg_cost']}"

    import datetime
    today       = datetime.date.today().isoformat()
    price_str   = f"Current live price: ${current_price}" if current_price else "Current price: not available outside market hours"
    price_val   = current_price if current_price else 0

    prompt = f"""Analyse {ticker} ({company}) and provide a complete investment analysis in JSON.

Today: {today} | {price_str}
User context: {context if context else 'General analysis'}
{pos_note}

Recent news (last 48h):
{news_text[:1500]}

Return ONLY raw JSON, no markdown, starting with open brace:

{{
  "score": 82,
  "event_category": "earnings",
  "primary_ticker": "{ticker}",
  "sector": "Technology",
  "current_price": {price_val},
  "buy_hold_sell": {{
    "recommendation": "BUY",
    "analyst_facts": "cite actual facts from news above",
    "claude_opinion": "your own assessment"
  }},
  "reasoning_chain": [
    {{"step": "Event", "text": "main catalyst"}},
    {{"step": "1st Order", "text": "immediate impact"}},
    {{"step": "2nd Order", "text": "downstream"}},
    {{"step": "Edge", "text": "why not priced in"}}
  ],
  "portfolio_impact": {{
    "held_positions": [{{"ticker": "{ticker}", "action": "ADD", "analyst_facts": "reason", "claude_rationale": "view", "current_equity": 0}}],
    "correlation_alerts": [],
    "hedge_suggestion": null
  }},
  "options_plays": [
    {{
      "ticker": "{ticker}",
      "type": "call",
      "role": "primary",
      "current_price": {price_val},
      "strike_note": "strike based on current price",
      "expiry_note": "Month DD YYYY",
      "days_out": 45,
      "reasoning": "why this play",
      "entry_strategy": "when to enter",
      "profit_target": "target price",
      "stop_loss": "stop price",
      "time_stop": "exit date",
      "iv_warning": "IV assessment",
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
  "summary_one_line": "one line thesis",
  "news_used": {json.dumps([a['title'][:80] for a in articles[:3]])}
}}"""

    response = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2500,
                timeout=45.0,
                messages=[{"role": "user", "content": prompt}]
            )
            text   = _clean_json(response.content[0].text)
            result = json.loads(text)
            result["is_manual_lookup"] = True
            result["lookup_ticker"]    = ticker
            result["lookup_company"]   = company
            return result

        except json.JSONDecodeError:
            try:
                raw    = response.content[0].text if response else ""
                result = _salvage_json(raw)
                if result and result.get("primary_ticker"):
                    result["is_manual_lookup"] = True
                    result["lookup_ticker"]    = ticker
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
            try:
                if response:
                    result = _salvage_json(response.content[0].text)
                    if result:
                        result["is_manual_lookup"] = True
                        result["lookup_ticker"]    = ticker
                        return result
            except Exception:
                pass
            return {"error": f"Analysis failed: {str(e)[:200]}", "score": 0, "is_manual_lookup": True}

    return {"error": "Max retries exceeded", "score": 0, "is_manual_lookup": True}


@router.post("/ask-play")
async def ask_about_play(body: dict):
    from core.analyser import ask_about_play as _ask
    play           = body.get("play", {})
    question       = body.get("question", "")
    signal_context = body.get("signal_context", {})
    if not question or not play:
        return {"error": "play and question are required"}
    answer = _ask(play, question, signal_context)
    return {"answer": answer}