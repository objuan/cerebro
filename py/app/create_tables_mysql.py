import sys
if __name__ =="__main__":
    sys.argv.append("BINANCE")

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
import pymysql

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)


conn = pymysql.connect(
        host="192.168.1.100",
        user="root",
        password="alice",
        database="binance",
        charset="utf8mb4",
        autocommit=True
    )

cur = conn.cursor()

# =========================================================
# DATABASE UTF8
# =========================================================

cur.execute("""
ALTER DATABASE binance
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
    CREATE TABLE IF NOT EXISTS company (
        symbol VARCHAR(64) NOT NULL,

        free_float DOUBLE,

        float_shares BIGINT,
        outstanding_shares BIGINT,

        shares_source VARCHAR(64),

        shares_update_dt DATETIME,

        PRIMARY KEY (symbol)

    )
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci
    """)

# =========================================================
# ib_ohlc_history
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_ohlc_history (
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    timeframe VARCHAR(16),
    timestamp BIGINT,

    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,

    base_volume DOUBLE,
    quote_volume DOUBLE,
    day_volume DOUBLE,
    quote_day_volume DOUBLE,
    day_gain DOUBLE,

    source VARCHAR(16),

    datetime DATETIME,
    ds_updated_at DATETIME,

    PRIMARY KEY (symbol, timeframe, timestamp)

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# ib_scanner
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_scanner (
    profile VARCHAR(255),
    strategy VARCHAR(255),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    data LONGTEXT,

    PRIMARY KEY(profile, timestamp)

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# ib_day_watch
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_day_watch (
    id INT AUTO_INCREMENT PRIMARY KEY,

    profile VARCHAR(255),
    symbol VARCHAR(64),

    date DATE,

    count INT,
    enabled TINYINT(1),

    timestamp BIGINT DEFAULT (UNIX_TIMESTAMP()),

    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE UNIQUE INDEX idx_ib_day_watch_unique
ON ib_day_watch(symbol, date)
""")


# =========================================================
# ib_scan_watch
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_scan_watch (
    id INT AUTO_INCREMENT PRIMARY KEY,

    profile VARCHAR(255),
    symbol VARCHAR(64),

    ts_enter BIGINT DEFAULT (UNIX_TIMESTAMP()),
    ds_enter DATETIME DEFAULT CURRENT_TIMESTAMP,

    ts_exit BIGINT DEFAULT NULL,
    ds_exit DATETIME DEFAULT NULL,

    closed TINYINT(1) DEFAULT 0

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE INDEX idx_ib_scan_watch
ON ib_scan_watch(symbol)
""")


# =========================================================
# ib_orders
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,

    trade_id VARCHAR(255),
    symbol VARCHAR(64),

    side VARCHAR(32),
    status VARCHAR(64),
    event_type VARCHAR(64),

    data LONGTEXT,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE INDEX ib_ib_orders
ON ib_orders(trade_id)
""")


# =========================================================
# ib_order_commissions
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ib_order_commissions (
    id INT AUTO_INCREMENT PRIMARY KEY,

    trade_id VARCHAR(255),
    symbol VARCHAR(64),

    pnl DOUBLE,
    commission DOUBLE,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE INDEX ib_order_commissions_idx
ON ib_order_commissions(trade_id)
""")


# =========================================================
# task_orders
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS task_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,

    task_id INT,

    symbol VARCHAR(64),
    status VARCHAR(64),

    step INT,

    data LONGTEXT,

    timestamp BIGINT,

    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    trade_id VARCHAR(255)

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# chart_lines
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS chart_lines (
    id INT AUTO_INCREMENT PRIMARY KEY,

    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(32) NOT NULL,

    guid VARCHAR(255) NOT NULL,
    type VARCHAR(64) NOT NULL,

    data LONGTEXT NOT NULL

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# chart_indicator
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS chart_indicator (
    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(255) NOT NULL,

    data LONGTEXT NOT NULL

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE UNIQUE INDEX idx_chart_indicator_name
ON chart_indicator(name)
""")


# =========================================================
# trade_marker
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS trade_marker (
    id INT AUTO_INCREMENT PRIMARY KEY,

    symbol VARCHAR(64) NOT NULL,
    timeframe VARCHAR(32) NOT NULL,

    data LONGTEXT NOT NULL

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# events
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,

    source VARCHAR(255),
    type VARCHAR(255),
    name VARCHAR(255),

    symbol VARCHAR(64),

    data LONGTEXT,

    timestamp BIGINT,

    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# black_list
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS black_list (
    id INT AUTO_INCREMENT PRIMARY KEY,

    symbol VARCHAR(255),

    error LONGTEXT,

    provider_disable TINYINT(1),
    user_day_disable TINYINT(1),
    user_all_disable TINYINT(1),

    last_day VARCHAR(32)

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# watch_list
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS watch_list (
    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(255),
    type VARCHAR(255),
    symbol VARCHAR(255),

    dt_day VARCHAR(32),

    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


# =========================================================
# news
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS news (
    id INT AUTO_INCREMENT PRIMARY KEY,

    guid VARCHAR(255),
    provider VARCHAR(255),
    symbol VARCHAR(255),
    source VARCHAR(255),

    published_dt DATETIME,
    published_at BIGINT,

    url LONGTEXT,
    data LONGTEXT,

    provider_last_dt DATETIME,

    dt_day VARCHAR(32),
    dt_hh VARCHAR(32)

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE UNIQUE INDEX idx_news_unique
ON news(provider, symbol, guid)
""")


# =========================================================
# back_profile
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS back_profile (
    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(255),

    data LONGTEXT

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE UNIQUE INDEX idx_back_profile
ON back_profile(name)
""")


# =========================================================
# back_session
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS back_session (
    id INT AUTO_INCREMENT PRIMARY KEY,

    strategy VARCHAR(255),

    dt_from VARCHAR(64),
    dt_to VARCHAR(64),

    in_data LONGTEXT,
    trades LONGTEXT,
    markers LONGTEXT,
    indicators LONGTEXT,
    script LONGTEXT,

    ds_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")


cur.execute("""
CREATE INDEX idx_back_session
ON back_session(strategy, dt_from, dt_to)
""")


# =========================================================
# ai_trainingset
# =========================================================

cur.execute("""
CREATE TABLE IF NOT EXISTS ai_trainingset (
    id INT AUTO_INCREMENT PRIMARY KEY,

    symbol VARCHAR(255),

    live CHAR(1),

    gain DOUBLE,
    volume DOUBLE,

    date VARCHAR(32),
    start VARCHAR(64),
    end VARCHAR(64),

    in_data LONGTEXT

)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
""")