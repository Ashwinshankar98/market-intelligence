import json
from fastapi import APIRouter
from database import get_connection

router = APIRouter(prefix="/api", tags=["intelligence"])

@router.get("/signals")
def get_signals(limit: int = 200, min_score: float = 0, days: int = 7):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM signals
        WHERE score >= ?
        AND created_at >= datetime('now', ? || ' days')
        ORDER BY created_at DESC
        LIMIT ?
    """, (min_score, f"-{days}", limit)).fetchall()
    conn.close()
    signals = []
    for r in rows:
        s = dict(r)
        for field in ["reasoning_chain", "options_plays", "ripple_tickers"]:
            try:
                s[field] = json.loads(s[field]) if s[field] else []
            except Exception:
                s[field] = []
        signals.append(s)
    return signals

@router.get("/signals/{signal_id}")
def get_signal(signal_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    s = dict(row)
    for field in ["reasoning_chain", "options_plays", "ripple_tickers"]:
        try:
            s[field] = json.loads(s[field]) if s[field] else []
        except Exception:
            s[field] = []
    return s

@router.get("/stats")
def get_stats():
    conn = get_connection()
    today_signals = conn.execute("""
        SELECT COUNT(*) as count FROM signals
        WHERE date(created_at) = date('now')
    """).fetchone()["count"]

    total_events = conn.execute("SELECT COUNT(*) as count FROM events").fetchone()["count"]

    avg_score = conn.execute("""
        SELECT AVG(score) as avg FROM signals
        WHERE date(created_at) = date('now')
    """).fetchone()["avg"] or 0

    top_sector = conn.execute("""
        SELECT sector, COUNT(*) as cnt FROM signals
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY sector ORDER BY cnt DESC LIMIT 1
    """).fetchone()

    high_conviction = conn.execute("""
        SELECT COUNT(*) as count FROM signals
        WHERE score >= 80 AND date(created_at) = date('now')
    """).fetchone()["count"]

    conn.close()
    return {
        "signals_today":    today_signals,
        "events_scanned":   total_events,
        "avg_score_today":  round(avg_score, 1),
        "top_sector":       top_sector["sector"] if top_sector else "N/A",
        "high_conviction":  high_conviction,
    }

@router.get("/sectors")
def get_sector_breakdown():
    conn = get_connection()
    rows = conn.execute("""
        SELECT sector, COUNT(*) as count, AVG(score) as avg_score
        FROM signals
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY sector
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/weekly")
def get_weekly_synthesis():
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM weekly_synthesis ORDER BY created_at DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row:
        return {}
    s = dict(row)
    for field in ["top_sectors", "keyword_weights"]:
        try:
            s[field] = json.loads(s[field]) if s[field] else {}
        except Exception:
            s[field] = {}
    return s

@router.post("/scan/trigger")
async def trigger_scan():
    """Manually trigger a scan — useful for testing."""
    from core.orchestrator import run_full_scan
    signals = await run_full_scan()
    return {"triggered": True, "signals_generated": len(signals)}

@router.get("/weights")
def get_active_weights():
    """Current category weights — updated every Sunday by weekly synthesis."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT category, weight, previous, direction, reason, updated_at
        FROM active_weights ORDER BY weight DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/ask-play")
async def ask_about_play(body: dict):
    """Ask Claude a specific question about an options play."""
    from core.analyser import ask_about_play as _ask
    play           = body.get("play", {})
    question       = body.get("question", "")
    signal_context = body.get("signal_context", {})
    if not question or not play:
        return {"error": "play and question are required"}
    answer = _ask(play, question, signal_context)
    return {"answer": answer}