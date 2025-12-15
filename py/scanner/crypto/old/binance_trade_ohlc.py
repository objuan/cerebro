import asyncio
import json
import sqlite3
import websockets
from datetime import datetime

WS_URL = "wss://stream.binance.com:9443/ws/!trade@arr"
DB_FILE = "db/crypto.db"

TIMEFRAMES = {
    "30s" : 30,
    "1m": 60,
    "5m": 300,
    "1h": 3600,
}

# ---------- SQLite ----------
conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
CREATE TABLE IF NOT EXISTS ohlc (
    exchange TEXT,
    pair TEXT,
    timeframe TEXT,
    timestamp INTEGER,

    open REAL,
    high REAL,
    low REAL,
    close REAL,

    base_volume REAL,
    quote_volume REAL,

    updated_at TEXT,

    PRIMARY KEY (exchange, pair, timeframe, timestamp)
)
""")

# ---------- Utils ----------
def candle_open_ts(ts_ms, tf_sec):
    return (ts_ms // (tf_sec * 1000)) * (tf_sec * 1000)

# ---------- Aggregator ----------
class OHLCAggregator:
    def __init__(self):
        self.active = {}   # (pair, tf) -> candle
        self.last_ts = {}  # (pair, tf) -> candle_open_ts

    def update_trade(self, pair, price, qty, ts_ms):
        for tf, sec in TIMEFRAMES.items():
            open_ts = candle_open_ts(ts_ms, sec)
            key = (pair, tf)

            # nuova candela → flush precedente
            if key in self.last_ts and self.last_ts[key] != open_ts:
                self.flush(pair, tf)

            if key not in self.active or self.last_ts.get(key) != open_ts:
                self.active[key] = {
                    "timestamp": open_ts,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "base_volume": qty,
                    "quote_volume": qty * price,
                }
                self.last_ts[key] = open_ts
            else:
                c = self.active[key]
                c["high"] = max(c["high"], price)
                c["low"] = min(c["low"], price)
                c["close"] = price
                c["base_volume"] += qty
                c["quote_volume"] += qty * price

    def flush(self, pair, tf):
        c = self.active.get((pair, tf))
        if not c:
            return

        cur.execute("""
        INSERT INTO ohlc VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exchange, pair, timeframe, timestamp) DO NOTHING
        """, (
            "binance",
            pair,
            tf,
            c["timestamp"],
            c["open"],
            c["high"],
            c["low"],
            c["close"],
            c["base_volume"],
            c["quote_volume"],
            datetime.utcnow().isoformat()
        ))

        del self.active[(pair, tf)]

# ---------- WebSocket ----------
async def run():
    agg = OHLCAggregator()

    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        print("🚀 Binance ALL trades stream connected")

        while True:
            msg = json.loads(await ws.recv())

            print(msg)
            for t in msg:
                pair = t["s"]                  # BTCUSDT
                price = float(t["p"])          # trade price
                qty = float(t["q"])            # base qty
                ts = t["T"]                    # trade time

                agg.update_trade(pair, price, qty, ts)

asyncio.run(run())
