"""
copilot.py - AI Quant Copilot.

Two layers:
1. A rule-based NLP engine that understands English / Hinglish requests (horizon, buy/sell, category,
   sector, minimum probability, count, symbols, mutual funds, FII/DII, news, watchlist commands) and answers
   them from the LIVE scans (no hard-coded picks).
2. Optional Google Gemini: when an API key is available the engine's numbers are handed to Gemini as
   grounding DATA and Gemini writes the explanation.  Gemini never invents prices: it only sees what
   the scans returned.
"""
from __future__ import annotations

import re

import numpy as np
import requests

import data as D
import engine as E
import macro as M
from knowledge import SECTOR_STOCKS, STOCK_NAMES, UNI

EMOJI = {"WAIT": "⚪", "READY FOR ENTRY": "🟡", "ENTER NOW": "🟢", "READY FOR EXIT": "🟠", "EXIT": "🔴"}

# ------------------------------------------------------------------------------
# Query understanding
# ------------------------------------------------------------------------------
TF_RULES = [
    (r"intraday|aaj ke liye|\btoday\b|same day|1 day|ek din|btst|\bday trade", "1 Day"),
    (r"short swing|short-swing|5 (trading )?day|1 week|ek hafte|ek week|\bweekly\b|\bhafte\b|\bweek\b(?!s)", "5 Trading Days"),
    (r"2 week|do hafte|two week|10 day", "2 Weeks"),
    (r"2-5 week|2 to 5 week|2 se 5|3 week|4 week|\bweeks\b|\bswing\b", "2-5 Weeks"),
    (r"1 month|ek mahine|ek month|monthly|\bmonth\b|mahine|21 day", "1 Month"),
    (r"3 month|teen mahine|quarter|positional", "3 Months"),
    (r"6 month|long term|longterm|long-term|lambe|1 year|\bsaal\b|\byears?\b|\bsip\b|investment", "6 Months+"),
]
SECTOR_RX = {
    "Financial Services": r"\bbank(s|ing)?\b|\bfinanc(e|ial)\b|\bnbfc\b",
    "Information Technology": r"\bit\b|\bsoftware\b|\btech(nology)?\b|\bit sector\b",
    "Healthcare & Pharma": r"\bpharma|\bhealth|\bhospital",
    "Automobile & Auto Components": r"\bauto(mobile)?s?\b|\bcars?\b|\bev\b",
    "Oil, Gas & Energy": r"\boil\b|\bgas\b|\benergy\b|\bcrude\b",
    "FMCG": r"\bfmcg\b|\bstaples\b",
    "Metals & Mining": r"\bmetals?\b|\bsteel\b|\bmining\b",
    "Telecommunication": r"\btelecom\b|\b5g\b",
    "Capital Goods & Infra": r"\binfra(structure)?\b|\bcapital goods\b|\bdefen[cs]e\b|\brailway",
    "Power & Utilities": r"\bpower\b|\butilit|\brenewable|\bsolar",
    "Construction Materials": r"\bcement\b",
    "Realty": r"\brealty\b|\breal estate\b|\bproperty\b",
    "Consumer Durables & Retail": r"\bdurables?\b|\bretail\b",
    "Chemicals": r"\bchemicals?\b",
    "Services (Ports, Aviation)": r"\baviation\b|\bairline|\bports?\b|\blogistics",
}
CAT_RX = {
    "Largecap": r"large ?cap|blue ?chip|nifty 50 stocks", "Midcap": r"mid ?cap", "Smallcap": r"small ?cap",
    "F&O": r"\bf ?& ?o\b|\bfno\b|futures", "Banks & Finance": r"\bbank|\bfinance|\bnbfc",
    "IT & Pharma": r"\bit\b|pharma", "Auto & Metals": r"\bauto|\bmetal",
}
MF_CAT_RX = {
    "Large Cap": r"large ?cap|blue ?chip", "Mid Cap": r"mid ?cap", "Small Cap": r"small ?cap", "Flexi Cap": r"flexi",
    "ELSS": r"elss|tax sav", "Index (Nifty 50)": r"index|nifty 50|nifty fund", "Sectoral / Thematic": r"sectoral|thematic|tech fund|pharma fund|banking fund|infra fund",
    "Balanced Advantage": r"balanced|\bbaf\b|hybrid", "Contra / Value": r"contra|value fund",
}
GLOSSARY = {
    "rsi": "RSI (14) measures momentum on a 0-100 scale. 50-68 = healthy bullish momentum, above 75 = overheated, below 35 = weak/oversold.",
    "macd": "MACD = EMA12 - EMA26 with a 9-period signal line. MACD above the signal = bullish momentum, below = bearish.",
    "atr": "ATR (14) is the average daily range. This app sizes stop-loss and target as multiples of ATR so they adapt to each stock's volatility.",
    "ema": "EMA gives more weight to recent prices. EMA9 / EMA21 stacks show short-term trend; price above both = uptrend.",
    "sma": "SMA is the simple average of the last N closes. SMA50 is the medium trend, SMA200 the long-term trend line.",
    "bollinger": "Bollinger Bands = SMA20 +/- 2 standard deviations. A squeeze (narrow bands) often precedes a volatility expansion.",
    "cmf": "Chaikin Money Flow (20) combines price position inside the day's range with volume. Above +0.05 = accumulation, below -0.05 = distribution.",
    "vwap": "Anchored VWAP of volume-surge days approximates where big players' average cost sits; this app uses it for 'big-player zones'.",
    "poc": "POC (Point of Control) is the price with the most traded volume in the lookback window - a magnet / support-resistance level.",
    "hit-rate": "Hit-rate = how often similar past signals were right (price higher for BUY / lower for SELL after the horizon). It is measured, not assumed.",
}
STOP = {"THE", "AND", "FOR", "BUY", "SELL", "TOP", "BEST", "WHAT", "WHICH", "WITH", "ABOUT", "STOCK", "STOCKS", "FUND", "FUNDS", "NIFTY",
        "TARGET", "ANALYSIS", "PRICE", "SHARE", "SIP", "SIPS", "FII", "DII", "FPI", "NEWS", "RSI", "MACD", "ATR", "EMA", "SMA", "SWING", "KYA", "HAI"}

