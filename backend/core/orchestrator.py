import os, json, hashlib
from database import get_connection
from scanners.news_scanner import scan_rss_feeds, scan_newsapi
from scanners.sec_scanner import scan_sec_filings
from scanners.reddit_scanner import scan_reddit
from core.analyser import quick_score, deep_analysis, weekly_synthesis
from core.notifier import send_signal_alert, send_weekly_summary
from core.portfolio import (
    get_alert_threshold, get_position_context,
    get_correlated_holdings, HOLDINGS, get_holdings_summary
)
import asyncio

# ── Fix 3: Raise Tier 2 → Tier 3 threshold from 65 to 72 ─────────────────────
QUICK_THRESHOLD  = int(os.getenv("QUICK_SCORE_THRESHOLD", 65))   # Tier 1 → Tier 2
DEEP_THRESHOLD   = int(os.getenv("DEEP_SCORE_THRESHOLD", 72))    # Tier 2 → Tier 3 (raised from 65)

# Breaking scan — only escalate to Tier 3 if score_boost this high (very critical events only)
BREAKING_CRITICAL_THRESHOLD = int(os.getenv("BREAKING_CRITICAL_THRESHOLD", 40))

# ── Dedup helpers ─────────────────────────────────────────────────────────────

def _headline_hash(headline: str) -> str:
    return hashlib.md5(headline[:120].encode()).hexdigest()

def _headline_seen(headline: str) -> bool:
    conn = get_connection()
    row  = conn.execute(
        "SELECT headline_hash FROM processed_headlines WHERE headline_hash=?",
        (_headline_hash(headline),)
    ).fetchone()
    conn.close()
    return row is not None

def _mark_headline(headline: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO processed_headlines (headline_hash) VALUES (?)",
        (_headline_hash(headline),)
    )
    conn.commit()
    conn.close()

def _already_signalled(headline: str) -> bool:
    conn = get_connection()
    row  = conn.execute(
        "SELECT id FROM signals WHERE headline_hash=?",
        (_headline_hash(headline),)
    ).fetchone()
    conn.close()
    return row is not None

# ── Shared Tier 3 helper ──────────────────────────────────────────────────────

