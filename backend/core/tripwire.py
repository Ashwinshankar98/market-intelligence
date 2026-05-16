import re

# ── High-signal keyword patterns ─────────────────────────────────────────────
# Each entry: (pattern, event_category, base_score_boost)
TRIPWIRES = [
    # Corporate restructuring
    (r"\blayoff[s]?\b|\blay.off[s]?\b|\brestructur\w+\b|\bdownsiz\w+\b|\bworkforce.reduc\w+\b|\bjob.cut[s]?\b", "restructuring", 15),
    # M&A
    (r"\bacquisition\b|\bacquir\w+\b|\bmerger\b|\btakeover\b|\bbuyout\b|\blbo\b|\bprivate.equity\b", "acquisition", 20),
    # Partnerships
    (r"\bpartnership\b|\bjoint.venture\b|\bcollabor\w+\b|\bstrategic.alliance\b|\bdeal.sign\w+\b|\bcontract.award\w+\b", "partnership", 12),
    # Earnings
    (r"\bearnings.beat\b|\bearnings.miss\b|\brevenue.beat\b|\beps.beat\b|\bguidance.rais\w+\b|\bguidance.lower\w+\b", "earnings", 18),
    # Insider activity
    (r"\binsider.buy\w+\b|\bform.4\b|\bsec.filing\b|\bceo.purchas\w+\b|\bcfo.purchas\w+\b|\bexecutive.buy\w+\b", "insider", 22),
    # Regulatory
    (r"\bantitrust\b|\bdoj.investi\w+\b|\bfda.approv\w+\b|\bfda.reject\w+\b|\bfine[s]?\b|\bpenalty\b|\bregulat\w+.action\b", "regulatory", 16),
    # AI / Tech deals
    (r"\bai.infrastructure\b|\bgpu.order[s]?\b|\bdata.center.deal\b|\bcloud.contract\b|\bai.partnership\b|\bchip.supply\b", "ai_tech", 18),
    # Macro / Policy
    (r"\bchips.act\b|\bsubsidy\b|\btariff[s]?\b|\bexport.restrict\w+\b|\btrade.ban\b|\bsanction[s]?\b", "macro_policy", 14),
    # Bankruptcy / distress
    (r"\bchapter.11\b|\bbankruptcy\b|\bdefault\b|\bdebt.restructur\w+\b|\bliquidat\w+\b", "distress", 25),
    # Quantum / emerging tech
    (r"\bquantum.computing\b|\bquantum.breakthrough\b|\bqubit[s]?\b|\bquantum.advantage\b", "quantum", 15),
]

# Tickers to always watch
WATCHLIST = [
    "NVDA","AMD","INTC","TSMC","ASML","AMAT","KLAC","LRCX",  # Semis
    "META","GOOG","MSFT","AMZN","AAPL","NFLX",               # Mega cap
    "IONQ","RGTI","QBTS","IBM","HONEYWELL",                   # Quantum
    "MU","WDC","STX","SK Hynix",                              # Memory
    "PLTR","BBAI","AI","SOUN",                                 # AI plays
    "SMCI","VRT","ANET","VST","CEG",                          # AI infra
    "SPY","QQQ","IWM","XLK","SOXX",                           # ETFs
]

TICKER_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in WATCHLIST) + r')\b',
    re.IGNORECASE
)

def run_tripwire(text: str) -> dict:
    """
    Tier 1 — zero cost keyword scan.
    Returns: { passed: bool, keywords: [], category: str, score_boost: int, tickers: [] }
    """
    text_lower = text.lower()
    matched_keywords = []
    category = None
    score_boost = 0

    for pattern, cat, boost in TRIPWIRES:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        if matches:
            matched_keywords.extend(matches)
            if boost > score_boost:
                score_boost = boost
                category = cat

    tickers = list(set(TICKER_PATTERN.findall(text)))

    # Must match at least one keyword to pass
    passed = len(matched_keywords) > 0

    # Bonus: if watchlist ticker is mentioned alongside keyword
    if tickers and passed:
        score_boost += 10

    return {
        "passed":   passed,
        "keywords": list(set(matched_keywords)),
        "category": category,
        "score_boost": min(score_boost, 35),  # cap the boost
        "tickers":  tickers,
    }
