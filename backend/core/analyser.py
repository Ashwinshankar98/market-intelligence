import os, json, re, time
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"

def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text  = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text

def _salvage_json(raw: str) -> dict:
    raw = _clean_json(raw)
    try:
        depth, last_valid = 0, 0
        for i, ch in enumerate(raw):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: last_valid = i + 1
        if last_valid:
            return json.loads(raw[:last_valid])
    except Exception:
        pass
    try:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m: return json.loads(m.group())
    except Exception:
        pass
    return {}

def _get_active_weights() -> dict:
    try:
        from database import get_connection
        conn = get_connection()
        rows = conn.execute("SELECT category, weight FROM active_weights").fetchall()
        conn.close()
        return {r["category"]: r["weight"] for r in rows}
    except Exception:
        return {}

def _get_current_price(ticker: str) -> float | None:
    """
    Fetch latest price using thread with timeout.
    Falls back gracefully — Claude estimates if unavailable.
    """
    import concurrent.futures

    def _fetch():
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_fetch)
            return future.result(timeout=4.0)
    except Exception:
        pass
    return None

def quick_score(headline: str, summary: str, category: str,
                tickers: list, investors: list = None) -> dict:
    weights    = _get_active_weights()
    cat_weight = weights.get(category, 1.0)

    prompt = f"""Rate this market event 0-100 for investment signal strength.
Category: {category} (weight: {cat_weight:.1f}x)
Investors: {', '.join(investors) if investors else 'none'}
Tickers: {', '.join(tickers) if tickers else 'none'}
Headline: {headline}
Summary: {summary[:300] if summary else 'N/A'}

0-40=noise, 41-64=weak, 65-79=good, 80-100=strong
Weight>1.0=score generously, Weight<1.0=score conservatively

Respond ONLY with raw JSON: {{"score": 75, "reason": "one sentence"}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            result = json.loads(_clean_json(response.content[0].text))
            raw_score = result.get("score", 0)
            result["score"] = min(100, round(raw_score * cat_weight))
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"score": 0, "reason": str(e)[:100]}
    return {"score": 0, "reason": "max retries"}


def deep_analysis(headline: str, summary: str, category: str,
                  tickers: list, quick_score_val: float, source: str,
                  position_context: dict = None,
                  portfolio_summary: str = None) -> dict:
    import datetime
    today = datetime.date.today().isoformat()

    # Fetch prices with short timeout — skip silently if slow
    price_context = {}
    for t in tickers[:3]:  # max 3 tickers to keep it fast
        try:
            p = _get_current_price(t)
            if p:
                price_context[t] = p
        except Exception:
            pass
    price_str = ""
    if price_context:
        price_str = "\nCurrent live prices (use these for strike recommendations):\n"
        for t, p in price_context.items():
            price_str += f"  {t}: ${p}\n"

    pos_str = ""
    if position_context:
        held = {t: ctx for t, ctx in position_context.items() if ctx.get("held")}
        not_held = {t: ctx for t, ctx in position_context.items() if not ctx.get("held")}
        if held:
            pos_str += "\nHELD POSITIONS:\n"
            for t, ctx in held.items():
                pos_str += f"  {t}: {ctx['shares']} shares, ${ctx['equity']:,} equity, avg ${ctx['avg_cost']}\n"
                if ctx.get("correlated_holdings"):
                    pos_str += f"    correlated: {', '.join(ctx['correlated_holdings'])}\n"
        if not_held:
            corr = [(t, ctx['correlated_holdings']) for t, ctx in not_held.items() if ctx.get('correlated_holdings')]
            if corr:
                pos_str += "\nCORRELATION ALERTS:\n"
                for t, c in corr:
                    pos_str += f"  {t} affects your: {', '.join(c)}\n"

    prompt = f"""You are a sophisticated event-driven investment analyst. Analyse this event and provide a complete investment analysis.

Today: {today}
Source: {source}
Category: {category}
Tickers: {', '.join(tickers) if tickers else 'unknown'}
Headline: {headline}
Detail: {summary[:600] if summary else 'N/A'}
{price_str}
{pos_str}

