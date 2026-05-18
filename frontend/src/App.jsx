import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const score_color = (s) => s >= 80 ? "#4ade80" : s >= 65 ? "#fbbf24" : "#f87171";
const rr_color = (s) => s >= 7 ? "#4ade80" : s >= 5 ? "#fbbf24" : "#f87171";

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
  hedge_fund: { bg: "#2a1a00", color: "#fb923c" },
  portfolio_move: { bg: "#1a0a2a", color: "#c084fc" },
  investment: { bg: "#0a2a1a", color: "#34d399" },
  space: { bg: "#0a0a2a", color: "#60a5fa" },
  optoelectronics: { bg: "#1a2a1a", color: "#4ade80" },
  rare_earth: { bg: "#2a1a0a", color: "#fb923c" },
};

const PRIORITY_SECTORS = new Set([
  "semiconductor", "memory", "ai_tech", "ai_infra", "optoelectronics",
  "quantum", "space", "rare_earth", "robotics", "ev_tech",
  "hedge_fund", "portfolio_move", "investment",
]);

function usePoll(fn, ms = 30000) {
  useEffect(() => { fn(); const id = setInterval(fn, ms); return () => clearInterval(id); }, [fn]);
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const h = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, []);
  return isMobile;
}

function Tag({ cat }) {
  const c = cat_colors[cat] || { bg: "#1a1a1a", color: "#888" };
  return (
    <span style={{ background: c.bg, color: c.color, fontSize: 9, padding: "2px 8px", borderRadius: 4, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase", whiteSpace: "nowrap" }}>
      {cat?.replace(/_/g, " ")}
    </span>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ background: "#0f0f1a", border: "0.5px solid #1e1e35", borderRadius: 10, padding: "12px 14px" }}>
      <div style={{ fontSize: 8, color: "#555", letterSpacing: 2, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || "#e2e8f0", marginBottom: 2, wordBreak: "break-word" }}>{value}</div>
      <div style={{ fontSize: 9, color: "#555" }}>{sub}</div>
    </div>
  );
}

function InfoBox({ label, children, color = "#555" }) {
  return (
    <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginBottom: 8 }}>
      <div style={{ fontSize: 9, color: color, letterSpacing: 2, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 11, color: "#e2e8f0", lineHeight: 1.7 }}>{children}</div>
    </div>
  );
}

function AskPlayBox({ play, signalContext }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const ask = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setAnswer("");
    try {
      const resp = await fetch(`${API}/api/ask-play`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ play, question, signal_context: signalContext }),
      });
      const data = await resp.json();
      setAnswer(data.answer || data.error || "No response");
    } catch (e) {
      setAnswer("Failed to connect");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "#0a0a1a", border: "0.5px solid #2a2a4a", borderRadius: 6, padding: "10px", marginTop: 8 }}>
      <div style={{ fontSize: 9, color: "#a78bfa", letterSpacing: 2, marginBottom: 8 }}>ASK CLAUDE ABOUT THIS PLAY</div>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === "Enter" && ask()}
          placeholder="e.g. What happens if earnings disappoint?"
          style={{ flex: 1, background: "#080810", border: "0.5px solid #2a2a4a", borderRadius: 6, color: "#e2e8f0", fontSize: 11, padding: "6px 10px", fontFamily: "inherit", outline: "none" }}
        />
        <button onClick={ask} disabled={loading || !question.trim()} style={{
          background: "#1e1e35", border: "0.5px solid #a78bfa", color: loading ? "#555" : "#a78bfa",
          borderRadius: 6, padding: "6px 14px", fontSize: 10, fontFamily: "inherit",
          cursor: loading ? "not-allowed" : "pointer", letterSpacing: 1, whiteSpace: "nowrap",
        }}>
          {loading ? "..." : "ASK →"}
        </button>
      </div>
      {answer && (
        <div style={{ marginTop: 8, padding: "8px 10px", background: "#080810", borderRadius: 6, fontSize: 11, color: "#aaa", lineHeight: 1.7 }}>
          {answer}
        </div>
      )}
    </div>
  );
}

