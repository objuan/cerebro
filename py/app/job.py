from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
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

logger = logging.getLogger(__name__)

RETENTION_DAYS = 1

def ms(ts):
    return int(ts * 1000)

def now_ms():
    return int(time.time() * 1000)

def week_ago_ms():
    return ms(time.time() - RETENTION_DAYS * 86400)


class Job:

    def __init__(self,db_file,max_symbols, table_name, live_table_name,historyActive=True, liveActive=True):
        
        self.symbols=[]
        self.db_file=db_file
        self.table_name=table_name
        self.live_table_name=live_table_name
        self.historyActive=historyActive
        self.liveActive=liveActive
        self.last_ts = {}
        self.max_symbols=max_symbols

        '''
        conn = sqlite3.connect(self.db_file, isolation_level=None)
        cur = conn.cursor()
        cur.execute(f"""
            DELETE FROM {self.live_table_name}
        """)
        conn.close()
        '''
        self.update_stats()

    def update_stats(self):
        self.monitor = self.live_symbols_dict()
        logger.debug(self.monitor)
        self.symbols = [ x["symbol"]  for x in self.monitor ]
        if self.max_symbols != None:
             self.symbols = self.symbols [:self.max_symbols]
        
        self.sql_symbols = str(self.symbols)[1:-1]
        logger.info(f"LISTEN SYMBOLS {self.symbols}")

    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.symbols

    def live_symbols_query(self, max_symbols)-> str:
        pass

    def live_symbols_df(self)-> pd.DataFrame:
        sql=self.live_symbols_query(self.max_symbols)

        #logger.info(sql)
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        #print("---",len(df))
        return df
    
    def live_symbols_dict(self):
        #print("live_symbols_dict",self.max_symbols)
        sql=self.live_symbols_query(self.max_symbols)

        #print(sql)
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        
        #print(rows)
        conn.close()
        return [dict(r) for r in rows]

    def tick(self):
       pass
    
    async def fetch_live_candles(self):
        pass

    async def  _fetch_missing_history(self,cursor, symbol, timeframe, since):
        pass

    async def align_data(self, timeframe):

        try:
            query_min = f"""
                SELECT min(timestamp) as min
                FROM {self.table_name}
                WHERE symbol = ? and timeframe=? and source == 'live'
                """
        
            query_max = f"""
                SELECT max(timestamp) as max
                FROM {self.table_name}
                WHERE symbol = ? and timeframe=? and source != 'live'
                """

            conn = sqlite3.connect(self.db_file)
            
            for symbol in self.live_symbols():
                    max_dt=None
                    update = False
                    df_min = pd.read_sql_query(query_min, conn, params= (symbol, timeframe))
                    df_max = pd.read_sql_query(query_max, conn, params= (symbol, timeframe))
                    #print(df)
                    if df_max.iloc[0]["max"]:
                        if not df_min.iloc[0]["min"]:
                            max_dt = int(df_max.iloc[0]["max"]/1000) # ultima data in unix time    
                        else:
                            max_dt = int(df_min.iloc[0]["min"]/1000) # ultima data in unix time 
                    
                    if max_dt:
                        last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(max_dt))

                        logger.info(f"LAST UPDATE DELTA {last_update_delta_min}")
                        # devo aggiornare ??? 
                        
                        if (timeframe =="1m" and last_update_delta_min.total_seconds()/60 > 5):
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
                        logger.debug("MAX.. ",max_dt)
                        logger.info(f"UPDATE HISTORY symbol:{symbol} tf:{timeframe} ->  since:{max_dt} {datetime.fromtimestamp(float(max_dt))}")

                        await self._fetch_missing_history(conn,symbol,timeframe,max_dt*1000)
                        
            conn.close()     
        except: 
            logger.error("ERROR",exc_info=True)

    async def ohlc_data(self,symbol: str, timeframe: str, limit: int = 1000):
        await self.align_data(timeframe)
       
        query = f"""
            SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM {self.table_name}
            WHERE symbol=? AND timeframe=?
            ORDER BY timestamp DESC
            LIMIT ?"""
             
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params= (symbol, timeframe, limit))
        df = df.iloc[::-1].reset_index(drop=True)
      
        conn.close()     
        return df
    
    
    def history_data(self,symbols: List[str], timeframe: str, *, since : int=None, limit: int = 1000):
        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None
        self.align_data(timeframe)
        sql_symbols = str(symbols)[1:-1]
     
        conn = sqlite3.connect(self.db_file)
        if since:
            #since = int(dt_from.timestamp()) * 1000
            query = f"""
                SELECT *
                FROM {self.table_name}
                WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                and timestamp>= {since}
                ORDER BY timestamp DESC
                LIMIT {limit}"""
                
            #print("since",since)
            df = pd.read_sql_query(query, conn)
        else:
            query = f"""
                SELECT *
                FROM {self.table_name}
                WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                ORDER BY timestamp DESC
                LIMIT {limit}"""
          
            df = pd.read_sql_query(query, conn)
            #print(query)

        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()     
        return df
    
    async def history_at_time(self, timeframe, datetime):
        await self.align_data(timeframe)
        #sql_pairs = str(pairs)[1:-1]

        query = f"""
            SELECT *
            FROM {self.table_name}
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