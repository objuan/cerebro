from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
from datetime import datetime
import time
from typing import List, Dict

from job import *
#from scanner.crypto import ohlc_history_manager

DB_FILE = "../db/crypto.db"

exchange_ccxt = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})


conn_exe = sqlite3.connect(DB_FILE, isolation_level=None)
cur_exe = conn_exe.cursor()

cur_exe.execute("PRAGMA journal_mode=WAL;")
cur_exe.execute("PRAGMA synchronous=NORMAL;")


###########


class CryptoJob(Job):

    def __init__(self, db_file, max_pairs):
        super().__init__()
        self.db_file=db_file
        self.last_ts = {}
        self.max_pairs=max_pairs

    def tick(self):
       pass 


    def fetch_new_candles(
        self,
        pair: str,
        timeframe: str,
        exchange: str = "binance"
    ) -> List[Dict]:

        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        key = (exchange, pair, timeframe)
        last_seen = self.last_ts.get(key, 0)

        # get 
        cur.execute("""
            SELECT *
            FROM ohlc_live
            WHERE exchange = ?
              AND pair = ?
              AND timeframe = ?
              AND updated_at > ?
            ORDER BY updated_at ASC
        """, (exchange, pair, timeframe, last_seen))

        rows = cur.fetchall()

        #update

        cur_exe.execute("""
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
            updated_at,
            ds_updated_at
        FROM ohlc_live
           WHERE exchange = ?
              AND pair = ?
              AND timeframe = ?
              AND updated_at > ?
        """, (exchange, pair, timeframe, last_seen))
        #cur_exe.commit()

        conn.close()

        if rows:
            self.last_ts[key] = rows[-1]["updated_at"]

        return [dict(r) for r in rows]


    def fetch_missing_history(self,pair, timeframe, since):
        #since = week_ago_ms()

        print(f"📥 fetching history {pair} {timeframe} {since}")

        ohlcv = exchange_ccxt.fetch_ohlcv(
            symbol=pair,
            timeframe=timeframe,
            since=since,
            limit=1000
        )

        for o in ohlcv:
            ts, open_, high, low, close, vol = o

            cur_exe.execute("""
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
   
