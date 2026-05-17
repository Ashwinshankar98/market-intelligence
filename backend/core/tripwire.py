import re

# ── High-signal keyword patterns ─────────────────────────────────────────────
TRIPWIRES = [
    # Corporate restructuring
    (r"\blayoff[s]?\b|\blay.off[s]?\b|\brestructur\w+\b|\bdownsiz\w+\b|\bworkforce.reduc\w+\b|\bjob.cut[s]?\b", "restructuring", 15),

    # M&A
    (r"\bacquisition\b|\bacquir\w+\b|\bmerger\b|\btakeover\b|\bbuyout\b|\blbo\b|\bprivate.equity\b", "acquisition", 20),

    # Partnerships
    (r"\bpartnership\b|\bjoint.venture\b|\bcollabor\w+\b|\bstrategic.alliance\b|\bdeal.sign\w+\b|\bcontract.award\w+\b", "partnership", 12),

    # Strategic investments
    (r"\binvest[s]?\b.*\bin\b|\bequity.stake\b|\bstrategic.investment\b|\bfunding.round\b|\blead[s]?.investor\b|\bseries.[a-e]\b|\bacquire[s]?.stake\b|\bminority.stake\b|\bmajority.stake\b", "investment", 20),

    # Earnings
    (r"\bearnings.beat\b|\bearnings.miss\b|\brevenue.beat\b|\beps.beat\b|\bguidance.rais\w+\b|\bguidance.lower\w+\b", "earnings", 18),

    # Insider activity (company executives)
    (r"\binsider.buy\w+\b|\bform.4\b|\bceo.purchas\w+\b|\bcfo.purchas\w+\b|\bexecutive.buy\w+\b|\bdirector.buy\w+\b", "insider", 22),

    # ── HEDGE FUNDS — major firms ─────────────────────────────────────────────
    (r"\bpershing.square\b|\bbill.ackman\b|\backman\b", "hedge_fund", 28),
    (r"\bark.invest\b|\bcathie.wood\b|\bark.innovation\b|\barkk\b|\barkg\b|\barkq\b|\barkw\b|\barkf\b|\barkx\b", "hedge_fund", 28),
    (r"\bberkshire.hathaway\b|\bwarren.buffett\b|\bbuffett\b|\bcharlie.munger\b", "hedge_fund", 28),
    (r"\bbridgewater\b|\bray.dalio\b|\bdalio\b", "hedge_fund", 25),
    (r"\bcitadel\b|\bken.griffin\b|\bgriffin\b", "hedge_fund", 25),
    (r"\bpoint72\b|\bsteve.cohen\b|\bcohen\b", "hedge_fund", 25),
    (r"\btiger.global\b|\bchase.coleman\b", "hedge_fund", 25),
    (r"\bcoatue\b|\bphilippe.laffont\b|\blaffont\b", "hedge_fund", 25),
    (r"\bd1.capital\b|\bdan.sundheim\b", "hedge_fund", 25),
    (r"\btwo.sigma\b|\bjohn.overdeck\b|\bdavid.siegel\b", "hedge_fund", 22),
    (r"\brenaissance.technolog\w+\b|\bjim.simons\b|\bsimons\b|\bmedallion.fund\b", "hedge_fund", 25),
    (r"\bthird.point\b|\bdaniel.loeb\b|\bloeb\b", "hedge_fund", 25),
    (r"\bgreenlight.capital\b|\bdavid.einhorn\b|\beinhorn\b", "hedge_fund", 25),
    (r"\bdruckenmiller\b|\bstanley.druckenmiller\b|\bduquesne\b", "hedge_fund", 28),
    (r"\bgeorge.soros\b|\bsoros.fund\b|\bquantum.fund\b", "hedge_fund", 25),
    (r"\bmichael.burry\b|\bburry\b|\bscion.asset\b", "hedge_fund", 28),
    (r"\bpaulson\b|\bjohn.paulson\b|\bpaulson.co\b", "hedge_fund", 22),
    (r"\bcarl.icahn\b|\bicahn\b|\bicahn.enterprises\b", "hedge_fund", 25),
    (r"\bdan.loeb\b|\bactivist.investor\b|\bactivist.hedge\b", "hedge_fund", 22),
    (r"\belliott.management\b|\bpaul.singer\b", "hedge_fund", 25),
    (r"\bvaliant\b|\bsequoia.fund\b|\bsoftbank.vision\b|\bmasayoshi.son\b|\bmasa.son\b", "hedge_fund", 22),
    (r"\btpg.capital\b|\bkkr\b|\bapollo.global\b|\bblackstone\b|\bcarlyle\b", "hedge_fund", 20),
    (r"\bvanguard\b|\bblackrock\b|\bstate.street\b|\bfidelity\b|\bt.rowe.price\b", "hedge_fund", 18),
    (r"\ba16z\b|\bandreessen.horowitz\b|\bsequoia.capital\b|\bkhosla\b|\bgreylock\b", "hedge_fund", 20),

    # ── Portfolio move language ───────────────────────────────────────────────
    (r"\bsold.all\b|\bexits?.position\b|\bdumps?\b|\bliquidat\w+.position\b|\bexited\b.*\bstake\b", "portfolio_move", 22),
    (r"\breduces?.stake\b|\btrimm\w+.position\b|\bpares?.back\b|\bcutting.position\b", "portfolio_move", 20),
    (r"\bbuilds?.position\b|\bincreases?.stake\b|\bnew.position\b|\binitiates?.position\b|\brotates?.into\b", "portfolio_move", 22),
    (r"\b13[fF].filing\b|\b13[fF].report\b|\bsec.13[fF]\b|\bquarterly.holdings\b", "portfolio_move", 20),
    (r"\bbuys?\s+\$\d+[mb]\b|\bpurchases?\s+\$\d+[mb]\b|\bstake.worth\b|\bposition.worth\b", "portfolio_move", 22),

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

    # Space
    (r"\brocket.launch\b|\bsatellite.deploy\b|\blaunch.vehicle\b|\border.manifest\b|\blaunch.contract\b", "space", 18),

    # Optoelectronics / photonics
    (r"\boptoelectronics\b|\bphotonics\b|\boptical.interconnect\b|\bsilicon.photonics\b|\bcopackaged.optics\b|\bcpo\b", "optoelectronics", 20),

    # Rare earth / critical minerals
    (r"\brave.earth\b|\bcritical.mineral[s]?\b|\blithium.supply\b|\bcobalt.mining\b|\bneodymium\b|\bchips.materials\b", "rare_earth", 18),
]

