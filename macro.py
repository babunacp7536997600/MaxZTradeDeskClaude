"""
macro.py - turns headlines and Forex Factory calendar events into
sector / stock / index / mutual-fund impact with a probability and an action.

The probabilities here are HEURISTIC (event importance x sensitivity), not
backtested statistics.  The UI labels them as "impact likelihood".
"""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from knowledge import NEG, POS, SHORT, MID

IST = ZoneInfo("Asia/Kolkata")

# ------------------------------------------------------------------------------
# Headline classification
# ------------------------------------------------------------------------------
NEWS_RULES = [
    (r"\b(bank|banks|banking|rbi|nbfc|lending|credit growth|npa|loan)\b", "Financial Services",
     "HDFCBANK, ICICIBANK, SBIN, KOTAKBANK", "Banking / Financial Services funds, Large Cap funds"),
    (r"\b(it services|software|nasscom|h-1b|outsourcing|cloud|infosys|tcs|wipro|hcl|generative ai|ai)\b", "Information Technology",
     "TCS, INFY, HCLTECH, TECHM", "Technology funds, Flexi Cap funds"),
    (r"\b(auto|automobile|car sales|vehicle|ev|suv|two-wheeler|tractor|dispatch)\b", "Automobile & Auto Components",
     "MARUTI, M&M, EICHERMOT, TVSMOTOR", "Auto / Consumption funds, Mid Cap funds"),
    (r"\b(pharma|drug|fda|usfda|hospital|healthcare|api)\b", "Healthcare & Pharma",
     "SUNPHARMA, DRREDDY, CIPLA, APOLLOHOSP", "Pharma & Healthcare funds"),
    (r"\b(oil|crude|gas|petrol|diesel|opec|refiner|brent)\b", "Oil, Gas & Energy",
     "RELIANCE, ONGC, BPCL, IOC", "Energy funds, Infra funds"),
    (r"\b(fmcg|consumer|rural demand|monsoon|inflation)\b", "FMCG",
     "HINDUNILVR, ITC, NESTLEIND, BRITANNIA", "Consumption funds, Large Cap funds"),
    (r"\b(steel|metal|aluminium|copper|iron ore|zinc)\b", "Metals & Mining",
     "TATASTEEL, JSWSTEEL, HINDALCO, VEDL", "Sectoral Metal funds, Value / Contra funds"),
    (r"\b(real estate|housing|property|realty)\b", "Realty",
     "DLF, GODREJPROP, OBEROIRLTY, PRESTIGE", "Real-estate / Infra funds"),
    (r"\b(infra|infrastructure|capex|order book|railway|defence|budget)\b", "Capital Goods & Infra",
     "LT, HAL, BEL, SIEMENS", "Infrastructure / PSU funds, Mid Cap funds"),
    (r"\b(power|renewable|solar|electricity|coal)\b", "Power & Utilities",
     "NTPC, POWERGRID, TATAPOWER, NHPC", "Power & Infra funds"),
    (r"\b(telecom|5g|spectrum|tariff)\b", "Telecommunication",
     "BHARTIARTL, TATACOMM", "Large Cap funds, Digital / Telecom thematics"),
    (r"\b(cement)\b", "Construction Materials", "ULTRACEMCO, AMBUJACEM, SHREECEM", "Infra / Mid Cap funds"),
]


def _hits(words, text):
    return sum(1 for k in words if re.search(rf"\b{re.escape(k)}", text))


def classify_news(title: str) -> dict:
    w = title.lower()
    pos, neg = _hits(POS, w), _hits(NEG, w)
    sector, stocks, mfs = "Broad Market / Nifty 50", "NIFTYBEES, large caps", "Index funds, Flexi Cap funds"
    matched = False
    for pat, sec, stk, mf in NEWS_RULES:
        if re.search(pat, w):
            sector, stocks, mfs, matched = sec, stk, mf, True
            break
    horizon = ("Short-term (1-5 days)" if any(k in w.split() for k in SHORT)
               else "Medium-term (2-6 weeks)" if any(k in w for k in MID) else "Short-term (1-5 days)")
    diff = pos - neg
    direction = "BULLISH" if diff > 0 else "BEARISH" if diff < 0 else "NEUTRAL"
    impact = int(np.clip(50 + 9 * abs(diff) + (5 if matched else 0) + (4 if any(k in w.split() for k in SHORT) else 0), 45, 90))
    if direction == "BULLISH":
        action = "Dip par buy ya breakout-high ke upar entry; swing low par SL. Pehle confirmation candle dekhein."
    elif direction == "BEARISH":
        action = "Naya long avoid karein; holdings me trailing SL tight karein, pullback par sell/short setup dekhein."
    else:
        action = "Price action aur volume confirmation ka intezar karein (WAIT)."
    return {"direction": direction, "score": diff, "sector": sector, "stocks": stocks, "mfs": mfs,
            "impact": impact, "horizon": horizon, "action": action,
            "tag": {"BULLISH": "🟢 Positive", "BEARISH": "🔴 Negative", "NEUTRAL": "⚪ Neutral"}[direction]}


