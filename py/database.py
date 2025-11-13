import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone
import zoneinfo  # disponibile da Python 3.9 in poi
import threading, time
import signal
import sys

LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Rome")
yf.set_tz_cache_location("cache")

DB_PATH = "quotes.db"

# Connessione (crea file se non esiste)
#conn = sqlite3.connect("quotes.db")
def get_connection():
    # Ogni thread crea la propria connessione
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_connection()
cur = conn.cursor()

"""Crea la tabella market non esiste"""
conn.execute("""
        CREATE TABLE IF NOT EXISTS market (
            name TEXT,
            open_local TEXT,
            close_local TEXT,
            open_continue_local TEXT,
            close_continue_local TEXT
        
        )
""")
conn.commit()

"""Crea la tabella meta se non esiste"""
cur.execute("""
CREATE TABLE IF NOT EXISTS ticker (
    id TEXT,
    name TEXT,
    summary TEXT,
    currency TEXT,
    sector TEXT,
    industry_group TEXT,
    industry TEXT,
    exchange TEXT,
    market TEXT,
    country TEXT,
    state TEXT,
    city TEXT,
    zipcode TEXT,
    website TEXT,
    market_cap REAL,
    isin TEXT,
    cusip TEXT,
    figi TEXT,
    composite_figi TEXT,
    shareclass_figi TEXT,
    yahoo INTEGER
)
""")
conn.commit()


"""Crea la tabella meta se non esiste"""
conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            id TEXT PRIMARY KEY,
            last_aggregated_1m TEXT,
            last_aggregated_5m TEXT
        )
