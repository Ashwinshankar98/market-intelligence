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

def _get_active_weights() -> dict:
    """Load current keyword weights from DB."""
    try:
        from database import get_connection
        conn = get_connection()
        rows = conn.execute("SELECT category, weight FROM active_weights").fetchall()
        conn.close()
        return {r["category"]: r["weight"] for r in rows}
    except Exception:
        return {}

def quick_score(headline: str, summary: str, category: str,
                tickers: list, investors: list = None) -> dict:
    """Tier 2 — fast score. ~100 tokens."""
    # Apply active weight to boost scores for high-performing categories
    weights    = _get_active_weights()
    cat_weight = weights.get(category, 1.0)

    prompt = f"""Rate this market event 0-100 for investment signal strength.
Event category: {category} (importance weight: {cat_weight:.1f}x)
Investors mentioned: {', '.join(investors) if investors else 'none'}
Tickers mentioned: {', '.join(tickers) if tickers else 'none'}
Headline: {headline}
Summary: {summary[:300] if summary else 'N/A'}

Score 0-100 where:
0-40 = noise, not actionable
41-64 = weak signal, skip
65-79 = good signal, worth analysing
80-100 = strong signal, act fast

The importance weight reflects historical performance of this category.
Weight > 1.0 means this category has been generating strong signals — score generously.
Weight < 1.0 means this category has been noisy — score conservatively.

IMPORTANT: Respond ONLY with raw JSON, no markdown: {{"score": 75, "reason": "one sentence"}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            result = json.loads(_clean_json(response.content[0].text))
            # Apply weight multiplier to score
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
    """Tier 3 — full analysis with options recommendations."""
    import datetime
    today = datetime.date.today().isoformat()

    pos_str = ""
    if position_context:
        held = {t: ctx for t, ctx in position_context.items() if ctx.get("held")}
        not_held = {t: ctx for t, ctx in position_context.items() if not ctx.get("held")}
        if held:
            pos_str += "\nHELD POSITIONS MENTIONED:\n"
            for t, ctx in held.items():
                pos_str += f"  {t}: {ctx['shares']} shares, ${ctx['equity']:,} equity, avg cost ${ctx['avg_cost']}\n"
                if ctx.get("correlated_holdings"):
                    pos_str += f"    correlated holdings: {', '.join(ctx['correlated_holdings'])}\n"
        if not_held:
            corr = [(t, ctx['correlated_holdings']) for t, ctx in not_held.items() if ctx.get('correlated_holdings')]
            if corr:
                pos_str += "\nCORRELATION ALERTS:\n"
                for t, c in corr:
                    pos_str += f"  {t} affects your: {', '.join(c)}\n"

    prompt = f"""You are a sophisticated event-driven investment analyst. Analyse this market event with full awareness of existing positions.

Today: {today}
Source: {source}
Category: {category}
Tickers: {', '.join(tickers) if tickers else 'unknown'}
Headline: {headline}
Detail: {summary[:600] if summary else 'N/A'}
{pos_str}

Tasks:
1. Reason through event chain (1st to 2nd to 3rd order)
2. For HELD positions: ADD, HOLD, or REDUCE
3. For CORRELATED positions: flag impact
4. Recommend options plays with strike, expiry, entry, profit target, stop loss, time stop, IV warning
5. Hedge suggestion if bearish for held position
6. Keep all text fields under 150 chars for efficiency

IMPORTANT: Raw JSON only, no markdown, start with open brace.

