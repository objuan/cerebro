import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import time as _time
import math
import os
import signal
import json
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import *
from utils import convert_json
#from message_bridge import *
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
util.startLoop()  # uncomment this line when in a notebook
from config import DB_FILE,CONFIG_FILE
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts
from company_loaders import *
from renderpage import WSManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

DB_TABLE = "ib_ohlc_live"

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
                    
CREATE TABLE IF NOT EXISTS ib_ohlc_history (
        exchange TEXT,
        symbol TEXT,
        timeframe TEXT,
        timestamp INTEGER,

        open REAL,
        high REAL,
        low REAL,
        close REAL,

        base_volume REAL,
        quote_volume REAL,
        day_volume REAL,

        source TEXT,        -- ib | live
        updated_at INTEGER,          
        ds_updated_at TEXT,

        PRIMARY KEY (exchange, symbol, timeframe, timestamp)
    )""")
     

cur.execute("""
    CREATE TABLE IF NOT EXISTS ib_ohlc_live (
        conindex INTEGER,
        symbol TEXT,
        exchange TEXT,
        timeframe TEXT,
        timestamp INTEGER, -- epoch ms
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        bid REAL,
        ask REAL,
        volume REAL,
        volume_day REAL,
        updated_at INTEGER, -- epoch ms
        ds_updated_at TEXT, -- epoch ms
        PRIMARY KEY(symbol, timeframe, timestamp)
    )""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS ib_ohlc_live_pre (
        mode  TEXT,
        conindex INTEGER,
        symbol TEXT,
        exchange TEXT,
        timeframe TEXT,
        timestamp INTEGER, -- epoch ms
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        bid REAL,
        ask REAL,
        volume REAL,
        volume_day REAL,
        updated_at INTEGER, -- epoch ms
        ds_updated_at TEXT, -- epoch ms
        PRIMARY KEY(symbol, timeframe, timestamp)
    )""")

cur.execute("""
    CREATE INDEX IF NOT EXISTS ib_idx_ohlc_ts
        ON ib_ohlc_live(timestamp)
    """)

cur.execute("""
    CREATE INDEX IF NOT EXISTS ib_idx_ohlc_ts_pre
        ON ib_ohlc_live_pre(timestamp)
    """)


cur.execute("""
       CREATE TABLE IF NOT EXISTS ib_scanner (
        mode TEXT,
        ts_exec  INTEGER,
        pos  INTEGER,
        conidex NUMBER  ,
        symbol TEXT ,
        available_chart_periods TEXT,
        company_name TEXT,
        contract_description_1 TEXT,
        listing_exchange TEXT,
        sec_type TEXT,
        PRIMARY KEY(mode,ts_exec,pos)
        )
    """)

cur.execute("""
       CREATE TABLE IF NOT EXISTS ib_live_watch (
        ts_exec  INTEGER,
        symbol TEXT ,
        mode TEXT,
        PRIMARY KEY(ts_exec)
        )
    """)


# Crea la tabella ib_orders se non esiste
cur.execute('''CREATE TABLE IF NOT EXISTS ib_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,
    symbol TEXT,
    side TEXT,
    status TEXT, 
    event_type TEXT,
    data TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS task_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INT,
    symbol TEXT,
    status TEXT, 
    step INT,
    data TEXT,
    timestamp INT,
    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    trade_id TEXT
)''')

cur.execute("""
    CREATE INDEX IF NOT EXISTS ib_ib_orders
        ON ib_orders(trade_id)
    """)


cur.execute("""
CREATE TABLE IF NOT EXISTS chart_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    guid TEXT NOT NULL,
    type TEXT NOT NULL,
    data TEXT NOT NULL
)
""")



cur.execute("""
CREATE TABLE IF NOT EXISTS chart_indicator (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    data TEXT NOT NULL
)
""")

cur.execute("""
CREATE UNIQUE INDEX  IF NOT EXISTS  idx_chart_indicator_name
ON chart_indicator(name);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS trade_marker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    data TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS  events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type VARCHAR(255),
    name VARCHAR(255),
    symbol VARCHAR(20),
    data TEXT,
    timestamp INTEGER,
    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    
);
            """)


cur.execute("""
CREATE TABLE IF NOT EXISTS  black_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(255),
    error TEXT,
    provider_disable INT,
    user_day_disable INT,
    user_all_disable INT,
    last_day TEXT
);
            """)


cur.execute("""
CREATE TABLE IF NOT EXISTS  watch_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255),
    type VARCHAR(255),
    symbol VARCHAR(255),
    dt_day TEXT,
    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
            """)

cur.execute("""
CREATE TABLE IF NOT EXISTS  news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guid VARCHAR(255),
    provider VARCHAR(255),
    symbol VARCHAR(255),
    source VARCHAR(255),
    published_dt DATETIME,
    published_at INT,
    url TEXT,
    data TEXT,
    provider_last_dt DATETIME,
    dt_day TEXT,
    dt_hh TEXT
);
            """)

cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_unique
ON news (provider, symbol, guid);""")


cur.execute("""
CREATE TABLE IF NOT EXISTS  back_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255),
    data TEXT
);
""")


cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_back_profile
ON back_profile (name);""")