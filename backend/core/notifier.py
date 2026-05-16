import os
import httpx

async def send_signal_alert(signal: dict):
    """Send a full signal alert to the intelligence Telegram group."""
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    score = signal.get("score", 0)
    score_emoji = "🔴" if score >= 85 else "🟡" if score >= 72 else "⚪"

    plays = signal.get("options_plays", [])
    primary = next((p for p in plays if p.get("role") == "primary"), None)
    ripples = [p for p in plays if p.get("role") == "ripple"]

    lines = [
        f"{score_emoji} <b>SIGNAL — {score}/100</b>",
        f"<b>{signal.get('primary_ticker', '?')} · {signal.get('event_category', '').upper()}</b>",
        f"<i>{signal.get('headline', '')[:120]}</i>",
        "",
        "─────────────────",
    ]

    chain = signal.get("reasoning_chain", [])
    if chain:
        lines.append("📊 <b>Reasoning chain</b>")
        for step in chain:
            lines.append(f"  {step.get('step')}: {step.get('text')}")
        lines.append("")

    if primary:
        lines += [
            "🎯 <b>Primary play</b>",
            f"  {primary['ticker']} {primary['type'].upper()}",
            f"  Strike: {primary['strike_note']}",
            f"  Expiry: {primary['expiry_note']}",
            f"  Why: {primary['reasoning'][:300]}",
            "",
        ]

    if ripples:
        lines.append("🔗 <b>Ripple plays</b>")
        for r in ripples[:2]:
            lines.append(f"  {r['ticker']} {r['type'].upper()} · {r['strike_note']} · {r['expiry_note']}")
        lines.append("")

    lines += [
        "─────────────────",
        f"⏰ Act within: <b>{signal.get('act_by_hours', '?')} hours</b>",
        f"📅 Catalyst: {signal.get('catalyst_date', 'TBD')}",
        f"📈 IV: {signal.get('iv_environment', '?').upper()} · Risk: {signal.get('risk_level', '?').upper()}",
        f"🏭 Sector: {signal.get('sector', '?')}",
    ]

    if signal.get("ripple_tickers"):
        ripple_str = ", ".join(signal["ripple_tickers"][:4])
        lines.append(f"👀 Also watch: {ripple_str}")

    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML"
        })


async def send_weekly_summary(synthesis: dict, signal_count: int):
    """Send Sunday weekly synthesis summary."""
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    sectors  = ", ".join(synthesis.get("top_sectors", []))
    themes   = synthesis.get("emerging_themes", [])
    watchlist = synthesis.get("recommended_watchlist_additions", [])

    message = "\n".join([
        "📋 <b>WEEKLY INTELLIGENCE SYNTHESIS</b>",
        "─────────────────",
        f"Signals reviewed: {signal_count}",
        f"Top sectors: {sectors}",
        "",
        f"📝 {synthesis.get('insights', '')}",
        "",
        f"🌐 Emerging themes: {', '.join(themes[:3])}",
        f"👀 New watchlist: {', '.join(watchlist[:5])}",
        "─────────────────",
        "Strategy weights updated for next week.",
    ])

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML"
        })
