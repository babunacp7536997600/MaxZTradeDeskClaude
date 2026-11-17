"""
store.py - watchlist / pinned persistence.

* Stored in `user_watchlist.json` next to the app (same file format as v1, so your existing file keeps working).
* On Streamlit Community Cloud the disk is EPHEMERAL (it resets when the app restarts / redeploys) and is shared by
  every visitor, so the Watchlist tab also offers Export / Import (download & upload the JSON) - use that as your
  permanent backup.
"""
import json
import os

WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_watchlist.json")

DEFAULT = {
    "stocks": ["RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "DRREDDY", "JSWSTEEL"],
    "funds": ["ICICI Prudential Technology Fund", "Parag Parikh Flexi Cap Fund", "HDFC Flexi Cap Fund"],
    "pinned": ["RELIANCE", "BHARTIARTL", "ICICI Prudential Technology Fund"],
}


def normalise(data):
    out = {k: [] for k in ("stocks", "funds", "pinned")}
    if isinstance(data, dict):
        for k in out:
            v = data.get(k, [])
            if isinstance(v, list):
                seen = []
                for x in v:
                    if isinstance(x, str) and x.strip() and x.strip() not in seen:
                        seen.append(x.strip())
                out[k] = seen
    return out


def load():
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return normalise(json.load(f))
    except Exception:
        pass
    return normalise(DEFAULT)


def save(data):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(normalise(data), f, indent=2)
        return True
    except Exception:
        return False


def is_fund(item, data):
    """A pinned item is a fund if it is stored in `funds` (or clearly looks like a scheme name)."""
    if item in data.get("funds", []):
        return True
    if item in data.get("stocks", []):
        return False
    low = item.lower()
    return " fund" in low or low.endswith("fund") or ("direct" in low and "growth" in low) or (" " in item and len(item) > 14)
