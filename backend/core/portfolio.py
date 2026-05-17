"""
Ashwin's portfolio — used for personalized alerts, correlation detection,
position-aware recommendations, and hedge suggestions.
Auto-generated from Robinhood export 2026-05-16.
"""

# ── Your holdings ─────────────────────────────────────────────────────────────
HOLDINGS = {
    # Mega positions (>$3k)
    "META":  {"shares": 11.1,    "equity": 6771,  "sector": "ai_tech",        "avg_cost": 615.60},
    "NVDA":  {"shares": 25.3,    "equity": 5687,  "sector": "semiconductor",   "avg_cost": 123.47},
    "GOOGL": {"shares": 12.5,    "equity": 4956,  "sector": "ai_tech",        "avg_cost": 322.24},
    "NBIS":  {"shares": 19,      "equity": 4139,  "sector": "ai_infra",       "avg_cost": 106.78},
    "SNDK":  {"shares": 2.5,     "equity": 3477,  "sector": "memory",         "avg_cost": 741.81},

    # Large positions ($1k-$3k)
    "DRAM":  {"shares": 50,      "equity": 2514,  "sector": "memory",         "avg_cost": 53.36},
    "WDC":   {"shares": 5,       "equity": 2380,  "sector": "memory",         "avg_cost": 281.00},
    "NFLX":  {"shares": 26.3,    "equity": 2289,  "sector": "streaming",      "avg_cost": 82.13},
    "SOFI":  {"shares": 122,     "equity": 1896,  "sector": "fintech",        "avg_cost": 25.56},
    "POET":  {"shares": 110,     "equity": 1743,  "sector": "optoelectronics","avg_cost": 11.82},
    "MRAM":  {"shares": 40,      "equity": 1480,  "sector": "memory",         "avg_cost": 36.11},
    "MU":    {"shares": 2,       "equity": 1431,  "sector": "memory",         "avg_cost": 748.25},
    "AMZN":  {"shares": 5,       "equity": 1313,  "sector": "ai_tech",        "avg_cost": 220.92},
    "TSLA":  {"shares": 3,       "equity": 1255,  "sector": "ev_tech",        "avg_cost": 425.56},
    "PLTR":  {"shares": 8.9,     "equity": 1190,  "sector": "ai_tech",        "avg_cost": 178.39},
    "XOM":   {"shares": 7.4,     "equity": 1173,  "sector": "energy",         "avg_cost": 135.41},
    "MSFT":  {"shares": 2.8,     "equity": 1168,  "sector": "ai_tech",        "avg_cost": 395.30},
    "IREN":  {"shares": 19.3,    "equity": 1017,  "sector": "ai_infra",       "avg_cost": 58.69},

    # Medium positions ($500-$1k)
    "HOOD":  {"shares": 11.6,    "equity": 889,   "sector": "fintech",        "avg_cost": 105.45},
    "APLD":  {"shares": 20,      "equity": 850,   "sector": "ai_infra",       "avg_cost": 24.92},
    "AMD":   {"shares": 2,       "equity": 840,   "sector": "semiconductor",  "avg_cost": 208.10},
    "AAPL":  {"shares": 2.4,     "equity": 718,   "sector": "ai_tech",        "avg_cost": 212.07},
    "CRWV":  {"shares": 6.2,     "equity": 666,   "sector": "ai_infra",       "avg_cost": 80.19},
    "GLW":   {"shares": 3.4,     "equity": 636,   "sector": "optoelectronics","avg_cost": 178.68},
    "LUMN":  {"shares": 62,      "equity": 622,   "sector": "telecom",        "avg_cost": 8.04},
    "KLAR":  {"shares": 40,      "equity": 606,   "sector": "fintech",        "avg_cost": 16.40},
    "CRCL":  {"shares": 5,       "equity": 561,   "sector": "fintech",        "avg_cost": 99.72},
    "RDDT":  {"shares": 3.6,     "equity": 561,   "sector": "social",         "avg_cost": 140.08},
    "UNH":   {"shares": 1.5,     "equity": 558,   "sector": "healthcare",     "avg_cost": 340.39},
    "INFQ":  {"shares": 42.7,    "equity": 539,   "sector": "quantum",        "avg_cost": 16.39},
    "PFE":   {"shares": 20.8,    "equity": 527,   "sector": "pharma",         "avg_cost": 24.85},
    "IONQ":  {"shares": 10,      "equity": 513,   "sector": "quantum",        "avg_cost": 60.75},
    "ARKX":  {"shares": 15,      "equity": 508,   "sector": "space",          "avg_cost": 33.20},
    "RKLB":  {"shares": 4,       "equity": 491,   "sector": "space",          "avg_cost": 118.21},
    "AVGO":  {"shares": 1,       "equity": 424,   "sector": "semiconductor",  "avg_cost": 331.14},

    # Smaller positions
    "UBER":  {"shares": 5,       "equity": 375,   "sector": "mobility",       "avg_cost": 96.11},
    "DUOL":  {"shares": 3,       "equity": 335,   "sector": "ai_tech",        "avg_cost": 191.50},
    "NKE":   {"shares": 7.9,     "equity": 332,   "sector": "consumer",       "avg_cost": 63.46},
    "SNOW":  {"shares": 2,       "equity": 315,   "sector": "ai_tech",        "avg_cost": 168.29},
    "QUBT":  {"shares": 30,      "equity": 313,   "sector": "quantum",        "avg_cost": 16.73},
    "SMCI":  {"shares": 10,      "equity": 309,   "sector": "ai_infra",       "avg_cost": 33.01},
    "XPEV":  {"shares": 19,      "equity": 297,   "sector": "ev_tech",        "avg_cost": 26.35},
    "RIOT":  {"shares": 12.6,    "equity": 293,   "sector": "crypto",         "avg_cost": 23.76},
    "ROOT":  {"shares": 5,       "equity": 276,   "sector": "fintech",        "avg_cost": 79.89},
    "NVEC":  {"shares": 3,       "equity": 269,   "sector": "semiconductor",  "avg_cost": 96.85},
    "BABA":  {"shares": 2,       "equity": 264,   "sector": "ai_tech",        "avg_cost": 160.56},
    "AMKR":  {"shares": 3.5,     "equity": 246,   "sector": "semiconductor",  "avg_cost": 28.65},
    "KLIC":  {"shares": 2.4,     "equity": 242,   "sector": "semiconductor",  "avg_cost": 42.55},
    "TEM":   {"shares": 5,       "equity": 218,   "sector": "ai_tech",        "avg_cost": 93.33},
    "KEEL":  {"shares": 50,      "equity": 218,   "sector": "infrastructure", "avg_cost": 4.87},
    "WBD":   {"shares": 7.8,     "equity": 210,   "sector": "media",          "avg_cost": 24.54},
    "ONDS":  {"shares": 20,      "equity": 209,   "sector": "robotics",       "avg_cost": 6.80},
    "QBTS":  {"shares": 10,      "equity": 202,   "sector": "quantum",        "avg_cost": 34.07},
    "BIDU":  {"shares": 1.4,     "equity": 193,   "sector": "ai_tech",        "avg_cost": 139.43},
    "BTBT":  {"shares": 100,     "equity": 179,   "sector": "crypto",         "avg_cost": 3.92},
    "MP":    {"shares": 2,       "equity": 122,   "sector": "rare_earth",     "avg_cost": 97.40},
    "TER":   {"shares": 0.26,    "equity": 86,    "sector": "semiconductor",  "avg_cost": 388.89},
    "TMQ":   {"shares": 20,      "equity": 82,    "sector": "rare_earth",     "avg_cost": 7.03},
    "USAR":  {"shares": 18.1,    "equity": 439,   "sector": "rare_earth",     "avg_cost": 32.01},
    "CUPR":  {"shares": 200,     "equity": 51,    "sector": "materials",      "avg_cost": 0.27},
    "RR":    {"shares": 10,      "equity": 26,    "sector": "robotics",       "avg_cost": 4.83},
    "FIG":   {"shares": 20,      "equity": 451,   "sector": "fintech",        "avg_cost": 23.07},
}

