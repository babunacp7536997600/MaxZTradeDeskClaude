# 📈 Trader Dashboard Pro — Stocks, Mutual Funds, Big-Player Zones & AI Copilot

An institutional-style research terminal for Indian equities (NSE), indices and mutual funds, built with **Streamlit + Plotly**.
Runs on a laptop, on your phone (same Wi-Fi) and 24x7 on **Streamlit Community Cloud**.

> ⚠️ Research tool, not investment advice. No software can guarantee a win-rate. See **"How to read the numbers"** below.

---

## ✨ What's in the app (nothing from v1 was removed)

| Page | What it does |
|---|---|
| 🏠 **Market & FII Radar** | FII/DII cash flows & streaks · **sector + stock radar for 1 Day / 1 Week / 1 Month / 3 Months / 6 Months+** with Buy %, Sell %, rank & conviction · sector drill-down · live forward matrix · today's inferred big-player footprint · NSDL sector flows · bulk/block deals · sector momentum |
| ⭐ **Watchlist & Pinned** | Add / remove stocks & funds, live signal, probability, status, entry/target/stop, full-analysis popup, **backup / restore** |
| 🔍 **Search & Multi-TF Engine** | Any stock, index or mutual fund (by NAV): 7 horizons, entry / target / stop / exit, candle pattern, strategy, news impact, **big-player zones + Up/Down price prediction**, 15m/1h/4h/1D/1W/1M candle engine |
| 🎯 **Stocks (High Conviction)** | Styles: **Short Swing (5 trading days)**, Swing, Intraday, F&O, Positional, Long Term · or any of 7 timeframes · up to 8 BUY + 8 SELL per section · **3 sections by expected move: 1–8 %, 8–16 %, >16 %** · click 🔍 for the full analysis |
| 💼 **Mutual Funds (Ranked)** | NAV-based ranking · Short Swing (5d), 2W, 1M, 3M, 6M+ · 9 categories · **3 sections: 1–5 %, 5–10 %, >10 %** · click 📊 for the full analysis |
| 🤖 **AI Quant Copilot** | Understands English/Hinglish, answers from the live scans (screener, analysis, compare, MFs, FII/DII, macro, watchlist commands) · optional Gemini |
| 📰 **News & Forex Factory** | Real Forex Factory calendar → impact likelihood, sectors / stocks / indices / mutual funds affected, suggested action · classified news stream · static macro playbook (RBI, FOMC, CPI, NFP, OPEC+) |

### Status badge on every result
Each card / analysis shows a live clock (`LIVE` / `OFFLINE`) and a lifecycle status:
**WAIT → READY FOR ENTRY → ENTER NOW → READY FOR EXIT → EXIT**.
When the market is offline the levels are based on the last close and apply to the next session.

### Big-player money zones + Up / Down price prediction
For every stock the full analysis shows:
* **Probable BUY cost zone** and **SELL / distribution zone** of big players (anchored VWAP of volume-surge days),
* **Point of control / value area** (volume profile) and a support/resistance map,
* **Up/Buy-side and Down/Sell-side price targets with the measured probability of being touched** within 5 days / 1 month / 3 months,
* disclosed **bulk & block deals** (real client names and prices) when the NSE feed is reachable.

For mutual funds the same panel shows **NAV zones** and Up/Down NAV reach probabilities.

---

## 🎯 How to read the numbers (please read)

* **Probability** = model confluence (trend, momentum, volume, candle, relative strength, market regime) **blended with the hit-rate that similar past signals actually produced** (across the whole universe and on that asset).
* **Backtest hit-rate** (shown next to it) is the *measured* number: how often similar signals were right after the horizon. **Trust this one most.** It is typically in the 50s–60s %, not 90 %. v1 showed 70–95 % "accuracy"; those figures were score-derived, not measured.
* **Target hit before stop** is stricter: price reached Target 1 without touching the stop. With a 2:1 reward-to-risk plan this is naturally below the hit-rate.
* Every score uses only past data at each point (verified by a look-ahead test). Backtests are still in-sample, ignore costs/slippage and use today's constituents (survivorship bias).
* Cards below your minimum probability are drawn **dashed** and labelled *lower conviction*; they only appear so a list is never empty.
* The probability slider (55–90 %) lets you raise the bar. At 80 %+ expect few or no setups — that is the honest answer.