IMPORTANT INSTRUCTIONS:
1. Use the live prices provided above for ALL strike price recommendations
2. For Buy/Hold/Sell: first cite FACTS from news/analysts, then separately give Claude opinion
3. For each option play include a risk_reward_score (1-10, where 10 is best risk/reward)
4. For held positions: state ADD/HOLD/REDUCE with factual reasoning
5. Keep individual text fields concise but DO NOT truncate — complete every field fully

Respond ONLY with raw JSON. No markdown. Start with open brace.

{{
  "score": 82,
  "event_category": "earnings",
  "primary_ticker": "AVGO",
  "sector": "semiconductor",
  "current_price": 185.50,
  "buy_hold_sell": {{
    "recommendation": "BUY",
    "analyst_facts": "Goldman Sachs raised PT to $220. Q2 revenue beat by 8%. Three analysts upgraded to Strong Buy this week. Custom ASIC pipeline expanding with 3 new hyperscaler contracts.",
    "claude_opinion": "The VMware integration margin expansion combined with AI revenue acceleration creates a compounding growth story. Street estimates likely still too conservative for FY2027."
  }},
  "reasoning_chain": [
    {{"step": "Event", "text": "full description without truncation"}},
    {{"step": "1st Order", "text": "full immediate impact"}},
    {{"step": "2nd Order", "text": "full downstream effects"}},
    {{"step": "3rd Order", "text": "full sector ripple"}},
    {{"step": "Edge", "text": "why market hasn't fully priced this"}}
  ],
  "portfolio_impact": {{
    "held_positions": [
      {{
        "ticker": "NVDA",
        "action": "ADD",
        "analyst_facts": "AVGO custom silicon validates AI chip demand broadly",
        "claude_rationale": "Your NVDA position benefits from overall AI capex expansion",
        "current_equity": 5687
      }}
    ],
    "correlation_alerts": [
      {{
        "ticker": "AMD",
        "held": true,
        "impact": "bullish",
        "note": "Full explanation of how this affects AMD without truncation"
      }}
    ],
    "hedge_suggestion": null
  }},
  "options_plays": [
    {{
      "ticker": "AVGO",
      "type": "call",
      "role": "primary",
      "current_price": 185.50,
      "strike_note": "$195 (5.1% OTM based on current $185.50)",
      "expiry_note": "Aug 15 2026 — 12 days past next earnings",
      "days_out": 89,
      "reasoning": "Complete reasoning without truncation",
      "entry_strategy": "Complete entry instructions",
      "profit_target": "Exact target with reasoning",
      "stop_loss": "Exact stop with reasoning",
      "time_stop": "Exit date with reasoning",
      "iv_warning": "Current IV assessment",
      "risk_reward_score": 7,
      "max_loss_pct": 40,
      "confidence": 75
    }}
  ],
  "act_by_hours": 48,
  "catalyst_date": "2026-06-01",
  "iv_environment": "normal",
  "risk_level": "medium",
  "ripple_tickers": ["AMD", "SMCI"],
  "summary_one_line": "Complete one-line thesis"
}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            try:
                return json.loads(text)
            except Exception:
                result = _salvage_json(response.content[0].text)
                if result and result.get("score", 0) > 0:
                    return result
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {"score": 0, "error": "JSON parse failed"}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            result = _salvage_json(response.content[0].text if response else "")
            if result:
                return result
            return {"score": 0, "error": str(e)[:200]}
    return {"score": 0, "error": "max retries"}


def ask_about_play(play: dict, question: str, signal_context: dict) -> str:
    """Answer a specific question about an options play."""
    prompt = f"""You are an options trading expert. Answer this specific question about an options play.

Signal context:
- Ticker: {signal_context.get('primary_ticker', '?')}
- Event: {signal_context.get('headline', '?')}
- Score: {signal_context.get('score', '?')}

Options play in question:
- Type: {play.get('type', '?').upper()} on {play.get('ticker', '?')}
- Strike: {play.get('strike_note', '?')}
- Expiry: {play.get('expiry_note', '?')}
- Current price: ${play.get('current_price', 'unknown')}
- Reasoning: {play.get('reasoning', '?')}
- Risk/reward score: {play.get('risk_reward_score', '?')}/10

User question: {question}

Answer directly and concisely. Be specific with numbers where relevant. If you need current market data you don't have, say so clearly."""

    try:
        response = client.messages.create(
            model=MODEL, max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Error: {str(e)[:100]}"


def weekly_synthesis(signals: list) -> dict:
    """Tier 4 — Sunday weekly review with intelligent weight updates."""
    if not signals:
        return {
            "insights": "No signals this week.",
            "top_sectors": [],
            "top_categories": [],
            "emerging_themes": [],
            "recommended_watchlist_additions": [],
            "weight_updates": []
        }

    try:
        from database import get_connection
        conn = get_connection()
        current_weights = {r["category"]: r["weight"] for r in
                          conn.execute("SELECT category, weight FROM active_weights").fetchall()}
        conn.close()
    except Exception:
        current_weights = {}

    from collections import defaultdict
    cat_stats = defaultdict(lambda: {"count": 0, "scores": [], "has_options": 0, "alerted": 0})
    for s in signals:
        cat = s.get("event_category") or "unknown"
        cat_stats[cat]["count"] += 1
        cat_stats[cat]["scores"].append(float(s.get("score") or 0))
        try:
            plays = json.loads(s["options_plays"]) if isinstance(s.get("options_plays"), str) else (s.get("options_plays") or [])
            if plays:
                cat_stats[cat]["has_options"] += 1
        except Exception:
            pass
        if s.get("telegram_sent"):
            cat_stats[cat]["alerted"] += 1

    stats_summary = []
    for cat, v in cat_stats.items():
        avg = round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else 0
        high = len([s for s in v["scores"] if s >= 80])
        low  = len([s for s in v["scores"] if s < 72])
        stats_summary.append(f"{cat}: {v['count']} signals, avg={avg}, high_score={high}, low_score={low}, actionable={v['has_options']}, alerted={v['alerted']}")

    stats_text = "\n".join(stats_summary)
    weights_text = json.dumps(current_weights)

    prompt = f"""You are reviewing this week's market intelligence signals to update category weights.

Current weights: {weights_text}

This week's statistics:
{stats_text}

Rules:
- INCREASE weight: category had multiple high-score signals, clear options plays, genuine market-moving events
- DECREASE weight: category flooded scanner with low scores, no clear catalyst, mostly noise
- Hard limits: weight 0.5-2.0, max change 0.3/week
- hedge_fund/portfolio_move: never below 1.0
- semiconductor/memory/quantum/ai_tech/space/optoelectronics: never below 0.8
- Zero signals this week = keep unchanged

Respond ONLY with raw JSON. No markdown. No code fences. Start with open brace.

{{"insights": "2-3 sentence week summary", "top_sectors": ["semiconductor"], "top_categories": ["partnership"], "emerging_themes": ["AI buildout"], "recommended_watchlist_additions": ["SMCI"], "weight_updates": [{{"category": "earnings", "new_weight": 0.8, "direction": "down", "reason": "15 signals avg score 68, mostly non-portfolio"}}]}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            result = json.loads(text)
            # Validate required fields exist
            if "insights" not in result:
                result["insights"] = "Weekly synthesis complete."
            if "weight_updates" not in result:
                result["weight_updates"] = []
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            # Try salvage
            try:
                result = _salvage_json(response.content[0].text if response else "")
                if result:
                    if "insights" not in result:
                        result["insights"] = "Weekly synthesis complete."
                    if "weight_updates" not in result:
                        result["weight_updates"] = []
                    return result
            except Exception:
                pass

    return {
        "insights": "Synthesis completed but response parsing failed.",
        "top_sectors": [],
        "top_categories": [],
        "emerging_themes": [],
        "recommended_watchlist_additions": [],
        "weight_updates": []
    }