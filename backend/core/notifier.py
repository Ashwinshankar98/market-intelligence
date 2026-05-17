import os
import httpx

async def send_signal_alert(signal: dict):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    score = signal.get("score", 0)
    score_emoji = "🔴" if score >= 85 else "🟡" if score >= 72 else "⚪"

    plays   = signal.get("options_plays", [])
    primary = next((p for p in plays if p.get("role") == "primary"), plays[0] if plays else None)
    ripples = [p for p in plays if p.get("role") != "primary"]

    portfolio_impact = signal.get("portfolio_impact", {})
    held_positions   = portfolio_impact.get("held_positions", [])
    corr_alerts      = portfolio_impact.get("correlation_alerts", [])
    hedge            = portfolio_impact.get("hedge_suggestion")
    corr_tickers     = signal.get("correlation_alert", [])

    lines = [
        f"{score_emoji} <b>SIGNAL — {score}/100</b>",
        f"<b>{signal.get('primary_ticker', '?')} · {signal.get('event_category', '').upper()}</b>",
        f"<i>{signal.get('headline', '')[:120]}</i>",
        f"Sector: {signal.get('sector', '?')} · Risk: {signal.get('risk_level', '?').upper()}",
        "",
        "─────────────────",
    ]

    # Portfolio impact section
    if held_positions:
        lines.append("📊 <b>Your positions</b>")
        for pos in held_positions[:3]:
            action = pos.get("action", "HOLD")
            emoji  = "➕" if action == "ADD" else "⏸" if action == "HOLD" else "➖"
            lines.append(f"  {emoji} {pos['ticker']}: {action} — {pos.get('rationale', '')[:80]}")
        lines.append("")

    if corr_alerts or corr_tickers:
        lines.append("🔗 <b>Correlation alerts</b>")
        for c in corr_alerts[:3]:
            impact_emoji = "📈" if c.get("impact") == "bullish" else "📉"
            lines.append(f"  {impact_emoji} {c['ticker']}: {c.get('note', '')[:80]}")
        if corr_tickers and not corr_alerts:
            lines.append(f"  Your {', '.join(corr_tickers)} positions are affected")
        lines.append("")

    if hedge:
        lines += [f"🛡 <b>Hedge suggestion</b>", f"  {str(hedge)[:120]}", ""]

    # Reasoning chain (condensed)
    chain = signal.get("reasoning_chain", [])
    if chain:
        lines.append("📊 <b>Reasoning</b>")
        for step in chain[:3]:
            lines.append(f"  {step.get('step')}: {step.get('text', '')[:80]}")
        lines.append("")

    # Primary options play
    if primary:
        lines += [
            "🎯 <b>Primary play</b>",
            f"  {primary['ticker']} {primary['type'].upper()} · {primary.get('strike_note', '')} · {primary.get('expiry_note', '')}",
            f"  Entry: {primary.get('entry_strategy', '')[:100]}",
            f"  Target: {primary.get('profit_target', '')[:80]}",
            f"  Stop: {primary.get('stop_loss', '')[:80]}",
            f"  Time stop: {primary.get('time_stop', '')[:60]}",
        ]
        if primary.get("iv_warning"):
            lines.append(f"  ⚠ IV: {primary['iv_warning'][:80]}")
        lines.append("")

    # Ripple plays (condensed)
    if ripples:
        lines.append("🔗 <b>Ripple plays</b>")
        for r in ripples[:2]:
            lines.append(f"  {r['ticker']} {r['type'].upper()} · {r.get('strike_note', '')} · {r.get('expiry_note', '')}")
        lines.append("")

    lines += [
        "─────────────────",
        f"⏰ Act within: <b>{signal.get('act_by_hours', '?')}h</b>",
        f"📅 Catalyst: {signal.get('catalyst_date', 'TBD')}",
    ]

    if signal.get("ripple_tickers"):
        lines.append(f"👀 Also watch: {', '.join(signal['ripple_tickers'][:4])}")

    message = "\n".join(lines)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})


async def send_weekly_summary(synthesis: dict, signal_count: int):
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
        await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})