# ── Sector groupings for alert filtering ──────────────────────────────────────
# PRIORITY sectors — alert at score >= 72
PRIORITY_SECTORS = {
    "semiconductor", "memory", "ai_tech", "ai_infra", "optoelectronics",
    "quantum", "space", "rare_earth", "robotics", "ev_tech",
}

# NON-PRIORITY sectors — only alert at score >= 90
NON_PRIORITY_SECTORS = {
    "energy", "fintech", "healthcare", "pharma", "consumer",
    "streaming", "social", "telecom", "media", "crypto",
    "infrastructure", "materials", "mobility",
}

# ── Correlation map — who moves with whom ────────────────────────────────────
# If news hits a key, flag these correlated holdings
CORRELATIONS = {
    "NVDA": ["AMD", "AVGO", "SMCI", "CRWV", "IREN", "APLD", "NBIS", "POET"],
    "AMD":  ["NVDA", "AVGO", "SMCI"],
    "MU":   ["SNDK", "WDC", "MRAM", "DRAM"],
    "SNDK": ["MU", "WDC", "MRAM", "DRAM"],
    "WDC":  ["SNDK", "MU", "MRAM", "DRAM"],
    "IONQ": ["QBTS", "QUBT", "INFQ"],
    "QBTS": ["IONQ", "QUBT", "INFQ"],
    "QUBT": ["IONQ", "QBTS", "INFQ"],
    "RKLB": ["ARKX"],
    "POET": ["GLW", "NVDA"],   # optoelectronics correlation
    "GLW":  ["POET"],
    "META": ["GOOGL", "AMZN", "MSFT", "AAPL"],
    "GOOGL":["META", "MSFT", "AMZN"],
    "MSFT": ["GOOGL", "META", "AMZN"],
    "SMCI": ["NVDA", "CRWV", "IREN", "APLD"],
    "AMKR": ["NVDA", "AMD", "AVGO"],   # packaging
    "KLIC": ["NVDA", "AMD", "AVGO"],   # bonding/packaging equipment
    "TER":  ["NVDA", "AMD", "MU"],     # test equipment
    "CRWV": ["NVDA", "SMCI", "IREN"],  # AI cloud
    "IREN": ["CRWV", "APLD", "NVDA"],  # AI compute
    "APLD": ["IREN", "CRWV", "NVDA"],
}

