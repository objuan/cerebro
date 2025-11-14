import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone
import zoneinfo  # disponibile da Python 3.9 in poi
import threading, time
import signal
import sys
from database import *

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

# Crea la tabella (solo la prima volta)
'''
cur.execute("""
CREATE TABLE IF NOT EXISTS live_quotes (
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

cur.execute("""
CREATE TABLE IF NOT EXISTS live_candles_1m (
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

print("DONE")