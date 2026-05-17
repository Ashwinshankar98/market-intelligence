import re
from core.portfolio import HOLDINGS

# ── Tickers that ALWAYS pass Tier 1 regardless of category ───────────────────
# These are your holdings + close sector peers
ALWAYS_WATCH = set([
    # Your holdings
    "META","NVDA","GOOGL","NBIS","SNDK","WDC","NFLX","SOFI","POET","MRAM",
    "MU","AMZN","TSLA","PLTR","XOM","MSFT","IREN","HOOD","APLD","AMD",
    "AAPL","CRWV","GLW","LUMN","KLAR","CRCL","RDDT","UNH","INFQ","PFE",
    "IONQ","ARKX","RKLB","AVGO","UBER","DUOL","NKE","SNOW","QUBT","SMCI",
    "XPEV","RIOT","ROOT","NVEC","BABA","AMKR","KLIC","TEM","KEEL","WBD",
    "ONDS","QBTS","BIDU","BTBT","MP","TER","TMQ","USAR","CUPR","RR","FIG",
    "DRAM","MRAM",
    # Close sector peers worth watching
    "TSMC","ASML","AMAT","KLAC","LRCX","ARM","QCOM","MRVL","NXPI","ON",
    "STX","SK","HYNIX","ASTS","SPCE","LMT","RTX","NOC","BA","PANW","CRWD",
    "NET","ZS","INTC","IBM","HONEYWELL","WOLF","STM","CDNS","SNPS",
    # ETFs you hold
    "VOO","VGT","SPY","QQQ","SMH","EWY","VYM","SCHD","IBIT",
])

# ── Categories that ALWAYS pass Tier 1 regardless of ticker ──────────────────
# These are sector-wide signals worth knowing about even for unknown companies
ALWAYS_PASS_CATEGORIES = {
    "hedge_fund",       # Any famous investor move
    "portfolio_move",   # Any fund buying/selling
    "quantum",          # Any quantum breakthrough
    "optoelectronics",  # Your POET/GLW sector
    "space",            # Your RKLB sector
    "rare_earth",       # Your MP/USAR sector
    "investment",       # Strategic investments
    "distress",         # Bankruptcies (always market-moving)
}