async def _run_tier3(event: dict) -> dict | None:
    """Run deep analysis on a single event. Returns signal dict or None."""
    if _already_signalled(event["headline"]):
        print(f"[Dedup] Already signalled — {event['headline'][:60]}")
        return None
    try:
        tickers = event.get("tickers", [])
        pos_ctx = get_position_context(tickers)

        analysis = deep_analysis(
            headline         = event["headline"],
            summary          = event["summary"],
            category         = event.get("category", "unknown"),
            tickers          = tickers,
            quick_score_val  = event.get("quick_score", event.get("score_boost", 0)),
            source           = event.get("source", "unknown"),
            position_context = pos_ctx,
            portfolio_summary= get_holdings_summary(),
        )

        if "error" in analysis or analysis.get("score", 0) < DEEP_THRESHOLD:
            print(f"[Tier3] skip — score {analysis.get('score',0):.0f}")
            return None

        score          = analysis.get("score", 0)
        primary_ticker = analysis.get("primary_ticker", "")
        sector         = analysis.get("sector", "")
        headline_h     = _headline_hash(event["headline"])

        # Correlation detection
        correlated      = get_correlated_holdings(primary_ticker)
        held_correlated = [t for t in correlated if t in HOLDINGS]
        if held_correlated:
            analysis["correlation_alert"] = held_correlated

        # Save to DB
        conn = get_connection()
        conn.execute("""
            INSERT INTO signals
                (event_id, score, event_category, primary_ticker, sector,
                 headline, headline_hash, reasoning_chain, options_plays,
                 act_by_hours, catalyst_date, iv_environment, risk_level,
                 ripple_tickers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("event_id"), score,
            analysis.get("event_category", ""),
            primary_ticker, sector,
            analysis.get("summary_one_line", event["headline"])[:500],
            headline_h,
            json.dumps(analysis.get("reasoning_chain", [])),
            json.dumps(analysis.get("options_plays", [])),
            analysis.get("act_by_hours", 48),
            analysis.get("catalyst_date", ""),
            analysis.get("iv_environment", "normal"),
            analysis.get("risk_level", "medium"),
            json.dumps(analysis.get("ripple_tickers", [])),
        ))
        conn.commit()
        signal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        # Alert threshold (portfolio-aware)
        threshold = get_alert_threshold(sector, tickers, analysis.get("event_category", ""))
        if score >= threshold:
            await send_signal_alert(analysis)
            conn = get_connection()
            conn.execute("UPDATE signals SET telegram_sent=1 WHERE id=?", (signal_id,))
            conn.commit()
            conn.close()
            print(f"[Tier3] SIGNAL {score:.0f} (threshold {threshold}) — {primary_ticker} — {analysis.get('event_category')} {'🔗 ' + str(held_correlated) if held_correlated else ''}")
        else:
            print(f"[Tier3] stored (score {score:.0f} < threshold {threshold} for '{sector}') — {primary_ticker}")

        return analysis

    except Exception as e:
        print(f"[Tier3] Error: {e}")
        return None

# ── Full hourly scan ──────────────────────────────────────────────────────────

async def run_full_scan():
    """
    Full hourly scan — all sources → Tier1 tripwire → Tier2 quick score → Tier3 deep analysis.
    Fix 3: Tier2→Tier3 threshold raised to 72.
    Fix 4: Tier1 tightened — generic keywords require watchlist ticker match.
    """
    print("[Orchestrator] Starting full scan...")

    results = await asyncio.gather(
        scan_rss_feeds(),
        scan_newsapi(),
        scan_sec_filings(),
        scan_reddit(),
        return_exceptions=True
    )

    all_events = []
    for r in results:
        if isinstance(r, list):
            all_events.extend(r)
        elif isinstance(r, Exception):
            print(f"[Orchestrator] Scanner error: {r}")

    # Dedup at event level
    seen_in_scan = set()
    deduped = []
    for event in all_events:
        h = _headline_hash(event["headline"])
        if h in seen_in_scan or _headline_seen(event["headline"]):
            continue
        seen_in_scan.add(h)
        deduped.append(event)

    print(f"[Orchestrator] {len(deduped)} unique events passed Tier 1")

    # ── Tier 2 — quick score ──────────────────────────────────────────────────
    tier2_passing = []
    for event in deduped:
        try:
            qs    = quick_score(
                headline  = event["headline"],
                summary   = event["summary"],
                category  = event.get("category", "unknown"),
                tickers   = event.get("tickers", []),
                investors = event.get("investors", []),
            )
            score = qs.get("score", 0) + event.get("score_boost", 0)
            _mark_headline(event["headline"])

            if event.get("event_id"):
                conn = get_connection()
                conn.execute("UPDATE events SET quick_score=?, passed_tier2=? WHERE id=?",
                    (score, 1 if score >= QUICK_THRESHOLD else 0, event["event_id"]))
                conn.commit()
                conn.close()

            if score >= QUICK_THRESHOLD:
                event["quick_score"] = score
                tier2_passing.append(event)
                print(f"[Tier2] PASS {score:.0f} — {event['headline'][:60]}")
            else:
                print(f"[Tier2] skip {score:.0f} — {event['headline'][:60]}")

        except Exception as e:
            print(f"[Tier2] Error: {e}")

    print(f"[Orchestrator] {len(tier2_passing)} events passed Tier 2")

    # ── Tier 3 — deep analysis (Fix 3: only score >= 72 proceeds) ────────────
    new_signals = []
    for event in tier2_passing:
        # Fix 3: raised threshold
        if event.get("quick_score", 0) < DEEP_THRESHOLD:
            print(f"[Tier3] below deep threshold ({DEEP_THRESHOLD}) — skipping {event['headline'][:50]}")
            continue
        signal = await _run_tier3(event)
        if signal:
            new_signals.append(signal)

    print(f"[Orchestrator] Scan complete. {len(new_signals)} signals generated.")
    return new_signals


# ── Breaking scan — Fix 2: ZERO Claude cost ───────────────────────────────────

async def run_breaking_scan():
    """
    Lightweight 15-min scan.
    Fix 2: NEVER calls Tier 2 (no Claude quick score).
    Only escalates to Tier 3 if score_boost >= 40 (truly critical events).
    Everything else waits for the next full hourly scan.

    Critical threshold examples:
      - "Ackman buys NVDA" → boost ~40 → escalates
      - "Chapter 11 bankruptcy SMCI" → boost ~25+25 = 50 → escalates
      - "IONQ quantum breakthrough" → boost ~30 → escalates
      - "McDonald's earnings beat" → boost ~18 → does NOT escalate
      - "YETI Q1 beat" → boost ~18 → does NOT escalate
    """
    print("[Breaking] Running zero-cost tripwire scan...")
    events = await scan_rss_feeds()

    # Only fresh events
    fresh = [e for e in events if not _headline_seen(e["headline"])]

    # Only truly critical — high boost score without needing Claude to confirm
    critical = [e for e in fresh if e.get("score_boost", 0) >= BREAKING_CRITICAL_THRESHOLD]

    if not critical:
        print(f"[Breaking] {len(fresh)} fresh events, none critical enough to escalate")
        return

    print(f"[Breaking] {len(critical)} CRITICAL events — escalating to Tier 3 (no Tier 2)")
    for event in critical[:2]:  # max 2 per breaking scan even for critical
        signal = await _run_tier3(event)
        if signal:
            _mark_headline(event["headline"])
            print(f"[Breaking] Escalated: {event['headline'][:60]}")


# ── Weekly synthesis ──────────────────────────────────────────────────────────

async def run_weekly_synthesis():
    print("[Weekly] Running synthesis...")
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM signals WHERE created_at >= datetime('now', '-7 days')
        ORDER BY score DESC
    """).fetchall()
    conn.close()

    signals = [dict(r) for r in rows]
    if not signals:
        print("[Weekly] No signals")
        return

    synthesis = weekly_synthesis(signals)

    from datetime import datetime, timedelta
    week_start = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT INTO weekly_synthesis (week_start, top_sectors, keyword_weights, insights, signals_reviewed)
        VALUES (?, ?, ?, ?, ?)
    """, (week_start,
          json.dumps(synthesis.get("top_sectors", [])),
          json.dumps(synthesis.get("keyword_weights", {})),
          synthesis.get("insights", ""),
          len(signals)))
    conn.commit()
    conn.close()

    await send_weekly_summary(synthesis, len(signals))
    print(f"[Weekly] Done. Reviewed {len(signals)} signals.")