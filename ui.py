"""
ui.py - shared Streamlit components: theme, status chips, trade cards, the full-analysis views
(used by the Search tab AND by the click-through dialogs of the Stocks / MF tabs) and the pinned bar.
"""
from __future__ import annotations

import html as _html
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data as D
import engine as E
import macro as M
import store
from knowledge import HOLD

_V = tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2])
STRETCH = {"width": "stretch"} if _V >= (1, 50) else {"use_container_width": True}

TF_ICON = {"1 Day": "⚡", "5 Trading Days": "🗓️", "2 Weeks": "🗓️", "2-5 Weeks": "📆", "1 Month": "📆", "3 Months": "🧭", "6 Months+": "🏔️"}

# ==============================================================================
# Theme
# ==============================================================================
CSS = """
<style>
.stApp{background-color:#0b0e14;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1400px}
.pinned-bar{display:flex;gap:10px;overflow-x:auto;padding:6px 2px 10px 2px;margin-bottom:6px;scrollbar-width:thin}
.pinned-pill{background:#121722;border:1px solid #283245;border-radius:10px;padding:7px 13px;display:flex;align-items:center;gap:9px;white-space:nowrap;font-size:.85rem;box-shadow:0 2px 8px rgba(0,0,0,.3);font-variant-numeric:tabular-nums}
.pinned-pill:hover{border-color:#f59e0b}
.section-banner{background:#121721;border:1px solid #232936;border-radius:10px;padding:12px 18px;margin:14px 0 18px 0;display:flex;align-items:center;gap:12px}
.section-banner-title{font-size:1.05rem;font-weight:700;color:#f3f4f6}
.section-banner-desc{font-size:.85rem;color:#9ca3af}
.trade-card{background:#121722;border:1px solid #232936;border-radius:12px;padding:16px;margin-bottom:8px;box-shadow:0 4px 14px rgba(0,0,0,.35);display:flex;flex-direction:column;justify-content:space-between;min-height:330px;position:relative}
.trade-card:hover{border-color:#3b82f6}
.trade-card.lowconf{border-style:dashed;opacity:.92}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;gap:8px}
.card-ticker{font-size:1.2rem;font-weight:800;color:#fff;letter-spacing:.4px}
.card-subtitle{font-size:.8rem;color:#8b949e;margin-top:-2px}
.badge-buy{background:rgba(16,185,129,.16);color:#10b981;border:1px solid rgba(16,185,129,.4);padding:4px 12px;border-radius:20px;font-weight:700;font-size:.78rem;white-space:nowrap}
.badge-sell{background:rgba(239,68,68,.16);color:#ef4444;border:1px solid rgba(239,68,68,.4);padding:4px 12px;border-radius:20px;font-weight:700;font-size:.78rem;white-space:nowrap}
.badge-wait,.badge-hold{background:rgba(156,163,175,.16);color:#9ca3af;border:1px solid rgba(156,163,175,.35);padding:4px 12px;border-radius:20px;font-weight:700;font-size:.78rem}
.card-meta-row{display:flex;align-items:center;gap:6px;margin:6px 0 12px 0;flex-wrap:wrap}
.rank-pill{background:#2b2210;color:#f59e0b;border:1px solid #78350f;padding:2px 8px;border-radius:6px;font-size:.75rem;font-weight:700}
.tag-pill{background:#161b24;color:#9ca3af;border:1px solid #2d3748;padding:2px 8px;border-radius:6px;font-size:.75rem}
.accuracy-pill{background:#111e2e;color:#60a5fa;border:1px solid #1e3a8a;padding:2px 8px;border-radius:6px;font-size:.75rem;font-weight:600}
.confluence-pill{background:#1a2217;color:#4ade80;border:1px solid #166534;padding:2px 8px;border-radius:6px;font-size:.73rem;font-weight:600}
.warn-pill{background:#2a1f10;color:#fbbf24;border:1px solid #92400e;padding:2px 8px;border-radius:6px;font-size:.72rem}
.status{padding:3px 10px;border-radius:6px;font-weight:800;font-size:.72rem;letter-spacing:.3px;white-space:nowrap;border:1px solid transparent}
.st-wait{background:#1c2230;color:#9ca3af;border-color:#374151}
.st-ready{background:#2a2410;color:#fbbf24;border-color:#92400e}
.st-enter{background:#0f3d2b;color:#34d399;border-color:#059669}
.st-rexit{background:#3a2210;color:#fb923c;border-color:#c2410c}
.st-exit{background:#3b1418;color:#f87171;border-color:#b91c1c}
.live-pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:700;border:1px solid #283245;background:#121722;white-space:nowrap}
.live-pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.live-on{color:#34d399;border-color:#065f46}.live-on i{background:#10b981}
.live-off{color:#9ca3af}.live-off i{background:#6b7280}
.live-pre{color:#fbbf24;border-color:#92400e}.live-pre i{background:#f59e0b}
.metric-grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px}
.metric-box{background:#0d1118;border:1px solid #1f2633;border-radius:8px;padding:8px 6px;text-align:center}
.metric-box-label{font-size:.68rem;color:#8b949e;text-transform:uppercase;font-weight:600;margin-bottom:3px}
.metric-box-val{font-size:.98rem;font-weight:700;color:#f3f4f6;font-variant-numeric:tabular-nums}
.metric-box-sub{font-size:.68rem;color:#6b7280}
.metric-val-buy{color:#10b981}.metric-val-sell{color:#ef4444}
.tactical-list{font-size:.79rem;color:#d1d5db;line-height:1.5;margin-bottom:8px}
.tactical-label{color:#9ca3af;font-weight:600}
.thesis-text{font-size:.8rem;color:#9ca3af;line-height:1.4;border-top:1px dashed #232936;padding-top:8px;margin-top:6px}
.band-head{display:flex;align-items:baseline;gap:10px;margin:18px 0 8px 0;padding-bottom:6px;border-bottom:1px solid #1f2633}
.band-head b{font-size:1rem;color:#f3f4f6}.band-head span{font-size:.82rem;color:#8b949e}
.macro-card{background:#121722;border:1px solid #232936;border-radius:10px;padding:14px 16px;margin-bottom:12px}
.macro-title{font-size:1.02rem;font-weight:700;color:#f3f4f6;margin-bottom:4px}
.zone-box{background:#0d1118;border:1px solid #1f2633;border-radius:10px;padding:10px 12px;font-size:.84rem;line-height:1.5}
.zone-buy{border-left:3px solid #10b981}.zone-sell{border-left:3px solid #ef4444}.zone-poc{border-left:3px solid #f59e0b}
.hero{background:#121722;border:1px solid #232936;border-radius:12px;padding:14px 16px;margin:6px 0 12px 0}
.news-item{background:#121722;border:1px solid #1f2633;border-radius:8px;padding:12px 14px;margin-bottom:10px}
.small-note{font-size:.78rem;color:#8b949e}
div[data-testid="stRadio"] div[role="radiogroup"]{gap:6px;flex-wrap:wrap}
@media (max-width:768px){.metric-box-val{font-size:.85rem}.card-ticker{font-size:1.05rem}.trade-card{min-height:0}.block-container{padding-left:.7rem;padding-right:.7rem}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


# ==============================================================================
# Small helpers
# ==============================================================================
def esc(x) -> str:
    return _html.escape(str(x)).replace("$", "&#36;")


def H(s: str):
    """Render a compact HTML snippet (newlines removed so markdown never breaks it)."""
    st.markdown(re.sub(r"\s*\n\s*", "", s.strip()), unsafe_allow_html=True)


def rs(x, d=2):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"₹{x:,.{d}f}"


STATUS_CLS = {"WAIT": "st-wait", "READY FOR ENTRY": "st-ready", "ENTER NOW": "st-enter", "READY FOR EXIT": "st-rexit", "EXIT": "st-exit"}


def status_chip(s: str) -> str:
    return f'<span class="status {STATUS_CLS.get(s, "st-wait")}">{esc(s)}</span>'


def live_chip(ms: dict) -> str:
    cls = {"OPEN": "live-on", "PRE-OPEN": "live-pre"}.get(ms["phase"], "live-off")
    return f'<span class="live-pill {cls}"><i></i>{esc(ms["label"])}</span>'


def market_now() -> dict:
    return E.market_status(holidays=D.market_holidays())


def banner(icon, title, desc):
    H(f'<div class="section-banner"><span style="font-size:1.3rem">{icon}</span><div>'
      f'<div class="section-banner-title">{esc(title)}</div><div class="section-banner-desc">{esc(desc)}</div></div></div>')


def kind_note(text):
    st.markdown(f'<div class="small-note">{text}</div>', unsafe_allow_html=True)


# ==============================================================================
# Watchlist / pins
# ==============================================================================
def init_state():
    ss = st.session_state
    ss.setdefault("watchlist_data", store.load())
    ss.setdefault("selected_stock", "RELIANCE")
    ss.setdefault("selected_mf", None)
    ss.setdefault("chat_history", [{"role": "assistant", "intro": True, "content":
        "👋 Namaste! Main aapka **AI Quant Market Copilot** hoon. Mujhse kisi bhi stock, index, sector ya mutual fund ke baare me poochiye - "
        "jaise *'top 5 short swing buy stocks 75% se upar'*, *'IT sector me swing sell setups'*, *'best flexi cap fund 3 months'*, "
        "*'FII DII kis sector me buy kar rahe hain'* ya *'add TCS to watchlist'*."}])


def _save():
    store.save(st.session_state.watchlist_data)


def set_pin(item, on: bool):
    w = st.session_state.watchlist_data
    pinned = w.get("pinned", [])
    if on and item not in pinned:
        pinned.append(item)
    if not on and item in pinned:
        pinned.remove(item)
    w["pinned"] = pinned
    _save()
    return f"📌 {'Pinned' if on else 'Unpinned'} **{item}**."


def set_watch(item, on: bool, is_fund=False):
    w = st.session_state.watchlist_data
    key = "funds" if is_fund else "stocks"
    items = w.get(key, [])
    if on and item not in items:
        items.append(item)
    if not on and item in items:
        items.remove(item)
    w[key] = items
    _save()
    return f"⭐ {'Added' if on else 'Removed'} **{item}** {'to' if on else 'from'} the watchlist."


def toggle_pin(item, rerun=True):
    on = item not in st.session_state.watchlist_data.get("pinned", [])
    set_pin(item, on)
    st.toast(f"{'Pinned' if on else 'Unpinned'} {item}", icon="📌")
    if rerun:
        st.rerun()


def toggle_watchlist(item, is_fund=False, rerun=True):
    on = item not in st.session_state.watchlist_data.get("funds" if is_fund else "stocks", [])
    set_watch(item, on, is_fund)
    st.toast(f"{'Added' if on else 'Removed'} {item} {'to' if on else 'from'} Watchlist", icon="⭐")
    if rerun:
        st.rerun()


def chat_actions():
    return {"get": lambda: st.session_state.watchlist_data,
            "pin": lambda s, on: set_pin(s, on),
            "watch": lambda s, on: set_watch(s, on, False)}


def reset_dialog_state():
    """Forget horizon / window choices of the previous dialog so every opened analysis starts at its own horizon."""
    for k in [k for k in st.session_state if str(k).startswith("dlg")]:
        del st.session_state[k]


def go_to(page: str):
    st.session_state["nav"] = page


# ==============================================================================
# Pinned quick-radar bar (auto-refreshes every 60 s while the market is live)
# ==============================================================================
def _pinned_bar_body():
    w = st.session_state.watchlist_data
    items = w.get("pinned", [])
    if not items:
        return
    pills = []
    for it in items:
        fund = store.is_fund(it, w)
        q = D.quick_quote(it, fund)
        if q:
            col = "#10b981" if q["chg"] >= 0 else "#ef4444"
            lab = esc(it if len(it) <= 22 else it[:20] + "…")
            price = f"{q['price']:,.2f}" if fund else f"₹{q['price']:,.1f}"
            pills.append(f'<div class="pinned-pill"><span>{"💼" if fund else ""} <b>{lab}</b></span><span>{price}</span>'
                         f'<span style="color:{col};font-weight:700">{q["chg"]:+.2f}%</span></div>')
        else:
            pills.append(f'<div class="pinned-pill"><b>{esc(it)}</b><span class="small-note">n/a</span></div>')
    H('<div style="font-size:.78rem;font-weight:700;color:#f59e0b;margin-bottom:2px">📌 PINNED QUICK-RADAR</div>'
      f'<div class="pinned-bar">{"".join(pills)}</div>')


def render_pinned_quick_bar():
    ms = market_now()
    fn = _pinned_bar_body
    if hasattr(st, "fragment"):
        fn = st.fragment(run_every=60 if ms["open"] else None)(_pinned_bar_body)
    fn()


# ==============================================================================
# Cards
# ==============================================================================
def _wait_rule(res, t):
    lv = res["levels"]
    if t["status"] == "ENTER NOW":
        return f"Trigger active - enter near {t['entry']:,.2f}"
    if t["status"] == "READY FOR EXIT":
        return "Book profits / tighten stop - move is stretched"
    if t["status"] == "EXIT":
        return "Structure weakening - exit longs"
    if "Engulfing" in res["pattern"]:
        return "Confirmation candle above/below the engulfing bar"
    if t["side"] == "BUY":
        return f"Close above {lv['high']:,.2f} (day high) with volume"
    return f"Close below {lv['low']:,.2f} (day low)"


def _zone_line(res):
    z = res.get("zones") or {}
    b = z.get("buy")
    if not b:
        return ""
    st_ = {"above": "price above zone - acts as support", "inside": "price inside zone", "below": "price below zone - overhead supply"}.get(z.get("buy_state"), "")
    return f'<div><span class="tactical-label">Big-player zone:</span> {b["low"]:,.0f}-{b["high"]:,.0f} <span class="small-note">({st_})</span></div>'


def stock_card(res, sym, rank, tf_label, thr, kp, lowconf=False, ms=None):
    t = res["tf"][tf_label]
    ms = ms or market_now()
    side = t["signal"] if t["signal"] != "WAIT" else t["side"]
    badge = "badge-buy" if side == "BUY" else "badge-sell"
    arrow = "↗ " if side == "BUY" else "↘ "
    w = st.session_state.watchlist_data
    hit = f'<div><span class="tactical-label">Backtest hit-rate:</span> {t["hit_pooled"]}% <span class="small-note">(n={t["hit_n"]:,}, base {t["base_rate"]}%)</span></div>' if t.get("hit_pooled") else ""
    conf = "High Confluence 🟢" if t["prob"] >= 80 else "Moderate Confluence 🟡" if t["prob"] >= 70 else "Base Setup ⚪"
    low = f'<span class="warn-pill">below {thr}% - lower conviction</span>' if lowconf else ""
    sub = esc(res.get("Name", sym)) + (f" · {esc(res['sector'])}" if res.get("sector") else "")
    sl_pct = f"-{t['risk_pct']:.1f}%" if side == "BUY" else f"+{t['risk_pct']:.1f}%"
    tg_pct = f"+{t['exp_pct']:.1f}%" if side == "BUY" else f"-{t['exp_pct']:.1f}%"
    H(f'''<div class="trade-card {'lowconf' if lowconf else ''}"><div>
    <div class="card-top"><div><div class="card-ticker">{esc(sym)}</div><div class="card-subtitle">{sub}</div></div><div class="{badge}">{arrow}{side}</div></div>
    <div class="card-meta-row"><span class="rank-pill">#{rank}</span><span class="tag-pill">{TF_ICON.get(tf_label, "")} {esc(tf_label)}</span>
    <span class="accuracy-pill">🎯 probability {t["prob"]}%</span><span class="confluence-pill">{conf}</span>{low}</div>
    <div class="card-meta-row" style="margin-top:-4px">{status_chip(t["status"])}{live_chip(ms)}<span class="small-note">LTP {res["price"]:,.2f} ({res["chg"]:+.2f}%)</span></div>
    <div class="metric-grid-3">
      <div class="metric-box"><div class="metric-box-label">ENTRY</div><div class="metric-box-val">{t["entry"]:,.2f}</div></div>
      <div class="metric-box"><div class="metric-box-label">TARGET</div><div class="metric-box-val metric-val-buy">{t["target"]:,.2f}</div><div class="metric-box-sub">{tg_pct}</div></div>
      <div class="metric-box"><div class="metric-box-label">STOP / SL</div><div class="metric-box-val metric-val-sell">{t["stop"]:,.2f}</div><div class="metric-box-sub">{sl_pct}</div></div></div>
    <div class="tactical-list"><div><span class="tactical-label">Strategy:</span> {esc(t["strategy"])}</div>
    <div><span class="tactical-label">Exit / trailing:</span> {esc(t["trail"])}</div>
    <div><span class="tactical-label">Wait for:</span> {esc(_wait_rule(res, t))}</div>
    <div><span class="tactical-label">Hold:</span> {esc(t["hold"])}</div>{hit}{_zone_line(res)}</div></div>
    <div class="thesis-text">{esc(res["thesis"])}</div></div>''')
    c1, c2, c3 = st.columns([1, 1, 1.25])
    with c1:
        if st.button("📌 Pinned" if sym in w.get("pinned", []) else "📌 Pin", key=f"{kp}_pin", **STRETCH):
            toggle_pin(sym)
    with c2:
        if st.button("⭐ Watching" if sym in w.get("stocks", []) else "⭐ Watch", key=f"{kp}_watch", **STRETCH):
            toggle_watchlist(sym, False)
    with c3:
        if st.button("🔍 Full Analysis", key=f"{kp}_dive", type="primary", **STRETCH):
            st.session_state.selected_stock = sym
            reset_dialog_state()
            open_detail("stock", sym, tf_label)


def mf_card(f, rank, tf_label, thr, kp, lowconf=False, ms=None):
    t = f["tf"][tf_label]
    ms = ms or market_now()
    side = t["signal"] if t["signal"] != "WAIT" else t["side"]
    badge = "badge-buy" if side == "BUY" else "badge-sell"
    name = f["Fund"]
    w = st.session_state.watchlist_data
    short = f.get("short", name)
    low = f'<span class="warn-pill">below {thr}% - lower conviction</span>' if lowconf else ""
    hit = f'<div><span class="tactical-label">Backtest hit-rate:</span> {t["hit_pooled"]}% <span class="small-note">(n={t["hit_n"]:,})</span></div>' if t.get("hit_pooled") else ""
    tg_pct = f"+{t['exp_pct']:.1f}%" if side == "BUY" else f"-{t['exp_pct']:.1f}%"
    H(f'''<div class="trade-card {'lowconf' if lowconf else ''}"><div>
    <div class="card-top"><div><div class="card-ticker" style="font-size:1rem;line-height:1.3">{esc(name)}</div>
    <div class="card-subtitle">{esc(f.get("category_group", ""))} · {esc(f.get("scheme_category", ""))}</div></div><div class="{badge}">{'↗ ' if side == 'BUY' else '↘ '}{'BUY' if side == 'BUY' else 'SELL'}</div></div>
    <div class="card-meta-row"><span class="rank-pill">#{rank}</span><span class="tag-pill">{TF_ICON.get(tf_label, "")} {esc(tf_label)}</span><span class="accuracy-pill">🎯 probability {t["prob"]}%</span>{low}</div>
    <div class="card-meta-row" style="margin-top:-4px">{status_chip(t["status"])}<span class="live-pill live-off"><i></i>NAV {f["nav_date"]:%d %b}</span></div>
    <div class="metric-grid-3">
      <div class="metric-box"><div class="metric-box-label">NAV</div><div class="metric-box-val">{f["nav"]:,.3f}</div></div>
      <div class="metric-box"><div class="metric-box-label">TARGET NAV</div><div class="metric-box-val metric-val-buy">{t["target"]:,.2f}</div><div class="metric-box-sub">{tg_pct}</div></div>
      <div class="metric-box"><div class="metric-box-label">STOP NAV</div><div class="metric-box-val metric-val-sell">{t["stop"]:,.2f}</div></div></div>
    <div class="tactical-list"><div><span class="tactical-label">Strategy:</span> {esc(t["strategy"])}</div>
    <div><span class="tactical-label">Review rule:</span> {esc(t["trail"])}</div>
    <div><span class="tactical-label">1Y / 3M return:</span> {f["stats"].get("1Y %", "-")}% / {f["stats"].get("3M %", "-")}%</div>
    <div><span class="tactical-label">Hold:</span> {esc(HOLD.get(f.get("category_group", ""), t["hold"]))}</div>{hit}</div></div>
    <div class="thesis-text">{esc(f["thesis"])}</div></div>''')
    c1, c2, c3 = st.columns([1, 1, 1.25])
    with c1:
        if st.button("📌 Pinned" if short in w.get("pinned", []) or name in w.get("pinned", []) else "📌 Pin", key=f"{kp}_pin", **STRETCH):
            toggle_pin(short)
    with c2:
        if st.button("⭐ Watching" if short in w.get("funds", []) or name in w.get("funds", []) else "⭐ Watch", key=f"{kp}_watch", **STRETCH):
            toggle_watchlist(short, True)
    with c3:
        if st.button("📊 Full Analysis", key=f"{kp}_dive", type="primary", **STRETCH):
            reset_dialog_state()
            open_detail("mf", f["code"], tf_label)


def lowconf_note(n_qualified, n_shown, thr, side):
    if n_shown and n_qualified < n_shown:
        kind_note(f"{n_qualified} {side} setup(s) cleared {thr}%. The remaining {n_shown - n_qualified} (dashed cards) are the next-best "
                  "signals, shown so the list is never empty - treat them as lower conviction.")


# ==============================================================================
# Charts
# ==============================================================================
def price_chart(d, t=None, bm=None, height=430, title=None):
    w = d.tail(180)
    fig = go.Figure(go.Candlestick(x=w.index, open=w.Open, high=w.High, low=w.Low, close=w.Close, name="Price",
                                   increasing_line_color="#10b981", decreasing_line_color="#ef4444"))
    for col, nm, color in [("S20", "SMA 20", "#f59e0b"), ("S50", "SMA 50", "#3b82f6"), ("S200", "SMA 200", "#a78bfa")]:
        if col in w and w[col].notna().any():
            fig.add_scatter(x=w.index, y=w[col], name=nm, line=dict(color=color, width=1.3))
    if t:
        for y, nm, color, dash in [(t["entry"], "Entry", "#e5e7eb", "dot"), (t["target"], "Target", "#10b981", "dash"), (t["stop"], "Stop", "#ef4444", "dash")]:
            fig.add_hline(y=y, line_dash=dash, line_color=color, line_width=1, annotation_text=nm, annotation_position="right")
    if bm:
        z = bm["zones"]
        if z.get("buy"):
            fig.add_hrect(y0=z["buy"]["low"], y1=z["buy"]["high"], fillcolor="rgba(16,185,129,0.10)", line_width=0,
                          annotation_text="Big-player BUY zone", annotation_position="top left", annotation_font_size=10)
        if z.get("sell"):
            fig.add_hrect(y0=z["sell"]["low"], y1=z["sell"]["high"], fillcolor="rgba(239,68,68,0.10)", line_width=0,
                          annotation_text="Big-player SELL zone", annotation_position="bottom left", annotation_font_size=10)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=26 if title else 8, b=0), xaxis_rangeslider_visible=False, template="plotly_dark",
                      paper_bgcolor="#0b0e14", plot_bgcolor="#121722", title=title,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def profile_chart(bm, height=330):
    prof = bm["zones"].get("profile")
    if not prof:
        return None
    c = bm["price"]
    colors = ["#3b82f6" if x < c else "#f59e0b" for x in prof["centers"]]
    fig = go.Figure(go.Bar(x=prof["profile"], y=prof["centers"], orientation="h", marker_color=colors, name="Volume at price"))
    fig.add_hline(y=c, line_color="#e5e7eb", line_dash="dot", annotation_text=f"LTP {c:,.2f}")
    fig.add_hline(y=prof["poc"], line_color="#f59e0b", annotation_text="POC")
    fig.add_hrect(y0=prof["va_low"], y1=prof["va_high"], fillcolor="rgba(148,163,184,0.08)", line_width=0)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=8, b=0), template="plotly_dark", paper_bgcolor="#0b0e14", plot_bgcolor="#121722",
                      xaxis_title="Traded volume (time for funds)", yaxis_title="Price", showlegend=False)
    return fig


# ==============================================================================
# Shared detail pieces
# ==============================================================================
def _horizon_table(res, funds=False):
    df = E.horizon_frame(res)
    if funds:
        df = df[df["Horizon"] != "1 Day"].copy()
        df = df.rename(columns={"LTP": "NAV"})
    return df


def _hz_config():
    return {"Signal": st.column_config.TextColumn(width="small"), "Status": st.column_config.TextColumn(width="medium"),
            "Exit rule": st.column_config.TextColumn(width="large")}


def plan_block(res, t, tf, funds=False):
    side = t["side"]
    col = "#10b981" if side == "BUY" else "#ef4444"
    unit = "NAV" if funds else "Price"
    rr = (t["exp_pct"] / t["risk_pct"]) if t["risk_pct"] else 0
    H(f'''<div class="hero"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px">
    {status_chip(t["status"])}<span style="font-weight:800;color:{col}">{"↗ BUY / UP side" if side == "BUY" else "↘ SELL / DOWN side"}</span>
    <span class="accuracy-pill">🎯 {t["prob"]}% probability · {esc(tf)}</span><span class="tag-pill">{esc(t["style"])} · {esc(t["hold"])}</span></div>
    <div class="metric-grid-3" style="grid-template-columns:repeat(5,1fr)">
    <div class="metric-box"><div class="metric-box-label">{unit} now</div><div class="metric-box-val">{res["price"]:,.2f}</div></div>
    <div class="metric-box"><div class="metric-box-label">Entry</div><div class="metric-box-val">{t["entry"]:,.2f}</div></div>
    <div class="metric-box"><div class="metric-box-label">Target 1</div><div class="metric-box-val metric-val-buy">{t["target"]:,.2f}</div><div class="metric-box-sub">{t["exp_pct"]:.1f}% away</div></div>
    <div class="metric-box"><div class="metric-box-label">Target 2</div><div class="metric-box-val metric-val-buy">{t["target2"]:,.2f}</div></div>
    <div class="metric-box"><div class="metric-box-label">Stop-loss</div><div class="metric-box-val metric-val-sell">{t["stop"]:,.2f}</div><div class="metric-box-sub">{t["risk_pct"]:.1f}% risk · R:R {rr:.1f}</div></div></div>
    <div class="tactical-list"><div><span class="tactical-label">Exit / trailing rule:</span> {esc(t["trail"])}</div>
    <div><span class="tactical-label">Strategy:</span> {esc(t["strategy"])}</div>
    <div><span class="tactical-label">Candle now:</span> {esc(res["pattern"])} ({esc(res["pattern_action"])}, reliability {res["pattern_acc"]}%) - {esc(res["pattern_note"])}</div></div></div>''')


def backtest_block(t):
    bt = t.get("bt") or {}
    side = t["signal"] if t["signal"] != "WAIT" else t["side"]
    b = bt.get(side) or {}
    c1, c2, c3, c4 = st.columns(4)
    pooled = t.get("hit_pooled")
    c1.metric("Universe hit-rate (similar signals)", f"{pooled}%" if pooled else "-", help=f"{t['hit_n']:,} past signals across the whole universe; baseline for this direction is {t['base_rate']}%." if pooled else None)
    own = t.get("hit_own")
    c2.metric("This asset's own hit-rate", f"{own}%" if own else "-", help=f"{t['hit_own_n']} past signals on this asset (shrunk toward the universe rate)." if own else None)
    if b.get("signals"):
        c3.metric("Target hit before stop", f"{b['win']:.0f}%", help=f"Of {b['signals']} past {side} signals on this asset: target reached without touching the stop within {t['n']} days.")
        c4.metric("Stopped out first", f"{b['loss']:.0f}%", help=f"Expired (neither): {100 - b['win'] - b['loss']:.0f}%. Average return after {t['n']}d: {b['avg']:+.2f}%.")
    else:
        c3.metric("Target hit before stop", "-")
        c4.metric("Stopped out first", "-")
    kind_note("Backtests are in-sample, use today's constituents (survivorship bias) and exclude costs / slippage. "
              "Treat them as a sanity check on the signal, not as a promise of future win-rate.")


def bigmap_block(bm_all, funds=False, kp="bm"):
    """Up / Down price prediction + where big players are positioned."""
    labels = list(bm_all)
    pick = st.radio("Prediction window", labels, horizontal=True, key=f"{kp}_win", index=min(1, len(labels) - 1),
                    format_func=lambda x: {"5 Trading Days": "5 trading days", "1 Month": "1 month", "3 Months": "3 months"}.get(x, x))
    bm = bm_all[pick]
    z = bm["zones"]
    c = bm["price"]
    bias_col = "#10b981" if bm["bias"].startswith("UP") else "#ef4444" if bm["bias"].startswith("DOWN") else "#9ca3af"
    H(f'''<div class="hero"><b style="color:{bias_col}">Bias: {esc(bm["bias"])}</b> &nbsp;·&nbsp; within <b>{bm["n_days"]} trading days</b>:
    <span style="color:#10b981"><b>Up / Buy side</b> - 50% chance to touch <b>{rs(bm["up50"])}</b>, 25% chance to touch <b>{rs(bm["up25"])}</b></span> &nbsp;|&nbsp;
    <span style="color:#ef4444"><b>Down / Sell side</b> - 50% chance to touch <b>{rs(bm["down50"])}</b>, 25% chance to touch <b>{rs(bm["down25"])}</b></span>
    <div class="small-note" style="margin-top:4px">Probabilities are measured: how often this {"fund's NAV" if funds else "stock"} touched those distances within {bm["n_days"]} days in the past
    when its signal looked like it does now ({bm["samples"]:,} comparable days).</div></div>''')

    cu, cd = st.columns(2)
    up = pd.DataFrame(bm["up"]).rename(columns={"level": "Level", "pct": "Move %", "prob": "Touch prob %", "basis": "Basis"})
    dn = pd.DataFrame(bm["down"]).rename(columns={"level": "Level", "pct": "Move %", "prob": "Touch prob %", "basis": "Basis"})
    with cu:
        st.markdown("**🟢 Up / Buy-side prediction (price reach)**")
        st.dataframe(up, hide_index=True, **STRETCH)
    with cd:
        st.markdown("**🔴 Down / Sell-side prediction (price reach)**")
        st.dataframe(dn, hide_index=True, **STRETCH)

    st.markdown("**🏦 Where big players (FII / FPI / DII / HNI) are positioned**" if not funds else "**🏦 NAV acceptance zones (where the fund spent most time)**")
    if funds:
        kind_note("Mutual funds have no traded volume and no 'strike price' - the NAV is simply the value of the portfolio. "
                  "The zones below are time-at-NAV levels; the underlying stock-level institutional positioning is not published per NAV.")
    cols = st.columns(3)
    with cols[0]:
        b = z.get("buy")
        if b and not funds:
            state = {"above": "Price is ABOVE the zone → they are in profit, zone acts as support.", "inside": "Price is INSIDE the zone.",
                     "below": "Price is BELOW the zone → they are under water, expect overhead supply."}.get(z.get("buy_state"), "")
            H(f'<div class="zone-box zone-buy"><b>Probable BUY cost zone</b><br>{rs(b["low"])} - {rs(b["high"])}<br>VWAP {rs(b["vwap"])} · {b["days"]} surge days<br><span class="small-note">{state}</span></div>')
        else:
            H('<div class="zone-box zone-buy"><b>Probable BUY cost zone</b><br><span class="small-note">No volume-surge accumulation days in the last 120 sessions.</span></div>')
    with cols[1]:
        s_ = z.get("sell")
        if s_ and not funds:
            state = {"above": "Price above zone - sellers' cost is below market.", "inside": "Price inside the distribution zone.",
                     "below": "Price below zone → that supply is overhead resistance."}.get(z.get("sell_state"), "")
            H(f'<div class="zone-box zone-sell"><b>Probable SELL / distribution zone</b><br>{rs(s_["low"])} - {rs(s_["high"])}<br>VWAP {rs(s_["vwap"])} · {s_["days"]} surge days<br><span class="small-note">{state}</span></div>')
        else:
            H('<div class="zone-box zone-sell"><b>Probable SELL / distribution zone</b><br><span class="small-note">No volume-surge distribution days in the last 120 sessions.</span></div>')
    with cols[2]:
        p = z.get("profile")
        if p:
            H(f'<div class="zone-box zone-poc"><b>Point of control (most traded price)</b><br>{rs(p["poc"])}<br>Value area {rs(p["va_low"])} - {rs(p["va_high"])}<br>'
              f'<span class="small-note">Footprint: {esc(z.get("footprint", "-"))}' + ("" if funds else f' ({z.get("net_share", 0):+.0f}% net buy-share)') + "</span></div>")
    st.caption("")
    left, right = st.columns([1, 1])
    with left:
        fig = profile_chart(bm)
        if fig is not None:
            st.plotly_chart(fig, **STRETCH)
    with right:
        sdf = pd.DataFrame(bm["structural"])
        if len(sdf):
            sdf = sdf.rename(columns={"name": "Level type", "level": "Price", "side": "Side", "pct": "Move %", "prob": "Touch prob %"})
            st.markdown("**Support / resistance map with reach probability**")
            st.dataframe(sdf.head(10), hide_index=True, **STRETCH)
    kind_note("Stock-level institutional entry prices are NOT published daily. Zones are inferred from volume-surge days (anchored VWAP) and the volume profile; "
              "disclosed bulk / block deals (real prices) are listed below when the NSE feed is reachable.")


def deals_block(symbol):
    df = D.deals_for_symbol(symbol)
    st.markdown("**🤝 Disclosed bulk / block deals (last 120 days, NSE)**")
    if df is None or len(df) == 0:
        st.info("No disclosed bulk/block deals found for this symbol (or the NSE feed is not reachable from this server).")
    else:
        st.dataframe(df.head(15), hide_index=True, **STRETCH)


def news_block(query, side, base_prob=None, key="news"):
    items = D.news(query)
    score, lab = M.news_pressure(items)
    st.markdown("**📰 News impact on this trade**")
    if not items:
        st.info("News feed abhi load nahi hua.")
        return
    adj = int(np.clip(score / 20, -5, 5)) * (1 if side == "BUY" else -1)
    extra = f" → with news overlay ~{int(np.clip(base_prob + adj, 1, 99))}%" if base_prob else ""
    st.markdown(f"News pressure: **{lab}** ({score:+d}) · {'supports' if adj > 0 else 'works against' if adj < 0 else 'is neutral for'} the **{side}** idea{extra}")
    for t, l, s, p in items[:6]:
        c = M.classify_news(t)
        fav = (c["direction"] == "BULLISH") == (side == "BUY") and c["direction"] != "NEUTRAL"
        rel = "supports your side" if fav else "against your side" if c["direction"] != "NEUTRAL" else "neutral"
        H(f'<div class="news-item"><div style="font-weight:700;font-size:.92rem"><a href="{esc(l)}" target="_blank" style="color:#60a5fa;text-decoration:none">{esc(t)}</a></div>'
          f'<div class="small-note">{esc(s)} · {esc(p)} · {c["tag"]} · impact likelihood {c["impact"]}% · {esc(c["horizon"])}</div>'
          f'<div style="font-size:.82rem;color:#d1d5db">Sector: <b style="color:#f59e0b">{esc(c["sector"])}</b> · Stocks: {esc(c["stocks"])} · MFs: {esc(c["mfs"])} · <i>{rel}</i></div>'
          f'<div style="font-size:.8rem;color:#9ca3af"><i>Action: {esc(c["action"])}</i></div></div>')


def drivers_block(res):
    st.markdown("**🧠 Why this signal (factor read-out)**")
    for x in res["drivers"]:
        st.markdown(f"- {x}")


# ==============================================================================
# Full analysis - stocks / indices
# ==============================================================================
def stock_detail(query, kp="srch", default_tf="5 Trading Days"):
    sym = D.resolve(query)
    with st.spinner(f"Analysing {query} (7 horizons, candles, big-player zones)…"):
        res = D.stock_full(sym)
    if res is None:
        st.error(f"'{query}' ka data nahi mila. Valid NSE symbol likhein (e.g. RELIANCE, TCS, INFY, NIFTY).")
        return
    pure = sym.replace(".NS", "").replace(".BO", "")
    is_idx = sym.startswith("^")
    ms = market_now()
    name = res.get("Name") or pure
    if not is_idx:
        name = D.info(sym).get("shortName") or name
    H(f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><span style="font-size:1.35rem;font-weight:800">📈 {esc(name)}</span>'
      f'<span class="tag-pill">{esc(sym)}</span>{live_chip(ms)}<span class="small-note">{esc(ms["detail"])} · last bar {res["asof"]:%d %b %Y}</span></div>')
    w = st.session_state.watchlist_data
    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        if st.button("📌 Pinned" if pure in w.get("pinned", []) else "📌 Pin to top bar", key=f"{kp}_pin", **STRETCH):
            toggle_pin(pure, rerun=(kp == "srch"))
    with b2:
        if st.button("⭐ In Watchlist" if pure in w.get("stocks", []) else "⭐ Add to Watchlist", key=f"{kp}_watch", **STRETCH):
            toggle_watchlist(pure, False, rerun=(kp == "srch"))

    tf = st.radio("Horizon / strategy", E.TF_LABELS, horizontal=True, index=E.TF_LABELS.index(default_tf) if default_tf in E.TF_LABELS else 1, key=f"{kp}_tf",
                  format_func=lambda x: f"{TF_ICON.get(x, '')} {x}")
    t = res["tf"][tf]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("LTP", f"₹{res['price']:,.2f}", f"{res['chg']:+.2f}%")
    c2.metric("Signal", t["signal"], f"Score {t['score']}")
    c3.metric("Buy probability", f"{t['buy_prob']}%")
    c4.metric("Sell probability", f"{t['sell_prob']}%", delta_color="inverse")
    c5.metric("RSI (14)", f"{res['rsi']:.1f}")
    plan_block(res, t, tf)
    if not ms["open"]:
        kind_note("Market is OFFLINE - status and levels are based on the last close and apply to the next session.")

    bm_key = {"1 Day": "5 Trading Days", "5 Trading Days": "5 Trading Days", "2 Weeks": "5 Trading Days", "2-5 Weeks": "1 Month", "1 Month": "1 Month"}.get(tf, "3 Months")
    st.plotly_chart(price_chart(res["_d"], t, res["bigmap"][bm_key]), **STRETCH)

    st.markdown("**🎯 All horizons at a glance (1 Day → 6 Months+)**")
    st.dataframe(_horizon_table(res), hide_index=True, column_config=_hz_config(), **STRETCH)

    st.markdown("**📊 Backtested reliability of this signal**")
    backtest_block(t)

    banner("🏦", "Big-player money zones & Up / Down price prediction",
           "Where FII / FPI / DII / other big players probably built positions, and how far price can go on the up (Buy) and down (Sell) side.")
    bigmap_block(res["bigmap"], kp=f"{kp}_bm")
    if not is_idx:
        deals_block(sym)

    banner("🕯️", "Multi-timeframe candlestick engine (live)", "15 Min, 1 Hour, 4 Hour, 1 Day, 1 Week, 1 Month candles with pattern, action, probability and status.")
    with st.spinner("Scanning intraday + higher timeframe candles…"):
        mtf = D.mtf_table(sym)
    if len(mtf):
        st.dataframe(mtf.drop(columns=[c for c in mtf.columns if c.startswith("_")]), hide_index=True, **STRETCH)
        buys, sells = int((mtf["Action"] == "BUY").sum()), int((mtf["Action"] == "SELL").sum())
        st.markdown(f"Timeframe vote: **{buys} BUY · {sells} SELL · {len(mtf) - buys - sells} WAIT** → "
                    + ("bullish alignment" if buys >= 4 else "bearish alignment" if sells >= 4 else "mixed - prefer the higher timeframe signal"))
    else:
        st.info("Intraday candle data abhi available nahi hai (market closed ya feed unavailable).")

    cl, cr = st.columns([1, 1])
    with cl:
        drivers_block(res)
    with cr:
        st.markdown("**📐 Statistical outlook (±1σ ranges)**")
        st.dataframe(E.outlook_frame(res["_d"]), hide_index=True, **STRETCH)
    news_block(f"{pure if not is_idx else query} share NSE India", t["side"], t["prob"], key=f"{kp}_news")

    if not is_idx:
        inf = D.info(sym)
        fmt = lambda k, m=1: f"{inf[k] * m:,.1f}" if inf.get(k) is not None else "-"
        st.markdown("**🏢 Company fundamental summary**")
        st.dataframe(pd.DataFrame([{"Sector": inf.get("sector", "-"), "Trailing PE": fmt("trailingPE"), "Price to Book": fmt("priceToBook"),
                                    "ROE %": fmt("returnOnEquity", 100), "Debt to Equity": fmt("debtToEquity"), "Market Cap ₹Cr": fmt("marketCap", 1e-7)}]),
                     hide_index=True, **STRETCH)


# ==============================================================================
# Full analysis - mutual funds (NAV based)
# ==============================================================================
def mf_verdict(t, res):
    if t["signal"] == "BUY":
        if t["status"] == "ENTER NOW":
            return "✅ SIP continue + lumpsum in 2-3 tranches (NAV trend and momentum aligned)."
        if t["status"] == "READY FOR EXIT":
            return "⚠️ NAV looks stretched - keep SIP going, avoid fresh lumpsum until a 3-5% dip."
        return "🟡 Prefer SIP / staggered entry; add lumpsum on a close above the trigger."
    if t["signal"] == "SELL" or t["status"] == "EXIT":
        return "🔴 Pause lumpsum, review holding; consider switching to a stronger peer if the weakness persists."
    return "⚪ No edge right now - hold existing units, continue SIP only if the horizon is 3+ years."


def mf_detail(code, name="", kp="srch_mf", default_tf="3 Months"):
    with st.spinner("Loading NAV history and analysing…"):
        res = D.mf_full(code)
    if res is None:
        st.error("Is scheme ka NAV history load nahi ho paya (ya data bahut kam hai).")
        return
    name = res.get("Fund") or name or f"Scheme {code}"
    ms = market_now()
    st.markdown(f"### 💼 {name}")
    st.caption(f"Category: {res['scheme_category']} | AMFI scheme code: {code} | NAV date {res['nav_date']:%d %b %Y}")
    w = st.session_state.watchlist_data
    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        if st.button("📌 Pinned" if name in w.get("pinned", []) else "📌 Pin to top bar", key=f"{kp}_pin", **STRETCH):
            toggle_pin(name, rerun=(kp == "srch_mf"))
    with b2:
        if st.button("⭐ In Watchlist" if name in w.get("funds", []) else "⭐ Add to Watchlist", key=f"{kp}_watch", **STRETCH):
            toggle_watchlist(name, True, rerun=(kp == "srch_mf"))
    tfs = [x for x in E.TF_LABELS if x != "1 Day"]
    tf = st.radio("Horizon / strategy", tfs, horizontal=True, index=tfs.index(default_tf) if default_tf in tfs else 3, key=f"{kp}_tf",
                  format_func=lambda x: f"{TF_ICON.get(x, '')} {x}")
    t = res["tf"][tf]
    H(f'<div class="small-note">{live_chip(ms)} &nbsp; NAV is declared once a day (after market close). Equity-fund order cut-off: 3:00 PM for same-day NAV. {esc(ms["detail"])}</div>')
    s = res["stats"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current NAV", f"₹{res['nav']:,.3f}", f"{res['chg']:+.2f}%")
    c2.metric("Signal", t["signal"], f"Score {t['score']}")
    c3.metric("Buy probability", f"{t['buy_prob']}%")
    c4.metric("Sell / underperform", f"{t['sell_prob']}%", delta_color="inverse")
    c5.metric("1 Year return", f"{s.get('1Y %', 0):+.2f}%")
    plan_block(res, t, tf, funds=True)
    H(f'<div class="hero"><b>SIP vs Lumpsum verdict:</b> {esc(mf_verdict(t, res))}<br><span class="small-note">Target NAV (1-year view): {rs(res["nav"] * (1.14 if t["signal"] == "BUY" else 1.06 if t["signal"] == "WAIT" else 1.02))} (heuristic) · Recommended hold: 3-5+ years for equity funds.</span></div>')

    nav = res["navs"].tail(500)
    fig = go.Figure(go.Scatter(x=nav.index, y=nav.values, name="NAV", line=dict(color="#60a5fa", width=2)))
    for n, color in ((50, "#3b82f6"), (200, "#a78bfa")):
        sm = res["navs"].rolling(n).mean().tail(500)
        fig.add_scatter(x=sm.index, y=sm.values, name=f"SMA {n}", line=dict(color=color, width=1.2))
    for y, nm, color in [(t["entry"], "Entry", "#e5e7eb"), (t["target"], "Target", "#10b981"), (t["stop"], "Stop", "#ef4444")]:
        fig.add_hline(y=y, line_dash="dash", line_color=color, line_width=1, annotation_text=nm, annotation_position="right")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=8, b=0), template="plotly_dark", paper_bgcolor="#0b0e14", plot_bgcolor="#121722",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, **STRETCH)

    st.markdown("**🎯 All horizons at a glance (NAV based)**")
    st.dataframe(_horizon_table(res, funds=True), hide_index=True, column_config=_hz_config(), **STRETCH)
    st.markdown("**📊 Backtested reliability of this signal**")
    backtest_block(t)
    st.markdown("**📈 Returns & risk**")
    st.dataframe(pd.DataFrame([s]), hide_index=True, **STRETCH)

    banner("🏦", "NAV zones & Up / Down NAV prediction", "How far the NAV can go on the up (Buy) and down (Sell) side, with measured touch probabilities.")
    bigmap_block(res["bigmap"], funds=True, kp=f"{kp}_bm")

    banner("🕯️", "NAV candlestick patterns", "Daily / weekly / monthly NAV candles (15-min, 1-hour and 4-hour candles do not exist for mutual funds).")
    mtf = D.mtf_table_nav(res["navs"])
    if len(mtf):
        st.dataframe(mtf.drop(columns=[c for c in mtf.columns if c.startswith("_")]), hide_index=True, **STRETCH)
    cl, cr = st.columns(2)
    with cl:
        drivers_block(res)
    with cr:
        st.markdown("**📐 Statistical outlook (±1σ NAV ranges)**")
        st.dataframe(E.outlook_frame(E.ind(E.nav_to_ohlc(res["navs"]))), hide_index=True, **STRETCH)
    news_block(name.split(" - ")[0] + " mutual fund", t["side"], t["prob"], key=f"{kp}_news")


# ==============================================================================
# Click-through dialog (Stocks / MF / Watchlist / Copilot)
# ==============================================================================
def _detail_body(kind, key, tf):
    if kind == "stock":
        stock_detail(key, kp="dlg", default_tf=tf if tf in E.TF_LABELS else "5 Trading Days")
    else:
        mf_detail(key, kp="dlg_mf", default_tf=tf if tf in E.TF_LABELS else "3 Months")


if hasattr(st, "dialog"):
    @st.dialog("Full analysis", width="large")
    def open_detail(kind, key, tf="5 Trading Days"):
        _detail_body(kind, key, tf)
else:  # very old Streamlit: fall back to an inline panel at the top of the page
    def open_detail(kind, key, tf="5 Trading Days"):
        st.session_state["_inline_detail"] = (kind, key, tf)
        st.rerun()