def news_pressure(items) -> tuple[int, str]:
    """Aggregate sentiment of (title, link, source, published) tuples -> (-100..100, label)."""
    if not items:
        return 0, "No news"
    sc = [classify_news(t[0])["score"] for t in items[:10]]
    tot = int(np.clip(np.mean(sc) * 35, -100, 100))
    return tot, ("Supportive" if tot > 15 else "Adverse" if tot < -15 else "Neutral")


# ------------------------------------------------------------------------------
# Forex Factory events
# ------------------------------------------------------------------------------
EVENT_RULES = [
    {
        "key": "US Fed rate / FOMC", "pat": r"federal funds|fomc|fed chair|powell|fed .*speak|interest rate decision",
        "ccy": ("USD",), "weight": 0.95, "invert": False,
        "stocks": "TCS, INFY, HCLTECH, HDFCBANK, ICICIBANK, JSWSTEEL, DLF",
        "indices": "Nifty 50, Nifty IT, Bank Nifty, USD/INR",
        "mfs": "US feeder / International funds, Technology funds, Flexi Cap (FII-heavy)",
        "hot": {"bias": "BEARISH", "down": ["Information Technology", "Financial Services", "Realty", "Metals & Mining"], "up": [],
                "note": "Hawkish / higher-than-expected rates: DXY and US yields rise, FII outflow risk, INR weakens.",
                "action": "Trim high-beta longs, tighten trailing SL on IT & banks; no fresh leveraged longs until the reaction candle closes."},
        "cool": {"bias": "BULLISH", "down": [], "up": ["Information Technology", "Financial Services", "Realty", "Metals & Mining"],
                 "note": "Dovish / lower rates: global liquidity improves, FII inflow and relief rally in rate-sensitives.",
                 "action": "Buy dips in IT & Bank Nifty above the previous-day high; prefer large caps first."},
    },
    {
        "key": "US inflation (CPI / PPI / PCE)", "pat": r"\bcpi\b|core cpi|\bppi\b|\bpce\b|inflation",
        "ccy": ("USD",), "weight": 0.9, "invert": False,
        "stocks": "INFY, WIPRO, COFORGE, HINDALCO, DLF",
        "indices": "Nifty 50, Nifty IT, Dollar Index (USD/INR)",
        "mfs": "Technology funds, Flexi Cap funds with US exposure",
        "hot": {"bias": "BEARISH", "down": ["Information Technology", "Realty", "Financial Services"], "up": [],
                "note": "Hotter inflation delays rate cuts: stronger dollar, weaker EM equities.",
                "action": "Avoid fresh IT/Realty longs; wait for a close above the pre-event high before re-entering."},
        "cool": {"bias": "BULLISH", "down": [], "up": ["Information Technology", "Realty", "Financial Services"],
                 "note": "Cooling inflation weakens DXY, strengthens INR and triggers FII buying in Nifty.",
                 "action": "Accumulate IT / banks on pullbacks; Nifty longs above the day's high."},
    },
    {
        "key": "US jobs (NFP / unemployment / claims)", "pat": r"non-farm|nfp|employment change|unemployment|jobless|claims|adp|payroll",
        "ccy": ("USD",), "weight": 0.88, "invert": False,
        "stocks": "TCS, HCLTECH, LTIM, PERSISTENT",
        "indices": "Nifty IT, Nifty 50",
        "mfs": "IT sector funds, Balanced Advantage funds",
        "hot": {"bias": "MIXED", "down": ["Realty"], "up": ["Information Technology"],
                "note": "Strong labour data: rate-cut hopes fade (valuation pressure) but IT demand outlook stays firm.",
                "action": "Hold IT winners with trailing SL; avoid adding to rate-sensitive Realty/NBFC."},
        "cool": {"bias": "BEARISH", "down": ["Information Technology", "Metals & Mining"], "up": ["FMCG", "Healthcare & Pharma"],
                 "note": "Weak jobs raise recession fears: growth sectors sell off, defensives outperform.",
                 "action": "Rotate towards FMCG / Pharma; keep tight stops on high-beta F&O."},
    },
    {
        "key": "US growth & activity (GDP / PMI / retail sales)", "pat": r"\bgdp\b|retail sales|\bism\b|\bpmi\b|durable|industrial production|consumer (confidence|sentiment)",
        "ccy": ("USD",), "weight": 0.7, "invert": False,
        "stocks": "TCS, INFY, TATASTEEL, HINDALCO, LT",
        "indices": "Nifty IT, Nifty Metal",
        "mfs": "Technology funds, Global / US feeder funds",
        "hot": {"bias": "BULLISH", "down": [], "up": ["Information Technology", "Metals & Mining", "Capital Goods & Infra"],
                "note": "Resilient US growth supports IT export demand and cyclical metals.",
                "action": "Buy dips in IT and metals; breakout entries above resistance."},
        "cool": {"bias": "BEARISH", "down": ["Information Technology", "Metals & Mining"], "up": ["FMCG", "Healthcare & Pharma"],
                 "note": "Slowing US activity hurts IT revenue outlook and metal demand.",
                 "action": "Reduce cyclicals, favour defensives; stay light on fresh longs."},
    },
    {
        "key": "Crude oil (inventories / OPEC)", "pat": r"crude oil|oil inventor|opec|natural gas|brent",
        "ccy": None, "weight": 0.78, "invert": False,
        "stocks": "ONGC, BPCL, IOC, ASIANPAINT, INDIGO",
        "indices": "Nifty Energy, Nifty 50",
        "mfs": "Energy funds, Consumption & Infrastructure funds",
        "hot": {"bias": "MIXED", "down": ["Services (Ports, Aviation)", "Oil, Gas & Energy"], "up": [],
                "note": "Bigger crude build / lower crude: positive for paints, aviation and OMCs, negative for upstream explorers (ONGC).",
                "action": "Buy OMC / paint / aviation dips; avoid fresh ONGC longs."},
        "cool": {"bias": "MIXED", "down": ["Services (Ports, Aviation)"], "up": ["Oil, Gas & Energy"],
                 "note": "Crude draw / OPEC cuts: upstream benefits, input costs rise for paints, tyres, aviation.",
                 "action": "Prefer ONGC / Oil India; tighten SL on aviation and paints."},
    },
    {
        "key": "China activity data", "pat": r".*", "ccy": ("CNY",), "weight": 0.65, "invert": False,
        "stocks": "TATASTEEL, JSWSTEEL, HINDALCO, VEDL, SRF",
        "indices": "Nifty Metal",
        "mfs": "Sectoral Metal funds, Value / Contra funds",
        "hot": {"bias": "BULLISH", "down": [], "up": ["Metals & Mining", "Chemicals"],
                "note": "Stronger China data lifts base-metal prices and global cyclicals.",
                "action": "Buy metals on breakouts; trail below EMA21."},
        "cool": {"bias": "BEARISH", "down": ["Metals & Mining", "Chemicals"], "up": [],
                 "note": "Weak China data drags metals and chemicals.",
                 "action": "Avoid fresh metal longs; book profits near resistance."},
    },
    {
        "key": "Global central bank (ECB / BoE / BoJ / others)", "pat": r"interest rate|rate decision|monetary policy|cash rate|bank rate|policy rate|boj|ecb|boe|rba|snb",
        "ccy": ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"), "weight": 0.6, "invert": False,
        "stocks": "HDFCBANK, ICICIBANK, TCS, INFY",
        "indices": "Nifty 50, Bank Nifty",
        "mfs": "Large Cap funds, Flexi Cap funds",
        "hot": {"bias": "BEARISH", "down": ["Financial Services", "Information Technology"], "up": [],
                "note": "Hawkish central bank (esp. BoJ): global liquidity tightens, carry-trade unwind can trigger EM outflows.",
                "action": "Keep leverage low; wait for the first 30-min candle to settle."},
        "cool": {"bias": "BULLISH", "down": [], "up": ["Financial Services", "Information Technology"],
                 "note": "Dovish central bank: liquidity supportive for EM flows.",
                 "action": "Buy dips in large caps; stay with trend."},
    },
]
_DEFAULT_RULE = {
    "key": "Other macro release", "weight": 0.5, "stocks": "Nifty 50 heavyweights", "indices": "Nifty 50",
    "mfs": "Index funds, Flexi Cap funds", "invert": False,
    "hot": {"bias": "MIXED", "down": [], "up": [], "note": "Limited India-specific read-through; watch global risk sentiment.",
            "action": "No directional edge - trade the reaction, not the headline."},
    "cool": {"bias": "MIXED", "down": [], "up": [], "note": "Limited India-specific read-through.", "action": "No directional edge - WAIT."},
}


