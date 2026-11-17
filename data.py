"""
data.py - every network call and every cached scan lives here.

Design rules
* Raw network access is isolated in `_http_get`, `_yf_download`, `_yf_history` (easy to mock / swap).
* Failures never produce invented numbers: functions return empty results and the UI says so.
  (The only fallbacks that still exist - FII/DII flows, NSDL sector table, bulk deals - are
  flagged as `live=False` and labelled "illustrative" on screen.)
* Empty / failed results are NOT left in the cache, so the next rerun retries.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from io import StringIO
from urllib.parse import quote

import feedparser
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

import engine as E
from knowledge import (BENCH, IDX, INDEX_NAMES, IX, MFU, NSDL_SECTOR_MAP, SEC, SECTOR_STOCKS, STOCK_NAMES, UA, UNI,
                       master_symbols, sector_of)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


# ==============================================================================
# Network layer
# ==============================================================================
def _http_get(url, headers=None, timeout=12, **kw):
    return requests.get(url, headers=headers or UA, timeout=timeout, **kw)


def _yf_download(tickers, **kw):
    return yf.download(tickers, progress=False, auto_adjust=True, **kw)


def _yf_history(symbol, **kw):
    return yf.Ticker(symbol).history(auto_adjust=True, **kw)


def _clean(df, intraday=False):
    """Flatten columns, keep OHLCV, drop NaN closes, tz-naive normalised daily index."""
    if df is None or len(df) == 0:
        return None
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    need = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in need):
        return None
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df[need + ["Volume"]].dropna(subset=["Close"])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if not intraday:
        idx = pd.to_datetime(df.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        df.index = idx.normalize()
    return df if len(df) else None


def _keep_if_good(cached_fn, result, is_empty):
    """Drop a cached failure so the next rerun retries instead of serving it for an hour."""
    if is_empty(result):
        try:
            cached_fn.clear()
        except Exception:
            pass
    return result


# ==============================================================================
# Price history
# ==============================================================================
@st.cache_data(ttl=1200, show_spinner=False)
def _download_daily_cached(symbols: tuple, period: str = "3y"):
    out = {}
    for i in range(0, len(symbols), 40):
        chunk = list(symbols[i:i + 40])
        try:
            raw = _yf_download(chunk, period=period, interval="1d", group_by="ticker", threads=True)
        except Exception:
            continue
        if raw is None or len(raw) == 0:
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            lv0 = set(raw.columns.get_level_values(0))
            for s in chunk:
                if s in lv0:
                    c = _clean(raw[s])
                    if c is not None:
                        out[s] = c
        elif len(chunk) == 1:
            c = _clean(raw)
            if c is not None:
                out[chunk[0]] = c
    return out


def download_daily(symbols: tuple, period: str = "3y"):
    return _keep_if_good(_download_daily_cached, _download_daily_cached(tuple(symbols), period), lambda r: not r)


@st.cache_data(ttl=300, show_spinner=False)
def hist(s, period="5y"):
    """(resolved symbol, daily OHLCV) - NSE first, BSE fallback.  Kept from v1."""
    for x in ([s, s[:-3] + ".BO"] if s.endswith(".NS") else [s]):
        try:
            d = _clean(_yf_history(x, period=period, interval="1d"))
            if d is not None and len(d) > 60:
                return x, d
        except Exception:
            pass
    return s, None


@st.cache_data(ttl=3600, show_spinner=False)
def info(s):
    try:
        return yf.Ticker(s).info or {}
    except Exception:
        return {}


_NAME_TO_SYM = {v.lower(): k for k, v in STOCK_NAMES.items()}


def resolve(q):
    """Free text -> Yahoo symbol."""
    k = q.strip().upper()
    if k in IDX:
        return IDX[k]
    if k.startswith("^") or "." in k:
        return k
    if k in STOCK_NAMES:
        return k + ".NS"
    low = q.strip().lower()
    if low in _NAME_TO_SYM:
        return _NAME_TO_SYM[low] + ".NS"
    if " " not in k:
        return k + ".NS"
    for nm, sym in _NAME_TO_SYM.items():
        if low in nm or nm in low:
            return sym + ".NS"
    try:
        r = [x["symbol"] for x in yf.Search(q, max_results=8).quotes if x["symbol"].endswith((".NS", ".BO"))]
        return r[0] if r else k.replace(" ", "") + ".NS"
    except Exception:
        return k.replace(" ", "") + ".NS"


@st.cache_data(ttl=300, show_spinner=False)
def idx():
    try:
        return _yf_download(list(IX), period="5d")["Close"].ffill()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def sectors():
    try:
        d = _yf_download(list(SEC.values()), period="6mo")["Close"].dropna(axis=1, how="all").ffill()
        inv = {v: k for k, v in SEC.items()}
        rows = [{"Sector": inv[c], **{lb: round((d[c].iloc[-1] / d[c].iloc[-1 - n] - 1) * 100, 2)
                                      for n, lb in [(1, "1D %"), (5, "1W %"), (21, "1M %"), (63, "3M %")]}} for c in d.columns]
        return pd.DataFrame(rows).sort_values("1M %", ascending=False)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def quick_quote(item: str, is_fund: bool = False):
    """Light price for the pinned bar: {label, price, chg, kind} or None."""
    try:
        if is_fund:
            hit = resolve_mf(item)
            if not hit:
                return None
            _, s = _mf_nav_raw(hit[0])
            if len(s) < 2:
                return None
            return {"label": item, "price": float(s.iloc[-1]), "chg": float((s.iloc[-1] / s.iloc[-2] - 1) * 100),
                    "kind": "fund", "asof": s.index[-1]}
        sym = resolve(item)
        d = _clean(_yf_history(sym, period="5d", interval="1d"))
        if d is None or len(d) < 2:
            return None
        return {"label": item, "price": float(d.Close.iloc[-1]), "chg": float((d.Close.iloc[-1] / d.Close.iloc[-2] - 1) * 100),
                "kind": "stock", "asof": d.index[-1]}
    except Exception:
        return None


# ==============================================================================
# NSE / news / calendar
# ==============================================================================
@st.cache_data(ttl=600, show_spinner=False)
def nse_api(path):
    h = {"User-Agent": UA["User-Agent"], "Accept": "application/json", "Referer": "https://www.nseindia.com/"}
    s = requests.Session()
    s.get("https://www.nseindia.com", headers=h, timeout=8)
    return s.get("https://www.nseindia.com/api/" + path, headers=h, timeout=10).json()


@st.cache_data(ttl=43200, show_spinner=False)
def market_holidays():
    """ISO dates of NSE trading holidays (empty tuple when the NSE feed is unreachable)."""
    try:
        j = nse_api("holiday-master?type=trading")
        out = []
        for row in j.get("CM", []):
            try:
                out.append(datetime.strptime(row["tradingDate"], "%d-%b-%Y").date().isoformat())
            except Exception:
                pass
        return tuple(out)
    except Exception:
        return tuple()


@st.cache_data(ttl=600, show_spinner=False)
def news(q):
    try:
        e = feedparser.parse("https://news.google.com/rss/search?q=" + quote(q) + "&hl=en-IN&gl=IN&ceid=IN:en").entries[:15]
        return [(x.title, x.link, x.get("source", {}).get("title", ""), x.get("published", "")[:22]) for x in e]
    except Exception:
        return []


# ---- Forex Factory ------------------------------------------------------------
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF = {"t": 0.0, "data": None, "src": "unavailable", "tried": 0.0}


def ff_calendar():
    """
    (events, source).  The free FF feed allows ~2 requests / 5 min per file, so:
    refresh at most every 45 min (process-wide), keep the last good copy on disk, never hammer.
    source in {"live", "disk-cache", "unavailable"}.
    """
    now = time.time()
    if _FF["data"] is not None and now - _FF["t"] < 2700:
        return _FF["data"], _FF["src"]
    if now - _FF["tried"] > 300:
        _FF["tried"] = now
        try:
            r = _http_get(FF_URL, timeout=10)
            if r.status_code == 200 and r.text.lstrip().startswith("["):
                data = r.json()
                _FF.update(t=now, data=data, src="live")
                try:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(os.path.join(CACHE_DIR, "ff_calendar.json"), "w") as f:
                        json.dump(data, f)
                except Exception:
                    pass
                return data, "live"
        except Exception:
            pass
    if _FF["data"] is not None:
        return _FF["data"], "live" if now - _FF["t"] < 86400 else "disk-cache"
    try:
        with open(os.path.join(CACHE_DIR, "ff_calendar.json")) as f:
            data = json.load(f)
        _FF.update(t=now - 2400, data=data, src="disk-cache")
        return data, "disk-cache"
    except Exception:
        return [], "unavailable"


# ==============================================================================
# FII / DII, NSDL, bulk deals
# ==============================================================================
FC = ["Date", "FII Buy", "FII Sell", "FII Net", "DII Buy", "DII Sell", "DII Net"]


def _clean_flow_df(df):
    df = df.iloc[:, :7].copy()
    df.columns = FC
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for c in FC[1:]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[,+₹\s]", "", regex=True), errors="coerce")
    return df.dropna().sort_values("Date", ascending=False).reset_index(drop=True)


def _scrape_groww():
    h = _http_get("https://www.groww.in/fii-dii-data", timeout=10).text
    for t in pd.read_html(StringIO(h)):
        if t.shape[1] >= 7:
            d = _clean_flow_df(t)
            if len(d) >= 5:
                return d
    raise ValueError("No table")


def _scrape_tapetide():
    x = _http_get("https://tapetide.com/fii-dii-data.md", timeout=10).text
    m = re.findall(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|((?:\s*-?[\d.]+\s*\|){6})", x)
    d = _clean_flow_df(pd.DataFrame([[a] + re.findall(r"-?[\d.]+", b) for a, b in m]))
    if len(d) < 5:
        raise ValueError("No rows")
    return d


@st.cache_data(ttl=900, show_spinner=False)
def _flows_cached():
    for name, fn in [("Groww", _scrape_groww), ("Tapetide", _scrape_tapetide)]:
        try:
            return fn(), name
        except Exception:
            pass
    dates = pd.date_range(end=datetime.today(), periods=10, freq="B").sort_values(ascending=False)
    h = pd.DataFrame({
        "Date": dates,
        "FII Buy": [11200, 10850, 9540, 12400, 10200, 9800, 11450, 12900, 10100, 9900],
        "FII Sell": [12850, 11950, 11200, 10800, 11700, 10500, 13100, 11500, 12400, 10800],
        "FII Net": [-1650, -1100, -1660, 1600, -1500, -700, -1650, 1400, -2300, -900],
        "DII Buy": [13400, 12600, 11800, 10200, 12900, 11400, 12800, 10900, 13700, 11600],
        "DII Sell": [10900, 10400, 9950, 9800, 10600, 10100, 10700, 9900, 11200, 10300],
        "DII Net": [2500, 2200, 1850, 400, 2300, 1300, 2100, 1000, 2500, 1300]})
    return h, "Fallback (ILLUSTRATIVE - live FII/DII sources unreachable)"


def flows():
    r = _flows_cached()
    if str(r[1]).startswith("Fallback"):
        _flows_cached.clear()
    return r


def flows_live(src) -> bool:
    return not str(src).startswith("Fallback")


@st.cache_data(ttl=21600, show_spinner=False)
def _fpi_cached():
    today = date.today()
    ends = []
    for i in range(3):
        y, m = divmod(today.year * 12 + today.month - 1 - i, 12)
        m += 1
        ends += [date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1), date(y, m, 15)]
    for e in sorted([x for x in ends if x < today], reverse=True)[:4]:
        for tok in dict.fromkeys([e.strftime("%b"), e.strftime("%b").upper(), e.strftime("%B")]):
            try:
                r = _http_get(f"https://www.fpi.nsdl.co.in/web/StaticReports/Fortnightly_Sector_wise_FII_Investment_Data/FIIInvestSector_{tok}{e.day:02d}{e.year}.html", timeout=6)
                if r.status_code == 200 and "Sectors" in r.text:
                    t = max(pd.read_html(StringIO(r.text)), key=lambda x: x.shape[1])
                    num = t.iloc[:, 2:].apply(lambda c: pd.to_numeric(c.astype(str).str.replace(",", ""), errors="coerce"))
                    df = pd.DataFrame({"Sector": t.iloc[:, 1].astype(str), "Prev Fortnight": num.iloc[:, 10],
                                       "Latest Fortnight": num.iloc[:, 20], "AUC": num.iloc[:, 30]}).dropna()
                    pr = list(dict.fromkeys(re.findall(r"Net Investment ([A-Za-z]+ \d{1,2}-\d{1,2}, \d{4})", r.text)))[:2]
                    if len(df) > 8:
                        return df, pr, e
            except Exception:
                pass
    fb = pd.DataFrame({
        "Sector": ["Information Technology", "Healthcare & Pharma", "Financial Services", "Automobile & Auto Components",
                   "Oil, Gas & Consumable Fuels", "Fast Moving Consumer Goods (FMCG)", "Metals & Mining", "Telecommunication"],
        "Prev Fortnight": [1850, 1240, -4200, 890, -1450, 320, -980, 2150],
        "Latest Fortnight": [2940, 1680, -3150, 1120, -1890, 480, -620, 2480],
        "AUC": [485000, 210000, 1850000, 340000, 520000, 410000, 280000, 195000]})
    return fb, ["ILLUSTRATIVE fallback - NSDL report unreachable"], today


def fpi_sector():
    r = _fpi_cached()
    if "ILLUSTRATIVE" in " ".join(map(str, r[1])):
        _fpi_cached.clear()
    return r


def fpi_live(periods) -> bool:
    return "ILLUSTRATIVE" not in " ".join(map(str, periods))


def _norm_deals(rows):
    out = []
    for r in rows or []:
        low = {str(k).lower(): v for k, v in r.items()}
        def pick(*keys):
            for k, v in low.items():
                if any(x in k for x in keys):
                    return v
            return None
        out.append({"Date": pick("date"), "Symbol": pick("symbol"), "Client": pick("client"),
                    "Buy/Sell": str(pick("buy")).upper()[:4] if pick("buy") is not None else None,
                    "Qty": pick("qty"), "Avg Price": pick("watp", "price")})
    return pd.DataFrame(out)


@st.cache_data(ttl=900, show_spinner=False)
def _bulk_cached():
    try:
        dl = nse_api("snapshot-capital-market-largedeal")
        rows = (dl.get("BULK_DEALS_DATA", []) or []) + (dl.get("BLOCK_DEALS_DATA", []) or [])
        z = _norm_deals(rows)
        if len(z) > 0:
            return z, True
    except Exception:
        pass
    return pd.DataFrame(), False


def bulk_deals():
    z, live = _bulk_cached()
    if not live:
        _bulk_cached.clear()
    return z, live


@st.cache_data(ttl=3600, show_spinner=False)
def deals_for_symbol(symbol: str, days: int = 120):
    """Disclosed NSE bulk + block deals (real client names and prices) for one stock."""
    sym = symbol.replace(".NS", "").replace(".BO", "")
    to_d, from_d = date.today(), date.today() - timedelta(days=days)
    fmt = lambda x: x.strftime("%d-%m-%Y")
    rows = []
    for kind in ("bulk-deals", "block-deals"):
        try:
            j = nse_api(f"historical/{kind}?symbol={quote(sym)}&from={fmt(from_d)}&to={fmt(to_d)}")
            for r in (j.get("data") if isinstance(j, dict) else j) or []:
                rows.append({**r, "_kind": "Bulk" if kind == "bulk-deals" else "Block"})
        except Exception:
            continue
    df = _norm_deals(rows)
    if len(df):
        df["Type"] = [r["_kind"] for r in rows]
    return df


# ==============================================================================
# Stock universe scan (one download, one calibration, every tab re-uses it)
# ==============================================================================
@st.cache_data(ttl=1200, show_spinner=False)
def _scan_master_cached():
    syms = tuple(s + ".NS" for s in master_symbols())
    frames = dict(_download_daily_cached(syms + (BENCH,), "3y"))
    bench_df = frames.pop(BENCH, None)
    regime, bench = E.market_regime(bench_df)
    today = pd.Timestamp.now().normalize()
    prepped, cal = {}, E.new_calib()
    for s, df in frames.items():
        if len(df) < 120 or (today - df.index[-1]).days > 12:
            continue
        d = E.ind(df)
        fl = E.pattern_flags(d)
        b = None if bench is None else bench.reindex(d.index, method="ffill")
        sc = E.family_scores(d, fl, regime, b)
        prepped[s] = (d, fl, sc, b)
        for tf in E.TIMEFRAMES:
            fr = d["Close"].shift(-tf["n"]) / d["Close"] - 1
            E.calib_add(cal, tf["label"], sc[tf["family"]].values, fr.values)
    cal = E.calib_finalize(cal)
    results = {}
    for s, (d, fl, sc, b) in prepped.items():
        sym = s.replace(".NS", "")
        r = E.analyze_prepped(d, fl, sc, STOCK_NAMES.get(sym, sym), cal, regime, b)
        r["Stock"], r["sector"] = sym, sector_of(sym)
        results[sym] = r
    nifty = None
    if bench_df is not None and len(bench_df) > 2:
        nifty = {"price": float(bench_df.Close.iloc[-1]), "chg": float((bench_df.Close.iloc[-1] / bench_df.Close.iloc[-2] - 1) * 100)}
    return {"results": results, "calib": cal, "n": len(results),
            "regime": None if regime is None else float(regime.iloc[-1]), "nifty": nifty,
            "failed": [s.replace(".NS", "") for s in syms if s not in prepped],
            "asof": max([r["asof"] for r in results.values()]) if results else None,
            "n_signals": int(sum(v["n"] for v in cal.values()) / max(len(cal), 1)) if cal else 0}


def scan_master():
    r = _scan_master_cached()
    floor = 0.3 * len(master_symbols())  # Yahoo throttled most of the batch -> do not keep it cached, retry next run
    return _keep_if_good(_scan_master_cached, r, lambda x: not x["results"] or x["n"] < floor)


def category_symbols(cat: str):
    return UNI[cat].split()


# ==============================================================================
# Institutional (FII / FPI / DII) sector & stock radar
# ==============================================================================
INST_HORIZONS = {"1 Day": "1 Day", "1 Week": "5 Trading Days", "1 Month": "1 Month", "3 Months": "3 Months", "6 Months+": "6 Months+"}
_W = {"1 Day": (.45, .35, .20), "1 Week": (.45, .30, .25), "1 Month": (.45, .25, .30), "3 Months": (.50, .20, .30), "6 Months+": (.55, .15, .30)}
_SESS = {"1 Day": 1, "1 Week": 5, "1 Month": 21, "3 Months": 21, "6 Months+": 21}


def map_nsdl_sector(name: str):
    n = str(name).lower()
    for key, sec in NSDL_SECTOR_MAP:
        if key in n:
            return sec
    return None


def _accum_part(r):
    cmf = float(np.clip(r.get("cmf", 0.0) * 200, -35, 35))
    obv = float(np.clip(r.get("obv_slope", 0.0) * 80, -25, 25))
    vs, ch = r.get("vol_spike", 1.0), r.get("chg", 0.0)
    foot = (30 if vs >= 1.5 else 12 if vs >= 1.1 else 0) * np.sign(ch)
    return float(np.clip(cmf + obv + foot, -90, 90))


def build_inst_matrix(scan: dict, flows_df: pd.DataFrame | None, fpi_df: pd.DataFrame | None):
    """
    -> dict(horizons={h: sector_df}, stocks={h: stock_df}, sector_flow, tilt)
    Score = w_price * calibrated-confluence + w_accum * volume/money-flow footprint + w_flow * (NSDL sector flow + FII/DII tilt).
    Stock-level FII/DII buying is NOT disclosed daily; the footprint is an inference from price x volume.
    """
    res = scan["results"]
    # --- sector flow z-score from NSDL (Rs Cr) ---
    sflow = {}
    if fpi_df is not None and len(fpi_df):
        for _, row in fpi_df.iterrows():
            sec = map_nsdl_sector(row["Sector"])
            if sec:
                sflow[sec] = sflow.get(sec, 0.0) + float(row["Latest Fortnight"])
    zs = {}
    if len(sflow) >= 3:
        v = np.array(list(sflow.values()))
        sd = v.std() or 1.0
        zs = {k: float(np.clip((x - v.mean()) / sd * 20, -40, 40)) for k, x in sflow.items()}

    def tilt(h):
        if flows_df is None or len(flows_df) == 0:
            return 0.0
        k = _SESS[h]
        net = float((flows_df.head(k)["FII Net"] + flows_df.head(k)["DII Net"]).sum())
        return float(15 * np.tanh(net / (3000 * np.sqrt(k))))

    sector_tables, stock_tables = {}, {}
    for h, tf_label in INST_HORIZONS.items():
        wp, wa, wf = _W[h]
        t = tilt(h)
        srows, trows = [], []
        for sec, syms in SECTOR_STOCKS.items():
            items = []
            for s in syms:
                r = res.get(s)
                if not r:
                    continue
                tf = r["tf"][tf_label]
                acc = _accum_part(r)
                flow = zs.get(sec, 0.0) + t
                inst = wp * tf["score"] + wa * acc + wf * flow
                bp = float(np.clip(50 + 0.45 * inst, 8, 92))
                items.append({"Stock": s, "Name": r["Name"], "Sector": sec, "Buy %": round(bp), "Sell %": round(100 - bp),
                              "Inst score": round(inst, 1), "Calibrated tech prob": f"{tf['prob']}% {tf['signal']}",
                              "Footprint": "Accumulation" if acc > 15 else "Distribution" if acc < -15 else "Neutral",
                              "CMF": round(r.get("cmf", 0.0), 2), "Vol x": r.get("vol_spike", 1.0), "1D %": round(r["chg"], 2),
                              "Status": tf["status"], "LTP": round(r["price"], 2), "Entry": tf["entry"], "Target": tf["target"],
                              "Stop": tf["stop"], "Side": tf["side"]})
            if not items:
                continue
            idf = pd.DataFrame(items).sort_values("Inst score", ascending=False)
            sc = float(idf["Inst score"].mean())
            bp = float(np.clip(50 + 0.5 * sc, 8, 92))
            top_b = idf[idf["Inst score"] > 0].head(3)
            top_s = idf[idf["Inst score"] < 0].tail(3).iloc[::-1]
            srows.append({
                "Sector": sec, "FPI Net (Rs Cr, NSDL)": None if sec not in sflow else round(sflow[sec]),
                "Flow bias": "Accumulating" if zs.get(sec, 0) > 8 else "Distributing" if zs.get(sec, 0) < -8 else "Neutral",
                "Footprint (CMF avg)": round(float(idf["CMF"].mean()), 2), "Score": round(sc, 1),
                "Buy %": round(bp), "Sell %": round(100 - bp),
                "Verdict": "ACCUMULATE" if bp >= 60 else "DISTRIBUTE" if bp <= 40 else "NEUTRAL",
                "Top BUY stocks": ", ".join(f"{a} ({b}%)" for a, b in zip(top_b["Stock"], top_b["Buy %"])) or "-",
                "Top SELL stocks": ", ".join(f"{a} ({b}%)" for a, b in zip(top_s["Stock"], top_s["Sell %"])) or "-",
            })
            trows.append(idf)
        sdf = pd.DataFrame(srows).sort_values("Score", ascending=False).reset_index(drop=True)
        if len(sdf):
            sdf.insert(0, "Rank", [f"#{i + 1}" for i in range(len(sdf))])
            sdf["Conviction %"] = sdf[["Buy %", "Sell %"]].max(axis=1)
        sector_tables[h] = sdf
        stock_tables[h] = pd.concat(trows).reset_index(drop=True) if trows else pd.DataFrame()
    return {"sector": sector_tables, "stock": stock_tables, "sector_flow": sflow, "tilt": {h: tilt(h) for h in INST_HORIZONS}}


def todays_footprint(scan: dict, min_spike=1.5, min_move=0.8):
    """Stocks whose latest session shows a big volume surge -> probable institutional buying / selling."""
    rows = []
    for s, r in scan["results"].items():
        if r["vol_spike"] >= min_spike and abs(r["chg"]) >= min_move:
            rows.append({"Stock": s, "Sector": r.get("sector") or "-", "LTP": round(r["price"], 2), "1D %": round(r["chg"], 2),
                         "Volume x": r["vol_spike"], "CMF20": round(r["cmf"], 2),
                         "Inferred": "BUYING" if r["chg"] > 0 else "SELLING"})
    return pd.DataFrame(rows).sort_values("Volume x", ascending=False) if rows else pd.DataFrame()


# ==============================================================================
# Multi-timeframe candles
# ==============================================================================
_MTF_SPECS = [("15 Min", "5d", "15m", 0.8), ("1 Hour", "1mo", "60m", 1.5), ("4 Hour", "3mo", "60m", 1.5),
              ("1 Day", "1y", "1d", 3.0), ("1 Week", "2y", "1wk", 6.0), ("1 Month", "5y", "1mo", 6.0)]


@st.cache_data(ttl=300, show_spinner=False)
def mtf_table(symbol):
    rows = []
    for name, period, interval, mult in _MTF_SPECS:
        try:
            raw = _yf_history(symbol, period=period, interval=interval)
            intraday = interval in ("15m", "60m")
            data = _clean(raw, intraday=intraday)
            if data is None:
                continue
            if name == "4 Hour":
                data = data.resample("4h", origin="start_day", offset="9h15min").agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
            row = E.mtf_row(name, data, mult)
            if row:
                rows.append(row)
        except Exception:
            continue
    return pd.DataFrame(rows)


def mtf_table_nav(nav: pd.Series):
    rows = []
    for name, rule, mult in [("1 Day", None, 3.0), ("1 Week", "W-FRI", 6.0), ("1 Month", "MS", 6.0)]:
        try:
            s = nav.tail(400) if rule is None else nav
            row = E.mtf_row(name, E.nav_to_ohlc(s, rule), mult)
            if row:
                rows.append(row)
        except Exception:
            continue
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def stock_full(symbol: str):
    """Everything the detail view needs for one stock / index (uses the universe calibration if available)."""
    sym, df = hist(symbol)
    if df is None:
        return None
    try:
        sc = _scan_master_cached()
        cal = sc["calib"]
    except Exception:
        cal = None
    bench_df = _download_daily_cached((BENCH,), "5y").get(BENCH)
    regime, bench = E.market_regime(bench_df)
    name = INDEX_NAMES.get(sym) or STOCK_NAMES.get(sym.replace(".NS", "").replace(".BO", ""), sym)
    res = E.analyze(df, cal, regime, bench.reindex(df.index, method="ffill") if bench is not None else None, name, with_bt=True)
    res["symbol"] = sym
    return res


# ==============================================================================
# Mutual funds (NAV based)
# ==============================================================================
def _mf_search_raw(q):
    j = requests.get("https://api.mfapi.in/mf/search", params={"q": q}, timeout=15).json()
    return [(x["schemeCode"], x["schemeName"]) for x in j]


def _mf_nav_raw3(code):
    j = requests.get(f"https://api.mfapi.in/mf/{code}", timeout=25).json()
    d = pd.DataFrame(j["data"])
    d.index = pd.to_datetime(d["date"], format="%d-%m-%Y")
    s = pd.to_numeric(d["nav"], errors="coerce").dropna().sort_index()
    return j["meta"].get("scheme_category", ""), s, j["meta"].get("scheme_name", "")


def _mf_nav_raw(code):
    cat, s, _ = _mf_nav_raw3(code)
    return cat, s


@st.cache_data(ttl=3600, show_spinner=False)
def mf_find(q):
    try:
        return _mf_search_raw(q)
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def mf_nav(code):
    try:
        return _mf_nav_raw(code)
    except Exception:
        return "", pd.Series(dtype=float)


def _pick_scheme(phrase, schemes):
    toks = [t for t in re.split(r"\W+", phrase.lower()) if t]
    best, best_s = None, -1e9
    for code, name in schemes:
        n = name.lower()
        hit = sum(1 for t in toks if t in n or t.rstrip("s") in n)
        if hit < max(1, int(len(toks) * 0.6)):
            continue
        s = hit * 3 + (6 if "direct" in n else 0) + (3 if "growth" in n else 0)
        s -= 12 if re.search(r"idcw|dividend|payout|reinvest|bonus|segregated", n) else 0
        s -= len(n) / 100
        if s > best_s:
            best, best_s = (code, name), s
    return best


def _resolve_mf_raw(phrase):
    """Thread-safe (no Streamlit cache) search phrase -> (code, Direct-Growth name) or None."""
    schemes = _mf_search_raw(phrase)
    if not schemes:
        schemes = _mf_search_raw(" ".join(phrase.split()[:3]))  # e.g. drop the trailing 'Fund'
    return _pick_scheme(phrase, schemes) if schemes else None


def resolve_mf(phrase):
    """Search phrase -> (scheme code, Direct-Growth scheme name) or None."""
    schemes = mf_find(phrase)
    if not schemes:
        schemes = mf_find(" ".join(phrase.split()[:3]))
    return _pick_scheme(phrase, schemes) if schemes else None


@st.cache_data(ttl=86400, show_spinner=False)
def _mf_codes_cached(category):
    def work(p):
        try:
            return p, _resolve_mf_raw(p)
        except Exception:
            return p, None
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(work, MFU[category]))
    return [(p, r[0], r[1]) for p, r in res if r]


def mf_codes(category):
    return _keep_if_good(_mf_codes_cached, _mf_codes_cached(category), lambda r: not r)


@st.cache_data(ttl=3600, show_spinner=False)
def _scan_mf_cached(category):
    funds = mf_codes(category)

    def work(item):
        try:
            return item, _mf_nav_raw(item[1])
        except Exception:
            return item, None
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = [g for g in ex.map(work, funds) if g[1] is not None]
    navs = [(it, cat, s.tail(1100)) for it, (cat, s) in got if len(s) > 220]
    if not navs:
        return {"results": [], "calib": {}}
    bench_df = _download_daily_cached((BENCH,), "3y").get(BENCH)
    regime, _ = E.market_regime(bench_df)

    frames = {}
    for it, cat, s in navs:
        d = E.ind(E.nav_to_ohlc(s))
        frames[it[1]] = (it, cat, s, d, E.pattern_flags(d))
    peer = pd.concat([f[3][["RET20", "RET63", "RET126"]].add_suffix(f"_{k}") for k, f in frames.items()], axis=1)
    bench = pd.DataFrame({c: peer[[x for x in peer.columns if x.startswith(c + "_")]].median(axis=1) for c in ("RET20", "RET63", "RET126")})

    cal, prepped = E.new_calib(), {}
    for k, (it, cat, s, d, fl) in frames.items():
        b = bench.reindex(d.index, method="ffill")
        sc = E.family_scores(d, fl, regime, b)
        prepped[k] = sc
        for tf in E.TIMEFRAMES:
            fr = d["Close"].shift(-tf["n"]) / d["Close"] - 1
            E.calib_add(cal, tf["label"], sc[tf["family"]].values, fr.values)
    cal = E.calib_finalize(cal)
    results = []
    for k, (it, cat, s, d, fl) in frames.items():
        b = bench.reindex(d.index, method="ffill")
        r = E.analyze_prepped(d, fl, prepped[k], it[2], cal, regime, b)
        _mfify(r)
        r.update({"Fund": it[2], "code": it[1], "category_group": category, "scheme_category": cat,
                  "nav": float(s.iloc[-1]), "nav_date": s.index[-1], "stats": E.mf_stats(s), "short": it[0]})
        results.append(r)
    return {"results": results, "calib": cal}


def _mfify(r):
    """Reword exit rules for NAV (you redeem / reduce, you do not 'square off')."""
    for t in r["tf"].values():
        t["trail"] = t["trail"].replace("Exit on weekly close", "Reduce if weekly NAV closes").replace("Exit on close", "Reduce if NAV closes")
        t["hold"] = t["hold"].replace("Same day - exit by 3:15 PM", "NAV is declared once a day")


def scan_mf(category):
    return _keep_if_good(_scan_mf_cached, _scan_mf_cached(category), lambda r: not r["results"])


def scan_mf_many(categories):
    out = []
    for c in categories:
        out += scan_mf(c)["results"]
    return out


@st.cache_data(ttl=900, show_spinner=False)
def mf_full(code):
    """Detail analysis for any scheme code (NAV based)."""
    try:
        cat, s, fname = _mf_nav_raw3(code)
    except Exception:
        return None
    if len(s) < 130:
        return None
    s = s.tail(1500)
    bench_df = _download_daily_cached((BENCH,), "3y").get(BENCH)
    regime, bench = E.market_regime(bench_df)
    res = E.analyze(E.nav_to_ohlc(s), None, regime, bench.reindex(s.index, method="ffill") if bench is not None else None, "", with_bt=True)
    _mfify(res)
    res.update({"scheme_category": cat, "nav": float(s.iloc[-1]), "nav_date": s.index[-1], "stats": E.mf_stats(s), "navs": s,
                "Fund": fname, "Name": fname, "code": code, "short": fname, "category_group": cat})
    res.pop("_d", None)
    res.pop("_sc", None)
    return res
