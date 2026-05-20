import os, json, re, asyncio, time
import httpx
import feedparser
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from core.analyser import _clean_json, _salvage_json
from core.portfolio import get_position_context, HOLDINGS
import anthropic

router = APIRouter(prefix="/api", tags=["lookup"])

client       = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=0)
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


def _resolve_to_ticker(user_input: str) -> str:
    """Resolve a company name to its ticker using yfinance Search."""
    import re as _re
    cleaned = user_input.strip().upper()
    # Already looks like a ticker (1–5 letters, no spaces)
    if _re.match(r'^[A-Z]{1,5}$', cleaned):
        return cleaned
    try:
        import yfinance as yf
        results = yf.Search(user_input, max_results=5).quotes
        for r in results:
            sym = r.get("symbol", "")
            # Prefer US-listed equities/ETFs (no dots = not foreign listed)
            if r.get("quoteType") in ("EQUITY", "ETF") and "." not in sym:
                return sym
        if results:
            return results[0].get("symbol", cleaned)
    except Exception:
        pass
    return cleaned


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def _do_lookup_stream(body: dict):
    """
    Async generator yielding SSE-style progress dicts then a final result dict.
    Consumers iterate with `async for event in _do_lookup_stream(body)`.
    """
    import datetime, time as _time
    raw_input = body.get("ticker", "").strip()
    if not raw_input:
        yield {"type": "result", "data": {"error": "ticker is required"}}
        return

    t0 = _time.monotonic()
    loop = asyncio.get_event_loop()

    def elapsed():
        return round(_time.monotonic() - t0, 1)

    # ── Step 1: Resolve ticker ─────────────────────────────────────────────────
    yield {"type": "progress", "step": "resolving", "msg": f"Resolving '{raw_input}'...", "done": False}
    ticker = await loop.run_in_executor(None, _resolve_to_ticker, raw_input)
    yield {"type": "progress", "step": "resolving", "msg": f"→ {ticker}", "elapsed": elapsed(), "done": True}

    company = body.get("company", raw_input)
    context = body.get("context", "")
    today   = datetime.date.today().isoformat()

    # ── Step 2: News + price in parallel ──────────────────────────────────────
    yield {"type": "progress", "step": "price", "msg": f"Fetching price & news for {ticker}...", "done": False}
    news_task  = asyncio.create_task(_fetch_top_news(ticker))
    price_task = loop.run_in_executor(None, _get_price_safe, ticker)
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

    # Alpaca fallback for price — run in executor (blocking sync client)
    if not current_price:
        yield {"type": "progress", "step": "price", "msg": "yfinance failed — trying Alpaca...", "done": False}
        try:
            from core.options_chain import _fetch_price_from_alpaca
            api_key = os.getenv("ALPACA_API_KEY", "")
            secret  = os.getenv("ALPACA_SECRET_KEY", "")
            if api_key and secret:
                alpaca_price = await loop.run_in_executor(
                    None, _fetch_price_from_alpaca, ticker, api_key, secret
                )
                if alpaca_price > 0:
                    current_price = alpaca_price
        except Exception:
            pass

    price_val    = current_price if current_price else 0
    price_str    = f"${current_price}" if current_price else "estimate from your knowledge"
    price_source = "live" if current_price else "estimated"
    price_msg    = f"${price_val} (live)" if current_price else "no price — Claude will estimate"
    yield {"type": "progress", "step": "price",
           "msg": f"{price_msg} · {len(articles or [])} news articles",
           "elapsed": elapsed(), "done": True}

    news_lines = [f"[{a.get('date','')}] {a.get('title','')}" for a in (articles or [])[:5]]
    news_str   = "\n".join(news_lines) if news_lines else "No recent news found."

    pos_note = ""
    held_equity = 0
    is_held = ticker in HOLDINGS
    if is_held:
        h = HOLDINGS[ticker]
        pos_note    = f"YOU HOLD: {h['shares']} shares @ avg ${h['avg_cost']} (equity ${h['equity']:,})"
        held_equity = h['equity']

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

    # ── Step 3: Options chain ─────────────────────────────────────────────────
    real_contracts = []
    options_source = "no_chain"
    if price_val > 0:
        yield {"type": "progress", "step": "options",
               "msg": f"Fetching options chain for {ticker} @ ${price_val}...", "done": False}
        try:
            from core.options_chain import get_options_chain
            # blocking sync client — run in executor to avoid stalling the event loop
            real_contracts = await loop.run_in_executor(None, get_options_chain, ticker, price_val)
            options_source = "alpaca" if real_contracts else "no_chain"
            opts_msg = f"{len(real_contracts)} contracts (Alpaca)" if real_contracts else "not optionable / no chain"
        except Exception as e:
            options_source = "error"
            opts_msg = f"error fetching chain"
        yield {"type": "progress", "step": "options",
               "msg": opts_msg, "elapsed": elapsed(), "done": True}
    else:
        options_source = "no_price"
        yield {"type": "progress", "step": "options",
               "msg": "Skipped (no price available)", "elapsed": elapsed(), "done": True}

    if real_contracts:
        options_chain_str = f"\nREAL OPTIONS CHAIN for {ticker} (from Alpaca — live tradeable contracts):\n"
        for c in real_contracts:
            g = c["greeks"]
            options_chain_str += (
                f"  {c['symbol']}  {c['type'].upper()}  strike=${c['strike']}  "
                f"exp={c['expiry']} ({c['days_out']}d)  {c['moneyness']}\n"
                f"    bid=${c['bid']}  ask=${c['ask']}  mid=${c['mid']}  "
                f"spread={c['spread_pct']}%  IV={c['iv_pct']}%  cost/contract=${c['cost_per_contract']}\n"
                f"    delta={g.get('delta')}  gamma={g.get('gamma')}  "
                f"theta={g.get('theta')}/day  vega={g.get('vega')}\n"
            )
        options_instruction = (
            "OPTIONS: Choose from the REAL CONTRACTS above — do NOT invent strikes. "
            "Pick the best 1-2 based on greeks and the thesis. Use the exact symbol. "
            "Include alpaca_symbol, bid, ask, mid, spread_pct, iv_pct, cost_per_contract, greeks, and greek_reasoning fields."
        )
        options_plays_template = """[{
      "ticker":"TICKER","type":"call","role":"primary","alpaca_symbol":"TICKER260620C00190000",
      "current_price":185.50,"strike_note":"$190 (2.4% OTM)","expiry_note":"Jun 20 2026 — reason",
      "days_out":32,"bid":8.50,"ask":8.80,"mid":8.65,"spread_pct":3.5,"iv_pct":42.0,
      "cost_per_contract":865.00,"greeks":{"delta":0.48,"gamma":0.012,"theta":-0.18,"vega":0.22},
      "greek_reasoning":"why this delta/theta fits the catalyst timeline",
      "reasoning":"complete reasoning","entry_strategy":"when and how to enter",
      "profit_target":"specific target","stop_loss":"specific stop","time_stop":"exit by date",
      "iv_warning":"IV environment assessment","risk_reward_score":7,"max_loss_pct":40,"confidence":75
    }]"""
    else:
        options_chain_str    = ""
        options_instruction  = "OPTIONS: No live chain available — set options_plays to []."
        options_plays_template = "[]"

    prompt = f"""Analyse {ticker} for investment. Return ONLY raw JSON starting with {{

Date:{today} Price:{price_str}{f" Context:{context}" if context else ""}
{pos_note}

News headlines:
{news_str}
{options_chain_str}
IMPORTANT:
- analyst_facts: Quote actual facts FROM THE NEWS ABOVE — analyst price targets, upgrades, earnings data, specific numbers.
- claude_opinion: Your own separate view on the investment thesis.
- {options_instruction}

Return this exact JSON structure:
{{
  "score":82,"event_category":"earnings","primary_ticker":"{ticker}","sector":"Technology","current_price":{price_val},
  "buy_hold_sell":{{
    "recommendation":"BUY",
    "analyst_facts":"Specific facts from news above",
    "claude_opinion":"Your own assessment"
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
  "options_plays":{options_plays_template},
  "act_by_hours":48,"catalyst_date":"{today}","iv_environment":"normal",
  "risk_level":"medium","ripple_tickers":[],"summary_one_line":"one line thesis",
  "news_used":{json.dumps([a.get('title','')[:60] for a in (articles or [])[:3]])}
}}"""

    # ── Step 4: Claude analysis ───────────────────────────────────────────────
    # Run the sync Anthropic client in a thread so the event loop stays live
    # and asyncio.wait_for can actually cancel it on timeout.
    # max_retries=0 on the client means this is a single 35s attempt.
    yield {"type": "progress", "step": "claude", "msg": "Calling Claude...", "done": False}

    def _call_claude():
        return client.messages.create(
            model=MODEL,
            max_tokens=2000,
            timeout=60.0,
            messages=[{"role": "user", "content": prompt}]
        )

    response = None
    result   = None
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call_claude),
                timeout=65.0
            )
            text   = _clean_json(response.content[0].text)
            result = json.loads(text)
            break

        except asyncio.TimeoutError:
            err_msg = "Request timed out"
            if attempt < 1:
                yield {"type": "progress", "step": "claude", "msg": "Timeout — retrying...", "done": False}
                await asyncio.sleep(1)
                continue
            yield {"type": "progress", "step": "claude",
                   "msg": f"Failed: {err_msg}", "elapsed": elapsed(), "done": True, "error": True}
            yield {"type": "result", "data": {
                "error": err_msg, "score": 0, "is_manual_lookup": True,
                "primary_ticker": ticker, "headline": f"{ticker} analysis timed out"
            }}
            return

        except json.JSONDecodeError:
            try:
                raw    = response.content[0].text if response else ""
                result = _salvage_json(raw)
                if result and result.get("primary_ticker"):
                    break
            except Exception:
                pass
            if attempt < 1:
                await asyncio.sleep(1)
                continue

        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(1)
                continue
            try:
                if response:
                    result = _salvage_json(response.content[0].text)
            except Exception:
                pass
            if not result:
                err = {
                    "error": str(e)[:200], "score": 0,
                    "is_manual_lookup": True, "primary_ticker": ticker,
                    "headline": f"{ticker} analysis failed"
                }
                yield {"type": "progress", "step": "claude",
                       "msg": f"Failed: {str(e)[:60]}", "elapsed": elapsed(), "done": True, "error": True}
                yield {"type": "result", "data": err}
                return

    if not result:
        err = {
            "error": "Max retries", "score": 0,
            "is_manual_lookup": True, "primary_ticker": ticker,
            "headline": f"{ticker} analysis"
        }
        yield {"type": "progress", "step": "claude",
               "msg": "Failed after retries", "elapsed": elapsed(), "done": True, "error": True}
        yield {"type": "result", "data": err}
        return

    result["is_manual_lookup"] = True
    result["lookup_ticker"]    = ticker
    result["price_source"]     = price_source
    result["options_source"]   = options_source

    yield {"type": "progress", "step": "claude",
           "msg": f"Analysis complete · score {result.get('score', 0)}", "elapsed": elapsed(), "done": True}
    yield {"type": "result", "data": result}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/lookup/stream")
async def lookup_ticker_stream(body: dict):
    """SSE endpoint — streams real-time progress then final result."""
    async def generate():
        try:
            async for event in _do_lookup_stream(body):
                yield _sse(event)
        except Exception as e:
            yield _sse({"type": "error", "msg": str(e)[:200]})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/lookup")
async def lookup_ticker(body: dict):
    """Non-streaming fallback — drains the generator and returns the final result."""
    try:
        async def _drain():
            async for event in _do_lookup_stream(body):
                if event.get("type") == "result":
                    return event.get("data", {})
            return None

        result = await asyncio.wait_for(_drain(), timeout=50.0)
        if result:
            return result
        ticker = body.get("ticker", "").upper()
        return {"error": "No result", "score": 0, "is_manual_lookup": True, "primary_ticker": ticker}

    except asyncio.TimeoutError:
        ticker = body.get("ticker", "").upper()
        return {
            "error": "Analysis timed out — try again",
            "score": 0,
            "is_manual_lookup": True,
            "primary_ticker": ticker,
            "headline": f"{ticker} analysis timed out",
        }