def parse_num(x):
    """'0.3%' -> 0.3 ; '150K' -> 150000 ; '4.25|4.5' -> 4.25 ; '' -> None."""
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    v = float(m.group())
    mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}.get(s[m.end():m.end() + 1].lower(), 1)
    return v * mult


def parse_event_time(s: str):
    try:
        return datetime.fromisoformat(str(s)).astimezone(IST)
    except Exception:
        return None


def _match_rule(title: str, ccy: str):
    t = title.lower()
    for rule in EVENT_RULES:
        if rule["ccy"] and ccy not in rule["ccy"]:
            continue
        if re.search(rule["pat"], t):
            return rule
    return _DEFAULT_RULE


def analyze_event(ev: dict, now: datetime | None = None) -> dict:
    """ev = {title, country, date, impact, forecast, previous}. -> enriched dict."""
    now = (now or datetime.now(IST)).astimezone(IST)
    title, ccy = ev.get("title", ""), ev.get("country", "")
    rule = _match_rule(title, ccy)
    when = parse_event_time(ev.get("date", ""))
    base = {"High": 84, "Medium": 66, "Low": 45, "Holiday": 20}.get(ev.get("impact", "Low"), 45)
    prob = base + int(round(10 * (rule["weight"] - 0.7)))
    hours = None
    if when is not None:
        hours = (when - now).total_seconds() / 3600
        if 0 <= hours <= 24:
            prob += 3
        elif hours < -36:
            prob -= 10
    prob = int(np.clip(prob, 20, 95))

    f, p = parse_num(ev.get("forecast")), parse_num(ev.get("previous"))
    outcome, scenario = "unknown", None
    if f is not None and p is not None:
        if f == p:
            outcome = "inline"
        else:
            above = f > p
            hot = (not above) if rule.get("invert") else above
            outcome = "hot" if hot else "cool"
            scenario = rule["hot" if hot else "cool"]
    both = scenario is None

    assets = []
    scen_list = [rule["hot"], rule["cool"]] if both else [scenario]
    for sc in scen_list:
        for sec in sc["up"]:
            assets.append({"scope": sec, "direction": "UP", "prob": int(np.clip(50 + (prob - 50) * 0.85, 40, 92)),
                           "when": "if hot" if both and sc is rule["hot"] else "if cool" if both else "expected"})
        for sec in sc["down"]:
            assets.append({"scope": sec, "direction": "DOWN", "prob": int(np.clip(50 + (prob - 50) * 0.85, 40, 92)),
                           "when": "if hot" if both and sc is rule["hot"] else "if cool" if both else "expected"})

    if scenario:
        headline, action = scenario["note"], scenario["action"]
        bias = scenario["bias"]
    else:
        headline = ("Direction depends on the print. HOT: " + rule["hot"]["note"] + "  COOL: " + rule["cool"]["note"])
        action = f"HOT: {rule['hot']['action']}  |  COOL: {rule['cool']['action']}"
        bias = "EVENT RISK"
    if hours is not None and 0 <= hours <= 2:
        action = "Event within 2 hours: avoid fresh positions, reduce size, widen stops. " + action
    return {**ev, "rule": rule["key"], "impact_prob": prob, "outcome": outcome, "bias": bias,
            "stocks": rule["stocks"], "indices": rule["indices"], "mfs": rule["mfs"], "assets": assets,
            "headline": headline, "action": action, "when": when, "hours": hours}