{{"score": 82, "event_category": "partnership", "primary_ticker": "NVDA", "sector": "semiconductor",
"reasoning_chain": [
  {{"step": "Event", "text": "brief description"}},
  {{"step": "1st Order", "text": "immediate impact"}},
  {{"step": "2nd Order", "text": "downstream"}},
  {{"step": "Edge", "text": "why not priced"}}
],
"portfolio_impact": {{
  "held_positions": [{{"ticker": "NVDA", "action": "ADD", "rationale": "reason", "current_equity": 5687}}],
  "correlation_alerts": [{{"ticker": "AMD", "held": true, "impact": "bullish", "note": "lifts AMD too"}}],
  "hedge_suggestion": null
}},
"options_plays": [
  {{
    "ticker": "NVDA", "type": "call", "role": "primary",
    "strike_note": "$230 (3% OTM)", "expiry_note": "Jul 18 2026",
    "days_out": 63, "reasoning": "why",
    "entry_strategy": "when to enter",
    "profit_target": "when to take profit",
    "stop_loss": "when to cut",
    "time_stop": "exit by date",
    "iv_warning": "IV assessment"
  }}
],
"act_by_hours": 48, "catalyst_date": "2026-07-01",
"iv_environment": "normal", "risk_level": "medium",
"ripple_tickers": ["AMD", "SMCI"],
"summary_one_line": "thesis in one line"
}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(_clean_json(response.content[0].text))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            try:
                raw = response.content[0].text
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    return json.loads(m.group())
            except Exception:
                pass
            return {"score": 0, "error": str(e)[:200]}
    return {"score": 0, "error": "max retries"}


def weekly_synthesis(signals: list) -> dict:
    """
    Tier 4 — Sunday weekly review.
    Intelligently adjusts weights UP and DOWN based on signal quality.
    Hard constraints: weights 0.5-2.0, max change 0.3 per week,
    hedge_fund never below 1.0, your sectors never below 0.8.
    """
    if not signals:
        return {"insights": "No signals this week.", "keyword_weights": {}}

    # Load current weights
    try:
        from database import get_connection
        conn = get_connection()
        current_weights = {r["category"]: r["weight"] for r in
                          conn.execute("SELECT category, weight FROM active_weights").fetchall()}
        conn.close()
    except Exception:
        current_weights = {}

    # Build signal stats per category
    from collections import defaultdict
    cat_stats = defaultdict(lambda: {"count": 0, "scores": [], "has_options": 0, "alerted": 0})
    for s in signals:
        cat = s.get("event_category", "unknown")
        cat_stats[cat]["count"] += 1
        cat_stats[cat]["scores"].append(s.get("score", 0))
        if s.get("options_plays") and s["options_plays"] != "[]":
            cat_stats[cat]["has_options"] += 1
        if s.get("telegram_sent"):
            cat_stats[cat]["alerted"] += 1

    stats_text = json.dumps({
        cat: {
            "signal_count": v["count"],
            "avg_score": round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else 0,
            "high_score_count": len([s for s in v["scores"] if s >= 80]),
            "low_score_count": len([s for s in v["scores"] if s < 72]),
            "had_actionable_options": v["has_options"],
            "sent_to_telegram": v["alerted"],
        }
        for cat, v in cat_stats.items()
    }, indent=2)

    prompt = f"""You are reviewing this week's market intelligence signals to update category weights for next week.

Current weights: {json.dumps(current_weights, indent=2)}

This week's signal statistics by category:
{stats_text}

Your job: Recommend new weights for each category based on performance.

Rules for adjusting weights:
INCREASE weight when: category had multiple high-score signals (≥80), signals had clear options plays, events were genuinely market-moving for the portfolio
DECREASE weight when: category flooded scanner with low-score signals (<72), signals had no clear catalyst or options play, category generated noise not signal

Hard constraints you MUST follow:
- Weights must stay between 0.5 (minimum) and 2.0 (maximum)
- No single category can change by more than 0.3 in one week
- 'hedge_fund' and 'portfolio_move' weights NEVER go below 1.0 (always important)
- 'semiconductor', 'memory', 'quantum', 'ai_tech', 'space', 'optoelectronics' NEVER go below 0.8 (core sectors)
- If a category had zero signals this week, keep weight unchanged (no data = no change)

For each category provide: new_weight, direction (up/down/stable), and a brief reason.

IMPORTANT: Respond ONLY with raw JSON. No markdown. No code fences.

{{
  "insights": "2-3 sentence summary of the week",
  "top_sectors": ["semiconductor", "quantum"],
  "top_categories": ["partnership", "hedge_fund"],
  "emerging_themes": ["AI sovereign buildout", "Memory supply tightening"],
  "recommended_watchlist_additions": ["SMCI", "VRT"],
  "weight_updates": [
    {{"category": "semiconductor", "new_weight": 1.2, "direction": "up", "reason": "3 high-score signals with clear options plays"}},
    {{"category": "earnings", "new_weight": 0.7, "direction": "down", "reason": "12 signals but avg score 68, mostly non-portfolio companies"}},
    {{"category": "quantum", "new_weight": 1.1, "direction": "up", "reason": "IONQ breakthrough generated 85-score signal with strong catalyst"}},
    {{"category": "hedge_fund", "new_weight": 1.0, "direction": "stable", "reason": "minimum floor maintained"}}
  ]
}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(_clean_json(response.content[0].text))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"insights": "Synthesis error", "keyword_weights": {}, "weight_updates": []}
    return {"insights": "Synthesis error", "keyword_weights": {}, "weight_updates": []}