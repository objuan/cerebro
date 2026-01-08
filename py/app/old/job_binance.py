import ccxt
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
from datetime import datetime
import time
import logging
from typing import List, Dict

from utils import *
from job import *
from renderpage import RenderPage
from config import TIMEFRAME_LEN_CANDLES
import warnings
warnings.filterwarnings("ignore")
#from scanner.crypto import ohlc_history_manager

DB_FILE = "../db/crypto.db"

exchange_ccxt = ccxt.binance({
    "enableRateLimit": True,
    'verbose': False,
    "options": {"defaultType": "spot"}
})



logging.getLogger("ccxt").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

conn_exe = sqlite3.connect(DB_FILE, isolation_level=None)
cur_exe = conn_exe.cursor()

cur_exe.execute("PRAGMA journal_mode=WAL;")
cur_exe.execute("PRAGMA synchronous=NORMAL;")


###########

TIMEFRAMES = ['1m', '5m']

conn_read = sqlite3.connect(DB_FILE, isolation_level=None)


class CryptoJob(Job):

    def __init__(self, db_file, max_symbols, historyActive=True, liveActive=True):
        super().__init__(db_file,max_symbols, "cry_ohlc_history","cry_ohlc_live",historyActive,liveActive)
        self.exchange ="binance"
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()

        cur.execute("""
    CREATE TABLE IF NOT EXISTS cry_ohlc_history (
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

        source TEXT,        -- ccxt | live
        updated_at INTEGER,          
        ds_updated_at TEXT,

        PRIMARY KEY (exchange, symbol, timeframe, timestamp)
    )""")
        conn.close()


    def tick(self):
       pass 

    def live_symbols_query(self, max_symbols)-> str:
        return f"""
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol
                        ORDER BY updated_at DESC
                    ) AS rn
                FROM cry_ohlc_live WHERE timeframe = '1m'
            )
            WHERE rn = 1
            ORDER BY quote_volume_24h desc limit 
            """  + " " +str(max_symbols)

    async def fetch_live_candles(self):
        
        key = "all"
        last_seen = self.last_ts.get(key, 0)
        
        if self.liveActive:
          
            #print(self.sql_pairs)
            cur_exe.execute(f"""
            INSERT OR REPLACE INTO cry_ohlc_history
            SELECT
                exchange,
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                base_volume,
                quote_volume,
                'live',
                updated_at,
                ds_updated_at
            FROM cry_ohlc_live
            WHERE exchange = ?
                    and  symbol in ({self.sql_symbols})
                AND updated_at > ?
            """, (self.exchange,  last_seen))

        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # get 
        cur.execute("""
            SELECT symbol, timeframe as tf ,updated_at as ts, timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM cry_ohlc_history
            WHERE exchange = ? 
              AND updated_at >= ?
            ORDER BY updated_at ASC
        """, (self.exchange,  last_seen))

        rows = cur.fetchall()

        conn.close()

        if rows:
            self.last_ts[key] = rows[-1]["ts"]

        return [dict(r) for r in rows]

    
    def _fetch_missing_history(self,cursor, symbol, timeframe, since):
        #since = week_ago_ms()

        update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
        candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

        logger.info(f">> Fetching history s:{symbol} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
        
        batch_count = 500
        i = 0
        while ( True):
            i=i+1

            logger.info(f"{i} ASK  {since}")

            ohlcv = exchange_ccxt.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=batch_count
            )

            logger.info(f"{i} Find rows # {len(ohlcv)}")
            if len(ohlcv) <1:
                break

            last = ohlcv[-1]
            since = last[0] + 1
            #logger.info(f"last # {last}")

            for o in ohlcv:
                ts, open_, high, low, close, vol = o
                
                cursor.execute("""
            INSERT INTO cry_ohlc_history (
                    exchange,
                    symbol,
                    timeframe,
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    base_volume,
                    quote_volume,
                    source,
                    updated_at,
                    ds_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange, symbol, timeframe, timestamp)
                DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    base_volume = excluded.base_volume,
                    quote_volume = excluded.quote_volume,
                    source = excluded.source,
                    updated_at = excluded.updated_at,
                    ds_updated_at = excluded.ds_updated_at
                
                            
                """, (
                    "binance",
                    symbol,
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
            
                '''
                
                cursor.execute("""
                INSERT OR REPLACE INTO  cry_ohlc_history VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?
                )
                """, (
                    "binance",
                    symbol,
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
                '''
                
            cursor.commit()

            

   