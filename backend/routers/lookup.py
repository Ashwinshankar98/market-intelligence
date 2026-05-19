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


def _get_price_safe(ticker: str) -> float | None:
    """
    Fetch latest price directly from Yahoo Finance HTTP API.
    No yfinance library — fast, reliable, works 24/7.
    """
    try:
        import urllib.request
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data   = json.loads(resp.read())
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            if closes:
                return round(float(closes[-1]), 2)
    except Exception:
        pass
    return None


async def _fetch_top_news(ticker: str, max_articles: int = 5) -> list:
    """Single RSS fetch — fast, no NewsAPI dependency."""
    try:
        url  = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        return [
            {"title": e.get("title", "")[:100], "date": e.get("published", "")[:10]}
            for e in feed.entries[:max_articles]
        ]
    except Exception:
        return []


@router.post("/lookup")
async def lookup_ticker(body: dict):
    try:
        return await asyncio.wait_for(_do_lookup(body), timeout=50.0)
    except asyncio.TimeoutError:
        return {
            "error": "Analysis timed out — try again",
            "score": 0,
            "is_manual_lookup": True,
            "primary_ticker": body.get("ticker", "").upper(),
            "headline": f"{body.get('ticker','').upper()} analysis timed out",
        }


async def _do_lookup(body: dict):
    ticker  = body.get("ticker", "").upper().strip()
    company = body.get("company", ticker)
    context = body.get("context", "")

    if not ticker:
        return {"error": "ticker is required"}

    import datetime
    today = datetime.date.today().isoformat()

    # Fetch news and price in parallel — price has 3s hard timeout
    news_task  = asyncio.create_task(_fetch_top_news(ticker))
    price_task = asyncio.get_event_loop().run_in_executor(None, _get_price_safe, ticker)

    # Wait max 8s for both — don't let price hang the whole request
    try:
        articles, current_price = await asyncio.wait_for(
            asyncio.gather(news_task, price_task, return_exceptions=True),
            timeout=8.0
        )
    except asyncio.TimeoutError:
        articles      = []
        current_price = None

    if isinstance(articles, Exception):      articles      = []
    if isinstance(current_price, Exception): current_price = None

    price_val = current_price if current_price else 0
    price_str = f"${current_price}" if current_price else "not available (market closed)"

    news_lines = [f"[{a.get('date','')}] {a.get('title','')}" for a in (articles or [])[:5]]
    news_str   = "\n".join(news_lines) if news_lines else "No recent news found."

    pos_note = ""
    held_equity = 0
    if ticker in HOLDINGS:
        h = HOLDINGS[ticker]
        pos_note    = f"YOU HOLD: {h['shares']} shares @ avg ${h['avg_cost']} (equity ${h['equity']:,})"
        held_equity = h['equity']

    prompt = f"""Analyse {ticker} for investment. Return ONLY raw JSON starting with {{

Date:{today} Price:{price_str}{f" Context:{context}" if context else ""}
{pos_note}

News headlines:
{news_str}

Return this exact JSON structure:
{{
  "score":82,"event_category":"earnings","primary_ticker":"{ticker}","sector":"Technology","current_price":{price_val},
  "buy_hold_sell":{{"recommendation":"BUY","analyst_facts":"cite news sources above","claude_opinion":"your view"}},
  "reasoning_chain":[
    {{"step":"Situation","text":"current state"}},
    {{"step":"Catalyst","text":"key upcoming event"}},
    {{"step":"Risk","text":"main downside risk"}},
    {{"step":"Edge","text":"why opportunity exists"}}
  ],
  "portfolio_impact":{{"held_positions":[{{"ticker":"{ticker}","action":"HOLD","analyst_facts":"reason","claude_rationale":"view","current_equity":{held_equity}}}],"correlation_alerts":[],"hedge_suggestion":null}},
  "options_plays":[{{
    "ticker":"{ticker}","type":"call","role":"primary","current_price":{price_val},
    "strike_note":"strike % OTM","expiry_note":"Month DD YYYY","days_out":45,
    "reasoning":"why","entry_strategy":"when to enter","profit_target":"target",
    "stop_loss":"stop","time_stop":"exit date","iv_warning":"IV level",
    "risk_reward_score":7,"max_loss_pct":40,"confidence":75
  }}],
  "act_by_hours":48,"catalyst_date":"{today}","iv_environment":"normal",
  "risk_level":"medium","ripple_tickers":[],"summary_one_line":"thesis",
  "news_used":{json.dumps([a.get('title','')[:60] for a in (articles or [])[:3]])}
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
            return {
                "error": str(e)[:200], "score": 0,
                "is_manual_lookup": True, "primary_ticker": ticker,
                "headline": f"{ticker} analysis failed"
            }

    return {
        "error": "Max retries", "score": 0,
        "is_manual_lookup": True, "primary_ticker": ticker,
        "headline": f"{ticker} analysis"
    }


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