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
    Fetch price using yfinance — was working fine before.
    yfinance domains are allowed on Railway unlike direct Yahoo Finance HTTP.
    """
    import concurrent.futures

    def _fetch():
        import yfinance as yf
        t = yf.Ticker(ticker)
        try:
            p = t.fast_info.last_price
            if p and p > 0:
                return round(float(p), 2)
        except Exception:
            pass
        hist = t.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_fetch)
            return future.result(timeout=5.0)
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

    # Fetch news and price in parallel
    news_task  = asyncio.create_task(_fetch_top_news(ticker))
    price_task = asyncio.get_event_loop().run_in_executor(None, _get_price_safe, ticker)

    try:
        articles, current_price = await asyncio.wait_for(
            asyncio.gather(news_task, price_task, return_exceptions=True),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        articles      = []
        current_price = None

    if isinstance(articles, Exception):      articles      = []
    if isinstance(current_price, Exception): current_price = None

    price_val = current_price if current_price else 0
    price_str = f"${current_price}" if current_price else "estimate from your knowledge"

    news_lines = [f"[{a.get('date','')}] {a.get('title','')}" for a in (articles or [])[:5]]
    news_str   = "\n".join(news_lines) if news_lines else "No recent news found."

    pos_note = ""
    held_equity = 0
    is_held = ticker in HOLDINGS
    if is_held:
        h = HOLDINGS[ticker]
        pos_note    = f"YOU HOLD: {h['shares']} shares @ avg ${h['avg_cost']} (equity ${h['equity']:,})"
        held_equity = h['equity']

    # Only include a held_positions template entry when the user actually holds the ticker
    if is_held:
        held_positions_template = f"""[{{
      "ticker":"{ticker}",
      "action":"ADD",
      "analyst_facts":"news-based reason to act on your existing position",
      "claude_rationale":"your view on the position",
      "current_equity":{held_equity}
    }}]"""
    else:
        held_positions_template = "[]"

    prompt = f"""Analyse {ticker} for investment. Return ONLY raw JSON starting with {{

Date:{today} Price:{price_str}{f" Context:{context}" if context else ""}
{pos_note}

News headlines:
{news_str}

IMPORTANT for buy_hold_sell:
- analyst_facts: Quote actual facts FROM THE NEWS ABOVE — analyst price targets, upgrades, earnings data, specific numbers. Do not use generic statements.
- claude_opinion: Your own separate view on the investment thesis. Be specific about risks and upside.

Return this exact JSON structure:
{{
  "score":82,"event_category":"earnings","primary_ticker":"{ticker}","sector":"Technology","current_price":{price_val},
  "buy_hold_sell":{{
    "recommendation":"BUY",
    "analyst_facts":"Specific facts from news above — e.g. BofA raised PT to $950, Samsung strike disrupting supply, new DDR5 product launch announced",
    "claude_opinion":"Your own assessment — e.g. The dip is a buying opportunity because supply disruption benefits MU's pricing power long term"
  }},
  "reasoning_chain":[
    {{"step":"Situation","text":"current state of {ticker}"}},
    {{"step":"Catalyst","text":"key upcoming catalyst"}},
    {{"step":"Risk","text":"main downside risk"}},
    {{"step":"Edge","text":"why this opportunity exists now"}}
  ],
  "portfolio_impact":{{
    "held_positions":{held_positions_template},
    "correlation_alerts":[],
    "hedge_suggestion":null
  }},
  "options_plays":[{{
    "ticker":"{ticker}","type":"call","role":"primary","current_price":{price_val},
    "strike_note":"strike with % OTM calculation","expiry_note":"Month DD YYYY — reason",
    "days_out":45,"reasoning":"complete reasoning for this specific play",
    "entry_strategy":"when and how to enter","profit_target":"specific price target",
    "stop_loss":"specific stop price","time_stop":"exit by date",
    "iv_warning":"current IV environment and advice",
    "risk_reward_score":7,"max_loss_pct":40,"confidence":75
  }}],
  "act_by_hours":48,"catalyst_date":"{today}","iv_environment":"normal",
  "risk_level":"medium","ripple_tickers":[],"summary_one_line":"one line thesis",
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


