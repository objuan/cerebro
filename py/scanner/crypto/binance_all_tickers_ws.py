import asyncio
import json
import websockets
import sqlite3
from datetime import datetime
import time

WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
DB_FILE = "db/crypto.db"
DB_TABLE = "ohlc_live"

RETENTION_HOURS = 48      # quante ore tenere
CLEANUP_INTERVAL = 3600  # ogni quanto pulire (1h)

# ---------- SQLite ----------
conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
CREATE TABLE IF NOT EXISTS ohlc_live (
    exchange TEXT,
    pair TEXT,
    timeframe TEXT,
    timestamp INTEGER, -- epoch ms
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    base_volume REAL,
    quote_volume REAL,
    base_volume_24h REAL,
    quote_volume_24h REAL,
    updated_at INTEGER, -- epoch ms
    ds_updated_at TEXT, -- epoch ms
    PRIMARY KEY(exchange, pair, timeframe, timestamp)
)""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_ohlc_ts
    ON ohlc_live(timestamp)
""")

TIMEFRAMES = {
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "1h": 3600,
}

async def cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)

        cutoff_ms = int(
            (time.time() - RETENTION_HOURS * 3600) * 1000
        )

        cur.execute("""
        DELETE FROM ohlc_live
        WHERE timestamp < ?
        """, (cutoff_ms,))

        #cur.execute("VACUUM;")  # opzionale, vedi nota sotto

        print(
            f"🧹 cleanup done (< {RETENTION_HOURS}h)"
        )

# stato rolling
last_stats = {}
agg_cache = {}

def floor_ts(ts_ms, sec):
    # ritorna in ms
    return (ts_ms // (sec*1000)) * (sec*1000)

def normalize_symbol(pair):
    if pair.endswith("USDC"):
        return pair[:-4]+"/USDC"
    elif pair.endswith("BTC"):
        return pair[:-3]+"/BTC"
    else:
        return pair

def update_ohlc(pair, price, d_base, d_quote,d_base_24, d_quote_24, ts_ms):
    for tf, sec in TIMEFRAMES.items():
        t = floor_ts(ts_ms, sec)
        key = (pair, tf, t)
        c = agg_cache.get(key)

        if c is None:
            agg_cache[key] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "base_vol": d_base,
                "quote_vol": d_quote,
                "base_vol_24h": d_base_24,
                "quote_vol_24h": d_quote_24
            }
        else:
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["base_vol"] += d_base
            c["quote_vol"] += d_quote
            c["base_vol_24h"] = d_base_24
            c["quote_vol_24h"] = d_quote_24

        save = agg_cache[key]
        cur.execute("""
        INSERT OR REPLACE INTO ohlc_live VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?, ? , ?)
        """, (
            "binance", normalize_symbol(pair), tf, t,
            save["open"], save["high"], save["low"], save["close"],
            save["base_vol"], save["quote_vol"],save["base_vol_24h"], save["quote_vol_24h"],
            int(time.time() * 1000),
            datetime.utcnow().isoformat()
        ))

async def run():
    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        print("🚀 Binance !ticker@arr connected")

        cleanup = asyncio.create_task(cleanup_task())

        while True:
            msg = json.loads(await ws.recv())

            for t in msg:
                pair = t["s"]
              
                if pair.endswith("USDC") or pair.endswith("BTC"):
                    #print(pair)
                    price = float(t["c"])
                    v = float(t["v"])
                    q = float(t["q"])
                    ts = t["E"]
                    
                    prev = last_stats.get(pair)
                    if prev:
                        d_base = max(0.0, v - prev["v"])
                        d_quote = max(0.0, q - prev["q"])
                    else:
                        d_base = d_quote = 0.0

                    last_stats[pair] = {"v": v, "q": q}

                    update_ohlc(pair, price, d_base, d_quote,v,q, ts)

asyncio.run(run())