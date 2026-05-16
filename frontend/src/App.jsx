import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const score_color = (s) => s >= 80 ? "#4ade80" : s >= 65 ? "#fbbf24" : "#f87171";
const score_emoji = (s) => s >= 85 ? "🔴" : s >= 72 ? "🟡" : "⚪";
const cat_colors = {
  restructuring: { bg: "#1a1a3a", color: "#a78bfa" },
  acquisition: { bg: "#1a2a1a", color: "#4ade80" },
  partnership: { bg: "#0d2010", color: "#34d399" },
  earnings: { bg: "#1f1500", color: "#fbbf24" },
  insider: { bg: "#0a1f1f", color: "#22d3ee" },
  regulatory: { bg: "#1f0a0a", color: "#f87171" },
  macro_policy: { bg: "#1a1500", color: "#fb923c" },
  ai_tech: { bg: "#0d1a2a", color: "#60a5fa" },
  quantum: { bg: "#1a0a2a", color: "#c084fc" },
  distress: { bg: "#2a0a0a", color: "#ef4444" },
};

function usePoll(fn, ms = 30000) {
  useEffect(() => { fn(); const id = setInterval(fn, ms); return () => clearInterval(id); }, []);
}

function Tag({ cat }) {
  const c = cat_colors[cat] || { bg: "#1a1a1a", color: "#888" };
  return (
    <span style={{ background: c.bg, color: c.color, fontSize: 9, padding: "2px 8px", borderRadius: 4, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>
      {cat?.replace("_", " ")}
    </span>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ background: "#0f0f1a", border: "0.5px solid #1e1e35", borderRadius: 10, padding: "14px 16px" }}>
      <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || "#e2e8f0", marginBottom: 3 }}>{value}</div>
      <div style={{ fontSize: 10, color: "#555" }}>{sub}</div>
    </div>
  );
}

function SignalCard({ signal, active, onClick }) {
  const plays = signal.options_plays || [];
  const primary = plays.find(p => p.role === "primary");
  return (
    <div onClick={onClick} style={{
      padding: "14px 16px", borderBottom: "0.5px solid #0d0d1a", cursor: "pointer",
      background: active ? "#13132a" : "transparent",
      borderLeft: active ? "2px solid #a78bfa" : "2px solid transparent",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Tag cat={signal.event_category} />
          {signal.primary_ticker && (
            <span style={{ background: "#080810", border: "0.5px solid #2a2a4a", color: "#e2e8f0", fontSize: 10, padding: "2px 7px", borderRadius: 4, fontWeight: 700 }}>
              {signal.primary_ticker}
            </span>
          )}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: score_color(signal.score), flexShrink: 0 }}>
          {Math.round(signal.score)}
        </div>
      </div>
      <div style={{ fontSize: 12, color: "#e2e8f0", marginBottom: 5, lineHeight: 1.4 }}>{signal.headline?.slice(0, 100)}</div>
      <div style={{ fontSize: 10, color: "#555", marginBottom: primary ? 6 : 0 }}>
        {signal.sector} · {signal.created_at?.slice(5, 16)}
      </div>
      {primary && (
        <div style={{ fontSize: 10, color: "#4ade80", background: "#052e16", padding: "3px 8px", borderRadius: 4, display: "inline-block" }}>
          {primary.ticker} {primary.type?.toUpperCase()} · {primary.strike_note} · {primary.expiry_note}
        </div>
      )}
    </div>
  );
}

