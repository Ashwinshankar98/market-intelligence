import os, json, re, asyncio, time
import httpx
import feedparser
from fastapi import APIRouter
from core.analyser import _clean_json, _salvage_json
from core.portfolio import get_position_context, HOLDINGS
import anthropic

router = APIRouter(prefix="/api", tags=["lookup"])

client       = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL        = "claude-sonnet-4-6"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

def _get_price(ticker: str) -> float | None:
    """Fast price fetch — tries multiple methods with short timeout."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        # fast_info is the quickest method
        p = t.fast_info.last_price
        if p and p > 0:
            return round(float(p), 2)
    except Exception:
        pass
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="1d", interval="5m")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None

async def _fetch_top_news(ticker: str, max_articles: int = 5) -> list:
    """Fetch only from ONE source fast — Google News RSS only."""
    try:
        url  = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        articles = []
        for e in feed.entries[:max_articles]:
            articles.append({
                "title":   e.get("title", "")[:100],
                "summary": (e.get("summary", "") or "")[:150],
                "date":    e.get("published", "")[:10],
            })
        return articles
    except Exception:
        return []


@router.post("/lookup")
async def lookup_ticker(body: dict):
    try:
        return await asyncio.wait_for(_do_lookup(body), timeout=50.0)
    except asyncio.TimeoutError:
        return {"error": "Analysis timed out — try again", "score": 0,
                "is_manual_lookup": True, "primary_ticker": body.get("ticker","").upper()}


async def _do_lookup(body: dict):
    ticker  = body.get("ticker", "").upper().strip()
    company = body.get("company", ticker)
    context = body.get("context", "")

    if not ticker:
        return {"error": "ticker is required"}

    import datetime
    today = datetime.date.today().isoformat()

    # Fetch news and price in parallel
    articles, current_price = await asyncio.gather(
        _fetch_top_news(ticker),
        asyncio.get_event_loop().run_in_executor(None, _get_price, ticker),
        return_exceptions=True
    )

    if isinstance(articles, Exception):
        articles = []
    if isinstance(current_price, Exception):
        current_price = None

    price_val  = current_price if current_price else 0
    price_str  = f"${current_price}" if current_price else "unknown (market closed)"

    # Build compact news string
    news_lines = [f"[{a['date']}] {a['title']}" for a in (articles or [])[:5]]
    news_str   = "\n".join(news_lines) if news_lines else "No recent news available."

    # Position context
    pos_note = ""
    if ticker in HOLDINGS:
        h = HOLDINGS[ticker]
        pos_note = f"YOU HOLD: {h['shares']} shares @ avg ${h['avg_cost']} (equity ${h['equity']:,})"

    # Compact prompt — no large example JSON
    prompt = f"""Analyse {ticker} ({company}) for investment. Return ONLY raw JSON starting with {{

Date: {today} | Price: {price_str}
{f"Context: {context}" if context else ""}
{pos_note}

Recent news:
{news_str}

JSON schema (fill all fields):
{{
  "score": 0-100,
  "event_category": "category",
  "primary_ticker": "{ticker}",
  "sector": "sector name",
  "current_price": {price_val},
  "buy_hold_sell": {{
    "recommendation": "BUY|HOLD|SELL",
    "analyst_facts": "what news/analysts say - cite sources",
    "claude_opinion": "your own view separate from analysts"
  }},
  "reasoning_chain": [
    {{"step": "Situation", "text": "current state of {ticker}"}},
    {{"step": "Catalyst", "text": "key upcoming catalyst"}},
    {{"step": "Risk", "text": "main risk to thesis"}},
    {{"step": "Edge", "text": "why opportunity exists now"}}
  ],
  "portfolio_impact": {{
    "held_positions": [{{"ticker": "{ticker}", "action": "ADD|HOLD|REDUCE", "analyst_facts": "news reason", "claude_rationale": "your view", "current_equity": {HOLDINGS.get(ticker, {}).get("equity", 0)}}}],
    "correlation_alerts": [],
    "hedge_suggestion": null
  }},
  "options_plays": [
    {{
      "ticker": "{ticker}",
      "type": "call|put",
      "role": "primary",
      "current_price": {price_val},
      "strike_note": "strike with % OTM",
      "expiry_note": "Month DD YYYY - reason",
      "days_out": 45,
      "reasoning": "why this play",
      "entry_strategy": "when/how to enter",
      "profit_target": "exit target",
      "stop_loss": "stop price",
      "time_stop": "exit by date",
      "iv_warning": "IV level assessment",
      "risk_reward_score": 1-10,
      "max_loss_pct": 100,
      "confidence": 0-100
    }}
  ],
  "act_by_hours": 48,
  "catalyst_date": "YYYY-MM-DD",
  "iv_environment": "low|normal|elevated|high",
  "risk_level": "low|medium|high",
  "ripple_tickers": [],
  "summary_one_line": "thesis in one sentence",
  "news_used": {json.dumps([a['title'][:60] for a in (articles or [])[:3]])}
}}"""

    response = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                timeout=40.0,
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
            if attempt < 1:
                time.sleep(1)
                continue

        except Exception as e:
            if attempt < 1:
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
            return {"error": str(e)[:200], "score": 0, "is_manual_lookup": True,
                    "primary_ticker": ticker}

    return {"error": "Max retries", "score": 0, "is_manual_lookup": True,
            "primary_ticker": ticker}


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