function OptionsPlay({ play, signalContext }) {
  const [showAsk, setShowAsk] = useState(false);
  const rr = play.risk_reward_score;

  return (
    <div style={{ background: "#080810", borderRadius: 8, padding: 14, marginBottom: 10, border: play.role === "primary" ? "0.5px solid #1a3a1a" : "0.5px solid #1a1a1a" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10, flexWrap: "wrap", gap: 6 }}>
        <div>
          <span style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginRight: 8 }}>{play.role?.toUpperCase()}</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9" }}>{play.ticker}</span>
          {play.current_price && <span style={{ fontSize: 11, color: "#555", marginLeft: 8 }}>@ ${play.current_price}</span>}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {rr && (
            <div style={{ background: "#0a0a12", borderRadius: 6, padding: "4px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 8, color: "#555", letterSpacing: 1 }}>R/R</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: rr_color(rr) }}>{rr}/10</div>
            </div>
          )}
          {play.confidence && (
            <div style={{ background: "#0a0a12", borderRadius: 6, padding: "4px 10px", textAlign: "center" }}>
              <div style={{ fontSize: 8, color: "#555", letterSpacing: 1 }}>CONF</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: score_color(play.confidence) }}>{play.confidence}%</div>
            </div>
          )}
          <span style={{ fontSize: 11, padding: "4px 10px", borderRadius: 4, fontWeight: 700, background: play.type === "call" ? "#052e16" : "#2d0a0a", color: play.type === "call" ? "#4ade80" : "#f87171" }}>
            {play.type?.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Strike / Expiry / Days */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 8 }}>
        {[["STRIKE", play.strike_note], ["EXPIRY", play.expiry_note], ["DAYS OUT", play.days_out]].map(([k, v]) => (
          <div key={k} style={{ background: "#0a0a12", borderRadius: 6, padding: "6px 8px" }}>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 2 }}>{k}</div>
            <div style={{ fontSize: 11, color: "#e2e8f0" }}>{v || "—"}</div>
          </div>
        ))}
      </div>

      {/* Max loss */}
      {play.max_loss_pct && (
        <div style={{ background: "#1a0a0a", borderRadius: 6, padding: "6px 10px", marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontSize: 10, color: "#f87171" }}>MAX LOSS IF WRONG</span>
          <span style={{ fontSize: 11, color: "#f87171", fontWeight: 700 }}>{play.max_loss_pct}% of premium</span>
        </div>
      )}

      {play.reasoning && <InfoBox label="WHY">{play.reasoning}</InfoBox>}
      {play.entry_strategy && <InfoBox label="🎯 ENTRY" color="#4ade80">{play.entry_strategy}</InfoBox>}
      {play.profit_target && <InfoBox label="💰 PROFIT TARGET" color="#4ade80">{play.profit_target}</InfoBox>}
      {play.stop_loss && <InfoBox label="🛑 STOP LOSS" color="#f87171">{play.stop_loss}</InfoBox>}
      {play.time_stop && <InfoBox label="⏰ TIME STOP" color="#fbbf24">{play.time_stop}</InfoBox>}
      {play.iv_warning && (
        <div style={{ background: "#1a1200", border: "0.5px solid #3a2a00", borderRadius: 6, padding: "8px 10px", marginBottom: 8 }}>
          <div style={{ fontSize: 9, color: "#fbbf24", letterSpacing: 2, marginBottom: 3 }}>⚠ IV WARNING</div>
          <div style={{ fontSize: 11, color: "#fbbf24", lineHeight: 1.6 }}>{play.iv_warning}</div>
        </div>
      )}

      {/* Ask Claude toggle */}
      <button onClick={() => setShowAsk(v => !v)} style={{
        background: "transparent", border: "0.5px solid #2a2a4a", color: "#a78bfa",
        borderRadius: 6, padding: "5px 12px", fontSize: 10, fontFamily: "inherit",
        cursor: "pointer", letterSpacing: 1, width: "100%", marginTop: 4,
      }}>
        {showAsk ? "▲ HIDE Q&A" : "💬 ASK CLAUDE ABOUT THIS PLAY"}
      </button>
      {showAsk && <AskPlayBox play={play} signalContext={signalContext} />}
    </div>
  );
}

