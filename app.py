"""
Trader Dashboard Pro - Streamlit entry point.

Pages (nothing from v1 was removed):
  🏠 Market & FII Radar · ⭐ Watchlist & Pinned · 🔍 Search & Multi-TF Engine · 🎯 Stocks (High Conviction)
  💼 Mutual Funds (Ranked) · 🤖 AI Quant Copilot · 📰 News & Forex Factory

Only the page you open is executed (v1 ran all 7 tabs on every click), so the app feels much faster on a phone.
"""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Trader Dashboard | Pro Stock, MF & AI Terminal", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

import copilot as C  # noqa: E402
import data as D  # noqa: E402
import engine as E  # noqa: E402
import macro as M  # noqa: E402
import store  # noqa: E402
import ui  # noqa: E402
from knowledge import IX, MFU, UNI  # noqa: E402

H, esc, STRETCH = ui.H, ui.esc, ui.STRETCH
ui.inject_css()
ui.init_state()

PAGES = ["🏠 Market & FII Radar", "⭐ Watchlist & Pinned", "🔍 Search & Multi-TF Engine", "🎯 Stocks (High Conviction)",
         "💼 Mutual Funds (Ranked)", "🤖 AI Quant Copilot", "📰 News & Forex Factory"]
TF_DESC = {"1 Day": "same-day setups (exit by 3:15 PM)", "5 Trading Days": "short swing - 5 trading days (1 week)", "2 Weeks": "about 10 trading days",
           "2-5 Weeks": "swing - 2 to 5 weeks", "1 Month": "about 21 trading days", "3 Months": "positional - 2 to 3 months", "6 Months+": "long term - 6 months or more"}


def cache_buster():
    st.cache_data.clear()
    st.rerun()


# ==============================================================================
# Shared: picking the best N setups, grouped by expected move
# ==============================================================================
def pick_banded(rows, side, thr, edges, per_band=8, min_total=6):
    """
    rows = [(key, res, tf_row)].  For each expected-move band (3 sections) keep up to `per_band` setups that clear `thr`.
    If fewer than `min_total` clear it overall, top up with the next-best signals (flagged as lower conviction).
    """
    cand = sorted([r for r in rows if r[2]["signal"] == side], key=lambda r: -r[2]["prob"])
    ok = []
    for b in range(3):
        ok += [r for r in cand if r[2]["prob"] >= thr and E.band_of(r[2]["exp_pct"], edges) == b][:per_band]
    ok.sort(key=lambda r: -r[2]["prob"])
    n_ok = len(ok)
    fill = [r for r in cand if r[2]["prob"] < thr][: max(0, min_total - n_ok)]
    return ok + fill, n_ok


def render_banded(chosen, n_ok, edges, titles, card_fn, kp, side, thr):
    ui.lowconf_note(n_ok, len(chosen), thr, side)
    ranks = {r[0]: i + 1 for i, r in enumerate(chosen)}
    for b, title in enumerate(titles):
        items = [r for r in chosen if E.band_of(r[2]["exp_pct"], edges) == b]
        H(f'<div class="band-head"><b>{esc(title[0])}</b><span>{esc(title[1])} · {len(items)} {"setup" if len(items) == 1 else "setups"}</span></div>')
        if not items:
            st.caption("No qualifying setups in this expected-move band right now.")
            continue
        cols = st.columns(3)
        for j, r in enumerate(items):
            with cols[j % 3]:
                card_fn(r, ranks[r[0]], f"{kp}_{side}_{b}_{j}", r[0] in [c[0] for c in chosen[n_ok:]])


