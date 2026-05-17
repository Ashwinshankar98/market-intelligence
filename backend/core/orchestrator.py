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

QUICK_THRESHOLD = int(os.getenv("QUICK_SCORE_THRESHOLD", 65))

# ── Dedup helpers ─────────────────────────────────────────────────────────────

def _headline_hash(headline: str) -> str:
    return hashlib.md5(headline[:120].encode()).hexdigest()

def _headline_seen(headline: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT headline_hash FROM processed_headlines WHERE headline_hash = ?",
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
    row = conn.execute(
        "SELECT id FROM signals WHERE headline_hash = ?",
        (_headline_hash(headline),)
    ).fetchone()
    conn.close()
    return row is not None

# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_full_scan():
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

    # Dedup
    seen_in_scan = set()
    deduped = []
    for event in all_events:
        h = _headline_hash(event["headline"])
        if h in seen_in_scan or _headline_seen(event["headline"]):
            print(f"[Dedup] Already seen — {event['headline'][:60]}")
            continue
        seen_in_scan.add(h)
        deduped.append(event)

    print(f"[Orchestrator] {len(deduped)} unique events passed Tier 1")

    # ── Tier 2 — quick score ──────────────────────────────────────────────────
    tier2_passing = []
    for event in deduped:
        try:
            qs = quick_score(
                headline=event["headline"],
                summary=event["summary"],
                category=event.get("category", "unknown"),
                tickers=event.get("tickers", []),
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

    # ── Tier 3 — deep analysis with portfolio context ─────────────────────────
    new_signals = []
    for event in tier2_passing:
        if _already_signalled(event["headline"]):
            print(f"[Dedup] Already signalled — {event['headline'][:60]}")
            continue

        try:
            tickers   = event.get("tickers", [])
            pos_ctx   = get_position_context(tickers)
            portfolio = get_holdings_summary()

            analysis = deep_analysis(
                headline=event["headline"],
                summary=event["summary"],
                category=event.get("category", "unknown"),
                tickers=tickers,
                quick_score_val=event.get("quick_score", 0),
                source=event.get("source", "unknown"),
                position_context=pos_ctx,
                portfolio_summary=portfolio,
            )

            if "error" in analysis or analysis.get("score", 0) < QUICK_THRESHOLD:
                print(f"[Tier3] skip — {analysis.get('score', 0):.0f}")
                continue

            # ── Portfolio-aware alert threshold ───────────────────────────────
            sector  = analysis.get("sector", "")
            score   = analysis.get("score", 0)
            threshold = get_alert_threshold(sector, tickers, analysis.get("event_category", ""))

            # Check correlations — flag if held tickers are correlated
            primary_ticker = analysis.get("primary_ticker", "")
            correlated     = get_correlated_holdings(primary_ticker)
            held_correlated = [t for t in correlated if t in HOLDINGS]

            if held_correlated:
                analysis["correlation_alert"] = held_correlated
                print(f"[Portfolio] Correlation: {primary_ticker} affects your {held_correlated}")

            # Save to DB regardless of alert threshold
            headline_h = _headline_hash(event["headline"])
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
                primary_ticker,
                sector,
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

            # ── Only send Telegram if score meets portfolio-aware threshold ────
            if score >= threshold:
                await send_signal_alert(analysis)
                conn = get_connection()
                conn.execute("UPDATE signals SET telegram_sent=1 WHERE id=?", (signal_id,))
                conn.commit()
                conn.close()
                print(f"[Tier3] SIGNAL {score:.0f} (threshold {threshold}) — {primary_ticker} — {analysis.get('event_category')} {'🔗 CORRELATED: ' + str(held_correlated) if held_correlated else ''}")
            else:
                print(f"[Tier3] stored (score {score:.0f} < threshold {threshold} for sector '{sector}') — {primary_ticker}")

            new_signals.append(analysis)

        except Exception as e:
            print(f"[Tier3] Error: {e}")

    print(f"[Orchestrator] Scan complete. {len(new_signals)} signals generated.")
    return new_signals


async def run_breaking_scan():
    print("[Breaking] Running lightweight tripwire scan...")
    events = await scan_rss_feeds()
    fresh    = [e for e in events if not _headline_seen(e["headline"])]
    critical = [e for e in fresh if e.get("score_boost", 0) >= 25]

    if critical:
        print(f"[Breaking] {len(critical)} critical events — escalating")
        for event in critical[:3]:
            try:
                if _already_signalled(event["headline"]):
                    continue
                tickers = event.get("tickers", [])
                pos_ctx = get_position_context(tickers)
                analysis = deep_analysis(
                    headline=event["headline"],
                    summary=event["summary"],
                    category=event.get("category", "unknown"),
                    tickers=tickers,
                    quick_score_val=event.get("score_boost", 0),
                    source=event.get("source", "unknown"),
                    position_context=pos_ctx,
                    portfolio_summary=get_holdings_summary(),
                )
                threshold = get_alert_threshold(
                    analysis.get("sector", ""),
                    tickers,
                    analysis.get("event_category", "")
                )
                if analysis.get("score", 0) >= threshold:
                    _mark_headline(event["headline"])
                    await send_signal_alert(analysis)
            except Exception as e:
                print(f"[Breaking] Error: {e}")


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
    """, (week_start, json.dumps(synthesis.get("top_sectors", [])),
          json.dumps(synthesis.get("keyword_weights", {})),
          synthesis.get("insights", ""), len(signals)))
    conn.commit()
    conn.close()

    await send_weekly_summary(synthesis, len(signals))
    print(f"[Weekly] Done. Reviewed {len(signals)} signals.")