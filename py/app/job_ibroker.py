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


logger = logging.getLogger(__name__)

conn_exe = sqlite3.connect(DB_FILE, isolation_level=None)
cur_exe = conn_exe.cursor()

cur_exe.execute("PRAGMA journal_mode=WAL;")
cur_exe.execute("PRAGMA synchronous=NORMAL;")

###########

TIMEFRAMES = ['1m', '5m']

conn_read = sqlite3.connect(DB_FILE, isolation_level=None)

class CryptoJob(Job):

    def __init__(self, db_file, max_pairs, historyActive=True, liveActive=True):
        super().__init__()
        self.db_file=db_file
        self.last_ts = {}
        self.max_pairs=max_pairs
        self.exchange: str = "binance"
        self.historyActive=historyActive
        self.liveActive=liveActive
        self.update_stats()

        conn = sqlite3.connect(DB_FILE, isolation_level=None)
        cur = conn.cursor()
        cur.execute("""
        DELETE FROM ohlc_live
        """)
        conn.close()

        # startup 
        #self.align_data()

    def tick(self):
       pass 

    def update_stats(self):
        self.monitor = self.live_symbols_dict()
        
        self.pairs = [ x["pair"]  for x in self.monitor ]
        self.sql_pairs = str(self.pairs)[1:-1]
        logger.info(f"LISTEN PAIRS {self.pairs}")

    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.pairs
    
    def live_symbols_df(self)-> pd.DataFrame:
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

        #logger.info(sql)
        conn = sqlite3.connect(self.db_file)

        df = pd.read_sql_query(sql, conn_read)
        conn.close()
        #print("---",len(df))
        return df
    
    def live_symbols_dict(self):
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

        #logger.info(sql)
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        
        #print(rows)
        conn.close()
        return [dict(r) for r in rows]

    async def fetch_live_candles(self):
        
        key = "all"
        last_seen = self.last_ts.get(key, 0)
        
        if self.liveActive:
          
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

    

    def _fetch_missing_history(self,cursor, pair, timeframe, since):
        #since = week_ago_ms()

        update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
        candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

        logger.info(f">> Fetching history p:{pair} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
        
        batch_count = 500
        i = 0
        while ( True):
            i=i+1

            logger.info(f"{i} ASK  {since}")

            ohlcv = exchange_ccxt.fetch_ohlcv(
                symbol=pair,
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
            INSERT INTO ohlc_history (
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
                    source,
                    updated_at,
                    ds_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange, pair, timeframe, timestamp)
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
            
                '''
                
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
                '''
                
            cursor.commit()

            

    def align_data(self, timeframe):


        query_min = """
            SELECT min(timestamp) as min
            FROM ohlc_history
            WHERE pair = ? and timeframe=? and source == 'live'
            """
      
        query_max = """
            SELECT max(timestamp) as max
            FROM ohlc_history
            WHERE pair = ? and timeframe=? and source != 'live'
            """
        
        conn = sqlite3.connect(self.db_file)
        
        for pair in self.pairs:
                max_dt=None
                update = False
                df_min = pd.read_sql_query(query_min, conn, params= (pair, timeframe))
                df_max = pd.read_sql_query(query_max, conn, params= (pair, timeframe))
                #print(df)
                if df_max.iloc[0]["max"]:
                    if not df_min.iloc[0]["min"]:
                        max_dt = int(df_max.iloc[0]["max"]/1000) # ultima data in unix time    
                    else:
                        max_dt = int(df_min.iloc[0]["min"]/1000) # ultima data in unix time 
                
                if max_dt:
                    last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(max_dt))

                    #logger.info(f"LAST UPDATE DELTA {last_update_delta_min}")
                    # devo aggiornare ??? 
                    
                    if (timeframe =="1m" and last_update_delta_min.total_seconds()/60 > 10):
                        update=True
                    if (timeframe =="5m" and last_update_delta_min.total_seconds()/60 > 30):
                        update=True
                    if (timeframe =="1h" and last_update_delta_min.total_seconds()/60 > 1):
                        update=True
                    if (timeframe =="1d" and last_update_delta_min.total_seconds()/60 > 24*60):
                        update=True
                else:
                    update=True
                    max_dt = int(
                        (datetime.now() - timedelta(seconds=seconds_from_candles(TIMEFRAME_LEN_CANDLES[timeframe], timeframe)))
                        .timestamp()
                        )
                #update=True
                if update:
                    print(max_dt)
                    logger.info(f"UPDATE HISTORY pair:{pair} tf:{timeframe} ->  since:{max_dt} {datetime.fromtimestamp(float(max_dt))}")

                    self._fetch_missing_history(conn,pair,timeframe,max_dt*1000)
                    
        conn.close()     
  

    def ohlc_data(self,pair: str, timeframe: str, limit: int = 1000):
        self.align_data(timeframe)

        query = """
            SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM ohlc_history
            WHERE pair=? AND timeframe=?
            ORDER BY timestamp DESC
            LIMIT ?"""
             
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(query, conn, params= (pair, timeframe, limit))
        df = df.iloc[::-1].reset_index(drop=True)
      
        conn.close()     
        return df
    
    
    def history_data(self,pairs: List[str], timeframe: str, *, since : int=None, limit: int = 1000):
        if len(pairs) == 0:
            logger.error("Pair empty !!!")
            return None
        self.align_data(timeframe)
        sql_pairs = str(pairs)[1:-1]
     
        conn = sqlite3.connect(self.db_file)
        if since:
            #since = int(dt_from.timestamp()) * 1000
            query = f"""
                SELECT *
                FROM ohlc_history
                WHERE pair in ({sql_pairs}) AND timeframe='{timeframe}'
                and timestamp>= {since}
                ORDER BY timestamp DESC
                LIMIT {limit}"""
                
            #print("since",since)
            df = pd.read_sql_query(query, conn)
        else:
            query = f"""
                SELECT *
                FROM ohlc_history
                WHERE pair in ({sql_pairs}) AND timeframe='{timeframe}'
                ORDER BY timestamp DESC
                LIMIT {limit}"""
          
            df = pd.read_sql_query(query, conn)
            #print(query)

        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()     
        return df
    
    def history_at_time(self, timeframe, datetime):
        self.align_data(timeframe)
        #sql_pairs = str(pairs)[1:-1]

        query = """
            SELECT *
            FROM ohlc_history
            WHERE timestamp >= ? and timestamp < ? AND timeframe=?
            """
        
        #datetime_after =  + timedelta(minutes=1)
        delta = timeframe_to_milliseconds(timeframe)

        unix_from = int(datetime.timestamp()) * 1000
        unix_to= unix_from+delta

       # logger.info(f"history_at_time -{sql_pairs}- {unix_from} {unix_to}")

        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params= (unix_from,unix_to,timeframe))
        conn.close()     
        return df
    
  
   