# ==============================================================================
# PAGE 1 - Market & FII radar
# ==============================================================================
def page_market():
    ms = ui.market_now()
    try:
        x = D.idx()
        if not x.empty:
            cols = st.columns(4)
            for i, k in enumerate(list(IX)):
                if k in x.columns:
                    cols[i].metric(IX[k], f"{x[k].iloc[-1]:,.1f}", f"{(x[k].iloc[-1] / x[k].iloc[-2] - 1) * 100:+.2f}%")
    except Exception:
        pass

    ui.banner("⚡", "Institutional FII / FPI & DII money-flow radar", "Cash-market flows, streaks and cumulative totals (provisional exchange data).")
    flows_df, src = D.flows()
    live = D.flows_live(src)
    if not live:
        st.warning("Live FII/DII sources are unreachable right now - the flow numbers below are ILLUSTRATIVE placeholders, not real data.")
    L = None
    if flows_df is not None and len(flows_df) > 0:
        L = flows_df.iloc[0]
        dt = f"{L.Date:%d %b %Y}"
        c1, c2, c3 = st.columns(3)
        c1.metric(f"FII / FPI net ({dt})", f"₹{L['FII Net']:,.0f} Cr", "Inflow 🟢" if L["FII Net"] >= 0 else "Outflow 🔴")
        c2.metric(f"DII net ({dt})", f"₹{L['DII Net']:,.0f} Cr", "Inflow 🟢" if L["DII Net"] >= 0 else "Outflow 🔴")
        c3.metric("Combined institutional net", f"₹{L['FII Net'] + L['DII Net']:,.0f} Cr")
        f_streak = sum(1 for v in flows_df["FII Net"] if (v > 0) == (flows_df["FII Net"].iloc[0] > 0))
        d_streak = sum(1 for v in flows_df["DII Net"] if (v > 0) == (flows_df["DII Net"].iloc[0] > 0))
        st.info(f"📊 **Institutional trend:** FII in **{'Buying 🟢' if flows_df['FII Net'].iloc[0] > 0 else 'Selling 🔴'} streak for {f_streak} sessions** | "
                f"DII in **{'Buying 🟢' if flows_df['DII Net'].iloc[0] > 0 else 'Selling 🔴'} streak for {d_streak} sessions** (source: {src})")
        cum = []
        for lb, k in [("1 Day", 1), ("5 Sessions (1 Week)", 5), ("21 Sessions (1 Month)", 21), ("Last 30 Sessions", min(30, len(flows_df)))]:
            if k <= len(flows_df):
                f_net, d_net = round(flows_df.head(k)["FII Net"].sum()), round(flows_df.head(k)["DII Net"].sum())
                cum.append({"Period": lb, "FII Net (₹ Cr)": f_net, "DII Net (₹ Cr)": d_net, "Total Net (₹ Cr)": f_net + d_net,
                            "Market Sentiment Bias": "Bullish 🟢" if f_net + d_net > 0 else "Defensive / Bearish 🔴"})
        st.dataframe(pd.DataFrame(cum), hide_index=True, **STRETCH)
        st.bar_chart(flows_df.head(20).set_index("Date")[["FII Net", "DII Net"]].sort_index(), **STRETCH)

    # ---------------------------------------------------------------- sector / stock radar
    ui.banner("🎯", "Where big players are deploying money - sectors & stocks, with Buy / Sell probability",
              "For the flow date above: which sectors and stocks look accumulated vs distributed, for 1 Day → 6 Months+.")
    with st.spinner("Scanning the stock universe (first load takes a little while)…"):
        scan = D.scan_master()
    fpi_df, periods, _ = D.fpi_sector()
    if not D.fpi_live(periods):
        st.warning("NSDL sector report unreachable - sector flow component is ILLUSTRATIVE; price/volume footprint below is still computed from live prices.")
    if not scan["results"]:
        st.error("Stock price data load nahi ho paya (Yahoo Finance unreachable). 'Refresh Terminal' dabakar dobara try karein.")
    else:
        mx = D.build_inst_matrix(scan, flows_df, fpi_df)
        hz = st.radio("Prediction horizon", list(D.INST_HORIZONS), horizontal=True, index=1, key="inst_hz")
        tilt = mx["tilt"][hz]
        if L is not None:
            st.caption(f"Flow date {L.Date:%d %b %Y} · FII {L['FII Net']:+,.0f} Cr · DII {L['DII Net']:+,.0f} Cr → market tilt {tilt:+.1f} pts on every sector score "
                       f"(score = {int(D._W[hz][0] * 100)}% price confluence + {int(D._W[hz][1] * 100)}% volume/money-flow footprint + {int(D._W[hz][2] * 100)}% NSDL sector flow & FII/DII tilt).")
        sd = mx["sector"][hz]
        cols = ["Rank", "Sector", "FPI Net (Rs Cr, NSDL)", "Flow bias", "Footprint (CMF avg)", "Buy %", "Sell %", "Conviction %", "Verdict", "Top BUY stocks", "Top SELL stocks"]
        st.dataframe(sd[cols], hide_index=True, column_config={
            "Buy %": st.column_config.ProgressColumn("Buy %", min_value=0, max_value=100, format="%d%%"),
            "Sell %": st.column_config.ProgressColumn("Sell %", min_value=0, max_value=100, format="%d%%"),
            "Conviction %": st.column_config.NumberColumn("Conviction %", format="%d%%")}, **STRETCH)

        sec_sel = st.selectbox("Sector drill-down (stocks inside the sector)", list(sd["Sector"]), key="inst_sec")
        stk = mx["stock"][hz]
        stk = stk[stk["Sector"] == sec_sel].copy()
        piv = pd.DataFrame({h: mx["stock"][h].set_index("Stock")["Buy %"] for h in D.INST_HORIZONS})
        stk = stk.merge(piv.add_prefix("Buy% ").reset_index(), on="Stock", how="left")
        show = ["Stock", "Name", "Buy %", "Sell %", "Footprint", "CMF", "Vol x", "1D %", "Calibrated tech prob", "Status", "LTP", "Entry", "Target", "Stop"] + [f"Buy% {h}" for h in D.INST_HORIZONS]
        st.dataframe(stk[show], hide_index=True, **STRETCH)

        st.markdown("**🔮 Forward predictive matrix (live)**")
        rows = []
        style = {"1 Day": "Intraday: buy 15-min breakout above day open, exit by 3:15 PM.", "1 Week": "Short swing (2-5 days): buy pull-backs to EMA9/21.",
                 "1 Month": "Swing / positional: buy above SMA50, trail below EMA21.", "3 Months": "Accumulate on dips; stay above SMA50.",
                 "6 Months+": "Core portfolio building; add on corrections, hold above SMA200."}
        for h in D.INST_HORIZONS:
            s_ = mx["sector"][h]
            if not len(s_):
                continue
            top, bot = s_.iloc[0], s_.iloc[-1]
            rows.append({"Horizon": h, "Accumulation sector": top["Sector"], "Top BUY stocks": top["Top BUY stocks"], "Buy probability": f"{top['Buy %']}%",
                         "Distribution sector": bot["Sector"], "Top SELL stocks": bot["Top SELL stocks"], "Sell probability": f"{bot['Sell %']}%",
                         "Institutional action": f"{top['Flow bias']} flow, footprint {top['Footprint (CMF avg)']:+.2f}. " + style[h],
                         "_c": max(top["Buy %"], bot["Sell %"])})
        fm = pd.DataFrame(rows)
        fm["Conviction rank"] = [f"#{int(r) + 1} ({c}%)" for r, c in zip(fm["_c"].rank(ascending=False, method="first") - 1, fm["_c"])]
        st.dataframe(fm.drop(columns=["_c"]), hide_index=True, **STRETCH)

        fp = D.todays_footprint(scan)
        st.markdown("**👣 Today's inferred big-player footprint (volume surge ≥1.5x with a ≥0.8% move)**")
        if len(fp):
            st.dataframe(fp, hide_index=True, **STRETCH)
        else:
            st.caption("No stock shows a decisive volume-surge footprint in the latest session.")
        st.caption("Stock-level FII/DII buying is NOT published daily. Sector flows come from NSDL (fortnightly); stock-level accumulation/distribution is inferred from price × volume "
                   "(CMF, OBV, volume surges). Treat as a research lens, not a disclosure.")

    # ---------------------------------------------------------------- NSDL, deals, sectors
    if fpi_df is not None and not fpi_df.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("**NSDL sector depository net investment (₹ Crore)**")
            st.dataframe(fpi_df.sort_values("Latest Fortnight", ascending=False), hide_index=True, **STRETCH)
        with c2:
            st.markdown("**Institutional net sector flows**")
            st.bar_chart(fpi_df.set_index("Sector")["Latest Fortnight"], **STRETCH)

    st.markdown("**🤝 Big players' bulk & block deals (high-volume transactions)**")
    deals, dlive = D.bulk_deals()
    if dlive and len(deals):
        st.dataframe(deals.head(15), hide_index=True, **STRETCH)
    else:
        st.warning("NSE deals feed unreachable from this server - showing an ILLUSTRATIVE sample only.")
        st.dataframe(pd.DataFrame([
            {"Date": datetime.today().strftime("%d-%b-%Y"), "Symbol": "TRENT", "Client": "Societe Generale", "Buy/Sell": "BUY", "Qty": "450,000", "Avg Price": "₹3,075.00"},
            {"Date": datetime.today().strftime("%d-%b-%Y"), "Symbol": "KOTAKBANK", "Client": "Morgan Stanley Asia", "Buy/Sell": "BUY", "Qty": "1,200,000", "Avg Price": "₹462.50"},
            {"Date": datetime.today().strftime("%d-%b-%Y"), "Symbol": "TMPV", "Client": "Vanguard Emerging Mkts", "Buy/Sell": "SELL", "Qty": "890,000", "Avg Price": "₹278.20"}]),
            hide_index=True, **STRETCH)

    st.markdown("**⚡ 6-month sector momentum & relative strength**")
    sec_df = D.sectors()
    if not sec_df.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
            st.dataframe(sec_df, hide_index=True, **STRETCH)
        with c2:
            st.bar_chart(sec_df.set_index("Sector")["1M %"], **STRETCH)


