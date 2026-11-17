"""
engine.py - quantitative core of the Trader Dashboard (no Streamlit imports).

What is new compared with the first version
-------------------------------------------
* 7 horizons (1 Day, 5 Trading Days, 2 Weeks, 2-5 Weeks, 1 Month, 3 Months, 6 Months+),
  each scored by its own factor family instead of one score reused everywhere.
* Probabilities are CALIBRATED: model confluence is blended with the hit-rate that
  similar signals actually produced in history (pooled over the whole universe and over
  the asset's own history).  Nothing is hard-coded any more.
* Candle-pattern reliability is measured on the asset's own history (shrunk to 50 %).
* Trade-lifecycle status: WAIT / READY FOR ENTRY / ENTER NOW / READY FOR EXIT / EXIT.
* Market live / offline clock for NSE (IST).
"""
from __future__ import annotations

import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
EPS = 1e-9

# ------------------------------------------------------------------------------
# Horizons
# ------------------------------------------------------------------------------
TIMEFRAMES = [
    {"label": "1 Day", "family": "intraday", "n": 1, "style": "Intraday", "hold": "Same day - exit by 3:15 PM"},
    {"label": "5 Trading Days", "family": "short", "n": 5, "style": "Short Swing", "hold": "2-5 trading days (1 week)"},
    {"label": "2 Weeks", "family": "short", "n": 10, "style": "Short Swing+", "hold": "8-10 trading days"},
    {"label": "2-5 Weeks", "family": "swing", "n": 15, "style": "Swing", "hold": "2-5 weeks (10-25 trading days)"},
    {"label": "1 Month", "family": "swing", "n": 21, "style": "Swing", "hold": "about 21 trading days"},
    {"label": "3 Months", "family": "positional", "n": 63, "style": "Positional", "hold": "2-3 months"},
    {"label": "6 Months+", "family": "long", "n": 126, "style": "Long Term", "hold": "6 months or more"},
]
TF_BY_LABEL = {t["label"]: t for t in TIMEFRAMES}
TF_LABELS = [t["label"] for t in TIMEFRAMES]

# Strategy tabs of the Stocks / MF pages -> horizon label
STYLE_TO_TF = {
    "Intraday": "1 Day", "Short Swing": "5 Trading Days", "F&O": "2 Weeks",
    "Swing": "2-5 Weeks", "Positional": "3 Months", "Long Term": "6 Months+",
}
FAMILIES = ["intraday", "short", "swing", "positional", "long"]
STATUSES = ["WAIT", "READY FOR ENTRY", "ENTER NOW", "READY FOR EXIT", "EXIT"]


# ------------------------------------------------------------------------------
# Market clock (NSE cash segment, IST)
# ------------------------------------------------------------------------------
def _fmt_delta(td: timedelta) -> str:
    secs = max(int(td.total_seconds()), 0)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    return f"{h}h {m:02d}m" if h else f"{m}m"


def market_status(now: datetime | None = None, holidays=()) -> dict:
    """Return live / offline state of NSE.  `holidays` = iterable of ISO dates."""
    now = (now or datetime.now(IST)).astimezone(IST)
    hol = set(holidays or ())
    o_t, c_t = time(9, 15), time(15, 30)

    def trading_day(d):
        return d.weekday() < 5 and d.isoformat() not in hol

    today = now.date()
    if trading_day(today):
        if o_t <= now.time() <= c_t:
            close_dt = datetime.combine(today, c_t, tzinfo=IST)
            return {"open": True, "phase": "OPEN", "label": "LIVE",
                    "detail": f"NSE open - closes in {_fmt_delta(close_dt - now)}", "now": now}
        if time(9, 0) <= now.time() < o_t:
            open_dt = datetime.combine(today, o_t, tzinfo=IST)
            return {"open": False, "phase": "PRE-OPEN", "label": "PRE-OPEN",
                    "detail": f"Pre-open session - market opens in {_fmt_delta(open_dt - now)}", "now": now}
    d = today if (trading_day(today) and now.time() < o_t) else today + timedelta(days=1)
    while not trading_day(d):
        d += timedelta(days=1)
    nxt = datetime.combine(d, o_t, tzinfo=IST)
    return {"open": False, "phase": "CLOSED", "label": "OFFLINE",
            "detail": f"NSE closed - opens {nxt:%a %d %b, %H:%M} IST (in {_fmt_delta(nxt - now)})", "now": now}


# ------------------------------------------------------------------------------
# Indicators
# ------------------------------------------------------------------------------
def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=1).mean()


def ind(df: pd.DataFrame) -> pd.DataFrame:
    """EMA/SMA, Bollinger, RSI, MACD, ATR, volume, money-flow, returns, 52-week position."""
    df = df.copy()
    c, h, l = df["Close"].astype(float), df["High"].astype(float), df["Low"].astype(float)
    d = c.diff()

    df["EMA9"], df["EMA21"] = _ema(c, 9), _ema(c, 21)
    for n in (20, 50, 200):
        df[f"S{n}"] = c.rolling(n).mean()

    std = c.rolling(20).std()
    df["BB_MID"] = df["S20"]
    df["BB_UP"] = df["S20"] + 2 * std
    df["BB_LOW"] = df["S20"] - 2 * std
    df["BB_WIDTH"] = (df["BB_UP"] - df["BB_LOW"]) / (df["BB_MID"].abs() + EPS)
    df["BB_SQUEEZE"] = df["BB_WIDTH"] <= df["BB_WIDTH"].rolling(60, min_periods=20).quantile(0.2)

    g = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    ls = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + g / (ls + 1e-12))
    g5 = d.clip(lower=0).ewm(alpha=1 / 5, adjust=False).mean()
    l5 = (-d.clip(upper=0)).ewm(alpha=1 / 5, adjust=False).mean()
    df["RSI5"] = 100 - 100 / (1 + g5 / (l5 + 1e-12))

    df["MACD"] = _ema(c, 12) - _ema(c, 26)
    df["SIG"] = _ema(df["MACD"], 9)
    df["MACD_HIST"] = df["MACD"] - df["SIG"]

    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    df["ATRP"] = df["ATR"] / (c.abs() + EPS) * 100

    vol = df["Volume"].astype(float).fillna(0) if "Volume" in df else pd.Series(0.0, index=df.index)
    if vol.sum() > 0:
        vs = vol.rolling(20).mean()
        df["VOL_SMA20"] = vs
        df["VOL_SPIKE"] = (vol / (vs + EPS)).where(vs > 0, 1.0)
        mfm = ((c - l) - (h - c)) / (h - l + EPS)
        df["CMF20"] = (mfm * vol).rolling(20).sum() / (vol.rolling(20).sum() + EPS)
        obv = (np.sign(d.fillna(0)) * vol).cumsum()
        df["OBV_SLOPE"] = (obv - obv.shift(20)) / (vol.rolling(20).sum() + EPS)
        df["HAS_VOL"] = True
    else:
        df["VOL_SMA20"], df["VOL_SPIKE"], df["CMF20"], df["OBV_SLOPE"] = 0.0, 1.0, 0.0, 0.0
        df["HAS_VOL"] = False

    for n in (1, 5, 10, 20, 63, 126, 252):
        df[f"RET{n}"] = (c / c.shift(n) - 1) * 100
    df["PH1"], df["PL1"] = h.shift(1), l.shift(1)
    df["HH252"] = h.rolling(252, min_periods=60).max()
    df["DD52"] = (c / df["HH252"] - 1) * 100
    df["EXT"] = (c - df["EMA21"]) / (df["ATR"] + EPS)
    return df