# ── Sector keyword map — what words trigger which sector ──────────────────────
SECTOR_KEYWORDS = {
    "semiconductor": ["semiconductor", "chip", "wafer", "fab", "foundry", "tsmc", "intel", "arm",
                      "eda", "cadence", "synopsys", "asml", "lam research", "applied materials"],
    "memory":        ["memory", "dram", "nand", "flash", "ssd", "hdd", "storage chip",
                      "hbm", "high bandwidth memory", "micron", "western digital", "sandisk"],
    "ai_tech":       ["artificial intelligence", "machine learning", "large language model",
                      "llm", "generative ai", "ai model", "neural network", "deep learning"],
    "ai_infra":      ["data center", "gpu cluster", "ai infrastructure", "hyperscaler",
                      "cooling", "power infrastructure", "coreweave", "nebius"],
    "optoelectronics":["optoelectronics", "photonics", "optical", "laser", "lidar",
                       "fiber optic", "poet technologies", "corning", "optical interconnect"],
    "quantum":       ["quantum computing", "qubit", "quantum advantage", "quantum error",
                      "quantum hardware", "ionq", "rigetti", "d-wave", "ibm quantum"],
    "space":         ["rocket", "satellite", "launch vehicle", "space exploration",
                      "rocket lab", "spacex", "orbital", "launch"],
    "rare_earth":    ["rare earth", "critical minerals", "lithium", "cobalt", "neodymium",
                      "mp materials", "mining", "critical metals"],
    "robotics":      ["robotics", "autonomous", "drone", "automation", "ondas", "humanoid robot"],
    "ev_tech":       ["electric vehicle", "ev", "battery", "charging", "tesla", "xpeng"],
}

def get_all_tickers() -> list:
    return list(HOLDINGS.keys())

def get_holdings_summary() -> str:
    """Return a concise portfolio summary for Claude prompts."""
    lines = ["Portfolio holdings (Ashwin):"]
    for ticker, info in sorted(HOLDINGS.items(), key=lambda x: -x[1]["equity"]):
        lines.append(f"  {ticker}: {info['shares']} shares, ${info['equity']:,} equity, sector={info['sector']}, avg_cost=${info['avg_cost']}")
    return "\n".join(lines)

def get_correlated_holdings(ticker: str) -> list:
    """Return holdings that are correlated to a given ticker."""
    correlated = CORRELATIONS.get(ticker.upper(), [])
    return [t for t in correlated if t in HOLDINGS]

def is_priority_sector(sector: str, tickers_mentioned: list) -> bool:
    """
    Returns True if the signal should be alerted at normal threshold (72).
    Returns False if it should only alert at high conviction (90).
    """
    # Always priority if sector matches
    if sector in PRIORITY_SECTORS:
        return True
    # Always priority if a held ticker is mentioned
    held = set(HOLDINGS.keys())
    for t in tickers_mentioned:
        if t.upper() in held:
            return True
    # Check sector keywords
    return False

def get_alert_threshold(sector: str, tickers_mentioned: list, event_category: str) -> int:
    """Return the minimum score needed to send a Telegram alert."""
    if is_priority_sector(sector, tickers_mentioned):
        return 72   # normal threshold for priority sectors
    return 90       # high conviction only for everything else

def get_position_context(tickers_mentioned: list) -> dict:
    """
    For any mentioned tickers, return position context for Claude.
    Includes: do we hold it, how much, correlated holdings.
    """
    context = {}
    for ticker in tickers_mentioned:
        t = ticker.upper()
        if t in HOLDINGS:
            h = HOLDINGS[t]
            context[t] = {
                "held": True,
                "shares": h["shares"],
                "equity": h["equity"],
                "avg_cost": h["avg_cost"],
                "sector": h["sector"],
                "correlated_holdings": get_correlated_holdings(t),
            }
        else:
            context[t] = {
                "held": False,
                "correlated_holdings": get_correlated_holdings(t),
            }
    return context
