import asyncio
import sqlite3
from datetime import datetime
import ccxt.pro as ccxt
import math

TIMEFRAMES = {
    "1m": 60,
    "5m": 300,
    "1h": 3600,
}

DB_FILE = "db/crypto.db"

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
def candle_timestamp(ts_ms, tf_seconds):
    return (ts_ms // (tf_seconds * 1000)) * (tf_seconds * 1000)

# ---------- Aggregator ----------
class OHLCAggregator:
    def __init__(self):
        self.cache = {}  # (pair, timeframe, ts) -> candle dict

    def update(self, exchange, pair, price, base_vol, quote_vol, ts_ms):
        for tf, seconds in TIMEFRAMES.items():
            candle_ts = candle_timestamp(ts_ms, seconds)
            key = (exchange, pair, tf, candle_ts)

            candle = self.cache.get(key)
            if candle is None:
                candle = {
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "base_volume": base_vol or 0,
                    "quote_volume": quote_vol or 0,
                }
                self.cache[key] = candle
            else:
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                candle["base_volume"] += base_vol or 0
                candle["quote_volume"] += quote_vol or 0

            self.flush(exchange, pair, tf, candle_ts, candle)

    def flush(self, exchange, pair, tf, ts, c):
        cur.execute("""
        INSERT INTO ohlc (
            exchange, pair, timeframe, timestamp,
            open, high, low, close,
            base_volume, quote_volume,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exchange, pair, timeframe, timestamp) DO UPDATE SET
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            base_volume = excluded.base_volume,
            quote_volume = excluded.quote_volume,
            updated_at = excluded.updated_at
        """, (
            exchange,
            pair,
            tf,
            ts,
            c["open"],
            c["high"],
            c["low"],
            c["close"],
            c["base_volume"],
            c["quote_volume"],
            datetime.utcnow().isoformat()
        ))

# ---------- Binance WebSocket ----------
class BinanceWS:
    def __init__(self, pairs):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}
        })
        self.pairs = pairs
        self.agg = OHLCAggregator()

    async def watch(self, pair):
        while True:
            try:
                t = await self.exchange.watch_ticker(pair)
                self.agg.update(
                    exchange="binance",
                    pair=pair,
                    price=t["last"],
                    base_vol=t.get("baseVolume"),
                    quote_vol=t.get("quoteVolume"),
                    ts_ms=t["timestamp"]
                )
            except Exception as e:
                print(pair, "WS error:", e)
                await asyncio.sleep(1)

    async def run(self):
        await asyncio.gather(*(self.watch(p) for p in self.pairs))

# ---------- MAIN ----------
async def main():
    exchange = ccxt.binance()
    markets = await exchange.load_markets()
    pairs = [
        p for p in markets
        if p.endswith("/USDT")
    ][:50]  # LIMITA SEMPRE

    ws = BinanceWS(pairs)
    print(f"Streaming {len(pairs)} pairs")
    await ws.run()

if __name__ == "__main__":
    asyncio.run(main())