# ── High-signal keyword patterns ─────────────────────────────────────────────
# (pattern, category, base_score_boost, requires_watchlist_ticker)
# requires_watchlist_ticker=True means generic match needs a known ticker to pass
TRIPWIRES = [
    # Corporate restructuring — only if watchlist ticker mentioned
    (r"\blayoff[s]?\b|\blay.off[s]?\b|\brestructur\w+\b|\bdownsiz\w+\b|\bworkforce.reduc\w+\b|\bjob.cut[s]?\b",
     "restructuring", 15, True),

    # M&A — only if watchlist ticker mentioned
    (r"\bacquisition\b|\bacquir\w+\b|\bmerger\b|\btakeover\b|\bbuyout\b|\blbo\b",
     "acquisition", 20, True),

    # Partnerships — only if watchlist ticker mentioned
    (r"\bpartnership\b|\bjoint.venture\b|\bstrategic.alliance\b|\bdeal.sign\w+\b|\bcontract.award\w+\b",
     "partnership", 12, True),

    # Strategic investments — only if watchlist ticker mentioned
    (r"\binvest[s]?\b.*\bin\b|\bequity.stake\b|\bstrategic.investment\b|\bfunding.round\b|\bacquire[s]?.stake\b",
     "investment", 20, True),

    # Earnings — ONLY if watchlist ticker mentioned (stops YETI/MCD/etc)
    (r"\bearnings.beat\b|\bearnings.miss\b|\brevenue.beat\b|\beps.beat\b|\bguidance.rais\w+\b|\bguidance.lower\w+\b",
     "earnings", 18, True),

    # Insider activity — only if watchlist ticker mentioned
    (r"\binsider.buy\w+\b|\bform.4\b|\bceo.purchas\w+\b|\bcfo.purchas\w+\b|\bexecutive.buy\w+\b",
     "insider", 22, True),

    # ── ALWAYS PASS — no ticker requirement ───────────────────────────────────

    # Hedge funds — always pass (famous investor = always relevant)
    (r"\bpershing.square\b|\bbill.ackman\b|\backman\b",                             "hedge_fund", 28, False),
    (r"\bark.invest\b|\bcathie.wood\b|\barkk\b|\barkg\b|\barkq\b|\barkx\b",         "hedge_fund", 28, False),
    (r"\bberkshire.hathaway\b|\bwarren.buffett\b|\bbuffett\b",                       "hedge_fund", 28, False),
    (r"\bbridgewater\b|\bray.dalio\b|\bdalio\b",                                     "hedge_fund", 25, False),
    (r"\bcitadel\b|\bken.griffin\b|\bgriffin\b",                                     "hedge_fund", 25, False),
    (r"\bpoint72\b|\bsteve.cohen\b",                                                 "hedge_fund", 25, False),
    (r"\btiger.global\b|\bcoatue\b|\bd1.capital\b",                                 "hedge_fund", 25, False),
    (r"\btwo.sigma\b|\brenaissance.technolog\w+\b|\bjim.simons\b",                  "hedge_fund", 25, False),
    (r"\bthird.point\b|\bdaniel.loeb\b|\bgreenlight\b|\bdavid.einhorn\b",           "hedge_fund", 25, False),
    (r"\bdruckenmiller\b|\bstanley.druckenmiller\b|\bduquesne\b",                   "hedge_fund", 28, False),
    (r"\bgeorge.soros\b|\bsoros.fund\b",                                             "hedge_fund", 25, False),
    (r"\bmichael.burry\b|\bburry\b|\bscion.asset\b",                                "hedge_fund", 28, False),
    (r"\bcarl.icahn\b|\bicahn\b|\belliott.management\b|\bpaul.singer\b",            "hedge_fund", 25, False),
    (r"\bsoftbank\b|\bmasayoshi.son\b|\bvision.fund\b",                             "hedge_fund", 22, False),
    (r"\bkkr\b|\bapollo.global\b|\bblackstone\b|\bcarlyle\b",                       "hedge_fund", 20, False),
    (r"\bblackrock\b|\bvanguard\b|\bstate.street\b|\bfidelity\b",                   "hedge_fund", 18, False),

    # Portfolio moves — always pass
    (r"\bsold.all\b|\bexits?.position\b|\bdumps?\b.*\bshares\b|\brotates?.into\b",  "portfolio_move", 22, False),
    (r"\breduces?.stake\b|\btrimm\w+.position\b|\bnew.position\b|\binitiates?.position\b",
     "portfolio_move", 20, False),
    (r"\b13[fF].filing\b|\b13[fF].report\b|\bquarterly.holdings\b",                "portfolio_move", 20, False),

    # Regulatory — only if watchlist ticker
    (r"\bantitrust\b|\bdoj.investi\w+\b|\bfda.approv\w+\b|\bfda.reject\w+\b",
     "regulatory", 16, True),

    # AI / Tech deals — always pass (sector-wide signal)
    (r"\bai.infrastructure\b|\bgpu.order[s]?\b|\bdata.center.deal\b|\bai.partnership\b|\bchip.supply\b",
     "ai_tech", 18, False),

    # Macro / Policy — always pass
    (r"\bchips.act\b|\bexport.restrict\w+\b|\btrade.ban\b|\bsanction[s]?\b|\btariff[s]?\b",
     "macro_policy", 14, False),

    # Bankruptcy — always pass (market-wide signal)
    (r"\bchapter.11\b|\bbankruptcy\b|\bdefault\b|\bdebt.restructur\w+\b|\bliquidat\w+\b",
     "distress", 25, False),

    # Quantum — always pass (your sector)
    (r"\bquantum.computing\b|\bquantum.breakthrough\b|\bqubit[s]?\b|\bquantum.advantage\b|\bquantum.error\b",
     "quantum", 15, False),

    # Space — always pass (your sector)
    (r"\brocket.launch\b|\bsatellite.deploy\b|\blaunch.vehicle\b|\blaunch.contract\b|\border.manifest\b",
     "space", 18, False),

    # Optoelectronics — always pass (your sector)
    (r"\boptoelectronics\b|\bphotonics\b|\boptical.interconnect\b|\bsilicon.photonics\b|\bcopackaged.optics\b|\bcpo\b",
     "optoelectronics", 20, False),

    # Rare earth — always pass (your sector)
    (r"\brave.earth\b|\bcritical.mineral[s]?\b|\bneodymium\b|\bcobalt.mining\b",
     "rare_earth", 18, False),
]

# Ticker pattern for detection
TICKER_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in sorted(ALWAYS_WATCH, key=len, reverse=True)) + r')\b',
    re.IGNORECASE
)

# Famous investor pattern
FAMOUS_INVESTORS_PATTERN = re.compile(
    r'\b(ackman|cathie wood|ark invest|buffett|berkshire|dalio|bridgewater|'
    r'druckenmiller|soros|burry|icahn|einhorn|loeb|griffin|citadel|'
    r'cohen|point72|tiger global|coatue|simons|renaissance|softbank|masa son)\b',
    re.IGNORECASE
)

def run_tripwire(text: str) -> dict:
    """
    Tier 1 — zero cost keyword scan.
    Fix 4: Generic keywords (earnings, layoffs, M&A) now require
    a watchlist ticker to be mentioned. Only sector-wide signals
    (quantum, space, hedge funds, AI deals) pass without a ticker.
    """
    text_lower = text.lower()
    matched_keywords = []
    category    = None
    score_boost = 0
    passed      = False

    tickers   = list(set(TICKER_PATTERN.findall(text)))
    investors = list(set(FAMOUS_INVESTORS_PATTERN.findall(text_lower)))
    has_watchlist_ticker = len(tickers) > 0

    for pattern, cat, boost, requires_ticker in TRIPWIRES:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        if not matches:
            continue

        # Fix 4: if this pattern requires a watchlist ticker and none found — skip
        if requires_ticker and not has_watchlist_ticker:
            continue

        matched_keywords.extend(matches)
        if boost > score_boost:
            score_boost = boost
            category    = cat
        passed = True

    # Always pass if a famous investor is mentioned
    if investors:
        passed       = True
        score_boost += 15
        if not category:
            category = "hedge_fund"

    # Bonus boosts
    if has_watchlist_ticker and passed:
        score_boost += 10
    if investors and has_watchlist_ticker:
        score_boost += 10   # investor + your ticker = very high signal

    return {
        "passed":      passed,
        "keywords":    list(set(matched_keywords)),
        "category":    category,
        "score_boost": min(score_boost, 45),
        "tickers":     tickers,
        "investors":   investors,
    }