function SignalDetail({ signal, onBack, isMobile }) {
  if (!signal) return (
    <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 12 }}>
      <div style={{ marginBottom: 8 }}>Select a signal to see full analysis</div>
      <div style={{ fontSize: 10, color: "#333" }}>or use the search bar to look up any ticker</div>
    </div>
  );

  const plays = signal.options_plays || [];
  const chain = signal.reasoning_chain || [];
  const ripples = signal.ripple_tickers || [];

  // Portfolio impact
  let portfolioImpact = signal.portfolio_impact || {};
  if (typeof portfolioImpact === "string") {
    try { portfolioImpact = JSON.parse(portfolioImpact); } catch (e) { portfolioImpact = {}; }
  }
  const heldPositions = portfolioImpact.held_positions || [];
  const corrAlerts = portfolioImpact.correlation_alerts || [];
  const hedgeSuggestion = portfolioImpact.hedge_suggestion;
  const corrTickers = signal.correlation_alert || [];

  const buyHoldSell = signal.buy_hold_sell || null;

  const signalContext = {
    primary_ticker: signal.primary_ticker,
    headline: signal.headline,
    score: signal.score,
    sector: signal.sector,
  };

  return (
    <div style={{ padding: 16, overflowY: "auto", height: "100%" }}>
      {isMobile && (
        <button onClick={onBack} style={{ background: "#1e1e35", border: "0.5px solid #a78bfa", color: "#a78bfa", borderRadius: 6, padding: "6px 14px", fontSize: 10, fontFamily: "inherit", cursor: "pointer", marginBottom: 14, letterSpacing: 2 }}>
          ← BACK
        </button>
      )}

      {/* Header */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {signal.is_manual_lookup && <span style={{ background: "#1f1500", color: "#fbbf24", fontSize: 9, padding: "2px 8px", borderRadius: 4, fontWeight: 700 }}>MANUAL LOOKUP</span>}
            <Tag cat={signal.event_category} />
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: score_color(signal.score || 0) }}>{Math.round(signal.score || 0)}</div>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 2 }}>SCORE / 100</div>
          </div>
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "#f1f5f9", lineHeight: 1.6, marginBottom: 6 }}>{signal.headline || signal.summary_one_line}</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, color: "#555" }}>{signal.sector}</span>
          {signal.current_price && <span style={{ fontSize: 11, color: "#4ade80" }}>Current: ${signal.current_price}</span>}
          <span style={{ fontSize: 11, color: "#555" }}>{signal.created_at?.slice(0, 16)} UTC</span>
        </div>
      </div>

      {/* Buy / Hold / Sell */}
      {buyHoldSell && (
        <div style={{ marginBottom: 14, background: "#080810", borderRadius: 8, padding: 12, border: "0.5px solid #1e1e35" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 3 }}>ANALYST CONSENSUS + CLAUDE VIEW</div>
            <span style={{
              fontSize: 13, fontWeight: 700, padding: "3px 12px", borderRadius: 4,
              background: buyHoldSell.recommendation === "BUY" ? "#052e16" : buyHoldSell.recommendation === "SELL" ? "#2d0a0a" : "#1a1500",
              color: buyHoldSell.recommendation === "BUY" ? "#4ade80" : buyHoldSell.recommendation === "SELL" ? "#f87171" : "#fbbf24"
            }}>
              {buyHoldSell.recommendation}
            </span>
          </div>
          {buyHoldSell.analyst_facts && (
            <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginBottom: 8 }}>
              <div style={{ fontSize: 9, color: "#60a5fa", letterSpacing: 2, marginBottom: 4 }}>📰 ANALYST FACTS & NEWS</div>
              <div style={{ fontSize: 11, color: "#e2e8f0", lineHeight: 1.7 }}>{buyHoldSell.analyst_facts}</div>
            </div>
          )}
          {buyHoldSell.claude_opinion && (
            <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px" }}>
              <div style={{ fontSize: 9, color: "#a78bfa", letterSpacing: 2, marginBottom: 4 }}>🤖 CLAUDE'S OPINION</div>
              <div style={{ fontSize: 11, color: "#e2e8f0", lineHeight: 1.7 }}>{buyHoldSell.claude_opinion}</div>
            </div>
          )}
        </div>
      )}

      {/* Portfolio impact — held positions */}
      {(heldPositions.length > 0 || corrAlerts.length > 0 || corrTickers.length > 0) && (
        <div style={{ marginBottom: 14, background: "#080810", borderRadius: 8, padding: 12, border: "0.5px solid #1a2a1a" }}>
          <div style={{ fontSize: 9, color: "#4ade80", letterSpacing: 3, marginBottom: 10 }}>YOUR PORTFOLIO IMPACT</div>

          {heldPositions.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 6 }}>HELD POSITIONS</div>
              {heldPositions.map((pos, i) => (
                <div key={i} style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#f1f5f9" }}>{pos.ticker}</span>
                    <span style={{
                      fontSize: 10, padding: "2px 8px", borderRadius: 4, fontWeight: 700,
                      background: pos.action === "ADD" ? "#052e16" : pos.action === "REDUCE" ? "#2d0a0a" : "#1a1500",
                      color: pos.action === "ADD" ? "#4ade80" : pos.action === "REDUCE" ? "#f87171" : "#fbbf24"
                    }}>{pos.action}</span>
                  </div>
                  {pos.analyst_facts && <div style={{ fontSize: 11, color: "#60a5fa", lineHeight: 1.6, marginBottom: 4 }}>📰 {pos.analyst_facts}</div>}
                  {(pos.claude_rationale || pos.rationale) && <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.6 }}>🤖 {pos.claude_rationale || pos.rationale}</div>}
                  {pos.current_equity && <div style={{ fontSize: 10, color: "#555", marginTop: 4 }}>Current equity: ${pos.current_equity?.toLocaleString()}</div>}
                </div>
              ))}
            </div>
          )}

          {(corrAlerts.length > 0 || corrTickers.length > 0) && (
            <div>
              <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 6 }}>CORRELATION ALERTS</div>
              {corrAlerts.map((c, i) => (
                <div key={i} style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#f1f5f9" }}>{c.ticker}</span>
                    <span style={{ fontSize: 10, color: c.impact === "bullish" ? "#4ade80" : "#f87171" }}>
                      {c.impact === "bullish" ? "📈" : "📉"} {c.impact?.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.6 }}>{c.note}</div>
                </div>
              ))}
              {corrTickers.length > 0 && corrAlerts.length === 0 && (
                <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ fontSize: 11, color: "#aaa" }}>Your {corrTickers.join(", ")} positions are affected by this news</div>
                </div>
              )}
            </div>
          )}

          {hedgeSuggestion && (
            <div style={{ background: "#0a0a12", borderRadius: 6, padding: "8px 10px", marginTop: 8, border: "0.5px solid #2a1a00" }}>
              <div style={{ fontSize: 9, color: "#fbbf24", letterSpacing: 2, marginBottom: 4 }}>🛡 HEDGE SUGGESTION</div>
              <div style={{ fontSize: 11, color: "#fbbf24", lineHeight: 1.6 }}>{hedgeSuggestion}</div>
            </div>
          )}
        </div>
      )}

      {/* Reasoning chain — NO truncation */}
      {chain.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 8 }}>REASONING CHAIN</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {chain.map((s, i) => (
              <div key={i} style={{ background: "#080810", borderRadius: 6, padding: "8px 10px" }}>
                <div style={{ fontSize: 9, color: "#a78bfa", letterSpacing: 2, marginBottom: 4 }}>{s.step?.toUpperCase()}</div>
                <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.6 }}>{s.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Options plays */}
      {plays.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 8 }}>OPTIONS PLAYS</div>
          {plays.map((play, i) => <OptionsPlay key={i} play={play} signalContext={signalContext} />)}
        </div>
      )}

      {/* Meta */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 14 }}>
        {[["ACT BY", `${signal.act_by_hours}h`], ["CATALYST", signal.catalyst_date || "TBD"], ["IV ENV", signal.iv_environment?.toUpperCase()], ["RISK", signal.risk_level?.toUpperCase()]].map(([k, v]) => (
          <div key={k} style={{ background: "#080810", borderRadius: 6, padding: "8px 10px" }}>
            <div style={{ fontSize: 9, color: "#555", letterSpacing: 2, marginBottom: 2 }}>{k}</div>
            <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 500 }}>{v || "—"}</div>
          </div>
        ))}
      </div>

      {/* Also watch */}
      {ripples.length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 6 }}>ALSO WATCH</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {ripples.slice(0, 8).map((t, i) => (
              <span key={i} style={{ background: "#0f0f1a", border: "0.5px solid #1e1e35", borderRadius: 6, padding: "3px 10px", fontSize: 11, color: "#888" }}>{t}</span>
            ))}
          </div>
        </div>
      )}

      {/* News used */}
      {signal.news_used?.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: 3, marginBottom: 6 }}>NEWS USED IN ANALYSIS</div>
          {signal.news_used.map((n, i) => <div key={i} style={{ fontSize: 10, color: "#444", marginBottom: 2 }}>· {n}</div>)}
        </div>
      )}
    </div>
  );
}

