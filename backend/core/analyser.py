import os, json, re, time
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL  = "claude-sonnet-4-6"

def _clean_json(text: str) -> str:
    """Strip markdown code fences Claude sometimes adds despite instructions."""
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

IMPORTANT: Respond ONLY with raw JSON, no markdown, no code fences: {{"score": 75, "reason": "one sentence"}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            return json.loads(text)
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"score": 0, "reason": str(e)[:100]}
    return {"score": 0, "reason": "max retries exceeded"}


def deep_analysis(headline: str, summary: str, category: str,
                  tickers: list, quick_score_val: float, source: str) -> dict:
    import datetime
    today = datetime.date.today().isoformat()

    prompt = f"""You are a sophisticated event-driven investment analyst. Analyse this market event and provide specific, actionable options recommendations.

Today's date: {today}
Event source: {source}
Event category: {category}
Tickers mentioned: {', '.join(tickers) if tickers else 'unknown'}
Headline: {headline}
Detail: {summary[:600] if summary else 'N/A'}

Your task:
1. Reason through the full event chain (1st order to 2nd order to 3rd order effects)
2. Identify the PRIMARY ticker to trade and any RIPPLE tickers
3. Recommend specific options plays with strike prices and expiry dates
4. For expiry: always pick catalyst date + 10-15 day buffer minimum
5. Identify ripple plays

Rules:
- Prefer calls on bullish events, puts on bearish
- For restructuring/layoffs: bullish call (cost savings to EPS beat)
- For partnerships: call on both partners + suppliers
- For regulatory action: put on target, call on competitors
- For insider buys: call on the stock, near-term expiry

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences. Start your response directly with the opening brace.

{{"score": 82, "event_category": "acquisition", "primary_ticker": "WBA", "sector": "Retail Pharmacy", "reasoning_chain": [{{"step": "Event", "text": "describe event"}}, {{"step": "Impact", "text": "describe impact"}}, {{"step": "Catalyst", "text": "describe catalyst"}}, {{"step": "Edge", "text": "describe edge"}}], "options_plays": [{{"ticker": "WBA", "type": "put", "role": "primary", "strike_note": "$12 (ATM)", "expiry_note": "Jun 20 2025", "days_out": 30, "reasoning": "PE buyout delisting risk"}}], "act_by_hours": 24, "catalyst_date": "2025-06-01", "iv_environment": "high", "risk_level": "high", "ripple_tickers": ["CVS", "RAD"], "summary_one_line": "one line summary"}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            return json.loads(text)
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            try:
                raw = response.content[0].text
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except Exception:
                pass
            return {"score": 0, "error": str(e)[:200]}
    return {"score": 0, "error": "max retries exceeded"}


def weekly_synthesis(signals: list) -> dict:
    if not signals:
        return {"insights": "No signals this week.", "keyword_weights": {}}

    signals_text = json.dumps([{
        "headline": s["headline"],
        "category": s["event_category"],
        "score": s["score"],
        "primary_ticker": s["primary_ticker"],
        "sector": s["sector"],
    } for s in signals[:50]], indent=2)

    prompt = f"""You are reviewing this week's market intelligence signals.

Signals this week:
{signals_text}

IMPORTANT: Respond ONLY with raw valid JSON. No markdown. No code fences.

{{"top_sectors": ["Semiconductors"], "top_categories": ["partnership"], "keyword_weights": {{"layoff": 1.2, "partnership": 1.4}}, "emerging_themes": ["AI buildout"], "insights": "summary here", "recommended_watchlist_additions": ["SMCI"]}}"""

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            text = _clean_json(response.content[0].text)
            return json.loads(text)
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"insights": "Synthesis error", "keyword_weights": {}}
    return {"insights": "Synthesis error", "keyword_weights": {}}