### What is real data and what is inferred
| Item | Source | Nature |
|---|---|---|
| Prices, volume, candles | Yahoo Finance (NSE) | real (may be ~15 min delayed) |
| Mutual fund NAV | AMFI via mfapi.in | real |
| FII / DII daily cash flows | Groww / Tapetide pages | real, provisional |
| Sector-wise FPI flow | NSDL fortnightly report | real, fortnightly |
| Bulk / block deals | NSE | real when reachable |
| **Stock-level FII/DII buying & their entry price** | *not published daily* | **inferred** from price × volume (CMF, OBV, surge-day VWAP) |
| Forex Factory events | `nfs.faireconomy.media` weekly feed | real (forecast/previous only) |
| Impact likelihood for events/news | rules × importance | heuristic, not statistical |

If a live source is unreachable the app says so and labels any placeholder as **ILLUSTRATIVE** — it never silently shows invented data as real.

---

## 🗂️ Project structure
```
app.py          pages & navigation          ui.py        cards, charts, full-analysis views
engine.py       indicators, scoring, calibration, status, zones, backtests
data.py         all network access, caches, universe / MF scans, FII-DII matrix
copilot.py      AI copilot (NLP engine + optional Gemini)
macro.py        news & Forex Factory impact engine
knowledge.py    universes, sector maps, names     store.py     watchlist persistence
tests/          offline smoke test (synthetic data)
.streamlit/config.toml   dark theme
```

---

## 🚀 Run locally (Windows)
1. Install **Python 3.10 – 3.13** from python.org (tick *Add Python to PATH*).
2. In this folder: `pip install -r requirements.txt`
3. Double-click **`run_app.bat`** (or `streamlit run app.py`). Opens at `http://localhost:8501`.

First load downloads ~3 years of prices for ~180 stocks (20–60 s); afterwards everything is cached (20 min for prices, 1 h for NAV).
Use **🔄 Refresh Terminal** to force fresh data.

## 📱 Use on your phone (same Wi-Fi)
Open the **Network URL** printed in the terminal (e.g. `http://192.168.1.5:8501`) in Chrome / Safari.

## 🌐 Deploy free on Streamlit Community Cloud (24x7, phone + laptop)
```bash
git init
git add .
git commit -m "Trader Dashboard Pro"
git branch -M main
git remote add origin https://github.com/<your-username>/trader-dashboard.git
git push -u origin main
```
Then at [share.streamlit.io](https://share.streamlit.io): **New app** → pick the repo → branch `main` → main file `app.py` → **Deploy**.

**Optional – Gemini for the copilot:** App settings → *Secrets* →
```toml
GEMINI_API_KEY = "your-key-from-aistudio.google.com"
```

### Good to know on Streamlit Cloud
* The server disk is **ephemeral**: the watchlist file resets on restart/redeploy and is shared by every visitor of your app. Use **Watchlist → Backup / restore** (download the JSON) or commit `user_watchlist.json` to GitHub.
* If Yahoo throttles the shared cloud IP you may see "data load nahi ho paya" — click **Refresh Terminal** after a minute (failed loads are never cached).
* NSE sites often block cloud IPs: bulk/block deals and NSDL may fall back to a labelled illustrative sample.
* Keep the repo private if you do not want others using your app URL.

## 🧪 Test without internet
```bash
python tests/smoke_test.py
```
Runs every page against synthetic prices and fails on any exception.

---

## ⚠️ Disclaimer
Signals are algorithmic research output (RSI, MACD, moving averages, ATR, volume, NAV momentum) calibrated on historical hit-rates, which do not guarantee future results.
Not SEBI-registered investment advice. Trading and investing involve market risk — use stop-losses and position sizing.
