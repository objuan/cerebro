from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import websockets
import time as _time
import pandas as pd
import sqlite3
from datetime import datetime, timedelta,time
import time
import logging
from typing import List, Dict
import requests
from utils import *
from message_bridge import *
#from job_cache import JobCache
#from job import *
from renderpage import RenderPage
import warnings
from company_loaders import *
from market import *
from dataclasses import dataclass
from config import TF_SEC_TO_DESC
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


intervals = [10, 30, 60, 300] 

RETENTION_DAYS = 1

def ms(ts):
    return int(ts * 1000)

def now_ms():
    return int(time.time() * 1000)

def week_ago_ms():
    return ms(time.time() - RETENTION_DAYS * 86400)

class MuloJob:

    def __init__(self,db_file, config):
        
        self.ready=False
        #self.cache = JobCache()
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.db_file=db_file
        self.table_name="ib_ohlc_history"
        #self.liveActive=config["live_service"]["enabled"]
        self.last_ts = {}
        #self.max_symbols=config["database"]["live"]["max_symbols"]
        self.historyActive =config["live_service"]["fetch_enabled"]  

        self.TIMEFRAME_UPDATE_SECONDS =config["live_service"]["TIMEFRAME_UPDATE_SECONDS"]  
        self.TIMEFRAME_LEN_CANDLES =config["live_service"]["TIMEFRAME_LEN_CANDLES"]  

        self.market = MarketService(config).getMarket("AUTO")
        self.marketZone = None

        self.conn_exe=sqlite3.connect(db_file, isolation_level=None)
        self.cur_exe = self.conn_exe.cursor()
        self.cur_exe.execute("PRAGMA journal_mode=WAL;")
        self.cur_exe.execute("PRAGMA synchronous=NORMAL;")
        self.update_ts={}
        self.symbol_to_exchange_map={}

        
    def getCurrentZone(self):
        return self.market.getCurrentZone()
    
    async def db_updateTicker(self,new_ticker):
        #print(new_ticker)
        symbol = new_ticker["s"]
        #if not symbol  in self.symbol_to_exchange_map:
        #    return
    
        run_time = int(_time.time() * 1000)
        ds_run_time  = datetime.utcnow().isoformat()
        ex = self.get_exchange(symbol)
        tf = TF_SEC_TO_DESC[new_ticker["tf"]]

        sql=f"""
                          INSERT INTO ib_ohlc_history (
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
                            day_volume,
                            source,
                            updated_at,
                            ds_updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
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
 
                    """

        self.cur_exe.execute(sql,(ex,symbol,tf,new_ticker["ts"],new_ticker["o"],
                                              new_ticker["h"],new_ticker["l"],new_ticker["c"],
                                               new_ticker["v"],new_ticker["v"]* new_ticker["c"],
                                               new_ticker["day_v"]
                                                 , "live",  run_time, ds_run_time))
        
        if int(new_ticker["tf"])>30:
            key = symbol+"_"+tf
       
            if not key in self.update_ts:
                self.update_ts[key] = new_ticker["ts"]

            last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(self.update_ts[key])/1000)
            if tf=="1m" and last_update_delta_min.total_seconds() > 60:
                await self._align_data(symbol,TF_SEC_TO_DESC[new_ticker["tf"]])
                self.update_ts[key] = new_ticker["ts"]
            elif tf == "5m" and last_update_delta_min.total_seconds() > 60*5:
                await self._align_data(symbol,TF_SEC_TO_DESC[new_ticker["tf"]])
                self.update_ts[key] = new_ticker["ts"]
            #print("last_update_delta_min" , last_update_delta_min)
 
    async def on_update_symbols(self,symbols,liveMode=True):
        logger.error(f"UPDATE SYMBOLS .. {symbols}")#MAX:{self.max_symbols}")

        self.symbols = symbols
          
        self.sql_symbols = str(self.symbols)[1:-1]

        if len(self.symbols) > 0:
            self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( self.symbols)
        else:
            logger.error(f"Empty symbol list !!! {symbols}")
            return
        #for s in self.symbols:
        #    self.tickers[s] = Ticker(symbol=s)

        logger.info(f"LISTEN SYMBOLS {self.symbols}")

        '''
        self.symbol_to_exchange_map = {}
        for _, row in self.df_fundamentals.iterrows():
            self.symbol_to_exchange_map[row["symbol"]] = row["exchange"]
        '''
      
        # startup 
        if liveMode:
            for symbol in self.symbols:
                for k,interval in TF_SEC_TO_DESC.items():
                    if int(k) > 30:
                        await self._align_data(symbol,interval)

    ##############

    def get_exchange(self,symbol):
        if not symbol in self.symbol_to_exchange_map:
                df = c_get_df(self.db_file,"SELECT exchange FROM STOCKS WHERE SYMBOL = ?",(symbol,))
                if not df.empty:
                    self.symbol_to_exchange_map[symbol] = df.iloc[0]["exchange"]
        return self.symbol_to_exchange_map[symbol]
    
    async def _fetch_missing_history(self,cursor, symbol, timeframe, since):
        #since = week_ago_ms()

        try:
            update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
            candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

            logger.info(f">> Fetching history s:{symbol} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
            
            #dt_start =  datetime.fromtimestamp(float(since)/1000)

            exchange = self.get_exchange(symbol)

            if timeframe == "1m":
                dt_end = datetime.utcnow()
                dt_start = dt_end - timedelta(days=6)
                logger.info(f">> Fetching LAST WEEK only for 1m {symbol} {dt_start} -> {dt_end}")

                df = yf.download(
                    tickers=symbol,
                    start=dt_start.strftime("%Y-%m-%d"),
                    interval="1m",
                    auto_adjust=False,
                    progress=False,
                )

                await self.process_data(exchange,symbol, timeframe, cursor, df)

            else:

                MAX_WINDOW = timedelta(days=7)

                dt_cursor = datetime.fromtimestamp(float(since) / 1000)
                dt_now = datetime.utcnow()

                batch_count = 500
                i = 0
                while dt_cursor < dt_now:

                    dt_end = min(dt_cursor + MAX_WINDOW, dt_now)

                    logger.info(
                        f"Fetching {timeframe} chunk {symbol} {dt_cursor} -> {dt_end}"
                    )

                    df = yf.download(
                        tickers=symbol,
                        start=dt_cursor.strftime("%Y-%m-%d"),
                        end=dt_end.strftime("%Y-%m-%d"),
                        interval=timeframe,
                        auto_adjust=False,
                        progress=False,
                    )

                    if not await self.process_data(exchange,symbol, timeframe, cursor, df):
                        break

                    # AVANZA IL CURSORE DI 7 GIORNI
                    dt_cursor = dt_end - timedelta(hours=1)

        except:
            logger.error("ERROR", exc_info=True)

    ########

    async def process_data(self,exchange,symbol,timeframe,cursor,df):
                
                if df.empty:
                    logger.info("No data returned, stopping.")
                    return False

                df = df.reset_index()
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

                dateName = "Date" if "Date" in df.columns else "Datetime"
                df[dateName] = df[dateName].astype("int64") // 10**9

                ohlcv = [
                    (b[0] * 1000, b.Open, b.High, b.Low, b.Close, b.Volume)
                    for b in df.itertuples(index=False)
                ]

                # ultima candela parziale
                ohlcv = ohlcv[:-1]

                logger.info(f"Rows fetched: {len(ohlcv)}")

                if not ohlcv:
                    return False

                for ts, open_, high, low, close, vol in ohlcv:
                    cursor.execute("""
                        INSERT INTO ib_ohlc_history (
                            exchange, symbol, timeframe, timestamp,
                            open, high, low, close,
                            base_volume, quote_volume,
                            source, updated_at, ds_updated_at
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
                        exchange,
                        symbol,
                        timeframe,
                        ts,
                        open_,
                        high,
                        low,
                        close,
                        vol,
                        vol * close,
                        "yahoo",
                        int(time.time() * 1000),
                        datetime.utcnow().isoformat()
                    ))

                cursor.commit()
                return True

    async def _align_data(self, symbol, timeframe):
        if not self.historyActive:
            return

        try:
            #logger.info(f"align_data {symbol} {timeframe}")

            query_max = f"""
                SELECT max(timestamp) as max
                FROM {self.table_name}
                WHERE symbol = ? and timeframe=? and source != 'live'
                """

            conn = sqlite3.connect(self.db_file)
            
            #for symbol in self.live_symbols():
            if True:
                    max_dt=None
                    update = False
                    #df_min = pd.read_sql_query(query_min, conn, params= (symbol, timeframe))
                    df_max = pd.read_sql_query(query_max, conn, params= (symbol, timeframe))
                    #print(df)
                    if df_max.iloc[0]["max"]:
                        #if not df_min.iloc[0]["min"]:
                            max_dt = int(df_max.iloc[0]["max"]/1000) # ultima data in unix time    
                        #else:
                        #    max_dt = int(df_min.iloc[0]["min"]/1000) # ultima data in unix time 
                    

                    #logger.info(f"max_dt {max_dt}")
                    if max_dt:
                        #if  self.marketZone == MarketZone.LIVE:
        
                            last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(max_dt))

                            #cache_key = f"{symbol}_{timeframe}_{max_dt}"
                            #val = self.cache.getCache(cache_key)
                            #if not val:
                            logger.info(f"LAST UPDATE DELTA {symbol} {timeframe} {last_update_delta_min}")
                            # devo aggiornare ??? 
                            
                            if (timeframe =="1m" and last_update_delta_min.total_seconds()/60 > 1):
                                update=True
                            if (timeframe =="5m" and last_update_delta_min.total_seconds()/60 > 5):
                                update=True
                            if (timeframe =="1h" and last_update_delta_min.total_seconds()/60 > 30):
                                update=True
                            if (timeframe =="1d" and last_update_delta_min.total_seconds()/60 > 24*60):
                                update=True

                    else:
                        update=True
                        max_dt = int(
                            (datetime.now() - timedelta(seconds=self.TIMEFRAME_LEN_CANDLES[timeframe]))
                            .timestamp()
                            )
                        logger.info(f"BEGIN HISTORY {max_dt} ")

                    #update=True
                    if update:
                        #cache_key = f"{symbol}_{timeframe}_{max_dt}"
                        #val = self.cache.getCache(cache_key)
                        #print("CACHE",df)
                        #if not val:
                        if True:
                            #logger.debug(f"MAX.. {max_dt}")
                            logger.info(f"UPDATE HISTORY symbol:{symbol} tf:{timeframe} ->  since:{max_dt} {datetime.fromtimestamp(float(max_dt))}")

                            await self._fetch_missing_history(conn,symbol,timeframe,max_dt*1000)
                            #self.cache.addCache_str(cache_key,cache_key)
                        else:
                            pass
                        
            conn.close()     
        except: 
            logger.error("ERROR",exc_info=True)

    async def ohlc_data(self,symbol: str, timeframe: str, limit: int = 1000):
        await self._align_data(symbol,timeframe)
       
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
    
    ########## tutti insieme
    async def history_data(self,symbols: List[str], timeframe: str, *, since : int=None, limit: int = 1000):
        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        for symbol in symbols:
            await self._align_data(symbol,timeframe)

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


        
    #######################

    '''
    def getTicker(self,symbol):
        if symbol in self.tickers:
            return self.tickers[symbol]
        else:
            return None
        
    def getTickersDF(self):
        if not self.tickers:
            return pd.DataFrame(
                columns=["symbol", "timestamp", "price", "bid", "ask", "volume_day"]
            )
  
        df = pd.DataFrame( [ t for k,t in self.tickers.items()])
    
        # sicurezza: timestamp come datetime
        #df["datetime"] = pd.to_datetime(df["timestamp"]/1000, utc=True, errors="coerce")
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df
    '''
    async def last_close(self,symbol: str,sym_start_time:datetime = None)-> float:
        if not sym_start_time:
            await self._align_data(symbol,"1m")

            ieri_mezzanotte = (
                (datetime.now()
                - timedelta(days=1))
                .replace(hour=23, minute=59, second=59, microsecond=0)
                
            )
        else:

            ieri_mezzanotte = (
                    (sym_start_time
                    - timedelta(days=1))
                    .replace(hour=23, minute=59, second=59, microsecond=0)
                    
                )
        unix_time = int(ieri_mezzanotte.timestamp()) * 1000
        #print("Last close time ", unix_time)
        df = self.get_df(f"""
                SELECT close 
                FROM ib_ohlc_history
                WHERE symbol='{symbol}' AND timeframe='1m'
                AND timestamp < {unix_time}
                ORDER BY timestamp DESC
                LIMIT 1
            """)

        if len(df)>0:
            return  float(df.iloc[0][0])
        else:
            return 0
    #######################
    
    def get_df(self,query, params=()):
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_disct(self,query, params=()):
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    