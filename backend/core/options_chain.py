"""
Fetch real options chain from Alpaca for any ticker.
Computes greeks via Black-Scholes (IV back-solved from market mid-price).
Used by deep_analysis to replace Claude-hallucinated strikes with real contracts.
"""

import os, math
from datetime import date, datetime, timedelta, timezone

RISK_FREE_RATE = 0.043
MAX_SPREAD_PCT = 0.25   # skip contracts where spread > 25% of mid
MAX_IV         = 3.0    # skip deep-ITM contracts with unrealistic IV (>300%)
MIN_IV         = 0.05   # skip contracts with suspiciously low IV
STRIKE_RANGE   = 0.18   # fetch strikes ±18% from current price
DAYS_MIN       = 21
DAYS_MAX       = 90
MAX_CANDIDATES = 4      # calls + puts to return to Claude


# ── Black-Scholes ──────────────────────────────────────────────────────────────

def _bs_price(S, K, T, r, sigma, opt):
    from scipy.stats import norm
    if T <= 0 or sigma <= 0:
        return max(0, S - K) if opt == "call" else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _implied_vol(mid, S, K, T, r, opt):
    from scipy.optimize import brentq
    if T <= 0 or mid <= 0:
        return None
    try:
        return round(brentq(
            lambda sig: _bs_price(S, K, T, r, sig, opt) - mid,
            1e-6, 10.0, xtol=1e-6, maxiter=100
        ), 4)
    except Exception:
        return None


def _greeks(S, K, T, r, sigma, opt):
    from scipy.stats import norm
    if T <= 0 or sigma <= 0:
        return {}
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    pdf = norm.pdf(d1)
    cdf_d1 = float(norm.cdf(d1))
    cdf_d2 = float(norm.cdf(d2))
    delta = cdf_d1 if opt == "call" else cdf_d1 - 1
    return {
        "delta": round(delta, 3),
        "gamma": round(float(pdf) / (S * sigma * math.sqrt(T)), 4),
        "theta": round((
            -(S * float(pdf) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * (cdf_d2 if opt == "call" else 1 - cdf_d2)
        ) / 365, 4),
        "vega": round(S * float(pdf) * math.sqrt(T) / 100, 4),
    }


def _time_to_expiry(expiry: date) -> float:
    exp_dt = datetime(expiry.year, expiry.month, expiry.day, 21, 0, 0, tzinfo=timezone.utc)
    secs = max(0, (exp_dt - datetime.now(timezone.utc)).total_seconds())
    return secs / (365.25 * 24 * 3600)


# ── Main fetch ─────────────────────────────────────────────────────────────────

_INVALID_TICKERS = {"ON", "NET", "BY", "AT", "OR", "IN", "RR", "MP", "SK"}

def get_options_chain(ticker: str, current_price: float) -> list[dict]:
    """
    Fetch real call + put candidates for ticker from Alpaca.
    Returns up to MAX_CANDIDATES contracts (mix of calls and puts)
    sorted by how close they are to ATM, with greeks and bid/ask.
    Returns [] if Alpaca keys not configured or ticker not optionable.
    """
    # Skip common-word false-positive tickers that Alpaca will reject
    if not ticker or len(ticker) < 2 or ticker.upper() in _INVALID_TICKERS:
        return []

    api_key = os.getenv("ALPACA_API_KEY", "")
    secret  = os.getenv("ALPACA_SECRET_KEY", "")
    if not api_key or not secret:
        return []

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOptionContractsRequest
        from alpaca.trading.enums import ContractType
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionSnapshotRequest
    except ImportError:
        return []

    try:
        trading     = TradingClient(api_key, secret, paper=True)
        data_client = OptionHistoricalDataClient(api_key, secret)
    except Exception:
        return []

    exp_from = date.today() + timedelta(days=DAYS_MIN)
    exp_to   = date.today() + timedelta(days=DAYS_MAX)
    lo_strike = str(round(current_price * (1 - STRIKE_RANGE)))
    hi_strike = str(round(current_price * (1 + STRIKE_RANGE)))

    candidates = []
    for opt_type, contract_type in [("call", ContractType.CALL), ("put", ContractType.PUT)]:
        try:
            req = GetOptionContractsRequest(
                underlying_symbols=[ticker],
                expiration_date_gte=exp_from,
                expiration_date_lte=exp_to,
                contract_type=contract_type,
                strike_price_gte=lo_strike,
                strike_price_lte=hi_strike,
                limit=30,
            )
            contracts = trading.get_option_contracts(req)
            if not contracts.option_contracts:
                continue

            symbols    = [c.symbol for c in contracts.option_contracts if c.tradable]
            strike_map = {c.symbol: (float(c.strike_price), c.expiration_date)
                          for c in contracts.option_contracts}

            if not symbols:
                continue

            snaps = data_client.get_option_snapshot(OptionSnapshotRequest(symbol_or_symbols=symbols))

            for sym, snap in snaps.items():
                q = snap.latest_quote
                if not q or q.bid_price is None or q.ask_price is None:
                    continue
                bid = float(q.bid_price)
                ask = float(q.ask_price)
                if bid <= 0 or ask <= 0:
                    continue

                mid        = (bid + ask) / 2
                spread     = ask - bid
                spread_pct = spread / mid if mid > 0 else 1.0
                if spread_pct > MAX_SPREAD_PCT:
                    continue

                strike, expiry = strike_map.get(sym, (None, None))
                if strike is None:
                    continue

                T  = _time_to_expiry(expiry)
                iv = _implied_vol(mid, current_price, strike, T, RISK_FREE_RATE, opt_type)
                if iv is None or iv > MAX_IV or iv < MIN_IV:
                    continue

                g = _greeks(current_price, strike, T, RISK_FREE_RATE, iv, opt_type)

                moneyness_pct = (strike - current_price) / current_price * 100
                label = "ATM" if abs(moneyness_pct) < 1 else (
                    f"+{moneyness_pct:.1f}% OTM" if moneyness_pct > 0 else
                    f"{moneyness_pct:.1f}% ITM"
                )

                candidates.append({
                    "symbol":       sym,
                    "type":         opt_type,
                    "strike":       strike,
                    "expiry":       str(expiry),
                    "days_out":     (expiry - date.today()).days,
                    "moneyness":    label,
                    "bid":          round(bid, 2),
                    "ask":          round(ask, 2),
                    "mid":          round(mid, 2),
                    "spread_pct":   round(spread_pct * 100, 1),
                    "iv_pct":       round(iv * 100, 1),
                    "cost_per_contract": round(mid * 100, 2),
                    "greeks":       g,
                })

        except Exception as e:
            print(f"[Options] {opt_type} fetch error for {ticker}: {e}")
            continue

    # Sort by closeness to ATM, tightest spread
    candidates.sort(key=lambda x: (abs(x["strike"] - current_price), x["spread_pct"]))

    # Return a balanced mix: best 2 calls + best 2 puts (or MAX_CANDIDATES total)
    calls = [c for c in candidates if c["type"] == "call"][:MAX_CANDIDATES // 2]
    puts  = [c for c in candidates if c["type"] == "put"][:MAX_CANDIDATES // 2]
    return calls + puts