_ALIAS = {}
for _s, _n in STOCK_NAMES.items():
    _ALIAS[_n.lower()] = _s
    first = _n.lower().split()[0]
    if len(first) >= 5 and first not in ("tata", "bajaj", "adani", "india", "indian", "state", "power", "bharat", "oil", "tech"):
        _ALIAS.setdefault(first, _s)
_ALIAS.update({"hdfc bank": "HDFCBANK", "icici bank": "ICICIBANK", "sbi": "SBIN", "airtel": "BHARTIARTL", "l&t": "LT",
               "maruti": "MARUTI", "mahindra": "M&M", "kotak": "KOTAKBANK", "axis bank": "AXISBANK", "tata motors": "TMPV"})
_INDICES = {"banknifty": "BANKNIFTY", "bank nifty": "BANKNIFTY", "nifty bank": "BANKNIFTY", "nifty it": "NIFTY IT",
            "sensex": "SENSEX", "nifty 50": "NIFTY", "nifty50": "NIFTY", "india vix": "VIX"}


def detect_tf(q, default):
    for rx, lab in TF_RULES:
        if re.search(rx, q):
            return lab
    return default


def detect_side(q):
    q = re.sub(r"short[\s-]?(swing|term)|long[\s-]?term", " ", q)  # 'short swing' / 'long term' are horizons, not directions
    sell = re.search(r"\b(sell|short|bearish|bech|girne|gir rahe|falling|exit|avoid|weak|down)\b", q)
    buy = re.search(r"\b(buy|long|kharid|bullish|accumulate|rally|upar|up side|upside)\b", q)
    if re.search(r"\b(both|dono|buy (aur|and|&|or) sell|sell (aur|and|&) buy)\b", q) or (sell and buy):
        return "BOTH"
    if sell:
        return "SELL"
    if buy or re.search(r"\b(top|best|recommend)\b", q):
        return "BUY"
    return "BOTH"


