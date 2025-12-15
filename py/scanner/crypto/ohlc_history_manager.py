import ccxt
import sqlite3
import time
from datetime import datetime, timedelta


DB_FILE = "db/crypto.db"
RETENTION_DAYS = 1

TIMEFRAMES = ["1m", "5m", "1h"]

exchange_ccxt = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ---------- SQLite ----------
conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
CREATE TABLE IF NOT EXISTS ohlc_history (
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

    source TEXT,        -- ccxt | live
    updated_at INTEGER,          
    ds_updated_at TEXT,

    PRIMARY KEY (exchange, pair, timeframe, timestamp)
)""")

# ---------- Utils ----------
def ms(ts):
    return int(ts * 1000)

def now_ms():
    return int(time.time() * 1000)

def week_ago_ms():
    return ms(time.time() - RETENTION_DAYS * 86400)

# ---------- Storico via CCXT ----------
def fetch_missing_history(pair, timeframe):
    since = week_ago_ms()

    print(f"📥 fetching history {pair} {timeframe}")

    ohlcv = exchange_ccxt.fetch_ohlcv(
        symbol=pair,
        timeframe=timeframe,
        since=since,
        limit=1000
    )

    for o in ohlcv:
        ts, open_, high, low, close, vol = o

        cur.execute("""
        INSERT OR REPLACE INTO  ohlc_history VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?
        )
        """, (
            "binance",
            pair,
            timeframe,
            ts,
            open_,
            high,
            low,
            close,
            vol,
            vol * close,
            "ccxt",
            int(time.time() * 1000),
            datetime.utcnow().isoformat()
        ))

# ---------- Merge LIVE → HISTORY ----------
def merge_live_into_history():
    cur.execute("""
    INSERT OR REPLACE INTO ohlc_history
    SELECT
        exchange,
        pair,
        timeframe,
        timestamp,
        open,
        high,
        low,
        close,
        base_volume,
        quote_volume,
        'live',
        updated_at
    FROM ohlc_live
    """)

# ---------- Cleanup ----------
def cleanup_history():
    cutoff = week_ago_ms()

    cur.execute("""
    DELETE FROM ohlc_history
    WHERE timestamp < ?
    """, (cutoff,))

# ---------- Bootstrap ----------
def bootstrap_pairs(pairs):
    for pair in pairs:
        for tf in TIMEFRAMES:
            cur.execute("""
            SELECT 1 FROM ohlc_history
            WHERE pair=? AND timeframe=?
            LIMIT 1
            """, (pair, tf))

            if cur.fetchone() is None:
                fetch_missing_history(pair, tf)

def update_history_pairs(pairs):
    for pair in pairs:
        for tf in TIMEFRAMES:
           fetch_missing_history(pair, tf)

# ---------- Public entry ----------
def sync_history(pairs):
    bootstrap_pairs(pairs)
    #merge_live_into_history()
    #update_history_pairs(pairs)
    #cleanup_history()


##############################

#from ohlc_history_manager import sync_history

if __name__ =="main":
    PAIRS = [
        "BTC/USDC",
        "ETH/USDC",
        "SOL/USDC",
    ]

    sync_history(PAIRS)