# ------------------------------------------------------------------------------
# Candlestick patterns
# ------------------------------------------------------------------------------
PATTERN_DEFS = [  # key, name, action, textbook reliability %
    ("doji", "Doji (Indecision)", "WAIT", 50),
    ("morning_star", "Morning Star (Bullish Reversal)", "BUY", 68),
    ("evening_star", "Evening Star (Bearish Reversal)", "SELL", 67),
    ("bull_engulf", "Bullish Engulfing", "BUY", 66),
    ("bear_engulf", "Bearish Engulfing", "SELL", 65),
    ("hammer", "Hammer (Bullish Reversal)", "BUY", 63),
    ("shooting", "Shooting Star (Bearish)", "SELL", 62),
    ("breakout", "20-Period Breakout", "BUY", 63),
    ("breakdown", "20-Period Breakdown", "SELL", 61),
    ("bull_maru", "Bullish Marubozu", "BUY", 58),
    ("bear_maru", "Bearish Marubozu", "SELL", 58),
]
BULL_REV = ["morning_star", "bull_engulf", "hammer", "bull_maru"]
BEAR_REV = ["evening_star", "bear_engulf", "shooting", "bear_maru"]


def pattern_flags(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Vectorised candle patterns for every bar (True = pattern completed on that bar)."""
    o, h, l, c = (df[k].astype(float) for k in ("Open", "High", "Low", "Close"))
    body = (c - o).abs()
    rng = (h - l) + EPS
    lo_w = np.minimum(o, c) - l
    up_w = h - np.maximum(o, c)
    po, pc = o.shift(1), c.shift(1)
    prior_trend = c.shift(1) / c.shift(6) - 1

    f = pd.DataFrame(index=df.index)
    f["doji"] = body < 0.1 * rng
    f["hammer"] = (lo_w > 2 * body) & (up_w < 0.5 * body) & (prior_trend < 0) & ~f["doji"]
    f["shooting"] = (up_w > 2 * body) & (lo_w < 0.5 * body) & (prior_trend > 0) & ~f["doji"]
    f["bull_engulf"] = (c > o) & (pc < po) & (c >= po) & (o <= pc)
    f["bear_engulf"] = (c < o) & (pc > po) & (c <= po) & (o >= pc)
    mid1 = (o.shift(2) + c.shift(2)) / 2
    small2 = (c.shift(1) - o.shift(1)).abs() < 0.3 * (h.shift(1) - l.shift(1) + EPS)
    f["morning_star"] = (c.shift(2) < o.shift(2)) & small2 & (c > o) & (c > mid1)
    f["evening_star"] = (c.shift(2) > o.shift(2)) & small2 & (c < o) & (c < mid1)
    f["breakout"] = c > h.shift(1).rolling(lookback).max()
    f["breakdown"] = c < l.shift(1).rolling(lookback).min()
    f["bull_maru"] = (body > 0.85 * rng) & (c > o)
    f["bear_maru"] = (body > 0.85 * rng) & (c < o)
    return f.fillna(False)


def pattern_reliability(df: pd.DataFrame, flags: pd.DataFrame, key: str, action: str, n: int = 5):
    """Measured hit-rate of a pattern on this asset's own history, shrunk to 50 %."""
    if key not in flags or action == "WAIT":
        return 50.0, 0
    fr = df["Close"].shift(-n) / df["Close"] - 1
    m = flags[key] & fr.notna()
    cnt = int(m.sum())
    if cnt == 0:
        return 50.0, 0
    hits = int(((fr[m] > 0) if action == "BUY" else (fr[m] < 0)).sum())
    return (hits + 10 * 0.5) / (cnt + 10) * 100, cnt


def _pattern_note(key, b, name, lookback=20):
    hi, lo = f"{b.High:,.2f}", f"{b.Low:,.2f}"
    return {
        "doji": "Candle me indecision hai; confirmation breakout candle ka intezar karein.",
        "hammer": f"Reversal candle ban chuki hai; entry candle high ({hi}) ke upar lein, SL {lo}.",
        "shooting": f"Top par rejection mila hai; short/exit candle low ({lo}) ke breakdown par karein.",
        "bull_engulf": f"Strong buying absorption; buy trigger above {hi}, strict SL {lo}.",
        "bear_engulf": f"Heavy selling pressure; exit long ya short initiate karein below {lo}.",
        "morning_star": f"Confirmed bottom reversal; aggressive buy above {hi}.",
        "evening_star": f"Confirmed top reversal; aggressive exit/short below {lo}.",
        "breakout": "Range breakout confirm; volume support ke sath buy karein, retest par add karein.",
        "breakdown": "Crucial support breakdown; fresh buy avoid karein, short target open.",
        "bull_maru": "Buyers in complete control without upper-shadow resistance.",
        "bear_maru": "Sellers in complete control; strong downside momentum.",
    }.get(key, "")


def detect_candlestick_pattern(df, flags=None, empirical=True, lookback=20):
    """Return (name, action, accuracy %, note) for the LAST candle (signature kept from v1)."""
    if len(df) < 5:
        return "Not enough data", "WAIT", 50, "Data insufficient"
    flags = pattern_flags(df, lookback) if flags is None else flags
    last = flags.iloc[-1]
    b = df.iloc[-1]
    for key, name, action, base in PATTERN_DEFS:
        if bool(last.get(key, False)):
            if key in ("breakout", "breakdown"):
                name = name.replace("20", str(lookback))
            acc = float(base)
            if empirical and len(df) >= 80:
                rate, cnt = pattern_reliability(df, flags, key, action)
                acc = 0.5 * base + 0.5 * rate if cnt else float(base)
            return name, action, int(round(np.clip(acc, 40, 92))), _pattern_note(key, b, name, lookback)
    if len(df) >= 20 and b.Close > df.Close.rolling(20).mean().iloc[-1]:
        return "Trend Continuation (Uptrend)", "BUY", 56, "Trend positive hai; dips par 20-SMA support ke paas accumulate karein."
    return "Trend Continuation (Downtrend)", "SELL", 55, "Trend weak hai; pullbacks par sell-on-rise strategy best hai."


# ------------------------------------------------------------------------------
# Multi-horizon factor scores (-100 .. +100), fully vectorised
# ------------------------------------------------------------------------------
def market_regime(bench_df: pd.DataFrame | None):
    """+1 / 0 / -1 regime series and benchmark returns from the index (Nifty) data."""
    if bench_df is None or len(bench_df) < 60:
        return None, None
    d = ind(bench_df)
    reg = pd.Series(0.0, index=d.index)
    reg[(d.Close > d.S50) & (d.S20 > d.S50)] = 1.0
    reg[(d.Close < d.S50) & (d.S20 < d.S50)] = -1.0
    bench = d[["RET20", "RET63", "RET126"]].copy()
    return reg, bench


def family_scores(d: pd.DataFrame, flags: pd.DataFrame, regime=None, bench=None) -> pd.DataFrame:
    """Score of every strategy family on every bar.  `d` must already contain ind()."""
    idx = d.index
    c = d["Close"]
    zero = pd.Series(0.0, index=idx)

    def S(cond, w, valid=None):
        cond = pd.Series(cond, index=idx).fillna(False).astype(bool)
        out = pd.Series(np.where(cond, float(w), -float(w)), index=idx)
        if valid is not None:
            out = out.where(pd.Series(valid, index=idx).fillna(False).astype(bool), 0.0)
        return out

    def SEL(conds, vals):
        return pd.Series(np.select([pd.Series(x, index=idx).fillna(False).values for x in conds], vals, 0.0), index=idx)

    v50, v200 = d["S50"].notna(), d["S200"].notna()
    reg = zero if regime is None else regime.reindex(idx, method="ffill").fillna(0.0)
    if bench is None:
        rs20 = rs63 = rs126 = zero
    else:
        b = bench.reindex(idx, method="ffill")
        rs20 = (d["RET20"] - b["RET20"]).fillna(0.0)
        rs63 = (d["RET63"] - b["RET63"]).fillna(0.0)
        rs126 = (d["RET126"] - b["RET126"]).fillna(0.0)

    rev = flags[BULL_REV].any(axis=1).astype(float) - flags[BEAR_REV].any(axis=1).astype(float)
    brk = flags["breakout"].astype(float) - flags["breakdown"].astype(float)

    vs = d["VOL_SPIKE"]
    ext_pen = SEL([d["EXT"] > 3.0, d["EXT"] < -3.0], [-8.0, 8.0])

    # ----- short swing (5-10 days) -----
    trend = S(c > d["EMA9"], 8) + S(d["EMA9"] > d["EMA21"], 8) + S(c > d["S50"], 8, v50) + S(d["S50"] > d["S200"], 6, v200)
    mom = (SEL([(d.RSI >= 50) & (d.RSI <= 68), (d.RSI >= 40) & (d.RSI < 50), d.RSI > 75, d.RSI < 35], [15.0, 5.0, -5.0, -15.0])
           + S(d["MACD"] > d["SIG"], 8) + S(d["MACD_HIST"] > d["MACD_HIST"].shift(1), 4) + (d["RET5"].clip(-6, 6)))
    volm = SEL([vs >= 1.5, vs >= 1.1], [12.0, 6.0]) * np.sign(trend)
    short = trend + mom + volm + 10 * rev + 6 * brk + ext_pen + (rs20 * 0.3).clip(-6, 6) + 5 * reg

    # ----- intraday (1 day, daily-bar proxies) -----
    cl_pos = (c - d["Low"]) / (d["High"] - d["Low"] + EPS)
    gap = (d["Open"] - c.shift(1)) / (d["ATR"] + EPS)
    i_sc = (SEL([c > d["PH1"], c < d["PL1"]], [12.0, -12.0]) + SEL([cl_pos > 0.75, cl_pos < 0.25], [10.0, -10.0])
            + SEL([d["RSI5"] > 60, d["RSI5"] < 40], [6.0, -6.0]) + S(c > d["EMA9"], 6) + S(d["MACD_HIST"] > 0, 5)
            + SEL([vs >= 1.5, vs >= 1.1], [15.0, 7.0]) * np.sign(S(c > d["EMA9"], 1) + SEL([cl_pos > 0.5], [1.0]) - 0.5)
            + 12 * rev + 8 * brk + SEL([gap > 0.5, gap < -0.5], [6.0, -6.0])
            + S(c > d["S20"], 6) + S(d["EMA9"] > d["EMA21"], 6) + 5 * reg)
    intraday = i_sc * (d["ATRP"] / 1.2).clip(0.5, 1.0)

    # ----- swing (2-6 weeks) -----
    trend = S(c > d["S20"], 10) + S(d["S20"] > d["S50"], 10, v50) + S(c > d["S50"], 8, v50)
    mom = (SEL([(d.RSI >= 45) & (d.RSI <= 65), d.RSI > 72, d.RSI < 40], [10.0, -6.0, -10.0]) + S(d["MACD"] > d["SIG"], 8)
           + (d["RET20"] * 0.5).clip(-8, 8))
    volm = SEL([vs >= 1.5, vs >= 1.1], [10.0, 5.0]) * np.sign(trend)
    flow = SEL([d["CMF20"] > 0.05, d["CMF20"] < -0.05], [6.0, -6.0])
    swing = trend + mom + volm + flow + 10 * brk + 6 * rev + (rs20 * 0.4).clip(-8, 8) + 5 * reg + 0.5 * ext_pen

    # ----- positional (1-3 months) -----
    positional = (S(d["S50"] > d["S200"], 15, v200) + S(c > d["S50"], 10, v50) + S(c > d["S200"], 8, v200)
                  + (d["RET63"] * 0.5).clip(-10, 10) + (rs63 * 0.4).clip(-10, 10)
                  + SEL([d["DD52"] > -8, d["DD52"] < -30], [6.0, -8.0]) + S(d["MACD"] > 0, 5)
                  + SEL([d["OBV_SLOPE"] > 0.05, d["OBV_SLOPE"] < -0.05], [5.0, -5.0]) + 5 * reg + 5 * rev)

    # ----- long term (6 months +) -----
    long_ = (S(c > d["S200"], 15, v200) + S(d["S50"] > d["S200"], 10, v200) + (d["RET126"] * 0.3).clip(-10, 10)
             + (d["RET252"].fillna(0) * 0.2).clip(-8, 8) + SEL([d["DD52"] > -10, d["DD52"] < -35], [8.0, -8.0])
             + S(d.RSI > 50, 4) + SEL([d["ATRP"] < 3.0], [4.0]) + (rs126 * 0.3).clip(-8, 8) + 3 * reg)

    out = pd.DataFrame({"intraday": intraday, "short": short, "swing": swing,
                        "positional": positional, "long": long_}, index=idx).clip(-100, 100)
    out.iloc[:60] = np.nan  # indicator warm-up
    return out


# ------------------------------------------------------------------------------
# Calibration (pooled hit-rate of past signals)
# ------------------------------------------------------------------------------
BINS = [(30, 45), (45, 60), (60, 75), (75, 101)]


def new_calib():
    return {}


def calib_add(calib: dict, label: str, score, fwd_ret) -> None:
    s, f = np.asarray(score, float), np.asarray(fwd_ret, float)
    ok = np.isfinite(s) & np.isfinite(f)
    s, f = s[ok], f[ok]
    rec = calib.setdefault(label, {"up": 0, "n": 0, "BUY": [[0, 0, 0.0] for _ in BINS], "SELL": [[0, 0, 0.0] for _ in BINS]})
    rec["up"] += int((f > 0).sum())
    rec["n"] += int(len(f))
    for i, (lo, hi) in enumerate(BINS):
        mb = (s >= lo) & (s < hi)
        if mb.any():
            rec["BUY"][i][0] += int((f[mb] > 0).sum()); rec["BUY"][i][1] += int(mb.sum()); rec["BUY"][i][2] += float(f[mb].sum())
        ms = (s <= -lo) & (s > -hi)
        if ms.any():
            rec["SELL"][i][0] += int((f[ms] < 0).sum()); rec["SELL"][i][1] += int(ms.sum()); rec["SELL"][i][2] += float(-f[ms].sum())


def calib_finalize(calib: dict) -> dict:
    out = {}
    for label, rec in calib.items():
        rows = {}
        for side in ("BUY", "SELL"):
            rows[side] = [(lo, hi, (h / n * 100) if n else None, n, (r / n * 100) if n else 0.0)
                          for (lo, hi), (h, n, r) in zip(BINS, rec[side])]
        out[label] = {**rows, "base_up": rec["up"] / rec["n"] * 100 if rec["n"] else 53.0, "n": rec["n"]}
    return out


def calib_lookup(cal, label, side, abs_score):
    """-> (hit-rate %, samples, avg return % after the horizon, base-rate %)."""
    base_up = 53.0
    if not cal or label not in cal:
        return (base_up if side == "BUY" else 100 - base_up), 0, 0.0, (base_up if side == "BUY" else 100 - base_up)
    rec = cal[label]
    base = rec["base_up"] if side == "BUY" else 100 - rec["base_up"]
    best = None
    for lo, hi, rate, n, avg in rec[side]:
        if n >= 25 and rate is not None and lo <= abs_score:
            best = (rate, n, avg, base)  # highest bin that is <= score and has enough samples
    return best if best else (base, 0, 0.0, base)


def own_hit(score: pd.Series, fr: pd.Series, side: str, prior: float, thr: float = 30, k: float = 12):
    """Asset's own historical hit-rate for the same side, shrunk toward the pooled prior."""
    m = (score >= thr if side == "BUY" else score <= -thr) & fr.notna() & score.notna()
    n = int(m.sum())
    if n == 0:
        return prior, 0
    hits = int(((fr[m] > 0) if side == "BUY" else (fr[m] < 0)).sum())
    return (hits + k * prior / 100) / (n + k) * 100, n


# ------------------------------------------------------------------------------
# Backtest of the full trade plan (target vs stop-loss) on one asset
# ------------------------------------------------------------------------------
def plan_stats(d: pd.DataFrame, score: pd.Series, n: int, thr: float = 30) -> dict:
    """How the ATR plan (T = 1.1*sqrt(n)*ATR, SL = 0.55*sqrt(n)*ATR) would have fared."""
    c, h, l, atr = d["Close"], d["High"], d["Low"], d["ATR"]
    fh = h.iloc[::-1].rolling(n, min_periods=n).max().iloc[::-1].shift(-1)
    fl = l.iloc[::-1].rolling(n, min_periods=n).min().iloc[::-1].shift(-1)
    fr = c.shift(-n) / c - 1
    tm, sm = 1.1 * math.sqrt(n), 0.55 * math.sqrt(n)
    out = {}
    for side, mask in (("BUY", score >= thr), ("SELL", score <= -thr)):
        m = mask & fh.notna() & fl.notna() & atr.notna()
        k = int(m.sum())
        if k == 0:
            out[side] = {"signals": 0}
            continue
        if side == "BUY":
            win = (fh >= c + tm * atr) & ~(fl <= c - sm * atr)
            loss = fl <= c - sm * atr
            hit, ret = fr > 0, fr
        else:
            win = (fl <= c - tm * atr) & ~(fh >= c + sm * atr)
            loss = fh >= c + sm * atr
            hit, ret = fr < 0, -fr
        out[side] = {"signals": k, "hit": float(hit[m].mean() * 100), "win": float(win[m].mean() * 100),
                     "loss": float(loss[m].mean() * 100), "avg": float(ret[m].mean() * 100)}
    return out


# ------------------------------------------------------------------------------
# Trade plan, lifecycle status, narrative helpers
# ------------------------------------------------------------------------------
def lifecycle_status(score: float, r) -> str:
    """WAIT / READY FOR ENTRY / ENTER NOW / READY FOR EXIT / EXIT for the recommended direction."""
    ext, rsi = float(r.EXT), float(r.RSI)
    macd_up = r.MACD > r.SIG
    if score >= 30:
        if ext > 3.2 or rsi > 78:
            return "READY FOR EXIT"
        if ext <= 1.6 and r.Close >= r.EMA9 and macd_up:
            return "ENTER NOW"
        return "READY FOR ENTRY"
    if score <= -30:
        if ext < -3.2 or rsi < 22:
            return "READY FOR EXIT"
        if ext >= -1.6 and r.Close <= r.EMA9 and not macd_up:
            return "ENTER NOW"
        return "READY FOR ENTRY"
    if 15 <= score < 30:
        return "READY FOR ENTRY"
    if -30 < score <= -15:
        return "EXIT"
    if rsi > 72:
        return "READY FOR EXIT"
    return "WAIT"


def trailing_rule(family: str, side: str, r) -> str:
    buy = side == "BUY"
    if family == "intraday":
        return "Trail 0.5 ATR - square-off by 3:15 PM"
    if family == "short":
        return f"Exit on close {'below' if buy else 'above'} {r.EMA9:,.2f} (EMA9)"
    if family == "swing":
        return f"Exit on close {'below' if buy else 'above'} {r.EMA21:,.2f} (EMA21)"
    if family == "positional":
        v = r.S50 if pd.notna(r.S50) else r.EMA21
        return f"Exit on close {'below' if buy else 'above'} {v:,.2f} (SMA50)"
    v = r.S200 if pd.notna(r.S200) else r.S50
    return f"Exit on weekly close {'below' if buy else 'above'} {v:,.2f} (SMA200)"


def strategy_name(r, flags_last, side: str, family: str) -> str:
    buy = side == "BUY"
    vs = float(r.VOL_SPIKE)
    if flags_last.get("breakout") and buy:
        return "Breakout + volume expansion" if vs >= 1.3 else "Range breakout (20-bar high)"
    if flags_last.get("breakdown") and not buy:
        return "Breakdown + volume expansion" if vs >= 1.3 else "Range breakdown (20-bar low)"
    if any(flags_last.get(k) for k in (BULL_REV if buy else BEAR_REV)):
        return "Reversal candle at swing extreme" if abs(r.EXT) > 1.5 else "Reversal-pattern confirmation"
    if bool(r.BB_SQUEEZE):
        return "Bollinger squeeze expansion"
    if buy and r.EMA9 > r.EMA21 > r.S50 and not pd.isna(r.S50):
        return "Trend-following (EMA 9>21>SMA50 stack)"
    if (not buy) and r.EMA9 < r.EMA21 < r.S50 and not pd.isna(r.S50):
        return "Trend-following short (EMA stack down)"
    if family in ("positional", "long") and pd.notna(r.S200):
        return "Positional trend (above SMA200)" if buy else "Positional downtrend (below SMA200)"
    if buy and r.RSI < 40:
        return "Oversold mean-reversion bounce"
    if (not buy) and r.RSI > 65:
        return "Overbought fade"
    return "Momentum continuation (MACD + RSI)"


def drivers(r, flags_last, pat_name, rs20, reg_now) -> list[str]:
    """Human-readable factor read-out (why the score is what it is)."""
    out = []
    stack = ("bullish stack (price > EMA9 > EMA21 > SMA50)" if r.Close > r.EMA9 > r.EMA21 > (r.S50 if pd.notna(r.S50) else 0)
             else "bearish stack (price < EMA9 < EMA21 < SMA50)" if r.Close < r.EMA9 < r.EMA21 < (r.S50 if pd.notna(r.S50) else 1e18)
             else "mixed / transitioning")
    out.append(f"Trend: {stack}.")
    out.append(f"Momentum: RSI {r.RSI:.1f}, MACD {'above' if r.MACD > r.SIG else 'below'} signal line.")
    if bool(r.HAS_VOL):
        out.append(f"Volume: {r.VOL_SPIKE:.2f}x the 20-day average; money-flow (CMF20) {r.CMF20:+.2f}.")
    out.append(f"Candle: {pat_name}.")
    if rs20 is not None and not pd.isna(rs20):
        out.append(f"Relative strength vs Nifty (20d): {rs20:+.1f}%.")
    if reg_now is not None:
        out.append("Market regime: Nifty " + ("above its 50-DMA (supportive)." if reg_now > 0 else "below its 50-DMA (headwind)." if reg_now < 0 else "range-bound."))
    out.append(f"Stretch: price is {r.EXT:+.1f} ATR from EMA21 ({'extended - avoid chasing' if abs(r.EXT) > 3 else 'not stretched'}).")
    if pd.notna(r.DD52):
        out.append(f"Position in 52-week range: {r.DD52:.1f}% from the high.")
    return out



# ------------------------------------------------------------------------------
# Big-player money zones + Up / Down price-reach prediction
# ------------------------------------------------------------------------------
TOUCH_GRID = np.array([0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0])


def volume_profile(d: pd.DataFrame, lookback: int = 126, bins: int = 40):
    """Volume-at-price over the last `lookback` bars (time-at-price when volume is absent)."""
    w = d.tail(lookback)
    lo, hi = float(w["Low"].min()), float(w["High"].max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    vols = w["Volume"].astype(float).values if bool(d["HAS_VOL"].iloc[-1]) else np.ones(len(w))
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    prof = np.zeros(bins)
    for L, H, V in zip(w["Low"].values, w["High"].values, vols):
        i0 = max(int(np.searchsorted(edges, L, side="right")) - 1, 0)
        i1 = min(int(np.searchsorted(edges, H, side="right")) - 1, bins - 1)
        prof[i0:i1 + 1] += V / (i1 - i0 + 1)
    if prof.sum() <= 0:
        return None
    poc = int(prof.argmax())
    lo_i = hi_i = poc
    acc = prof[poc]
    while acc < 0.70 * prof.sum() and (lo_i > 0 or hi_i < bins - 1):
        down = prof[lo_i - 1] if lo_i > 0 else -1
        up = prof[hi_i + 1] if hi_i < bins - 1 else -1
        if up >= down:
            hi_i += 1; acc += prof[hi_i]
        else:
            lo_i -= 1; acc += prof[lo_i]
    nodes = [float(centers[i]) for i in range(1, bins - 1)
             if prof[i] >= prof[i - 1] and prof[i] >= prof[i + 1] and prof[i] >= 0.5 * prof.max()]
    return {"centers": centers, "profile": prof, "poc": float(centers[poc]),
            "va_low": float(edges[lo_i]), "va_high": float(edges[hi_i + 1]), "nodes": nodes}


def _anchored_zone(w: pd.DataFrame, mask: pd.Series):
    if int(mask.sum()) == 0:
        return None
    tp = (w["High"] + w["Low"] + w["Close"]) / 3
    v = w["Volume"].astype(float)
    vm = v[mask]
    if vm.sum() <= 0:
        return None
    vwap = float((tp[mask] * vm).sum() / vm.sum())
    spread = float(np.sqrt(((tp[mask] - vwap) ** 2 * vm).sum() / vm.sum()))
    return {"vwap": vwap, "low": vwap - 0.6 * spread, "high": vwap + 0.6 * spread,
            "days": int(mask.sum()), "vol": float(vm.sum()), "last": w.index[mask][-1]}


def institutional_zones(d: pd.DataFrame, lookback: int = 120) -> dict:
    """
    Inferred big-player (FII / DII / HNI) cost zones from tape footprints:
      * BUY footprint  = volume-surge (>=1.8x) up-days closing in the upper half of the range
      * SELL footprint = volume-surge down-days closing in the lower half
    plus the volume profile (POC / value area).  These are INFERENCES - true per-stock
    institutional entry prices are only disclosed for bulk / block deals.
    """
    w = d.tail(lookback)
    c = float(d["Close"].iloc[-1])
    out = {"has_volume": bool(d["HAS_VOL"].iloc[-1]), "buy": None, "sell": None, "profile": None}
    if out["has_volume"]:
        pos = (w["Close"] - w["Low"]) / (w["High"] - w["Low"] + EPS)
        surge = w["VOL_SPIKE"] >= 1.8
        out["buy"] = _anchored_zone(w, surge & (w["Close"] > w["Open"]) & (pos > 0.5))
        out["sell"] = _anchored_zone(w, surge & (w["Close"] < w["Open"]) & (pos < 0.5))
        bv = out["buy"]["vol"] if out["buy"] else 0.0
        sv = out["sell"]["vol"] if out["sell"] else 0.0
        tot = bv + sv
        net = (bv - sv) / tot if tot > 0 else 0.0
        out["net_share"] = round(net * 100, 1)
        out["footprint"] = "Accumulation" if net > 0.2 else "Distribution" if net < -0.2 else "Balanced"
    else:
        out["net_share"], out["footprint"] = 0.0, "n/a (no volume data)"
    out["profile"] = volume_profile(d, lookback=min(126, len(d)))
    if out["buy"]:
        z = out["buy"]
        out["buy_state"] = ("above" if c > z["high"] else "inside" if c >= z["low"] else "below")
    if out["sell"]:
        z = out["sell"]
        out["sell_state"] = ("above" if c > z["high"] else "inside" if c >= z["low"] else "below")
    return out


def touch_curve(d: pd.DataFrame, score: pd.Series, n: int, k: float = 20.0) -> dict:
    """
    Empirical probability that price TOUCHES +m / -m 'units' (unit = sqrt(n) * ATR) within the next
    n bars, measured on this asset's own history and conditioned on the current signal bucket
    (shrunk toward the unconditional frequency).
    """
    c, h, l, atr = d["Close"], d["High"], d["Low"], d["ATR"]
    fh = h.iloc[::-1].rolling(n, min_periods=n).max().iloc[::-1].shift(-1)
    fl = l.iloc[::-1].rolling(n, min_periods=n).min().iloc[::-1].shift(-1)
    unit = math.sqrt(n) * atr
    valid = fh.notna() & fl.notna() & unit.notna() & score.notna()
    cur = float(score.iloc[-1]) if pd.notna(score.iloc[-1]) else 0.0
    cond = valid & ((score >= 30) if cur >= 30 else (score <= -30) if cur <= -30 else (score.abs() < 30))
    nn = int(cond.sum())
    res = {"n": nn, "grid": TOUCH_GRID}
    for name, dist in (("up", (fh - c) / (unit + EPS)), ("down", (c - fl) / (unit + EPS))):
        base = np.array([(dist[valid] >= m).mean() if valid.any() else 0.0 for m in TOUCH_GRID])
        if nn > 0:
            cnd = np.array([(dist[cond] >= m).mean() for m in TOUCH_GRID])
            p = (cnd * nn + k * base) / (nn + k)
        else:
            p = base
        res[name] = np.minimum.accumulate(np.clip(p, 0, 1)) * 100  # touch-prob must fall with distance
    return res


def _prob_at(curve: dict, side: str, dist_units: float) -> float:
    xs = np.r_[0.0, curve["grid"]]
    ys = np.r_[100.0, curve[side]]
    return float(np.interp(max(dist_units, 0.0), xs, ys))


def _level_at(curve: dict, side: str, prob: float):
    """Distance (units) at which touch-probability falls to `prob` %."""
    xs = np.r_[0.0, curve["grid"]]
    ys = np.r_[100.0, curve[side]]
    if prob >= ys[0]:
        return 0.0
    if prob <= ys[-1]:
        return float(xs[-1])
    return float(np.interp(prob, ys[::-1], xs[::-1]))


def big_player_map(d: pd.DataFrame, score: pd.Series, n: int, row: dict | None = None) -> dict:
    """
    Combined view: where big players are (probably) positioned, which levels act as
    support / resistance, and the measured chance of price reaching Up and Down levels
    within `n` trading days.
    """
    r = d.iloc[-1]
    c = float(r["Close"])
    unit = math.sqrt(n) * float(r["ATR"])
    zones = institutional_zones(d)
    curve = touch_curve(d, score, n)

    ups, downs = [], []
    for m in (0.5, 1.0, 1.5, 2.0):
        ups.append({"level": round(c + m * unit, 2), "pct": round(m * unit / c * 100, 2),
                    "prob": round(_prob_at(curve, "up", m), 1), "basis": f"{m:g} x sqrt({n})d-ATR"})
        downs.append({"level": round(c - m * unit, 2), "pct": round(-m * unit / c * 100, 2),
                      "prob": round(_prob_at(curve, "down", m), 1), "basis": f"{m:g} x sqrt({n})d-ATR"})

    # structural levels (support / resistance) with the same measured probabilities
    structural = []
    prof = zones.get("profile")
    cands = []
    if prof:
        cands += [("Volume-profile POC", prof["poc"]), ("Value-area high", prof["va_high"]), ("Value-area low", prof["va_low"])]
        cands += [("High-volume node", x) for x in prof["nodes"]]
    if zones.get("buy"):
        cands += [("Big-player BUY zone (mid)", zones["buy"]["vwap"])]
    if zones.get("sell"):
        cands += [("Big-player SELL zone (mid)", zones["sell"]["vwap"])]
    cands += [("52-week high", float(r["HH252"]) if pd.notna(r["HH252"]) else None),
              ("SMA50", float(r["S50"]) if pd.notna(r["S50"]) else None),
              ("SMA200", float(r["S200"]) if pd.notna(r["S200"]) else None),
              ("20-bar high", float(d["High"].tail(20).max())), ("20-bar low", float(d["Low"].tail(20).min()))]
    seen = set()
    for name, lvl in cands:
        if lvl is None or not np.isfinite(lvl) or abs(lvl - c) / c < 0.002:
            continue
        key = round(lvl, 1)
        if key in seen:
            continue
        seen.add(key)
        side = "up" if lvl > c else "down"
        dist = abs(lvl - c) / (unit + EPS)
        structural.append({"name": name, "level": round(lvl, 2), "side": "UP" if side == "up" else "DOWN",
                           "pct": round((lvl / c - 1) * 100, 2), "prob": round(_prob_at(curve, side, dist), 1)})
    structural.sort(key=lambda x: abs(x["pct"]))

    up50, dn50 = c + _level_at(curve, "up", 50) * unit, c - _level_at(curve, "down", 50) * unit
    up25, dn25 = c + _level_at(curve, "up", 25) * unit, c - _level_at(curve, "down", 25) * unit
    p_up1, p_dn1 = _prob_at(curve, "up", 1.0), _prob_at(curve, "down", 1.0)
    bias = "UP / BUY" if p_up1 > p_dn1 + 3 else "DOWN / SELL" if p_dn1 > p_up1 + 3 else "BALANCED"
    return {"zones": zones, "curve": curve, "up": ups, "down": downs, "structural": structural,
            "up50": round(up50, 2), "down50": round(dn50, 2), "up25": round(up25, 2), "down25": round(dn25, 2),
            "bias": bias, "n_days": n, "samples": curve["n"], "price": c, "unit": unit}

# ------------------------------------------------------------------------------
# Single-asset analysis
# ------------------------------------------------------------------------------
def _tf_row(tf, s, d, r, flags_last, cal, own_fr, sc_series, with_bt):
    n, fam, label = tf["n"], tf["family"], tf["label"]
    s = float(s) if pd.notna(s) else 0.0
    lean = "BUY" if s >= 0 else "SELL"
    signal = "BUY" if s >= 30 else ("SELL" if s <= -30 else "WAIT")
    a = float(r.ATR) if pd.notna(r.ATR) else float(r.Close) * 0.02
    sd = 1 if lean == "BUY" else -1
    tm, sm = 1.1 * math.sqrt(n), 0.55 * math.sqrt(n)
    entry = round(float(r.High if (fam == "intraday" and sd == 1) else r.Low if fam == "intraday" else r.Close), 2)

    if signal == "WAIT":
        buy_prob = int(np.clip(50 + 0.25 * s, 38, 62))  # no clear edge -> probabilities stay near 50/50
        prob, pooled, pooled_n, avg_ret, base, own, own_n = max(buy_prob, 100 - buy_prob), None, 0, 0.0, None, None, 0
    else:
        conf = float(np.clip(50 + 0.44 * abs(s), 50, 95))
        pooled, pooled_n, avg_ret, base = calib_lookup(cal, label, signal, abs(s))
        own, own_n = (own_hit(sc_series, own_fr[n], signal, pooled) if own_fr is not None else (pooled, 0))
        hit = 0.5 * pooled + 0.5 * own
        prob = int(round(0.55 * conf + 0.45 * hit))
        buy_prob = prob if signal == "BUY" else 100 - prob

    row = {
        "label": label, "family": fam, "n": n, "style": tf["style"], "hold": tf["hold"], "score": round(s, 1),
        "signal": signal, "side": lean, "prob": int(prob), "buy_prob": int(buy_prob), "sell_prob": int(100 - buy_prob),
        "entry": entry, "stop": round(entry - sd * sm * a, 2), "target": round(entry + sd * tm * a, 2),
        "target2": round(entry + sd * tm * 1.6 * a, 2),
        "exp_pct": round(abs(tm * a) / max(entry, EPS) * 100, 2),
        "risk_pct": round(abs(sm * a) / max(entry, EPS) * 100, 2),
        "trail": trailing_rule(fam, lean, r),
        "status": lifecycle_status(s, r),
        "strategy": strategy_name(r, flags_last, lean, fam),
        "hit_pooled": None if pooled is None else round(pooled, 1), "hit_n": pooled_n,
        "hit_own": None if own is None else round(own, 1), "hit_own_n": own_n,
        "avg_ret": round(avg_ret, 2), "base_rate": None if base is None else round(base, 1),
    }
    if with_bt:
        row["bt"] = plan_stats(d, sc_series, n)
    return row



def _compact_zones(d):
    try:
        z = institutional_zones(d)
        return {"buy": z.get("buy") and {k: z["buy"][k] for k in ("vwap", "low", "high", "days")},
                "sell": z.get("sell") and {k: z["sell"][k] for k in ("vwap", "low", "high", "days")},
                "net_share": z.get("net_share", 0.0), "footprint": z.get("footprint", "n/a"),
                "poc": z["profile"]["poc"] if z.get("profile") else None,
                "buy_state": z.get("buy_state"), "sell_state": z.get("sell_state")}
    except Exception:
        return {}

def analyze_prepped(d, flags, sc, name="", cal=None, regime=None, bench=None, with_bt=False):
    """Analysis from already computed indicators / flags / scores."""
    r = d.iloc[-1]
    flags_last = flags.iloc[-1]
    own_fr = {tf["n"]: d["Close"].shift(-tf["n"]) / d["Close"] - 1 for tf in TIMEFRAMES}
    tf_rows = {}
    for tf in TIMEFRAMES:
        tf_rows[tf["label"]] = _tf_row(tf, sc[tf["family"]].iloc[-1], d, r, flags_last, cal, own_fr, sc[tf["family"]], with_bt)

    p_name, p_action, p_acc, p_note = detect_candlestick_pattern(d, flags)
    base = tf_rows["5 Trading Days"]
    reg_now = None if regime is None else float(regime.reindex(d.index, method="ffill").iloc[-1]) if len(regime) else None
    rs20 = None
    if bench is not None:
        b = bench.reindex(d.index, method="ffill")
        rs20 = float(d["RET20"].iloc[-1] - b["RET20"].iloc[-1]) if pd.notna(b["RET20"].iloc[-1]) else None

    c = float(r.Close)
    prev = float(d["Close"].iloc[-2]) if len(d) > 1 else c
    res = {
        "Name": name, "price": c, "chg": (c / prev - 1) * 100, "rsi": float(r.RSI), "atr": float(r.ATR),
        "atrp": float(r.ATRP), "vol_spike": round(float(r.VOL_SPIKE), 2), "cmf": float(r.CMF20),
        "obv_slope": float(r.OBV_SLOPE), "ret": {k: (None if pd.isna(r[f"RET{k}"]) else float(r[f"RET{k}"])) for k in (5, 20, 63, 126)},
        "above50": bool(pd.notna(r.S50) and c > r.S50), "ext": float(r.EXT),
        "zones": _compact_zones(d),
        "pattern": p_name, "pattern_action": p_action, "pattern_acc": p_acc, "pattern_note": p_note,
        "tf": tf_rows, "asof": d.index[-1],
        # --- legacy keys used by the first version of the UI -------------------
        "score": base["score"], "signal": base["signal"], "buy_prob": base["buy_prob"], "sell_prob": base["sell_prob"],
        "accuracy": base["prob"],
        "confluence": ("High Confluence 🟢" if base["prob"] >= 80 else "Moderate Confluence 🟡" if base["prob"] >= 70 else "Base Setup ⚪"),
        "drivers": drivers(r, flags_last, p_name, rs20, reg_now), "regime": reg_now, "rs20": rs20,
        "levels": {"ema9": float(r.EMA9), "ema21": float(r.EMA21), "s50": None if pd.isna(r.S50) else float(r.S50),
                   "s200": None if pd.isna(r.S200) else float(r.S200), "bb_up": float(r.BB_UP), "bb_low": float(r.BB_LOW),
                   "high": float(r.High), "low": float(r.Low)},
    }
    res["thesis"] = thesis_text(res, base)
    return res


def thesis_text(res, row):
    nm = res.get("Name") or "This asset"
    if row["signal"] == "BUY":
        return (f"{nm}: {row['strategy']} - RSI {res['rsi']:.0f}, volume {res['vol_spike']:.1f}x, "
                f"candle: {res['pattern']}. Backtested follow-through {row['hit_pooled'] or '-'}% over {row['n']}d.")
    if row["signal"] == "SELL":
        return (f"{nm}: {row['strategy']} - weak structure (RSI {res['rsi']:.0f}), candle: {res['pattern']}. "
                f"Prefer exits / short setups below {res['levels']['ema9']:,.2f}.")
    return f"{nm}: no clean edge (score {row['score']}). Wait for a high-volume break of {res['levels']['high']:,.2f} or {res['levels']['low']:,.2f}."


def analyze(df, cal=None, regime=None, bench=None, name="", with_bt=False):
    """Full analysis of a raw OHLCV frame (public entry point; v1-compatible keys are included)."""
    d = ind(df)
    flags = pattern_flags(d)
    sc = family_scores(d, flags, regime, bench)
    res = analyze_prepped(d, flags, sc, name or getattr(df, "name", ""), cal, regime, bench, with_bt)
    res["plan"] = plan_frame(res)
    res["outlook"] = outlook_frame(d)
    res["_d"], res["_flags"] = d, flags
    res["_sc"] = sc
    res["bigmap"] = {lab: big_player_map(d, sc[TF_BY_LABEL[lab]["family"]], TF_BY_LABEL[lab]["n"]) for lab in ("5 Trading Days", "1 Month", "3 Months")}
    return res


# Legacy-style frames --------------------------------------------------------------
_STYLE_ROWS = [("Intraday", "1 Day"), ("Short Swing", "5 Trading Days"), ("Swing", "2-5 Weeks"),
               ("Positional", "3 Months"), ("Long-term", "6 Months+")]


def plan_frame(res) -> pd.DataFrame:
    rows = []
    for style, lab in _STYLE_ROWS:
        t = res["tf"][lab]
        rows.append([style, t["side"], t["entry"], t["stop"], t["target"], t["trail"], t["hold"],
                     f"{t['prob']}%", t["status"], f"{t['exp_pct']:.1f}%"])
    return pd.DataFrame(rows, columns=["Style", "Side", "Entry", "Stop-loss", "Target", "Trailing SL", "Hold",
                                       "Probability", "Status", "Expected Move"])


def horizon_frame(res) -> pd.DataFrame:
    rows = []
    for lab in TF_LABELS:
        t = res["tf"][lab]
        rows.append({
            "Horizon": lab, "Strategy": t["style"], "Signal": t["signal"],
            "Probability": f"{t['prob']}%", "Buy %": f"{t['buy_prob']}%", "Sell %": f"{t['sell_prob']}%",
            "LTP": round(res["price"], 2), "Entry": t["entry"], "Target": t["target"], "Stop-loss": t["stop"],
            "Exit rule": t["trail"], "Exp. move": f"{t['exp_pct']:.1f}%", "Hold": t["hold"], "Status": t["status"],
        })
    return pd.DataFrame(rows)


def outlook_frame(d: pd.DataFrame) -> pd.DataFrame:
    """Statistical +-1 sigma range per horizon (kept from v1)."""
    C, r = d["Close"], d.iloc[-1]
    c = float(r.Close)
    v = float(C.pct_change().tail(60).std())
    k = lambda *b: sum(1 if x else -1 for x in b)
    g = lambda s, n: (C.iloc[-n] if len(C) >= n else C.iloc[0])
    l200 = pd.notna(r.S200)
    s1 = k(r.MACD > r.SIG, c > C.iloc[-2], r.RSI > 50)
    s5 = k(c > r.S20, c > g(C, 6), r.MACD > 0)
    s21 = k(c > r.S50, c > g(C, 22), r.S20 > r.S50)
    s63 = k(l200 and r.S50 > r.S200, c > g(C, 64), c > r.S50)
    lab = lambda x: "Bullish 🟢" if x >= 2 else "Bearish 🔴" if x <= -2 else "Sideways ⚪"
    return pd.DataFrame(
        [[n, lab(s), f"{c * (1 - v * dd ** .5):,.1f} - {c * (1 + v * dd ** .5):,.1f}", f"{int(np.clip(50 + s * 14, 25, 95))}%"]
         for n, s, dd in [("1 Day", s1, 1), ("1 Week", s5, 5), ("1 Month", s21, 21), ("3 Months", s63, 63)]],
        columns=["Horizon", "Bias", "Likely Range (+-1 sigma)", "Confluence"])


# ------------------------------------------------------------------------------
# Multi-timeframe candle engine (15m, 1h, 4h, 1d, 1w, 1m)
# ------------------------------------------------------------------------------
def mtf_row(tf_name: str, data: pd.DataFrame, mult: float):
    if data is None or len(data) < 12:
        return None
    d = ind(data)
    flags = pattern_flags(d)
    sc = family_scores(d, flags)["short"]
    s = float(sc.iloc[-1]) if pd.notna(sc.iloc[-1]) else 0.0
    p_name, p_action, p_acc, p_note = detect_candlestick_pattern(d, flags)
    pd_dir = 1 if p_action == "BUY" else -1 if p_action == "SELL" else 0
    total = s + 18 * pd_dir
    action = "BUY" if total >= 25 else "SELL" if total <= -25 else "WAIT"
    r = d.iloc[-1]
    c = float(r.Close)
    a = float(r.ATR) if pd.notna(r.ATR) else c * 0.01
    sd = 1 if action == "BUY" else -1 if action == "SELL" else 0
    t1 = round(c + sd * mult * a, 2) if sd else round(c * 1.01, 2)
    sl = round(c - sd * 0.7 * mult * a, 2) if sd else round(c * 0.99, 2)
    prob = int(round(np.clip(0.5 * np.clip(50 + 0.4 * abs(total), 50, 90) + 0.5 * p_acc, 45, 90))) if action != "WAIT" else int(p_acc)
    stt = lifecycle_status(total, r)
    guidance = p_note if p_action != "WAIT" else "Indecision - wait for a decisive candle close."
    return {"Timeframe": tf_name, "LTP": round(c, 2), "Pattern": p_name, "Action": action, "Probability": f"{prob}%",
            "Target": t1, "Stop Loss": sl, "Status": stt, "Guidance": guidance, "_prob": prob, "_score": round(total, 1)}


# ------------------------------------------------------------------------------
# Mutual fund helpers (NAV based)
# ------------------------------------------------------------------------------
def nav_to_ohlc(s: pd.Series, rule: str | None = None) -> pd.DataFrame:
    s = s.dropna().astype(float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if rule is None:
        df = pd.DataFrame({"Close": s})
        df["Open"] = s.shift(1).fillna(s)
        df["High"] = df[["Open", "Close"]].max(axis=1)
        df["Low"] = df[["Open", "Close"]].min(axis=1)
    else:
        g = s.resample(rule)
        df = pd.DataFrame({"Open": g.first(), "High": g.max(), "Low": g.min(), "Close": g.last()}).dropna()
    df["Volume"] = 0.0
    return df[["Open", "High", "Low", "Close", "Volume"]]


def mf_stats(s: pd.Series) -> dict:
    if len(s) == 0:
        return {}
    r = {"Latest NAV": round(float(s.iloc[-1]), 3)}
    for n, k in [(7, "1W %"), (21, "1M %"), (63, "3M %"), (126, "6M %"), (252, "1Y %")]:
        if len(s) > n:
            r[k] = round((s.iloc[-1] / s.iloc[-1 - n] - 1) * 100, 2)
    if len(s) > 756:
        r["3Y CAGR %"] = round(((s.iloc[-1] / s.iloc[-757]) ** (1 / 3) - 1) * 100, 2)
    r["Vol %"] = round(float(s.pct_change().std() * (252 ** 0.5) * 100), 2)
    r["MaxDD %"] = round(float((s / s.cummax() - 1).min() * 100), 2)
    r["Trend"] = "Up 🟢" if len(s) > 50 and s.iloc[-1] > s.tail(50).mean() else "Down 🔴"
    return r


# ------------------------------------------------------------------------------
# Convenience
# ------------------------------------------------------------------------------
def band_of(pct: float, edges) -> int:
    """0,1,2 -> which expected-move band a setup falls in."""
    return 0 if pct < edges[0] else 1 if pct < edges[1] else 2


STOCK_BANDS = (8.0, 16.0)   # 1-8 %, 8-16 %, >16 %
MF_BANDS = (5.0, 10.0)      # 1-5 %, 5-10 %, >10 %
