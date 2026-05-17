import os, json, re, time
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"

def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text

def quick_score(headline: str, summary: str, category: str, tickers: list) -> dict:
    prompt = f"""Rate this market event 0-100 for investment signal strength.
Event category: {category}
Tickers mentioned: {', '.join(tickers) if tickers else 'none'}
Headline: {headline}
Summary: {summary[:300] if summary else 'N/A'}

Score 0-100 where:
0-40 = noise, not actionable
41-64 = weak signal, skip
65-79 = good signal, worth analysing
80-100 = strong signal, act fast

IMPORTANT: Respond ONLY with raw JSON, no markdown: {{"score": 75, "reason": "one sentence"}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(_clean_json(response.content[0].text))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"score": 0, "reason": str(e)[:100]}
    return {"score": 0, "reason": "max retries"}


def deep_analysis(headline: str, summary: str, category: str,
                  tickers: list, quick_score_val: float, source: str,
                  position_context: dict = None, portfolio_summary: str = None) -> dict:
    import datetime
    today = datetime.date.today().isoformat()

    # Build position context string
    pos_str = ""
    if position_context:
        held = {t: ctx for t, ctx in position_context.items() if ctx.get("held")}
        not_held = {t: ctx for t, ctx in position_context.items() if not ctx.get("held")}
        if held:
            pos_str += "\nHELD POSITIONS MENTIONED:\n"
            for t, ctx in held.items():
                pos_str += f"  {t}: {ctx['shares']} shares, ${ctx['equity']:,} equity, avg cost ${ctx['avg_cost']}\n"
                if ctx.get("correlated_holdings"):
                    pos_str += f"    → Also holds correlated: {', '.join(ctx['correlated_holdings'])}\n"
        if not_held:
            corr_info = [(t, ctx['correlated_holdings']) for t, ctx in not_held.items() if ctx.get('correlated_holdings')]
            if corr_info:
                pos_str += "\nCORRELATION ALERTS:\n"
                for t, corr in corr_info:
                    pos_str += f"  {t} news affects held positions: {', '.join(corr)}\n"

    prompt = f"""You are a sophisticated event-driven investment analyst managing a personal portfolio. Analyse this market event with full awareness of existing positions.

Today: {today}
Source: {source}
Category: {category}
Tickers mentioned: {', '.join(tickers) if tickers else 'unknown'}
Headline: {headline}
Detail: {summary[:600] if summary else 'N/A'}
{pos_str}

Your task:
1. Reason through event chain (1st → 2nd → 3rd order effects)
2. For HELD positions: say whether to ADD, HOLD, or REDUCE. Never recommend opening a new position if already held — recommend adding to it or hedging it.
3. For CORRELATED positions: flag how this news affects other holdings
4. For NEW positions: recommend if worth buying
5. Include specific options plays with strike, expiry, entry, profit target, stop loss, time stop
6. Flag if IV is elevated (don't buy options when IV is high — wait for it to drop)
7. Include hedge suggestion if the news is bearish for a held position

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences. Start directly with {{

{{"score": 82, "event_category": "partnership", "primary_ticker": "NVDA", "sector": "semiconductor",
"reasoning_chain": [
  {{"step": "Event", "text": "describe event"}},
  {{"step": "1st Order", "text": "immediate impact"}},
  {{"step": "2nd Order", "text": "downstream effects"}},
  {{"step": "3rd Order", "text": "sector ripple"}},
  {{"step": "Edge", "text": "why not fully priced"}}
],
"portfolio_impact": {{
  "held_positions": [
    {{"ticker": "NVDA", "action": "ADD", "rationale": "this news strengthens the thesis", "current_equity": 5687}}
  ],
  "correlation_alerts": [
    {{"ticker": "AMD", "held": true, "impact": "bullish", "note": "NVDA partnership lifts AMD too"}}
  ],
  "hedge_suggestion": null
}},
"options_plays": [
  {{
    "ticker": "NVDA",
    "type": "call",
    "role": "primary",
    "strike_note": "$230 (3% OTM)",
    "expiry_note": "Jul 18 2026",
    "days_out": 63,
    "reasoning": "full reasoning",
    "entry_strategy": "Buy on a pullback to $220 support or at open if gapping up moderately",
    "profit_target": "Sell at $260 (30% gain on option) or when stock reaches $245",
    "stop_loss": "Exit if option loses 40% or stock closes below $215",
    "time_stop": "Exit by Jun 30 if thesis hasn't played out",
    "iv_warning": "IV currently normal — good time to buy. Avoid if IV spikes above 60."
  }}
],
"act_by_hours": 48,
"catalyst_date": "2026-07-01",
"iv_environment": "normal",
"risk_level": "medium",
"ripple_tickers": ["AMD", "SMCI", "CRWV"],
"summary_one_line": "one line thesis summary"
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
    if not signals:
        return {"insights": "No signals this week.", "keyword_weights": {}}

    signals_text = json.dumps([{
        "headline": s["headline"], "category": s["event_category"],
        "score": s["score"], "primary_ticker": s["primary_ticker"], "sector": s["sector"],
    } for s in signals[:50]], indent=2)

    prompt = f"""Review this week's market intelligence signals for a tech/AI/quantum/space focused portfolio.

Signals:
{signals_text}

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences.

{{"top_sectors": ["Semiconductors"], "top_categories": ["partnership"],
"keyword_weights": {{"layoff": 1.2, "partnership": 1.4}},
"emerging_themes": ["AI buildout"],
"insights": "2-3 sentence summary",
"recommended_watchlist_additions": ["SMCI"]}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(_clean_json(response.content[0].text))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"insights": "Synthesis error", "keyword_weights": {}}
    return {"insights": "Synthesis error", "keyword_weights": {}}