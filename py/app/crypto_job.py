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

#from scanner.crypto import ohlc_history_manager
logger = logging.getLogger(__name__)

DB_FILE = "../db/crypto.db"

exchange_ccxt = ccxt.binance({
    "enableRateLimit": True,
    'verbose': False,
    "options": {"defaultType": "spot"}
})


conn_exe = sqlite3.connect(DB_FILE, isolation_level=None)
cur_exe = conn_exe.cursor()

cur_exe.execute("PRAGMA journal_mode=WAL;")
cur_exe.execute("PRAGMA synchronous=NORMAL;")


###########

TIMEFRAMES = ['1m', '5m']


class CryptoJob(Job):

    def __init__(self, db_file, max_pairs, debugMode=False):
        super().__init__()
        self.db_file=db_file
        self.last_ts = {}
        self.max_pairs=max_pairs
        self.exchange: str = "binance"
        self.debugMode=debugMode
        self.update_stats()

        # startup 
        self.align_data()

    def tick(self):
       pass 

    def update_stats(self):
        self.monitor = self.top_pairs()
        
        self.pairs = [ x["pair"]  for x in self.monitor ]
        self.sql_pairs = str(self.pairs)[1:-1]
        logger.info(f"LISTEN PAIRS {self.pairs}")

    def live_pairs(self, volume):
        return  ["BTC/USDC", "ETH/USDC"]
    
    def top_pairs(self):
        sql="""
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY pair
                        ORDER BY updated_at DESC
                    ) AS rn
                FROM ohlc_live WHERE timeframe = '1m'
            )
            WHERE rn = 1
            ORDER BY quote_volume_24h desc limit 
            """  + " " +str(self.max_pairs)

        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        print(rows)

        conn.close()

        return [dict(r) for r in rows]

    async def fetch_new_candles(self):
        key = "all"
        last_seen = self.last_ts.get(key, 0)
        
        if not self.debugMode:
          
            #print(self.sql_pairs)
            cur_exe.execute(f"""
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
                    and  pair in ({self.sql_pairs})
                AND updated_at > ?
            """, (self.exchange,  last_seen))

        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # get 
        cur.execute("""
            SELECT pair, timeframe as tf ,updated_at as ts, timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM ohlc_history
            WHERE exchange = ? 
              AND updated_at >= ?
            ORDER BY updated_at ASC
        """, (self.exchange,  last_seen))

        rows = cur.fetchall()

        conn.close()

        if rows:
            self.last_ts[key] = rows[-1]["ts"]

        return [dict(r) for r in rows]

    def _fetch_new_candles(
        self,
        pair: str,
        timeframe: str
    ) -> List[Dict]:

        if self.debugMode:
            return

        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        key = (self.exchange, pair, timeframe)
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
        """, (self.exchange, pair, timeframe, last_seen))

        rows = cur.fetchall()

        #logger.info(f"Find rows # {len(rows)}")
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
        """, (self.exchange, pair, timeframe, last_seen))
        #cur_exe.commit()

        conn.close()

        if rows:
            self.last_ts[key] = rows[-1]["updated_at"]

        return [dict(r) for r in rows]


    def fetch_missing_history(self,cursor, pair, timeframe, since,limit=1000):
        #since = week_ago_ms()

        logger.info(f"fetching history {pair} {timeframe} {since}")

        ohlcv = exchange_ccxt.fetch_ohlcv(
            symbol=pair,
            timeframe=timeframe,
            since=since,
            limit=limit
        )

        logger.info(f"Find rows # {len(ohlcv)}")

        for o in ohlcv:
            ts, open_, high, low, close, vol = o

            cursor.execute("""
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
        cursor.commit()

    def align_data(self, limit=1000):
        if self.debugMode:
            return
        
        query = """
            SELECT max(timestamp) as max
            FROM ohlc_history
            WHERE pair = ? and timeframe=? and source != 'live'
            """
             
        conn = sqlite3.connect(DB_FILE)

        for pair in self.pairs:
            for timeframe in TIMEFRAMES:
                df = pd.read_sql_query(query, conn, params= (pair, timeframe))
                max_dt = int(df.iloc[0]["max"])
                logger.info(f"STARTUP pair:{pair} tf:{timeframe} -> {max_dt}")

                self.fetch_missing_history(conn,pair,timeframe,max_dt,limit)
                
        conn.close()     
        return df

    def ohlc_data(self,pair: str, timeframe: str, limit: int = 1000):
        self.align_data()

        query = """
            SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM ohlc_history
            WHERE pair=? AND timeframe=?
            ORDER BY timestamp DESC
            LIMIT ?"""
             
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(query, conn, params= (pair, timeframe, limit))
        df = df.iloc[::-1].reset_index(drop=True)
        '''
        if len(df) < limit:
            since = calculate_since(timeframe, limit)
            logger.info(f"UPDATE CANDLES {pair} {timeframe} since {since} old:{len(df)}")
            self.fetch_missing_history(conn,pair,timeframe,since,limit)

            df = pd.read_sql_query(query, conn, params= (pair, timeframe, limit))
        '''
        conn.close()     
        return df
   