def detect_symbols(text):
    q = text.lower()
    found = []
    for k, v in _INDICES.items():
        if k in q and v not in found:
            found.append(v)
    for alias in sorted(_ALIAS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", q) and _ALIAS[alias] not in found:
            found.append(_ALIAS[alias])
    for tok in re.findall(r"[A-Z][A-Z&\-]{2,13}", text):
        if tok in STOCK_NAMES and tok not in found:
            found.append(tok)
    if not found:
        for tok in re.findall(r"\b[A-Z]{3,12}\b", text):
            if tok not in STOP and tok not in found:
                found.append(tok)
    return found


def parse(text: str) -> dict:
    q = text.lower().strip()
    n = None
    m = re.search(r"top\s*(\d+)|(\d+)\s*(stocks|funds|mf|picks|shares|names)", q)
    if m:
        n = int(m.group(1) or m.group(2))
    prob = None
    m = re.search(r"(\d{2})\s*(%|percent|pratishat)|(?:accuracy|probability|prob)\s*(?:above|>=|>|se upar)?\s*(\d{2})|(\d{2})\s*(?:se upar|above|\+)", q)
    if m:
        prob = int(next(g for g in (m.group(1), m.group(3), m.group(4)) if g))
    elif re.search(r"high (accuracy|probability|conviction)|accurate", q):
        prob = 70
    sector = next((s for s, rx in SECTOR_RX.items() if re.search(rx, q)), None)
    cat = next((c for c, rx in CAT_RX.items() if re.search(rx, q)), None)
    mf_cat = next((c for c, rx in MF_CAT_RX.items() if re.search(rx, q)), None)
    is_mf = bool(re.search(r"\b(mf|mfs|mutual|fund|funds|sip|nav|elss|amc)\b|flexi ?cap", q))
    return {"q": q, "text": text, "tf": detect_tf(q, None), "side": detect_side(q), "n": n, "min_prob": prob,
            "sector": sector, "category": cat, "mf_cat": mf_cat, "is_mf": is_mf, "symbols": detect_symbols(text)}


# ------------------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------------------
def rs(x):
    return f"₹{x:,.2f}"


def _mkt_line():
    ms = E.market_status(holidays=D.market_holidays())
    if ms["open"]:
        return f"🟢 **LIVE** - {ms['detail']}"
    return f"🔴 **OFFLINE** - {ms['detail']} (levels below are for the next session)"


def _pick_line(i, r, t, extra=""):
    nm = r.get("Name") or r.get("Fund") or r.get("Stock")
    sym = r.get("Stock") or r.get("short") or ""
    arrow = "↗" if t["side"] == "BUY" else "↘"
    hit = f" | hit-rate {t['hit_pooled']}% (n={t['hit_n']:,})" if t.get("hit_pooled") else ""
    return (f"**{i}. {sym}** ({nm}) - {arrow} {t['signal']} · **{t['prob']}%** · {EMOJI[t['status']]} *{t['status']}*  \n"
            f"LTP {rs(r['price'])} | Entry {rs(t['entry'])} | Target {rs(t['target'])} ({t['exp_pct']:+.1f}%) | SL {rs(t['stop'])}{hit}  \n"
            f"_{t['strategy']} · candle: {r['pattern']} · hold {t['hold']}_{extra}")


def _cards(kind, items, tf):
    return [{"kind": kind, "key": k, "tf": tf} for k in items]


# ------------------------------------------------------------------------------
# Answer builders
# ------------------------------------------------------------------------------
def _screen_stocks(p):
    scan = D.scan_master()
    res = scan["results"]
    if not res:
        return {"text": "Market data abhi load nahi ho paya (Yahoo Finance unreachable). 'Refresh Terminal' dabakar dobara try karein.", "cards": [], "intent": "screen"}
    tf = p["tf"] or "2-5 Weeks"
    syms = list(res)
    if p["category"]:
        cs = set(UNI[p["category"]].split())
        syms = [s for s in syms if s in cs]
    if p["sector"]:
        ss = set(SECTOR_STOCKS[p["sector"]])
        syms = [s for s in syms if s in ss]
    thr = p["min_prob"] or 70
    n = p["n"] or 5
    sides = ["BUY", "SELL"] if p["side"] == "BOTH" else [p["side"]]
    lines = [_mkt_line(), "",
             f"🔎 Scanned **{len(syms)}** stocks · horizon **{tf}** · min probability **{thr}%**"
             + (f" · category **{p['category']}**" if p["category"] else "") + (f" · sector **{p['sector']}**" if p["sector"] else "")]
    cards, any_pick = [], False
    for side in sides:
        rows = [(s, res[s], res[s]["tf"][tf]) for s in syms if res[s]["tf"][tf]["signal"] == side]
        rows.sort(key=lambda x: -x[2]["prob"])
        good = [x for x in rows if x[2]["prob"] >= thr][:n]
        near = [x for x in rows if x[2]["prob"] < thr][:max(0, n - len(good))]
        lines += ["", f"### {'🟢 BUY' if side == 'BUY' else '🔴 SELL / Avoid'} setups"]
        if not good:
            lines.append(f"Is filter par koi {side} setup {thr}% se upar qualify nahi hua.")
        for i, (s, r, t) in enumerate(good, 1):
            lines.append(_pick_line(i, r, t))
        if near:
            lines.append(f"_Next best (below {thr}% - lower conviction):_")
            for i, (s, r, t) in enumerate(near, len(good) + 1):
                lines.append(_pick_line(i, r, t))
        any_pick = any_pick or bool(good)
        cards += _cards("stock", [x[0] for x in good + near][:6], tf)
    if any_pick:
        lines.append("\n_Probability = confluence blended with measured hit-rate of similar past signals. Not a guarantee._")
    return {"text": "\n\n".join(lines), "cards": cards, "intent": "screen"}


def _analyze_symbol(sym, p):
    q = D.resolve(sym)
    res = D.stock_full(q)
    if not res:
        return {"text": f"**{sym}** ka data nahi mila. Valid NSE symbol likhein (jaise RELIANCE, TCS, NIFTY).", "cards": [], "intent": "symbol"}
    tf = p["tf"] or "5 Trading Days"
    t = res["tf"][tf]
    bm = res["bigmap"].get(tf) or res["bigmap"]["5 Trading Days"]
    lines = [_mkt_line(), "", f"### 📊 {res.get('Name') or sym} ({q}) - LTP {rs(res['price'])} ({res['chg']:+.2f}%)",
             f"**{tf}:** {t['signal']} · **{t['prob']}%** · {EMOJI[t['status']]} **{t['status']}** · strategy: {t['strategy']}",
             f"Entry {rs(t['entry'])} | Target {rs(t['target'])} (+{t['exp_pct']}%) / T2 {rs(t['target2'])} | Stop-loss {rs(t['stop'])} | Exit rule: {t['trail']}",
             f"Candle now: **{res['pattern']}** ({res['pattern_action']}, {res['pattern_acc']}%) · RSI {res['rsi']:.1f} · Volume {res['vol_spike']}x",
             "", "| Horizon | Signal | Prob | Entry | Target | SL | Status |", "|---|---|---|---|---|---|---|"]
    for lab in E.TF_LABELS:
        x = res["tf"][lab]
        lines.append(f"| {lab} | {x['signal']} | {x['prob']}% | {x['entry']:,.2f} | {x['target']:,.2f} | {x['stop']:,.2f} | {EMOJI[x['status']]} {x['status']} |")
    z = bm["zones"]
    lines += ["", f"**Big-player map ({bm['n_days']}-day view):** bias **{bm['bias']}** - 50% chance to touch **{rs(bm['up50'])}** (up) vs **{rs(bm['down50'])}** (down)."]
    if z.get("buy"):
        lines.append(f"Inferred institutional BUY zone {rs(z['buy']['low'])} - {rs(z['buy']['high'])} (VWAP {rs(z['buy']['vwap'])}); footprint: {z['footprint']}.")
    nw = D.news(f"{sym} share NSE India")
    score, lab = M.news_pressure(nw)
    lines.append(f"News pressure: **{lab}** ({score:+d}).")
    return {"text": "\n\n".join(lines), "cards": _cards("stock", [sym], tf), "intent": "symbol"}


def _compare(a, b, p):
    tf = p["tf"] or "5 Trading Days"
    rows = []
    for s in (a, b):
        res = D.stock_full(D.resolve(s))
        if not res:
            return {"text": f"{s} ka data nahi mila.", "cards": [], "intent": "compare"}
        t = res["tf"][tf]
        rows.append((s, res, t))
    lines = [f"### ⚖️ {a} vs {b} ({tf})", "", "| | " + " | ".join(r[0] for r in rows) + " |", "|---|" + "---|" * len(rows)]
    def row(lbl, f):
        lines.append(f"| {lbl} | " + " | ".join(f(r) for r in rows) + " |")
    row("LTP", lambda r: rs(r[1]["price"]))
    row("Signal / Prob", lambda r: f"{r[2]['signal']} {r[2]['prob']}%")
    row("Status", lambda r: f"{EMOJI[r[2]['status']]} {r[2]['status']}")
    row("Entry → Target", lambda r: f"{r[2]['entry']:,.2f} → {r[2]['target']:,.2f}")
    row("Stop-loss", lambda r: f"{r[2]['stop']:,.2f}")
    row("RSI", lambda r: f"{r[1]['rsi']:.0f}")
    row("Hit-rate (past)", lambda r: f"{r[2]['hit_pooled']}%" if r[2]["hit_pooled"] else "-")
    best = max(rows, key=lambda r: (r[2]["prob"] if r[2]["signal"] == "BUY" else -r[2]["prob"]))
    lines.append(f"\n**Edge:** {best[0]} currently has the stronger bullish set-up for this horizon.")
    return {"text": "\n".join(lines), "cards": _cards("stock", [a, b], tf), "intent": "compare"}


def _flows(p):
    fl, src = D.flows()
    scan = D.scan_master()
    fpi, per, _ = D.fpi_sector()
    lines = []
    if len(fl):
        L = fl.iloc[0]
        lines.append(f"### 🏦 Institutional flows - {L.Date:%d %b %Y} (source: {src})")
        lines.append(f"FII/FPI net **{L['FII Net']:,.0f} Cr** · DII net **{L['DII Net']:,.0f} Cr** · combined **{L['FII Net'] + L['DII Net']:,.0f} Cr**")
        if not D.flows_live(src):
            lines.append("⚠️ _Live FII/DII sources unreachable - these flow numbers are illustrative._")
    if scan["results"]:
        mx = D.build_inst_matrix(scan, fl, fpi)
        hz = {"1 Day": "1 Day", "5 Trading Days": "1 Week", "2 Weeks": "1 Week", "2-5 Weeks": "1 Month", "1 Month": "1 Month", "3 Months": "3 Months", "6 Months+": "6 Months+"}.get(p["tf"] or "", "1 Week")
        sd = mx["sector"][hz]
        lines.append(f"\n**Sector radar - horizon {hz}** (inferred from NSDL flows + price/volume footprint):")
        for _, r in sd.head(3).iterrows():
            lines.append(f"- 🟢 **{r['Sector']}** {r['Rank']} · Buy {r['Buy %']}% · top: {r['Top BUY stocks']}")
        for _, r in sd.tail(3).iloc[::-1].iterrows():
            lines.append(f"- 🔴 **{r['Sector']}** {r['Rank']} · Sell {r['Sell %']}% · weak: {r['Top SELL stocks']}")
        fp = D.todays_footprint(scan)
        if len(fp):
            b = fp[fp["Inferred"] == "BUYING"].head(4)
            s_ = fp[fp["Inferred"] == "SELLING"].head(4)
            if len(b):
                lines.append("\n**Probable big-player BUYING today (volume surge + up-move):** " + ", ".join(f"{a} ({v}x)" for a, v in zip(b["Stock"], b["Volume x"])))
            if len(s_):
                lines.append("**Probable big-player SELLING today:** " + ", ".join(f"{a} ({v}x)" for a, v in zip(s_["Stock"], s_["Volume x"])))
    lines.append("\n_Note: stock-level FII/DII buying is not published daily; sector flow is NSDL data, stock-level is an inference from price x volume._")
    return {"text": "\n".join(lines), "cards": [], "intent": "flows"}


def _macro(p):
    evs, src = D.ff_calendar()
    if not evs:
        return {"text": "Forex Factory calendar abhi reachable nahi hai (feed rate-limit / network). Thodi der baad try karein - News tab me static macro playbook available hai.", "cards": [], "intent": "macro"}
    an = [M.analyze_event(e) for e in evs if e.get("impact") in ("High", "Medium")]
    an = [a for a in an if a["hours"] is None or a["hours"] > -12]
    an.sort(key=lambda a: (-(a["impact_prob"]), a["hours"] if a["hours"] is not None else 999))
    lines = [f"### 🌍 High-impact macro events (Forex Factory, source: {src})"]
    for a in an[:5]:
        w = a["when"].strftime("%a %d %b %H:%M IST") if a["when"] else "-"
        lines.append(f"**{a['country']} - {a['title']}** · {w} · impact likelihood **{a['impact_prob']}%**  \n"
                     f"Sectors: {', '.join(sorted({x['scope'] for x in a['assets']})) or 'broad market'} · Stocks: {a['stocks']}  \n"
                     f"💡 {a['action']}")
    return {"text": "\n\n".join(lines), "cards": [], "intent": "macro"}


def _market(p):
    scan = D.scan_master()
    res = scan["results"]
    lines = [_mkt_line(), "", "### 🧭 Market snapshot"]
    if scan.get("nifty"):
        lines.append(f"Nifty 50: **{scan['nifty']['price']:,.1f}** ({scan['nifty']['chg']:+.2f}%) · regime: "
                     + ("🟢 above 50-DMA" if (scan["regime"] or 0) > 0 else "🔴 below 50-DMA" if (scan["regime"] or 0) < 0 else "⚪ range-bound"))
    if res:
        br = np.mean([1 if r["above50"] else 0 for r in res.values()]) * 100
        buys = sum(1 for r in res.values() if r["tf"]["5 Trading Days"]["signal"] == "BUY")
        sells = sum(1 for r in res.values() if r["tf"]["5 Trading Days"]["signal"] == "SELL")
        lines.append(f"Breadth: **{br:.0f}%** of {len(res)} stocks above 50-DMA · short-swing BUY signals **{buys}** vs SELL **{sells}**.")
    return {"text": "\n\n".join(lines), "cards": [], "intent": "market"}


MF_TFS = {"1 Day": "5 Trading Days", "5 Trading Days": "5 Trading Days", "2 Weeks": "2 Weeks", "2-5 Weeks": "1 Month", "1 Month": "1 Month",
          "3 Months": "3 Months", "6 Months+": "6 Months+"}


def _screen_mf(p):
    tf = MF_TFS.get(p["tf"] or "6 Months+", "6 Months+")
    cats = [p["mf_cat"]] if p["mf_cat"] else ["Flexi Cap", "Large Cap", "Mid Cap", "Small Cap"]
    funds = D.scan_mf_many(cats)
    if not funds:
        return {"text": "Mutual fund NAV data abhi load nahi ho paya (mfapi.in unreachable). Thodi der baad try karein.", "cards": [], "intent": "mf"}
    thr, n = p["min_prob"] or 70, p["n"] or 5
    sides = ["BUY", "SELL"] if p["side"] == "BOTH" else [p["side"]]
    lines = [f"🔎 Scanned **{len(funds)}** funds ({', '.join(cats)}) by NAV · horizon **{tf}** · min probability **{thr}%**"]
    cards = []
    for side in sides:
        rows = sorted([f for f in funds if f["tf"][tf]["signal"] == side], key=lambda f: -f["tf"][tf]["prob"])
        good = [f for f in rows if f["tf"][tf]["prob"] >= thr][:n]
        near = [f for f in rows if f["tf"][tf]["prob"] < thr][:max(0, n - len(good))]
        lines.append(f"### {'🟢 BUY / Accumulate' if side == 'BUY' else '🔴 SELL / Reduce'} funds" + ("" if good else f" (none ≥{thr}%)"))
        for i, f in enumerate(good + near, 1):
            t = f["tf"][tf]
            if near and i == len(good) + 1:
                lines.append(f"_Next best (below {thr}% - lower conviction):_")
            lines.append(f"**{i}. {f['Fund']}** - {t['signal']} · **{t['prob']}%** · {EMOJI[t['status']]} *{t['status']}*  \n"
                         f"NAV {rs(f['nav'])} ({f['nav_date']:%d %b}) | expected {t['exp_pct']:+.1f}% | 1Y {f['stats'].get('1Y %', '-')}% | {t['strategy']}")
        cards += _cards("mf", [f["code"] for f in good + near][:6], tf)
    lines.append("\n_MF signals use NAV history and peer-relative strength; NAV is declared once a day._")
    return {"text": "\n\n".join(lines), "cards": cards, "intent": "mf"}


def _analyze_mf(phrase, p):
    hit = D.resolve_mf(phrase)
    if not hit:
        return None
    res = D.mf_full(hit[0])
    if not res:
        return None
    tf = MF_TFS.get(p["tf"] or "3 Months", "3 Months")
    t = res["tf"][tf]
    lines = [f"### 💼 {hit[1]}", f"NAV **{rs(res['nav'])}** ({res['nav_date']:%d %b %Y}) · {res['scheme_category']}",
             f"**{tf}:** {t['signal']} · **{t['prob']}%** · {EMOJI[t['status']]} {t['status']} · {t['strategy']}",
             f"Entry NAV {rs(t['entry'])} | Target NAV {rs(t['target'])} ({t['exp_pct']:+.1f}%) | Stop NAV {rs(t['stop'])} | {t['trail']}",
             f"Returns: " + " · ".join(f"{k} {v}%" for k, v in res["stats"].items() if k.endswith("%") and k not in ("Vol %", "MaxDD %"))]
    return {"text": "\n\n".join(lines), "cards": _cards("mf", [hit[0]], tf), "intent": "mf-detail"}


def _watchlist(p, actions):
    q, syms = p["q"], [s for s in p["symbols"] if s not in ("NIFTY",)]
    w = actions["get"]()
    if re.search(r"\b(show|dikhao|list|mera|my|view)\b", q) and not re.search(r"\b(add|remove|delete|pin)\b", q):
        return {"text": f"**⭐ Watchlist stocks:** {', '.join(w['stocks']) or '-'}\n\n**💼 Funds:** {', '.join(w['funds']) or '-'}\n\n**📌 Pinned:** {', '.join(w['pinned']) or '-'}", "cards": [], "intent": "watch"}
    if not syms:
        return {"text": "Kaunsa stock chahiye? Jaise: *'add TCS to watchlist'* ya *'pin RELIANCE'*.", "cards": [], "intent": "watch"}
    out = []
    for s in syms:
        if re.search(r"\b(unpin)\b", q):
            out.append(actions["pin"](s, False))
        elif re.search(r"\bpin\b", q):
            out.append(actions["pin"](s, True))
        elif re.search(r"\b(remove|delete|hatao|nikalo)\b", q):
            out.append(actions["watch"](s, False))
        else:
            out.append(actions["watch"](s, True))
    return {"text": "\n\n".join(out), "cards": [], "intent": "watch"}


HELP = """### 🤖 Main ye sab kar sakta hoon
- **Screener:** *"top 5 high accuracy short swing buy stocks"*, *"midcap 1 month sell setups 75% se upar"*, *"IT sector me swing buy"*
- **Stock / Index analysis:** *"RELIANCE analysis"*, *"banknifty target stop loss"*
- **Compare:** *"TCS vs INFY"*
- **Mutual funds:** *"best flexi cap fund 3 months"*, *"mid cap mf sell side"*, *"Parag Parikh Flexi Cap analysis"*
- **FII / DII:** *"FII DII abhi kis sector me buy kar rahe hain?"*
- **Macro / news:** *"Forex Factory high impact events"*
- **Watchlist:** *"add TATASTEEL to watchlist"*, *"pin INFY"*, *"show my watchlist"*
- **Concepts:** *"what is RSI"*, *"POC kya hai"*"""


# ------------------------------------------------------------------------------
# Gemini (optional)
# ------------------------------------------------------------------------------
def gemini_reply(api_key: str, model: str, question: str, data_text: str, timeout=40) -> str:
    base = "https://generativelanguage.googleapis.com/v1beta"
    prompt = ("You are a careful Indian stock-market research assistant inside a trading dashboard. "
              "Use ONLY the numbers in DATA; never invent prices, probabilities or news. If DATA is empty or does not answer the question, "
              "say what is missing and answer conceptually. Reply in the user's language (Hinglish is fine), concise, use bullet points and "
              "keep the key levels. End with one line: this is analysis, not SEBI-registered investment advice.\n\n"
              f"DATA:\n{data_text or '(none)'}\n\nQUESTION: {question}")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1000}}

    def call(m):
        return requests.post(f"{base}/models/{m}:generateContent", params={"key": api_key}, json=body, timeout=timeout)

    r = call(model)
    if r.status_code in (400, 404):
        try:
            ms = requests.get(f"{base}/models", params={"key": api_key}, timeout=15).json().get("models", [])
            ok = [m["name"].split("/")[-1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m["name"]]
            if ok:
                r = call(ok[0])
        except Exception:
            pass
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


# ------------------------------------------------------------------------------
# Router
# ------------------------------------------------------------------------------
def rule_answer(text: str, actions: dict) -> dict:
    p = parse(text)
    q = p["q"]
    syms = p["symbols"]

    if re.search(r"\b(help|madad|kya kar sakte|what can you|commands)\b", q):
        return {"text": HELP, "cards": [], "intent": "help"}
    m = re.search(r"(?:what is|what's|meaning of|explain)\s+([a-z\-]+)|([a-z\-]+)\s+(?:kya hai|matlab|ka matlab)", q)
    if m and (m.group(1) or m.group(2)) in GLOSSARY:
        k = m.group(1) or m.group(2)
        return {"text": f"**{k.upper()}** - {GLOSSARY[k]}", "cards": [], "intent": "glossary"}
    if re.search(r"\b(watchlist|watch list|pin|unpin)\b", q) or (re.search(r"\b(add|remove|delete)\b", q) and syms):
        return _watchlist(p, actions)
    if len(syms) >= 2 and re.search(r"\bvs\b|versus|compare|\bya\b|\bor\b|\baur\b|\bbetter\b", q):
        return _compare(syms[0], syms[1], p)
    if re.search(r"\b(fii|fpi|dii|institution|big player|smart money|bulk|block deal|nsdl)\b", q):
        return _flows(p)
    if re.search(r"\b(news|forex factory|fomc|fed|cpi|nfp|calendar|macro|event|events)\b", q):
        return _macro(p)
    if p["is_mf"]:
        generic = {"mutual", "fund", "funds", "mf", "mfs", "sip", "sips", "best", "top", "buy", "sell", "analysis", "analyse", "nav", "for", "ke", "liye", "me", "kaunse",
                   "kaunsa", "konsi", "konsa", "hain", "hai", "batao", "the", "term", "long", "short", "side", "setup", "setups", "picks", "accuracy", "high", "upar", "show",
                   "give", "list", "recommend", "good", "target", "which", "what", "month", "months", "week", "weeks", "year", "years", "day", "days", "trading", "swing", "invest"}
        cat_words = {"large", "mid", "small", "cap", "flexi", "flexicap", "elss", "index", "sectoral", "thematic", "balanced", "advantage", "contra", "value", "hybrid",
                     "tax", "saver", "nifty", "equity", "midcap", "smallcap", "largecap", "baf"}
        words = [w for w in re.findall(r"[a-z]+", q) if w not in generic and len(w) > 2]
        specific = [w for w in words if w not in cat_words]
        if specific and not p["n"]:  # an AMC / scheme name is present -> analyse that fund
            r = _analyze_mf(" ".join(words), p)
            if r:
                return r
        return _screen_mf(p)
    if syms and not re.search(r"\b(top|best|picks|setups?|screener|konsi|kaunse)\b", q):
        return _analyze_symbol(syms[0], p)
    if re.search(r"\b(market|outlook|overview|breadth)\b", q) and not p["sector"]:
        return _market(p)
    if p["sector"] or re.search(r"\b(stocks?|shares?|picks?|setups?|swing|intraday|buy|sell|top|best|konsi|kaunse|recommend|batao)\b", q):
        return _screen_stocks(p)
    if syms:
        return _analyze_symbol(syms[0], p)
    return {"text": "Sawal poori tarah samajh nahi aaya. Aap stock/sector/horizon bataiye - jaise *'top 5 short swing buy stocks'*, *'TCS analysis'*, *'best flexi cap fund'*.\n\n" + HELP,
            "cards": [], "intent": "fallback"}


def answer(text: str, actions: dict, gemini: dict | None = None) -> dict:
    """gemini = {"key": ..., "model": ...} or None.  Returns {text, data_text, cards, intent, note}."""
    try:
        out = rule_answer(text, actions)
    except Exception as e:  # never let the chat crash the page
        out = {"text": f"⚠️ Is query ko process karte waqt error aaya: `{type(e).__name__}`. Dobara try karein ya query thodi badal kar poochein.", "cards": [], "intent": "error"}
    out["data_text"], out["note"] = out["text"], ""
    if gemini and gemini.get("key") and out["intent"] not in ("watch", "help", "error"):
        try:
            ctx = out["text"] if out["intent"] != "fallback" else ""
            out["text"] = gemini_reply(gemini["key"], gemini.get("model") or "gemini-2.5-flash", text, ctx)
            out["note"] = "gemini"
        except Exception as e:
            out["note"] = f"Gemini unavailable ({type(e).__name__}) - showing built-in engine answer."
    return out
