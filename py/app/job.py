from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict
import requests
from utils import *
from message_bridge import *
from job_cache import JobCache
from job import *
from renderpage import RenderPage
import warnings
from company_loaders import *
from market import *
from dataclasses import dataclass
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


class Ticker:
    symbol:str
    timestamp : datetime
    price: float
    bid:float
    ask:float
    volume_day: float

    last_close:float
    day_open:float
    
    def __init__(self,symbol):
        self.symbol=symbol
        self.timestamp=0
        self.price=0
        self.bid=0
        self.ask=0
        self.volume_day=0
        self.last_close=0
        self.day_open=0

    def copy(self, other:"Ticker"):
        self.price=other.price
        self.bid=other.bid
        self.ask=other.ask
        self.timestamp=other.timestamp
        self.volume_day=other.volume_day
    def __str__(self):
        return f"{self.symbol} p:{self.price} ask:{self.ask} bid:{self.bid} vol:{self.volume_day}"

class Job:

    def __init__(self,db_file, config,table_name, live_table_name):
        
        self.cache = JobCache()
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.db_file=db_file
        self.table_name=table_name
        self.live_table_name=live_table_name
        self.liveActive=config["database"]["live"]["enabled"]
        self.last_ts = {}
        self.max_symbols=config["database"]["live"]["max_symbols"]
        self.historyActive =config["database"]["logic"]["fetch_enabled"]  

        self.TIMEFRAME_UPDATE_SECONDS =config["database"]["logic"]["TIMEFRAME_UPDATE_SECONDS"]  
        self.TIMEFRAME_LEN_CANDLES =config["database"]["logic"]["TIMEFRAME_LEN_CANDLES"]  

        self.market = MarketService(config).getMarket("AUTO")
        #logger.info(f"TIMEFRAME_LEN_CANDLES {self.TIMEFRAME_LEN_CANDLES}")
        #self.batch_client = MessageClient(MessageDatabase(db_file), "fetcher")
        #self.batch_client = AsyncMessageClient(MessageDatabase(db_file), "fetcher")

        #asyncio.create_task(self.on_receive())
             
        '''
        conn = sqlite3.connect(self.db_file, isolation_level=None)
        cur = conn.cursor()
        cur.execute(f"""
            DELETE FROM {self.live_table_name}
        """)
        conn.close()
        '''
        #self.update_stats()
    
    '''
    async def on_receive(self):
        while True:
            self.batch_client.tick()
            await asyncio.sleep(0.5)
    '''

    async def send_batch(self,rest_point, msg=None):
        
        url = "http://127.0.0.1:2000/"+rest_point

        if msg:
            params = msg
            response = requests.get(url, params=params, timeout=5)
        else:
            response = requests.get(url,  timeout=5)

        if response.ok:
            data = response.json()
            if data["status"] == "ok":
                return data["data"]
            else:
                logger.error("Errore:", response.status_code)
                return None
        else:
            logger.error("Errore:", response.status_code)
            return None

    async def scanner(self):
        pass

    async def on_update_symbols(self):
        logger.info(f"UPDATE SYMBOLS ..")#MAX:{self.max_symbols}")

        self.monitor = await self.send_batch("symbols")
        #logger.info(f"<< {df_symbols}")

        #self.monitor = self._live_symbols_dict()
        logger.debug(f" {self.monitor} .. { [x['symbol'] for x in self.monitor]}")

        if len(self.monitor) > 0:
            self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( [x['symbol'] for x in self.monitor])

        logger.debug(f"Fundamentals \n{self.df_fundamentals}")
                                              
        #logger.debug(f"self.monitor \n{self.monitor} \n{self.df_fundamentals}")
        
        self.symbols = [ x["symbol"]  for x in self.monitor ]
        if self.max_symbols != None:
             self.symbols = self.symbols [:self.max_symbols]
        
        self.sql_symbols = str(self.symbols)[1:-1]
        for s in self.symbols:
            self.tickers[s] = Ticker(symbol=s)

        logger.info(f"LISTEN SYMBOLS {self.symbols}")
      

    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.symbols

    def tick(self):
       pass
    
    async def fetch_live_candles(self):
        pass

    async def  _fetch_missing_history(self,cursor, symbol, timeframe, since):
        pass

    async def _align_data(self, symbol, timeframe):
        if not self.historyActive:
            return
        try:
            #logger.info(f"align_data {symbol} {timeframe}")

           

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
            
            #for symbol in self.live_symbols():
            if True:
                    max_dt=None
                    update = False
                    df_min = pd.read_sql_query(query_min, conn, params= (symbol, timeframe))
                    df_max = pd.read_sql_query(query_max, conn, params= (symbol, timeframe))
                    #print(df)
                    if df_max.iloc[0]["max"]:
                        #if not df_min.iloc[0]["min"]:
                            max_dt = int(df_max.iloc[0]["max"]/1000) # ultima data in unix time    
                        #else:
                        #    max_dt = int(df_min.iloc[0]["min"]/1000) # ultima data in unix time 
                    

                    #logger.info(f"max_dt {max_dt}")
                    if max_dt:
                        last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(max_dt))

                        cache_key = f"{symbol}_{timeframe}_{max_dt}"
                        val = self.cache.getCache(cache_key)
                        if not val:
                            logger.info(f"LAST UPDATE DELTA {symbol} {timeframe} {last_update_delta_min}")
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
                            (datetime.now() - timedelta(seconds=self.TIMEFRAME_LEN_CANDLES[timeframe]))
                            .timestamp()
                            )
                        logger.info(f"BEGIN HISTORY {max_dt} ")

                    #update=True
                    if update:
                        cache_key = f"{symbol}_{timeframe}_{max_dt}"
                        val = self.cache.getCache(cache_key)
                        #print("CACHE",df)
                        if not val:
                            #logger.debug(f"MAX.. {max_dt}")
                            logger.info(f"UPDATE HISTORY symbol:{symbol} tf:{timeframe} ->  since:{max_dt} {datetime.fromtimestamp(float(max_dt))}")

                            await self._fetch_missing_history(conn,symbol,timeframe,max_dt*1000)
                            self.cache.addCache_str(cache_key,cache_key)
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
    
    async def history_at_time_NOT_USED(self, timeframe, datetime):
        await self._align_data(timeframe)
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
    
    def last_price(self,symbol: str)-> float:
        df = self.get_df(f"""
                SELECT close 
                FROM ib_ohlc_live
                WHERE symbol='{symbol}' AND timeframe='1m'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        
        if len(df)>0:
            return  df.iloc[0][0]
        else:
            return 0
        
    def last_close(self,symbol: str)-> float:

        ieri_mezzanotte = (
                (datetime.now()
                - timedelta(days=1))
                .replace(hour=23, minute=59, second=59, microsecond=0)
                
            )
        unix_time = int(ieri_mezzanotte.timestamp()) * 1000
        print("Last close time ", unix_time)
        df = self.get_df(f"""
                SELECT close 
                FROM ib_ohlc_live
                WHERE symbol='{symbol}' AND timeframe='1m'
                AND timestamp < {unix_time}
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        
        if len(df)>0:
            return  df.iloc[0][0]
        else:
            return 0
        
    def updateTicker(self,ticker:Ticker):
        if ticker.symbol in self.tickers:
            self.tickers[ticker.symbol].copy(ticker)
        else:
            self.tickers[ticker.symbol] = ticker

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
        df = pd.DataFrame(
            [{
                "symbol": t.symbol,
                "timestamp": t.timestamp ,
                "price": t.price,
                "bid": t.bid,
                "ask": t.ask,
                "volume_day": t.volume_day
            } for k,t in self.tickers.items()]
        )
    
        # sicurezza: timestamp come datetime
        #df["datetime"] = pd.to_datetime(df["timestamp"]/1000, utc=True, errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
        

    def get_df(self,query, params=()):
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    