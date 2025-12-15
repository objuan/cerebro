# ==============================================================
# IBKR SMALL-CAP MOMENTUM SCANNER
# Libreria: ibind (Client Portal Web API)
# Dati simboli + float: SQLite
# ==============================================================
# CRITERI:
# - Prezzo: 2$ – 20$
# - Volume odierno >= 5x media 30g
# - Premarket >= +2%
# - Giorno >= +10%
# - Float piccolo (da DB)
# ==============================================================

import time
import sqlite3
import pandas as pd
from ibind import IbkrClient

# ---------------- CONFIGURAZIONE ----------------
DB_PATH = "symbols.db"          # SQLite con tabella symbols
FLOAT_MAX = 30_000_000           # soglia float
PRICE_MIN = 2
PRICE_MAX = 20
VOLUME_MULTIPLIER = 5
PREMARKET_MIN_PCT = 2
DAY_MIN_PCT = 10
SLEEP_BETWEEN_REQUESTS = 0.25    # rate limit safety

# ------------------------------------------------

client = IbkrClient()
client.tickle()

# =================================================
# DATABASE
# SQLite schema required:
# CREATE TABLE symbols (
#     symbol TEXT PRIMARY KEY,
#     float INTEGER,
#     conid INTEGER
# );
# =================================================

def load_symbols_from_db():
    """Load symbols with float and cached conid if available"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT symbol, float, conid FROM symbols WHERE float <= ?",
        conn,
        params=(FLOAT_MAX,)
    )
    conn.close()
    return df

# =================================================
# IBKR HELPERS
# =================================================

def get_conid(symbol, cached_conid=None):
    if cached_conid:
        return cached_conid
    r = client.symbol_search(symbol)
    for item in r.data:
        if item.get("symbol") == symbol and item.get("assetClass") == "STK":
            return item.get("conid")
    return None
    r = client.symbol_search(symbol)
    for item in r.data:
        if item.get("symbol") == symbol and item.get("assetClass") == "STK":
            return item.get("conid")
    return None


def get_last_price(conid):
    r = client.marketdata_snapshot(
        conids=[conid],
        fields=["31"]  # last price
    )
    snap = r.data[0]
    try:
        return float(snap.get("31", 0))
    except Exception:
        return 0


def get_daily_bars(conid, days=30):
    r = client.marketdata_history(
        conid=conid,
        period=f"{days}d",
        bar="1d",
        outsideRth=False
    )
    return pd.DataFrame(r.data)


def get_intraday_bars(conid, outside_rth):
    r = client.marketdata_history(
        conid=conid,
        period="1d",
        bar="5min",
        outsideRth=outside_rth
    )
    return pd.DataFrame(r.data)

# =================================================
# CALCOLI
# =================================================

def check_volume(df_daily):
    """Check volume and compute Relative Volume (RVOL)"""
    if len(df_daily) < 10:
        return False, 0, 0, 0

    avg_vol = df_daily["volume"].iloc[:-1].mean()
    today_vol = df_daily["volume"].iloc[-1]
    rvol = today_vol / avg_vol if avg_vol > 0 else 0

    return rvol >= VOLUME_MULTIPLIER, avg_vol, today_vol, rvol
    if len(df_daily) < 10:
        return False, 0, 0

    avg_vol = df_daily["volume"].iloc[:-1].mean()
    today_vol = df_daily["volume"].iloc[-1]

    return today_vol >= VOLUME_MULTIPLIER * avg_vol, avg_vol, today_vol


def calc_pct(df):
    if len(df) < 2:
        return 0
    return (df.iloc[-1]["close"] - df.iloc[0]["open"]) / df.iloc[0]["open"] * 100

# =================================================
# SCANNER
# =================================================

def run_scanner():
    symbols_df = load_symbols_from_db()
    results = []

    print(f"Scanning {len(symbols_df)} symbols...")

    for _, row in symbols_df.iterrows():
        cached_conid = row.get("conid")
        symbol = row["symbol"]
        float_shares = row["float"]

        try:
            conid = get_conid(symbol, cached_conid)
            if not cached_conid and conid:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE symbols SET conid=? WHERE symbol=?", (conid, symbol))
                conn.commit()
                conn.close()
            if not conid:
                continue

            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # ---- PREZZO ----
            price = get_last_price(conid)
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue

            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # ---- VOLUME ----
            df_daily = get_daily_bars(conid)
            ok_vol, avg_vol, today_vol, rvol = check_volume(df_daily)
            if not ok_vol:
                continue

            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # ---- PREMARKET ----
            df_pm = get_intraday_bars(conid, outside_rth=True)
            pm_pct = calc_pct(df_pm)
            if pm_pct < PREMARKET_MIN_PCT:
                continue

            time.sleep(SLEEP_BETWEEN_REQUESTS)

            # ---- GIORNO ----
            df_day = get_intraday_bars(conid, outside_rth=False)
            day_pct = calc_pct(df_day)
            if day_pct < DAY_MIN_PCT:
                continue

            # ---- MATCH ----
            results.append({
                "rvol": round(rvol, 2),
                "symbol": symbol,
                "price": round(price, 2),
                "avg_volume": int(avg_vol),
                "today_volume": int(today_vol),
                "premarket_pct": round(pm_pct, 2),
                "day_pct": round(day_pct, 2),
                "float": int(float_shares)
            })

            print(f"MATCH: {symbol}  PM:{pm_pct:.1f}%  DAY:{day_pct:.1f}%  VOL:{today_vol}")

        except Exception as e:
            print(f"Error {symbol}: {e}")

    return pd.DataFrame(results)

# =================================================
# WEBSOCKET ALERT (IBIND)
# =================================================
from ibind import IbkrWsClient, IbkrWsKey

ws = IbkrWsClient(start=False)
#ws.subscribe(channel=IbkrWsKey.NOTIFICATIONS.channel)


def start_ws_on_results(df_results):
    """Start WebSocket subscriptions only for matched symbols"""
    if df_results.empty:
        return
    ws.start()

    for _, row in df_results.iterrows():
        conid = int(row.get("conid", 0))
        if conid:
            # Live market data for selected stocks only
            ws.subscribe(
                channel=IbkrWsKey.MARKET_DATA.channel,
                conid=conid
            )
            print(f"WS subscribed: {row['symbol']} ({conid})")

    print("WebSocket live on selected symbols")

 
# =================================================
# TELEGRAM ALERT
# =================================================
import requests


TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": msg,
    "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Telegram error", e)

'''
send_telegram(
    f"🚀 *MOMENTUM STOCK*\n"
    f"Ticker: {symbol}\n"
    f"Price: ${price:.2f}\n"
    f"Premarket: {pm_pct:.1f}%\n"
    f"Day: {day_pct:.1f}%\n"
    f"RVOL: {rvol:.2f}\n"
    f"Float: {float_shares:,}"
)
'''
# =================================================
# MAIN
# =================================================

if __name__ == "__main__":
    df_results = run_scanner()

    if not df_results.empty:
        df_results.sort_values(by="today_volume", ascending=False, inplace=True)
        df_results.to_csv("scanner_results.csv", index=False)
        print("\nResults saved to scanner_results.csv")
    else:
        print("\nNo symbols matched criteria.")