""")
conn.commit()

def get_last_aggregated(conn,period):
    """Restituisce un dizionario {id: last_timestamp}"""
    cur = conn.cursor()
    cur.execute(f"SELECT id, last_aggregated_{period} FROM meta")
    rows = cur.fetchall()
    return {r[0]: r[1] for r in rows if r[1]}

def update_last_aggregated(conn, period, updates: dict):
    """Aggiorna la tabella meta per ciascun simbolo"""
    cur = conn.cursor()
    for symbol, ts in updates.items():
        cur.execute(f"""
            INSERT INTO meta (id, last_aggregated_{period})
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET last_aggregated_{period}=excluded.last_aggregated_{period}
        """, (symbol, ts))

# Crea la tabella (solo la prima volta)
'''
cur.execute("""
CREATE TABLE IF NOT EXISTS quotes (
    id TEXT,
    price REAL,
    time_utc TEXT,
    time_local TEXT,
    exchange TEXT,
    quote_type INTEGER,
    market_hours INTEGER,
    change_percent REAL,
    day_volume INTEGER,
    change REAL,
    last_size INTEGER,
    price_hint INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    PRIMARY KEY (id, time_local)
)
""")
conn.commit()
'''

'''
cur.execute("""
CREATE TABLE IF NOT EXISTS candles_5m (
    id TEXT,
    timestamp TEXT,     -- inizio della candela
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()
'''
cur.execute("""
CREATE TABLE IF NOT EXISTS candles_1m (
    id TEXT,
    timestamp TEXT,     -- inizio della candela
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()

########### history 

cur.execute("""
CREATE TABLE IF NOT EXISTS candles_1d_history (
    id TEXT,
    timestamp TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()


cur.execute("""
CREATE TABLE IF NOT EXISTS candles_1h_history (
    id TEXT,
    timestamp TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()

cur.execute("""
CREATE TABLE IF NOT EXISTS candles_5m_history (
    id TEXT,
    timestamp TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()


cur.execute("""
CREATE TABLE IF NOT EXISTS candles_1m_history (
    id TEXT,
    timestamp TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (id, timestamp)
)
""")
conn.commit()

# 1. Vista 15 minuti

cur.execute("""
CREATE VIEW IF NOT EXISTS candles_5m AS
SELECT
    id,
    datetime(
        CAST(strftime('%s', timestamp) / (5 * 60) AS INT) * (5 * 60),
        'unixepoch'
    ) AS timestamp_5m,
    MIN(low) AS low,
    MAX(high) AS high,
   
    -- open: primo valore del gruppo di 5 minuti
    (
        SELECT open FROM candles_1m c2
        WHERE c2.id = c.id
          AND datetime(
                CAST(strftime('%s', c2.timestamp) / (5 * 60) AS INT) * (5 * 60),
                'unixepoch'
              ) = datetime(
                CAST(strftime('%s', c.timestamp) / (5 * 60) AS INT) * (5 * 60),
                'unixepoch'
              )
        ORDER BY c2.timestamp ASC
        LIMIT 1
    ) AS open,

    -- close: ultimo valore del gruppo di 5 minuti
    (
        SELECT close FROM candles_1m c3
        WHERE c3.id = c.id
          AND datetime(
                CAST(strftime('%s', c3.timestamp) / (5 * 60) AS INT) * (5 * 60),
                'unixepoch'
              ) = datetime(
                CAST(strftime('%s', c.timestamp) / (5 * 60) AS INT) * (5 * 60),
                'unixepoch'
              )
        ORDER BY c3.timestamp DESC
        LIMIT 1
    ) AS close,
     SUM(volume) AS volume


FROM candles_1m c
GROUP BY id, timestamp_5m
""")

conn.commit()

# Candela 15 minuti
cur.execute("""
CREATE VIEW IF NOT EXISTS candles_15m AS
SELECT
    id,
    datetime(CAST(strftime('%s', timestamp) / (15 * 60) AS INT) * (15 * 60), 'unixepoch') AS timestamp_15m,
    MIN(low) AS low,
    MAX(high) AS high,
    SUM(volume) AS volume,
    (SELECT open FROM candles_5m c2
     WHERE c2.id = c.id
       AND datetime(CAST(strftime('%s', c2.timestamp) / (15 * 60) AS INT) * (15 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (15 * 60) AS INT) * (15 * 60), 'unixepoch')
     ORDER BY c2.timestamp ASC LIMIT 1) AS open,
    (SELECT close FROM candles_5m c3
     WHERE c3.id = c.id
       AND datetime(CAST(strftime('%s', c3.timestamp) / (15 * 60) AS INT) * (15 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (15 * 60) AS INT) * (15 * 60), 'unixepoch')
     ORDER BY c3.timestamp DESC LIMIT 1) AS close
FROM candles_5m c
GROUP BY id, timestamp_15m;
""")

conn.commit()

# 2. Vista 30 minuti
cur.execute("""
CREATE VIEW IF NOT EXISTS candles_30m AS
SELECT
    id,
    datetime(CAST(strftime('%s', timestamp) / (30 * 60) AS INT) * (30 * 60), 'unixepoch') AS timestamp_30m,
    MIN(low) AS low,
    MAX(high) AS high,
    SUM(volume) AS volume,
    (SELECT open FROM candles_5m c2
     WHERE c2.id = c.id
       AND datetime(CAST(strftime('%s', c2.timestamp) / (30 * 60) AS INT) * (30 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (30 * 60) AS INT) * (30 * 60), 'unixepoch')
     ORDER BY c2.timestamp ASC LIMIT 1) AS open,
    (SELECT close FROM candles_5m c3
     WHERE c3.id = c.id
       AND datetime(CAST(strftime('%s', c3.timestamp) / (30 * 60) AS INT) * (30 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (30 * 60) AS INT) * (30 * 60), 'unixepoch')
     ORDER BY c3.timestamp DESC LIMIT 1) AS close
FROM candles_5m c
GROUP BY id, timestamp_30m;
""")

conn.commit()
# 3. Vista 1 ora
cur.execute("""
CREATE VIEW IF NOT EXISTS candles_1h AS
SELECT
    id,
    datetime(CAST(strftime('%s', timestamp) / (60 * 60) AS INT) * (60 * 60), 'unixepoch') AS timestamp_1h,
    MIN(low) AS low,
    MAX(high) AS high,
    SUM(volume) AS volume,
    (SELECT open FROM candles_5m c2
     WHERE c2.id = c.id
       AND datetime(CAST(strftime('%s', c2.timestamp) / (60 * 60) AS INT) * (60 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (60 * 60) AS INT) * (60 * 60), 'unixepoch')
     ORDER BY c2.timestamp ASC LIMIT 1) AS open,
    (SELECT close FROM candles_5m c3
     WHERE c3.id = c.id
       AND datetime(CAST(strftime('%s', c3.timestamp) / (60 * 60) AS INT) * (60 * 60), 'unixepoch')
           = datetime(CAST(strftime('%s', c.timestamp) / (60 * 60) AS INT) * (60 * 60), 'unixepoch')
     ORDER BY c3.timestamp DESC LIMIT 1) AS close
FROM candles_5m c
GROUP BY id, timestamp_1h;
""")
conn.commit()

###################################

def get_tickers(conn, watchlistName):
    conn = get_connection()
    query = f"""
    SELECT ticker from watchlist where name = '{watchlistName}' and enabled=1
    """
    cur = conn.cursor()
    cur.execute(query)
    for row in  cur.fetchall():    
        #print(row[0])
        return [ r.replace("\"","") for r in row[0].split(",") ]
    return []

def select(query, noPandaMode=False):
    #print(query)
    conn = get_connection()
    df =  pd.read_sql(query,conn)
    conn.close()
    if len(df) == 1:
        arr = df.to_numpy()[0]
        return arr
    else:
        if noPandaMode:
            return df.to_dict(orient="records")
        else:
            return df