function SignalDetail({ signal }) {
  if (!signal) return (
    <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 12 }}>
      Select a signal to see full analysis
    </div>
  );

  const plays = signal.options_plays || [];
  const chain = signal.reasoning_chain || [];
  const ripples = signal.ripple_tickers || [];

  return (
    <div style={{ padding: 16, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
          <Tag cat={signal.event_category} />
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: score_color(signal.score) }}>{Math.round(signal.score)}</div>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 2 }}>SCORE / 100</div>
          </div>
        </div>
        <div style={{ fontSize: 14, fontWeight: 500, color: "#f1f5f9", lineHeight: 1.5, marginBottom: 6 }}>{signal.headline}</div>
        <div style={{ fontSize: 11, color: "#555" }}>{signal.sector} · {signal.created_at?.slice(0, 16)} UTC</div>
      </div>

      {chain.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 8 }}>REASONING CHAIN</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {chain.map((s, i) => (
              <div key={i} style={{ flex: 1, minWidth: 100, background: "#080810", borderRadius: 6, padding: "8px 10px" }}>
                <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 3 }}>{s.step?.toUpperCase()}</div>
                <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.4 }}>{s.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {plays.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 8 }}>OPTIONS PLAYS</div>
          {plays.map((play, i) => (
            <div key={i} style={{ background: "#080810", borderRadius: 8, padding: 12, marginBottom: 8, border: play.role === "primary" ? "0.5px solid #1a3a1a" : "0.5px solid #1a1a1a" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div>
                  <span style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginRight: 6 }}>{play.role?.toUpperCase()}</span>
                  <span style={{ fontSize: 16, fontWeight: 700, color: "#f1f5f9" }}>{play.ticker}</span>
                </div>
                <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 4, fontWeight: 700, background: play.type === "call" ? "#052e16" : "#2d0a0a", color: play.type === "call" ? "#4ade80" : "#f87171" }}>
                  {play.type?.toUpperCase()}
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                {[["STRIKE", play.strike_note], ["EXPIRY", play.expiry_note], ["DAYS OUT", play.days_out]].map(([k, v]) => (
                  <div key={k} style={{ background: "#0a0a12", borderRadius: 6, padding: "6px 8px" }}>
                    <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 2 }}>{k}</div>
                    <div style={{ fontSize: 11, color: "#e2e8f0" }}>{v || "—"}</div>
                  </div>
                ))}
              </div>
              {play.reasoning && (
                <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginTop: 6 }}>
                  <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 4 }}>WHY</div>
                  <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.6 }}>{play.reasoning}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 14 }}>
        {[
          ["ACT BY", `${signal.act_by_hours}h`],
          ["CATALYST", signal.catalyst_date || "TBD"],
          ["IV ENV", signal.iv_environment?.toUpperCase()],
          ["RISK", signal.risk_level?.toUpperCase()],
        ].map(([k, v]) => (
          <div key={k} style={{ background: "#080810", borderRadius: 6, padding: "8px 10px" }}>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 2 }}>{k}</div>
            <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 500 }}>{v || "—"}</div>
          </div>
        ))}
      </div>

      {ripples.length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 6 }}>ALSO WATCH</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {ripples.slice(0, 6).map((t, i) => (
              <span key={i} style={{ background: "#0f0f1a", border: "0.5px solid #1e1e35", borderRadius: 6, padding: "3px 10px", fontSize: 11, color: "#888" }}>{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [stats, setStats] = useState(null);
  const [signals, setSignals] = useState([]);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [st, sg] = await Promise.all([
        fetch(`${API}/api/stats`).then(r => r.json()),
        fetch(`${API}/api/signals?limit=50`).then(r => r.json()),
      ]);
      setStats(st);
      setSignals(Array.isArray(sg) ? sg : []);
      setLastUpdate(new Date());
      setLoading(false);
    } catch (e) { console.error(e); }
  }, []);

  usePoll(fetchAll, 30000);

  const filtered = signals.filter(s => {
    if (filter === "all") return true;
    if (filter === "high") return s.score >= 80;
    return s.event_category === filter;
  });

  const categories = [...new Set(signals.map(s => s.event_category).filter(Boolean))];

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#080810", color: "#fff", fontFamily: "'IBM Plex Mono', monospace" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 11, color: "#a78bfa", letterSpacing: 5, marginBottom: 6 }}>MARKET INTELLIGENCE</div>
        <div style={{ fontSize: 11, color: "#555" }}>connecting to scanner...</div>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#080810", color: "#e2e8f0", fontFamily: "'IBM Plex Mono', monospace", display: "flex", flexDirection: "column" }}>

      {/* Header */}
      <div style={{ padding: "20px 24px 16px", borderBottom: "0.5px solid #1e1e35", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 9, color: "#a78bfa", letterSpacing: 6, marginBottom: 4 }}>MARKET INTELLIGENCE</div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>Signal Dashboard</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end", marginBottom: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", animation: "pulse 2s infinite" }} />
            <div style={{ fontSize: 10, color: "#4ade80", letterSpacing: 2 }}>SCANNING LIVE</div>
          </div>
          <div style={{ fontSize: 10, color: "#555" }}>{lastUpdate?.toLocaleTimeString()}</div>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, padding: "16px 24px" }}>
        <StatCard label="SIGNALS TODAY" value={stats?.signals_today ?? 0} sub="generated" color="#a78bfa" />
        <StatCard label="HIGH CONVICTION" value={stats?.high_conviction ?? 0} sub="score ≥ 80" color="#4ade80" />
        <StatCard label="EVENTS SCANNED" value={(stats?.events_scanned ?? 0).toLocaleString()} sub="all sources" color="#60a5fa" />
        <StatCard label="AVG SCORE" value={stats?.avg_score_today ?? 0} sub="today" color="#fbbf24" />
        <StatCard label="TOP SECTOR" value={stats?.top_sector ?? "—"} sub="this week" color="#22d3ee" />
      </div>

      {/* Filter bar */}
      <div style={{ padding: "0 24px 12px", display: "flex", gap: 6, flexWrap: "wrap" }}>
        {["all", "high", ...categories].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "4px 12px", fontSize: 9, letterSpacing: 2, fontFamily: "inherit",
            background: filter === f ? "#1e1e35" : "transparent",
            color: filter === f ? "#a78bfa" : "#555",
            border: `0.5px solid ${filter === f ? "#a78bfa" : "#1e1e35"}`,
            borderRadius: 20, cursor: "pointer", textTransform: "uppercase",
          }}>
            {f === "high" ? "HIGH CONVICTION" : f}
          </button>
        ))}
      </div>

      {/* Main two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 0, flex: 1, overflow: "hidden", margin: "0 24px 24px", border: "0.5px solid #1e1e35", borderRadius: 10 }}>

        {/* Signal list */}
        <div style={{ borderRight: "0.5px solid #1e1e35", overflowY: "auto" }}>
          <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #1e1e35", display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 9, color: "#555", letterSpacing: 3 }}>SIGNALS ({filtered.length})</span>
            <span style={{ fontSize: 9, color: "#555" }}>refreshes every 30s</span>
          </div>
          {filtered.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 11 }}>
              No signals yet — scanner running...
            </div>
          ) : filtered.map(s => (
            <SignalCard
              key={s.id}
              signal={s}
              active={selected?.id === s.id}
              onClick={() => setSelected(s)}
            />
          ))}
        </div>

        {/* Signal detail */}
        <div style={{ background: "#0a0a12", overflowY: "auto" }}>
          <SignalDetail signal={selected} />
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #080810; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #080810; }
        ::-webkit-scrollbar-thumb { background: #1e1e35; border-radius: 2px; }
      `}</style>
    </div>
  );
}