function SearchBar({ onResult }) {
  const [ticker, setTicker] = useState("");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");

  const STEPS = ["Fetching latest news...", "Getting current prices...", "Sending to Claude...", "Building options plays...", "Almost done..."];

  const handleSearch = async () => {
    if (!ticker.trim()) return;
    setLoading(true); setError(""); setStep(0);
    const iv = setInterval(() => setStep(p => p < STEPS.length - 1 ? p + 1 : p), 5000);
    try {
      const resp = await fetch(`${API}/api/lookup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: ticker.toUpperCase().trim(), company: ticker.trim(), context: context.trim() }),
      });
      const data = await resp.json();
      if (data.error) setError(data.error);
      else onResult(data);
    } catch (e) {
      setError("Failed to connect");
    } finally {
      clearInterval(iv); setLoading(false); setStep(0);
    }
  };

  return (
    <div style={{ padding: "12px 16px", borderBottom: "0.5px solid #1e1e35", background: "#0a0a12" }}>
      <div style={{ fontSize: 9, color: "#fbbf24", letterSpacing: 3, marginBottom: 8 }}>MANUAL TICKER LOOKUP</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input value={ticker} onChange={e => setTicker(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Ticker (e.g. META)"
            style={{ background: "#080810", border: "0.5px solid #2a2a4a", borderRadius: 6, color: "#e2e8f0", fontSize: 12, padding: "8px 12px", fontFamily: "inherit", width: "35%", outline: "none" }} />
          <input value={context} onChange={e => setContext(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Context (e.g. recent layoffs)"
            style={{ background: "#080810", border: "0.5px solid #2a2a4a", borderRadius: 6, color: "#e2e8f0", fontSize: 12, padding: "8px 12px", fontFamily: "inherit", flex: 1, outline: "none" }} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={handleSearch} disabled={loading || !ticker.trim()} style={{ background: loading ? "#1a1a2a" : "#1e1e35", border: "0.5px solid #a78bfa", color: loading ? "#555" : "#a78bfa", borderRadius: 6, padding: "8px 20px", fontSize: 11, letterSpacing: 2, fontFamily: "inherit", cursor: loading ? "not-allowed" : "pointer", fontWeight: 700 }}>
            {loading ? "ANALYSING..." : "ANALYSE →"}
          </button>
          {error && <div style={{ fontSize: 11, color: "#f87171" }}>{error}</div>}
        </div>
        {loading && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#a78bfa", animation: "pulse 1s infinite" }} />
              <div style={{ fontSize: 11, color: "#a78bfa" }}>{STEPS[step]}</div>
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              {STEPS.map((_, i) => <div key={i} style={{ height: 2, flex: 1, borderRadius: 1, background: i <= step ? "#a78bfa" : "#1e1e35", transition: "background 0.5s" }} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SignalCard({ signal, active, onClick }) {
  const plays = signal.options_plays || [];
  const primary = plays.find(p => p.role === "primary") || plays[0];
  return (
    <div onClick={onClick} style={{ padding: "14px 16px", borderBottom: "0.5px solid #0d0d1a", cursor: "pointer", background: active ? "#13132a" : "transparent", borderLeft: active ? `2px solid ${signal.is_manual_lookup ? "#fbbf24" : "#a78bfa"}` : "2px solid transparent" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", flex: 1, marginRight: 8 }}>
          {signal.is_manual_lookup && <span style={{ background: "#1f1500", color: "#fbbf24", fontSize: 9, padding: "2px 8px", borderRadius: 4, fontWeight: 700 }}>LOOKUP</span>}
          <Tag cat={signal.event_category} />
          {signal.primary_ticker && <span style={{ background: "#080810", border: "0.5px solid #2a2a4a", color: "#e2e8f0", fontSize: 10, padding: "2px 7px", borderRadius: 4, fontWeight: 700 }}>{signal.primary_ticker}</span>}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: score_color(signal.score || 0), flexShrink: 0 }}>{Math.round(signal.score || 0)}</div>
      </div>
      <div style={{ fontSize: 12, color: "#e2e8f0", marginBottom: 5, lineHeight: 1.4 }}>{(signal.headline || signal.summary_one_line)?.slice(0, 100)}</div>
      <div style={{ fontSize: 10, color: "#555", marginBottom: primary ? 6 : 0 }}>{signal.sector} · {signal.created_at?.slice(5, 16)}</div>
      {primary && (
        <div style={{ fontSize: 10, color: "#4ade80", background: "#052e16", padding: "3px 8px", borderRadius: 4, display: "inline-block" }}>
          {primary.ticker} {primary.type?.toUpperCase()} · {primary.strike_note?.split("(")[0].trim()}
          {primary.risk_reward_score && <span style={{ color: rr_color(primary.risk_reward_score), marginLeft: 6 }}>R/R {primary.risk_reward_score}/10</span>}
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
  const [timeRange, setTimeRange] = useState("7d");
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [lookupResults, setLookupResults] = useState([]);
  const isMobile = useIsMobile();

  const fetchAll = useCallback(async () => {
    try {
      const days = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 365;
      const [st, sg] = await Promise.all([
        fetch(`${API}/api/stats`).then(r => r.json()),
        fetch(`${API}/api/signals?limit=200&days=${days}`).then(r => r.json()),
      ]);
      setStats(st);
      setSignals(Array.isArray(sg) ? sg : []);
      setLastUpdate(new Date());
      setLoading(false);
    } catch (e) { console.error(e); }
  }, [timeRange]);

  usePoll(fetchAll, 30000);

  const handleLookupResult = (result) => {
    const enriched = { ...result, id: `lookup-${Date.now()}`, created_at: new Date().toISOString(), headline: result.summary_one_line || `${result.primary_ticker} analysis` };
    setLookupResults(prev => [enriched, ...prev]);
    setSelected(enriched);
  };

  const allSignals = [...lookupResults, ...signals];
  const filtered = allSignals.filter(s => {
    if (filter === "all") return true;
    if (filter === "high") return s.score >= 80;
    if (filter === "portfolio") return PRIORITY_SECTORS.has(s.sector) || s.score >= 90 || s.is_manual_lookup;
    if (filter === "lookup") return s.is_manual_lookup;
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
      <div style={{ padding: "16px 16px 12px", borderBottom: "0.5px solid #1e1e35", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 8, color: "#a78bfa", letterSpacing: 4, marginBottom: 3 }}>MARKET INTELLIGENCE</div>
          <div style={{ fontSize: isMobile ? 18 : 22, fontWeight: 700 }}>Signal Dashboard</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end", marginBottom: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", animation: "pulse 2s infinite" }} />
            <div style={{ fontSize: 9, color: "#4ade80", letterSpacing: 2 }}>LIVE</div>
          </div>
          <div style={{ fontSize: 9, color: "#555", marginBottom: 6 }}>{lastUpdate?.toLocaleTimeString()}</div>
          <div style={{ display: "flex", gap: 4 }}>
            {["7d", "30d", "all"].map(t => (
              <button key={t} onClick={() => setTimeRange(t)} style={{ padding: "3px 8px", fontSize: 9, letterSpacing: 1, fontFamily: "inherit", background: timeRange === t ? "#1e1e35" : "transparent", color: timeRange === t ? "#4ade80" : "#555", border: `0.5px solid ${timeRange === t ? "#4ade80" : "#1e1e35"}`, borderRadius: 4, cursor: "pointer", textTransform: "uppercase" }}>{t}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "repeat(2,1fr)" : "repeat(5,1fr)", gap: 8, padding: "12px 16px" }}>
        <StatCard label="SIGNALS TODAY" value={stats?.signals_today ?? 0} sub="generated" color="#a78bfa" />
        <StatCard label="HIGH CONVICTION" value={stats?.high_conviction ?? 0} sub="score ≥ 80" color="#4ade80" />
        <StatCard label="EVENTS SCANNED" value={(stats?.events_scanned ?? 0).toLocaleString()} sub="all sources" color="#60a5fa" />
        <StatCard label="AVG SCORE" value={stats?.avg_score_today ?? 0} sub="today" color="#fbbf24" />
        <StatCard label="TOP SECTOR" value={stats?.top_sector ?? "—"} sub="this week" color="#22d3ee" />
      </div>

      <SearchBar onResult={handleLookupResult} />

      {/* Filters */}
      <div style={{ padding: "10px 16px", display: "flex", gap: 6, flexWrap: "wrap", overflowX: "auto" }}>
        {["all", "high", "portfolio", "lookup", ...categories].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{ padding: "4px 10px", fontSize: 9, letterSpacing: 1, fontFamily: "inherit", background: filter === f ? "#1e1e35" : "transparent", color: filter === f ? (f === "lookup" ? "#fbbf24" : f === "portfolio" ? "#4ade80" : "#a78bfa") : "#555", border: `0.5px solid ${filter === f ? (f === "lookup" ? "#fbbf24" : f === "portfolio" ? "#4ade80" : "#a78bfa") : "#1e1e35"}`, borderRadius: 20, cursor: "pointer", textTransform: "uppercase", whiteSpace: "nowrap" }}>
            {f === "high" ? "HIGH CONVICTION" : f === "lookup" ? `LOOKUPS (${lookupResults.length})` : f === "portfolio" ? "MY SECTORS" : f}
          </button>
        ))}
      </div>

      {/* Main layout */}
      {isMobile ? (
        <div style={{ flex: 1, overflow: "hidden", margin: "0 16px 16px", border: "0.5px solid #1e1e35", borderRadius: 10 }}>
          {selected ? (
            <div style={{ height: "100%", overflowY: "auto", background: "#0a0a12" }}>
              <SignalDetail signal={selected} onBack={() => setSelected(null)} isMobile={true} />
            </div>
          ) : (
            <div style={{ height: "100%", overflowY: "auto" }}>
              <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #1e1e35" }}>
                <span style={{ fontSize: 9, color: "#555", letterSpacing: 3 }}>SIGNALS ({filtered.length}) — tap to expand</span>
              </div>
              {filtered.length === 0 ? <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 11 }}>No signals yet</div>
                : filtered.map(s => <SignalCard key={s.id} signal={s} active={false} onClick={() => setSelected(s)} />)}
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 0, flex: 1, overflow: "hidden", margin: "0 16px 16px", border: "0.5px solid #1e1e35", borderRadius: 10 }}>
          <div style={{ borderRight: "0.5px solid #1e1e35", overflowY: "auto" }}>
            <div style={{ padding: "10px 16px", borderBottom: "0.5px solid #1e1e35", display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: 9, color: "#555", letterSpacing: 3 }}>SIGNALS ({filtered.length})</span>
              <span style={{ fontSize: 9, color: "#555" }}>refreshes 30s</span>
            </div>
            {filtered.length === 0 ? <div style={{ padding: 32, textAlign: "center", color: "#555", fontSize: 11 }}>No signals yet — scanner running...</div>
              : filtered.map(s => <SignalCard key={s.id} signal={s} active={selected?.id === s.id} onClick={() => setSelected(s)} />)}
          </div>
          <div style={{ background: "#0a0a12", overflowY: "auto" }}>
            <SignalDetail signal={selected} isMobile={false} />
          </div>
        </div>
      )}

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #080810; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #080810; }
        ::-webkit-scrollbar-thumb { background: #1e1e35; border-radius: 2px; }
        input::placeholder { color: #333; }
        input:focus { border-color: #a78bfa !important; }
      `}</style>
    </div>
  );
}