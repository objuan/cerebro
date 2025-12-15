import ccxt
import requests
import sqlite3
import pandas as pd
from datetime import datetime
from tqdm import tqdm

# ---------------- CONFIG ----------------
EXCHANGES = ["binance"]#, "kraken", "kucoin"]
QUOTES = ["USDT", "BTC"]
DB_FILE = "db/crypto.db"


COINGECKO_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
COINGECKO_COIN_URL = "https://api.coingecko.com/api/v3/coins/{}"
# ----------------------------------------

# ---------- DB ----------
conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS symbols (
    exchange TEXT,
    pair TEXT,
    symbol TEXT,

    base TEXT,
    quote TEXT,

    last_price REAL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    previous_close REAL,
    open_price REAL,

    base_volume REAL,
    quote_volume REAL,

    open_time INTEGER,
    close_time INTEGER,

    free_float REAL,
    updated_at TEXT,

    PRIMARY KEY (exchange, pair)
)
""")
conn.commit()

# ---------- CoinGecko cache ----------
print("Carico lista token CoinGecko...")
cg_list = requests.get(COINGECKO_LIST_URL, timeout=30).json()
cg_map = {}
for c in cg_list:
    cg_map.setdefault(c["symbol"].lower(), []).append(c["id"])

def get_free_float(symbol):
    ids = cg_map.get(symbol.lower())
    if not ids:
        return None
    try:
        data = requests.get(
            COINGECKO_COIN_URL.format(ids[0]),
            timeout=30
        ).json()
        return data.get("market_data", {}).get("circulating_supply")
    except Exception:
        return None

# ---------- SCAN ----------
rows = 0
now = datetime.utcnow().isoformat()

for ex_id in EXCHANGES:
    print(f"\nScanning {ex_id}...")
    exchange = getattr(ccxt, ex_id)({"enableRateLimit": True})

    try:
        markets = exchange.load_markets()
    except Exception as e:
        print("Errore markets:", e)
        continue

    pairs = [
        p for p in markets
        if any(p.endswith(f"/{q}") for q in QUOTES)
    ]

    for pair in tqdm(pairs):
        try:
            ticker = exchange.fetch_ticker(pair)
        except Exception:
            continue

        base, quote = pair.split("/")
        info = ticker.get("info", {})

        # ---- valori CCXT standard ----
        last_price = ticker.get("last")
        open_p = ticker.get("open")
        high = ticker.get("high")
        low = ticker.get("low")
        close = ticker.get("close")
        previous_close = ticker.get("previousClose")

        base_volume = ticker.get("baseVolume")
        quote_volume = ticker.get("quoteVolume")

        # ---- valori da info (exchange-specific) ----
        symbol_native = info.get("symbol")
        open_price_info = info.get("openPrice") or info.get("open")
        open_time = info.get("openTime")
        close_time = info.get("closeTime")

        cur.execute("""
        INSERT INTO symbols (
            exchange, pair, symbol,
            base, quote,
            last_price, open, high, low, close,
            previous_close, open_price,
            base_volume, quote_volume,
            open_time, close_time,
            free_float, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exchange, pair) DO UPDATE SET
            symbol = excluded.symbol,
            last_price = excluded.last_price,
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            previous_close = excluded.previous_close,
            open_price = excluded.open_price,
            base_volume = excluded.base_volume,
            quote_volume = excluded.quote_volume,
            open_time = excluded.open_time,
            close_time = excluded.close_time,
            free_float = excluded.free_float,
            updated_at = excluded.updated_at
        """, (
            ex_id,
            pair,
            symbol_native,

            base,
            quote,

            last_price,
            open_p,
            high,
            low,
            close,
            previous_close,
            open_price_info,

            base_volume,
            quote_volume,

            open_time,
            close_time,

            get_free_float(base),
            now
        ))

        rows += 1
        if (rows %10!=0):
            conn.commit()            

conn.commit()
print(f"\nScan completato. Righe processate: {rows}")

# ---------- VIEW ----------
df = pd.read_sql("""
SELECT
    exchange, pair, symbol,
    last_price,
    base_volume, quote_volume,
    open, high, low, close,
    free_float, updated_at
FROM symbols
ORDER BY quote_volume DESC
LIMIT 30
""", conn)

print("\nTOP 30 per quote volume:")
print(df)

conn.close()