# ==============================================================================
# PAGE 2 - Watchlist & pinned
# ==============================================================================
def page_watchlist():
    ui.banner("⭐", "My persistent watchlist & pinned assets", "Live price, signal, probability, status, target and stop for everything you track.")
    wl = st.session_state.watchlist_data
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        new_item = st.text_input("Add to watchlist (stock symbol or mutual-fund name)", placeholder="e.g. INFY, TATAMOTORS, HDFC Mid Cap", key="wl_new")
    with c2:
        item_type = st.selectbox("Asset type", ["Stock / Index", "Mutual Fund"], key="wl_type")
    with c3:
        st.write("")
        if st.button("➕ Add asset", key="wl_add", **STRETCH) and new_item.strip():
            is_f = item_type == "Mutual Fund"
            ui.set_watch(new_item.strip() if is_f else new_item.strip().upper(), True, is_f)
            st.rerun()

    tf = st.radio("Show signals for horizon", E.TF_LABELS, horizontal=True, index=1, key="wl_tf")
    ms = ui.market_now()
    scan = D.scan_master()["results"]
    stocks = wl.get("stocks", [])
    st.markdown(f"#### 📈 Watchlist stocks ({len(stocks)})  {ui.live_chip(ms)}", unsafe_allow_html=True)
    if stocks:
        rows = []
        for sym in stocks:
            res = scan.get(sym) or D.stock_full(D.resolve(sym))
            if not res:
                rows.append({"Stock": sym, "LTP": "n/a"})
                continue
            t = res["tf"][tf]
            rows.append({"Stock": sym, "Pinned": "📌" if sym in wl.get("pinned", []) else "", "LTP": f"₹{res['price']:,.2f}", "1D": f"{res['chg']:+.2f}%",
                         "Signal": t["signal"], "Buy %": f"{t['buy_prob']}%", "Sell %": f"{t['sell_prob']}%", "Probability": f"{t['prob']}%", "Status": t["status"],
                         "Entry": t["entry"], "Target": t["target"], "Stop": t["stop"], "Candle": res["pattern"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, **STRETCH)
        a, b, c = st.columns(3)
        with a:
            sel_open = st.selectbox("Open full analysis", stocks, key="wl_open")
            if st.button("🔍 Full analysis", key="wl_open_btn", type="primary"):
                ui.reset_dialog_state()
                ui.open_detail("stock", sel_open, tf)
        with b:
            sel_remove = st.selectbox("Remove stock", ["Select stock..."] + stocks, key="wl_rm")
            if st.button("🗑️ Remove stock", key="wl_rm_btn") and sel_remove != "Select stock...":
                ui.toggle_watchlist(sel_remove, False)
        with c:
            sel_pin = st.selectbox("Toggle pin", ["Select stock..."] + stocks, key="wl_pin")
            if st.button("📌 Toggle pin", key="wl_pin_btn") and sel_pin != "Select stock...":
                ui.toggle_pin(sel_pin)
    else:
        st.info("Watchlist me koi stock nahi hai. Upar se add karein ya kisi card ke ⭐ button se.")

    funds = wl.get("funds", [])
    st.markdown("---")
    st.markdown(f"#### 💼 Watchlist mutual funds ({len(funds)})")
    mf_tf = tf if tf != "1 Day" else "5 Trading Days"
    for i, fn in enumerate(funds):
        hit = D.resolve_mf(fn)
        r = D.mf_full(hit[0]) if hit else None
        a, b, c, d_, e = st.columns([3.2, 1.6, 1, 1, 1])
        with a:
            if r:
                t = r["tf"][mf_tf]
                st.markdown(f"**{hit[1]}**  \nNAV ₹{r['nav']:,.3f} ({r['chg']:+.2f}%) · {t['signal']} {t['prob']}% · {t['status']}")
            else:
                st.markdown(f"**{fn}**  \n_NAV data unavailable_")
        with b:
            if r:
                st.caption(f"Target NAV {r['tf'][mf_tf]['target']:,.2f}  \nStop NAV {r['tf'][mf_tf]['stop']:,.2f}")
        with c:
            if st.button("📊 Analysis", key=f"wlf_an_{i}", **STRETCH) and hit:
                ui.reset_dialog_state()
                ui.open_detail("mf", hit[0], mf_tf)
        with d_:
            if st.button("📌 Pinned" if fn in wl.get("pinned", []) else "📌 Pin", key=f"wlf_pin_{i}", **STRETCH):
                ui.toggle_pin(fn)
        with e:
            if st.button("🗑️ Remove", key=f"wlf_rm_{i}", **STRETCH):
                ui.toggle_watchlist(fn, True)
    if not funds:
        st.info("Watchlist me koi Mutual Fund nahi hai. Kisi MF card par ⭐ Watch dabayein.")

    st.markdown("---")
    with st.expander("💾 Backup / restore (important on Streamlit Cloud)"):
        st.caption("On Streamlit Community Cloud the server disk resets when the app restarts, so keep a backup. Download the file and upload it again whenever needed "
                   "(or commit `user_watchlist.json` to your GitHub repo).")
        st.download_button("⬇️ Download watchlist.json", json.dumps(store.normalise(wl), indent=2), "user_watchlist.json", "application/json", key="wl_dl")
        up = st.file_uploader("Restore from watchlist.json", type=["json"], key="wl_up")
        if up is not None and st.button("Apply restore", key="wl_apply"):
            try:
                st.session_state.watchlist_data = store.normalise(json.load(up))
                store.save(st.session_state.watchlist_data)
                st.success("Watchlist restored.")
                st.rerun()
            except Exception:
                st.error("Invalid JSON file.")


# ==============================================================================
# PAGE 3 - Search
# ==============================================================================
def page_search():
    ui.banner("🔍", "Deep asset analysis & multi-timeframe candlestick engine",
              "Any stock, index or mutual fund: Buy/Sell probability, entry / target / stop / exit, candle pattern, strategy, news impact, big-player zones.")
    c1, c2 = st.columns([3, 1])
    with c1:
        query = st.text_input("Search asset (stock, index, sector, or mutual fund)", value=st.session_state.selected_stock,
                              placeholder="e.g. RELIANCE, TCS, NIFTY, BANKNIFTY, Parag Parikh Flexi Cap", key="srch_q")
    with c2:
        stype = st.radio("Asset class", ["Stock / Index", "Mutual Fund"], horizontal=True, key="srch_type")
    if not query:
        return
    ql = query.lower()
    if stype == "Mutual Fund" or any(w in ql for w in ("fund", "direct", "growth")):
        schemes = D.mf_find(query)[:30]
        if not schemes:
            st.warning("Koi mutual fund nahi mila. AMC aur category likhein (e.g. 'Parag Parikh Flexi' ya 'HDFC Mid Cap').")
            return
        schemes.sort(key=lambda x: ("direct" not in x[1].lower(), "growth" not in x[1].lower()))
        names = dict(schemes)
        code = st.selectbox("Select mutual fund scheme", [x[0] for x in schemes], format_func=lambda c: names[c], key="srch_mf_pick")
        ui.mf_detail(code, names[code], kp="srch_mf")
    else:
        ui.stock_detail(query, kp="srch")


# ==============================================================================
# PAGE 4 - Stocks
# ==============================================================================
def page_stocks():
    ms = ui.market_now()
    c1, c2, c3 = st.columns([3, 1.4, 1.3])
    with c1:
        view = st.radio("Filter setups by", ["Trading style", "Timeframe horizon"], horizontal=True, key="stk_view")
    with c2:
        cat = st.selectbox("Market category", ["All Categories"] + list(UNI), key="stk_cat")
    with c3:
        thr = st.slider("Min probability %", 55, 90, 70, 1, key="stk_thr")
    if view == "Trading style":
        style = st.radio("Style", ["Short Swing", "Swing", "Intraday", "F&O", "Positional", "Long Term"], horizontal=True, key="stk_style")
        tf = E.STYLE_TO_TF[style]
        title = f"{style} setups"
        if style == "F&O" and cat == "All Categories":
            cat = "F&O"
    else:
        tf = st.radio("Timeframe", E.TF_LABELS, horizontal=True, index=1, key="stk_tf")
        title = f"Stock ideas - {tf}"
    ui.banner("⚡", title, f"Highest-conviction setups ranked by probability · {TF_DESC[tf]} · up to 8 per section; dashed cards are below {thr}% (lower conviction).")

    with st.spinner("Scanning universe and calibrating probabilities on historical hit-rates…"):
        scan = D.scan_master()
    res = scan["results"]
    if not res:
        st.error("Market data abhi load nahi ho paya (Yahoo Finance unreachable). 'Refresh Terminal' dabakar dobara try karein.")
        return
    syms = [s for s in res if cat == "All Categories" or s in set(UNI[cat].split())]
    H(f'{ui.live_chip(ms)} <span class="small-note">&nbsp;{esc(ms["detail"])} · {len(syms)} stocks scanned ({len(scan["failed"])} symbols had no data) · '
      f'Nifty regime: {"🟢 above 50-DMA" if (scan["regime"] or 0) > 0 else "🔴 below 50-DMA" if (scan["regime"] or 0) < 0 else "⚪ range-bound"} · '
      f'data as of {scan["asof"]:%d %b %Y}</span>')
    rows = [(s, res[s], res[s]["tf"][tf]) for s in syms]
    titles = [("Section 1 · expected move 1% - 8%", "smaller, higher-hit-rate moves"), ("Section 2 · expected move 8% - 16%", "bigger swing moves"),
              ("Section 3 · expected move above 16%", "large trend moves")]

    def card(r, rank, kp, low):
        ui.stock_card(r[1], r[0], rank, tf, thr, kp, lowconf=low, ms=ms)

    for side, head in (("BUY", "🟢 Top Buy setups"), ("SELL", "🔴 Top Sell / Short / Avoid setups")):
        chosen, n_ok = pick_banded(rows, side, thr, E.STOCK_BANDS)
        st.markdown(f"## {head} - {len(chosen)} picks ({n_ok} ≥ {thr}%)")
        if not chosen:
            st.info(f"Is category / horizon me abhi koi {side} signal nahi hai.")
            continue
        render_banded(chosen, n_ok, E.STOCK_BANDS, titles, card, re.sub(r"\W", "", f"stk{tf}{cat}"), side, thr)
        st.markdown("---")
    st.caption("Probability = confluence score blended with the measured hit-rate of similar past signals across this universe and the stock itself. "
               "Expected move = distance to Target 1 (ATR-based). Click 🔍 Full Analysis for entry, exit, candles, news and big-player zones.")


# ==============================================================================
# PAGE 5 - Mutual funds
# ==============================================================================
def page_mf():
    ms = ui.market_now()
    c1, c2, c3 = st.columns([3, 1.4, 1.3])
    with c1:
        tfs = {"5 Trading Days (Short Swing)": "5 Trading Days", "2 Weeks": "2 Weeks", "1 Month": "1 Month", "3 Months": "3 Months", "6 Months+": "6 Months+"}
        hz = st.radio("Mutual fund horizon / style", list(tfs), horizontal=True, index=2, key="mf_hz")
        tf = tfs[hz]
    with c2:
        cat = st.selectbox("Category", list(MFU) + ["All Categories (slower)"], key="mf_cat")
    with c3:
        thr = st.slider("Min probability %", 55, 90, 70, 1, key="mf_thr")
    ui.banner("🕒", f"Fund ideas - {hz}", f"NAV-based ranking · {TF_DESC[tf]} · peer-relative momentum, trend and volatility, calibrated on past hit-rates.")
    with st.spinner("Loading NAV histories from AMFI (mfapi.in) and scoring funds…"):
        funds = D.scan_mf_many(list(MFU) if cat.startswith("All") else [cat])
    if not funds:
        st.error("Mutual fund NAV data abhi load nahi ho paya (mfapi.in unreachable). Thodi der baad try karein.")
        return
    H(f'<span class="live-pill live-off"><i></i>NAV declared once a day</span> <span class="small-note">&nbsp;{len(funds)} funds scored · latest NAV '
      f'{max(f["nav_date"] for f in funds):%d %b %Y} · {esc(ms["detail"])}</span>')
    rows = [(f["code"], f, f["tf"][tf]) for f in funds]
    titles = [("Section 1 · expected move 1% - 5%", "steady"), ("Section 2 · expected move 5% - 10%", "stronger"), ("Section 3 · expected move above 10%", "high return potential")]

    def card(r, rank, kp, low):
        ui.mf_card(r[1], rank, tf, thr, kp, lowconf=low, ms=ms)

    for side, head in (("BUY", "🟢 Top Buy / Accumulate funds"), ("SELL", "🔴 Top Sell / Reduce funds")):
        chosen, n_ok = pick_banded(rows, side, thr, E.MF_BANDS)
        st.markdown(f"## {head} - {len(chosen)} picks ({n_ok} ≥ {thr}%)")
        if not chosen:
            st.info(f"Is category me abhi koi {side} signal nahi hai.")
            continue
        render_banded(chosen, n_ok, E.MF_BANDS, titles, card, re.sub(r"\W", "", f"mf{tf}{cat}"), side, thr)
        st.markdown("---")
    st.caption("ℹ️ A category has a limited number of funds, and one fund cannot be both a Buy and a Sell - choose 'All Categories' for the longest lists. "
               "Mutual-fund 'strike prices' do not exist; the full analysis shows NAV zones and Up / Down NAV reach probabilities instead.")


# ==============================================================================
# PAGE 6 - AI copilot
# ==============================================================================
def _gemini_cfg():
    key = st.session_state.get("gem_key", "")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            key = ""
    return {"key": key, "model": st.session_state.get("gem_model", "gemini-2.5-flash")} if key else None


def _chat_cards(msg, idx):
    cards = msg.get("cards") or []
    if not cards:
        return
    scan = D.scan_master()["results"]
    cols = st.columns(3)
    shown = 0
    for k, cd in enumerate(cards[:6]):
        tf = cd["tf"]
        with cols[shown % 3]:
            if cd["kind"] == "stock":
                res = scan.get(cd["key"])
                if res:
                    ui.stock_card(res, cd["key"], k + 1, tf, 70, f"chat{idx}_{k}")
                    shown += 1
            else:
                res = D.mf_full(cd["key"])
                if res:
                    ui.mf_card(res, k + 1, tf if tf in res["tf"] else "3 Months", 70, f"chat{idx}_{k}")
                    shown += 1


def page_ai():
    ui.banner("🤖", "AI Quant Market Copilot & screener assistant",
              "Ask in English or Hinglish. Answers come from the live scans (stocks, funds, flows, macro) - and from Gemini if you add a key.")
    st.markdown("**⚡ Quick suggestions**")
    chips = [("🚀 Top 75%+ swing buys", "Mujhe top 5 high accuracy swing buy stocks batao"), ("⚡ Short swing (5 days)", "Konsi stocks me 1 week short swing setup ban raha hai?"),
             ("🔻 Top sell / avoid setups", "top 5 sell setups 1 month"), ("💼 Best MFs for SIP", "Top mutual funds kaunse hain long term SIP ke liye?"),
             ("📊 FII / DII sectors", "FII aur DII abhi kis sector me buy kar rahe hain?"), ("🌍 Macro events", "Forex Factory high impact events kaunse hain?")]
    quick = None
    for row in (chips[:3], chips[3:]):
        cols = st.columns(3)
        for col, (lab, q) in zip(cols, row):
            if col.button(lab, key=f"chip_{lab}", **STRETCH):
                quick = q
    with st.expander("⚙️ Advanced AI settings (optional Google Gemini)"):
        st.text_input("Gemini API key (leave blank to use the built-in engine)", type="password", key="gem_key")
        st.text_input("Gemini model", value="gemini-2.5-flash", key="gem_model")
        st.caption("Free key: aistudio.google.com. On Streamlit Cloud add `GEMINI_API_KEY` under App settings → Secrets so you never paste it again. "
                   "Gemini only receives the numbers produced by this app's scans.")
    for i, msg in enumerate(st.session_state.chat_history):
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                if msg.get("note") and msg["note"] != "gemini":
                    st.caption(msg["note"])
                _chat_cards(msg, i)
                if msg.get("note") == "gemini" and msg.get("data_text"):
                    with st.expander("📊 Data the answer is based on"):
                        st.markdown(msg["data_text"])
    prompt = st.chat_input("Ask about any stock, sector, mutual fund, flows, news or your watchlist…")
    prompt = quick or prompt
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.spinner("Scanning live data…"):
            out = C.answer(prompt, ui.chat_actions(), _gemini_cfg())
        st.session_state.chat_history.append({"role": "assistant", "content": out["text"], "cards": out.get("cards", []), "data_text": out.get("data_text", ""), "note": out.get("note", "")})
        st.rerun()
    if len(st.session_state.chat_history) > 1 and st.button("🧹 Clear chat", key="chat_clear"):
        st.session_state.chat_history = st.session_state.chat_history[:1]
        st.rerun()


# ==============================================================================
# PAGE 7 - News & Forex Factory
# ==============================================================================
STATIC_MACRO = [
    ("US Fed Interest Rate Decision (FOMC)", "🔴 HIGH IMPACT", "Upcoming / Active Cycle", "88% impact likelihood", "IT (Export), Metals, Financial Services",
     "TCS, INFY, TECHM, HDFCBANK, JSWSTEEL", "Sectoral Tech Funds, International US Feeder Funds, Banking ETFs",
     "Hawkish Fed means pressure on tech valuations and FII debt outflows. Dovish / rate-cut triggers a relief rally in IT & large caps."),
    ("US CPI Inflation Data (MoM & YoY)", "🔴 HIGH IMPACT", "Monthly Release", "84% impact likelihood", "Information Technology, Real Estate, Dollar Index (USD/INR)",
     "INFY, WIPRO, COFORGE, HINDALCO", "Technology Sector Funds, Flexi Cap Funds with US exposure",
     "Cooling US inflation weakens DXY, which strengthens INR and triggers FII equity buying in emerging markets like Nifty."),
    ("US Non-Farm Payrolls (NFP) & Unemployment Rate", "🔴 HIGH IMPACT", "First Friday of Month", "81% impact likelihood", "Global Growth Equities, Tech Outsourcing",
     "TCS, HCLTECH, LTIM", "IT Sector Mutual Funds, Balanced Advantage Funds",
     "Resilient labour data dampens rate-cut hopes; weak jobs raise recession fears. Keep tight trailing SL on high-beta F&O."),
    ("RBI MPC Monetary Policy & Repo Rate Decision", "🔴 HIGH IMPACT (DOMESTIC)", "Bi-Monthly MPC Meet", "92% impact likelihood", "Banking & Financials, Auto, Real Estate, NBFCs",
     "HDFCBANK, ICICIBANK, SBIN, MARUTI, M&M, DLF, GODREJPROP", "Banking Sector Funds, Dynamic Bond & Gilt Funds, Large & Mid Cap Funds",
     "Dovish stance / rate cut boosts bank margins and auto sales. Buy Bank Nifty on confirmation."),
    ("OPEC+ Crude Oil Production & Pricing Meeting", "🟡 MEDIUM-HIGH IMPACT", "Monthly / Scheduled", "78% impact likelihood", "Oil & Gas, Paints, Aviation, Tyres",
     "ONGC, BPCL, IOC, ASIANPAINT, BERGERPAINT, INDIGO", "Energy Funds, Consumption & Infrastructure Funds",
     "Crude slump reduces India's trade deficit: bullish for Paints and Aviation; bearish for upstream explorers (ONGC)."),
]


def _event_card(a):
    when = a["when"].strftime("%a %d %b, %H:%M IST") if a["when"] else "-"
    hrs = a["hours"]
    cd = "" if hrs is None else (f"in {int(hrs)}h {int((hrs % 1) * 60)}m" if hrs >= 0 else f"released {int(-hrs)}h ago")
    imp_col = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#9ca3af", "Holiday": "#6b7280"}.get(a.get("impact"), "#9ca3af")
    bias_col = {"BULLISH": "#10b981", "BEARISH": "#ef4444"}.get(a["bias"], "#f59e0b")
    ups = sorted({x["scope"] for x in a["assets"] if x["direction"] == "UP"})
    dns = sorted({x["scope"] for x in a["assets"] if x["direction"] == "DOWN"})
    pr = max([x["prob"] for x in a["assets"]] or [a["impact_prob"]])
    fc = f' · forecast <b>{esc(a.get("forecast") or "-")}</b> vs previous <b>{esc(a.get("previous") or "-")}</b>'
    H(f'''<div class="macro-card"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
    <span class="macro-title">{esc(a["country"])} · {esc(a["title"])}</span>
    <span style="display:flex;gap:6px;flex-wrap:wrap"><span style="color:{imp_col};font-weight:700;font-size:.78rem;border:1px solid {imp_col};padding:2px 9px;border-radius:12px">{esc(a.get("impact", ""))} impact</span>
    <span style="color:{bias_col};font-weight:700;font-size:.78rem;border:1px solid {bias_col};padding:2px 9px;border-radius:12px">{esc(a["bias"])}</span></span></div>
    <div class="small-note">{when} · {cd}{fc} · <span style="color:#60a5fa;font-weight:600">impact likelihood {a["impact_prob"]}%</span> · {esc(a["rule"])}</div>
    <div style="font-size:.84rem;line-height:1.55;color:#d1d5db;margin-top:6px">
    <div><b style="color:#10b981">▲ Likely UP ({pr}%):</b> {esc(", ".join(ups) or "-")}</div>
    <div><b style="color:#ef4444">▼ Likely DOWN ({pr}%):</b> {esc(", ".join(dns) or "-")}</div>
    <div><b style="color:#3b82f6">Stocks & indices:</b> {esc(a["stocks"])} · {esc(a["indices"])}</div>
    <div><b style="color:#f59e0b">Mutual funds:</b> {esc(a["mfs"])}</div></div>
    <div style="font-size:.82rem;color:#9ca3af;background:#0d1118;border-left:3px solid #f59e0b;padding:8px 12px;margin-top:8px;border-radius:4px">{esc(a["headline"])}<br>💡 <b>Strategic action:</b> {esc(a["action"])}</div></div>''')


def page_news():
    ui.banner("🌍", "Forex Factory & global economic calendar (cross-asset impact predictor)",
              "Real calendar events → impact likelihood, affected sectors / stocks / indices / mutual funds and a suggested action.")
    evs, src = D.ff_calendar()
    label = {"live": "🟢 live Forex Factory feed", "disk-cache": "🟡 last saved copy (feed rate-limited)", "unavailable": "🔴 feed unreachable"}[src]
    st.caption(f"Source: {label}. The free feed refreshes at most every 45 minutes. The weekly feed carries forecast & previous values but not the released 'actual'.")
    if evs:
        an = [M.analyze_event(e) for e in evs]
        c1, c2, c3 = st.columns([2, 2, 1.4])
        imp = c1.multiselect("Impact", ["High", "Medium", "Low", "Holiday"], default=["High", "Medium"], key="ff_imp")
        ccys = sorted({a["country"] for a in an})
        cur = c2.multiselect("Currency / region", ccys, default=[c for c in ccys if c in ("USD", "CNY", "EUR", "GBP", "JPY")] or ccys, key="ff_ccy")
        up_only = c3.toggle("Upcoming only", value=True, key="ff_up")
        sel = [a for a in an if a.get("impact") in imp and a["country"] in cur and (not up_only or a["hours"] is None or a["hours"] > -2)]
        sel.sort(key=lambda a: (a["when"] is None, a["when"]))
        st.caption(f"{len(sel)} events match.")
        for a in sel[:25]:
            _event_card(a)
        if not sel:
            st.info("Filter ke hisab se koi event nahi mila.")
    else:
        st.warning("Forex Factory calendar abhi reachable nahi hai. Neeche static macro playbook dekhein; thodi der baad page refresh karein.")
    with st.expander("📚 Static macro playbook (RBI MPC, FOMC, CPI, NFP, OPEC+) - reference", expanded=not evs):
        for ev in STATIC_MACRO:
            H(f'''<div class="macro-card"><div style="display:flex;justify-content:space-between;align-items:center"><span class="macro-title">{esc(ev[0])}</span>
            <span style="color:#ef4444;font-weight:700;font-size:.8rem;background:rgba(239,68,68,.15);padding:3px 10px;border-radius:12px">{esc(ev[1])}</span></div>
            <div class="small-note">Schedule: {esc(ev[2])} · <span style="color:#60a5fa;font-weight:600">{esc(ev[3])}</span></div>
            <div style="font-size:.84rem;line-height:1.5;color:#d1d5db"><div><b style="color:#f59e0b">Affected sectors:</b> {esc(ev[4])}</div>
            <div><b style="color:#3b82f6">Affected stocks & indices:</b> {esc(ev[5])}</div><div><b style="color:#10b981">Affected mutual funds:</b> {esc(ev[6])}</div></div>
            <div style="font-size:.83rem;color:#9ca3af;background:#0d1118;border-left:3px solid #f59e0b;padding:8px 12px;margin-top:10px;border-radius:4px">💡 <b>Strategic action:</b> {esc(ev[7])}</div></div>''')

    st.markdown("---")
    topic = st.radio("Market news stream", ["Market & Indices", "FII / DII & Flows", "RBI & Monetary Policy", "Global Cues & Wall Street", "Quarterly Results & Earnings"],
                     horizontal=True, key="news_topic")
    qmap = {"Market & Indices": "Sensex Nifty stock market India", "FII / DII & Flows": "FII DII flows India stocks NSE", "RBI & Monetary Policy": "RBI repo rate inflation India economy",
            "Global Cues & Wall Street": "Wall Street US Fed crude oil markets", "Quarterly Results & Earnings": "India quarterly results earnings stocks"}
    items = D.news(qmap[topic])
    if not items:
        st.info("News feed loading… kripya refresh karein.")
    for t, l, s, p in items:
        c = M.classify_news(t)
        H(f'''<div class="news-item"><div style="font-weight:700;font-size:.95rem;margin-bottom:3px"><a href="{esc(l)}" target="_blank" style="color:#60a5fa;text-decoration:none">{esc(t)}</a></div>
        <div class="small-note">{esc(s)} · {esc(p)} · <b>{c["tag"]}</b> · impact likelihood {c["impact"]}% · {esc(c["horizon"])}</div>
        <div style="font-size:.83rem;color:#d1d5db;margin-top:4px"><span style="color:#f59e0b">Sector:</span> {esc(c["sector"])} · <span style="color:#3b82f6">Stocks:</span> {esc(c["stocks"])} · <span style="color:#10b981">MFs:</span> {esc(c["mfs"])}</div>
        <div style="font-size:.8rem;color:#9ca3af;margin-top:3px"><i>Suggested action: {esc(c["action"])}</i></div></div>''')


# ==============================================================================
# Shell
# ==============================================================================
ms = ui.market_now()
col_h1, col_h2 = st.columns([5, 1])
with col_h1:
    H(f'''<div style="display:flex;align-items:center;gap:12px"><span style="font-size:2rem">📈</span><div>
    <h1 style="margin:0;font-size:1.7rem;font-weight:800;color:#fff">TRADER DASHBOARD <span style="font-size:.8rem;color:#f59e0b;background:#2b2210;border:1px solid #78350f;padding:2px 8px;border-radius:6px;vertical-align:middle">PRO QUANT & AI</span></h1>
    <p style="margin:2px 0 0 0;font-size:.82rem;color:#8b949e">Calibrated multi-horizon signals · big-player zones · Up/Down price prediction · live status · AI copilot</p></div></div>''')
with col_h2:
    if st.button("🔄 Refresh Terminal", key="refresh", **STRETCH):
        cache_buster()
H(f'<div style="margin:8px 0 4px 0">{ui.live_chip(ms)} <span class="small-note">&nbsp;{esc(ms["detail"])} · '
  f'{datetime.now(ZoneInfo("Asia/Kolkata")):%d %b %Y, %H:%M} IST</span></div>')
ui.render_pinned_quick_bar()

page = st.radio("Navigation", PAGES, horizontal=True, key="nav", label_visibility="collapsed")
{PAGES[0]: page_market, PAGES[1]: page_watchlist, PAGES[2]: page_search, PAGES[3]: page_stocks,
 PAGES[4]: page_mf, PAGES[5]: page_ai, PAGES[6]: page_news}[page]()

H('<div style="text-align:center;color:#6b7280;font-size:.78rem;border-top:1px solid #1f2633;padding-top:16px;margin-top:30px">'
  '⚠️ <b>Disclaimer:</b> Signals are computed algorithmically for research (RSI, MACD, moving averages, ATR, volume, NAV momentum) and calibrated on historical hit-rates, '
  'which do not guarantee future results. Big-player zones are inferred from price × volume; true institutional entry prices are only disclosed for bulk/block deals. '
  'This is not SEBI-registered investment advice. Trading and investing involve market risk.</div>')