# ── Watchlist — tickers + fund names ─────────────────────────────────────────
WATCHLIST = [
    # Your holdings — semiconductors
    "NVDA","AMD","AVGO","INTC","TSMC","ASML","AMAT","KLAC","LRCX","AMKR","KLIC","TER","NVEC","SNDK",
    # Your holdings — memory
    "MU","WDC","MRAM","DRAM","STX",
    # Your holdings — AI / big tech
    "META","GOOGL","MSFT","AMZN","AAPL","NFLX","PLTR","SNOW","DUOL","TEM","BIDU","BABA",
    # Your holdings — AI infrastructure
    "NBIS","CRWV","IREN","APLD","SMCI",
    # Your holdings — quantum
    "IONQ","QBTS","QUBT","INFQ","IBM",
    # Your holdings — space
    "RKLB","ARKX","ONDS",
    # Your holdings — optoelectronics
    "POET","GLW",
    # Your holdings — rare earth
    "MP","USAR","TMQ",
    # Your holdings — EV/mobility
    "TSLA","XPEV","UBER",
    # Your holdings — fintech/other
    "SOFI","HOOD","RDDT","LUMN","KLAR","CRCL","FIG",
    # Your holdings — energy/commodities
    "XOM","SLV","IAU","ICOP",
    # ETFs you hold
    "VOO","VGT","SPY","QQQ","SMH","EWY","VYM","SCHD","IBIT","ARKX",
    # Famous funds — their common tickers they trade
    "BRK.B","BRK.A",
    # Sector peers worth watching
    "ARM","QCOM","MRVL","NXPI","ON","WOLF","STM",
    "PANW","CRWD","S","ZS","NET",
    "ASTS","SPCE","LMT","RTX","NOC","BA",
]

# ── Famous investors and their known focus areas ──────────────────────────────
FAMOUS_INVESTORS = {
    "bill ackman":        {"fund": "Pershing Square",    "style": "activist, concentrated long"},
    "pershing square":    {"fund": "Pershing Square",    "style": "activist, concentrated long"},
    "cathie wood":        {"fund": "ARK Invest",         "style": "disruptive innovation, high growth"},
    "ark invest":         {"fund": "ARK Invest",         "style": "disruptive innovation, high growth"},
    "warren buffett":     {"fund": "Berkshire Hathaway", "style": "value, long-term, quality"},
    "berkshire":          {"fund": "Berkshire Hathaway", "style": "value, long-term, quality"},
    "ray dalio":          {"fund": "Bridgewater",        "style": "macro, risk parity"},
    "ken griffin":        {"fund": "Citadel",            "style": "multi-strategy, quant"},
    "steve cohen":        {"fund": "Point72",            "style": "discretionary equity"},
    "stanley druckenmiller": {"fund": "Duquesne",        "style": "macro, concentrated"},
    "george soros":       {"fund": "Soros Fund",         "style": "macro, global"},
    "michael burry":      {"fund": "Scion Asset",        "style": "value, contrarian, deep research"},
    "carl icahn":         {"fund": "Icahn Enterprises",  "style": "activist, corporate governance"},
    "dan loeb":           {"fund": "Third Point",        "style": "activist, event-driven"},
    "david einhorn":      {"fund": "Greenlight Capital", "style": "value, short selling"},
    "chase coleman":      {"fund": "Tiger Global",       "style": "growth, venture/tech"},
    "philippe laffont":   {"fund": "Coatue",             "style": "tech-focused long/short"},
    "paul singer":        {"fund": "Elliott Management", "style": "activist, distressed"},
    "masayoshi son":      {"fund": "SoftBank Vision",    "style": "vision fund, large bets"},
    "jim simons":         {"fund": "Renaissance Tech",   "style": "quantitative, algorithmic"},
}

TICKER_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in WATCHLIST) + r')\b',
    re.IGNORECASE
)

INVESTOR_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in FAMOUS_INVESTORS.keys()) + r')\b',
    re.IGNORECASE
)

def run_tripwire(text: str) -> dict:
    """
    Tier 1 — zero cost keyword scan.
    Returns: { passed, keywords, category, score_boost, tickers, investors }
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

    tickers   = list(set(TICKER_PATTERN.findall(text)))
    investors = list(set(INVESTOR_PATTERN.findall(text_lower)))

    passed = len(matched_keywords) > 0

    # Extra boosts
    if tickers and passed:
        score_boost += 10
    if investors:
        score_boost += 15   # famous investor mention always boosts
        passed = True       # famous investor = always pass tripwire
    if category == "hedge_fund" and tickers:
        score_boost += 10   # fund + ticker = very high signal

    return {
        "passed":      passed,
        "keywords":    list(set(matched_keywords)),
        "category":    category,
        "score_boost": min(score_boost, 45),
        "tickers":     tickers,
        "investors":   investors,
    }