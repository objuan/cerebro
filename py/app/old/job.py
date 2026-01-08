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

tf_map = {
    10 : "10s",
    30 : "30s",
    60 : "1m",
    300 : "5m"
}

RETENTION_DAYS = 1

def ms(ts):
    return int(ts * 1000)

def now_ms():
    return int(time.time() * 1000)

def week_ago_ms():
    return ms(time.time() - RETENTION_DAYS * 86400)

class Job:

    def __init__(self,db_file, config,table_name):
        
        self.ready=False
        self.cache = JobCache()
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.db_file=db_file
        self.table_name=table_name
        self.liveActive=config["database"]["live"]["enabled"]
        self.last_ts = {}
        self.max_symbols=config["database"]["live"]["max_symbols"]
        self.historyActive =config["database"]["logic"]["fetch_enabled"]  

        self.TIMEFRAME_UPDATE_SECONDS =config["database"]["logic"]["TIMEFRAME_UPDATE_SECONDS"]  
        self.TIMEFRAME_LEN_CANDLES =config["database"]["logic"]["TIMEFRAME_LEN_CANDLES"]  

        self.market = MarketService(config).getMarket("AUTO")
        self.marketZone = None

        self.conn_exe=sqlite3.connect(db_file, isolation_level=None)
        self.cur_exe = self.conn_exe.cursor()
        self.cur_exe.execute("PRAGMA journal_mode=WAL;")
        self.cur_exe.execute("PRAGMA synchronous=NORMAL;")

        # live feeds
    
    async def bootstrap(self, onStartHandler):
        uri = "ws://localhost:2000/ws/tickers"
        
        try:
            # Ci si connette al server
            await self.on_update_symbols()

            async with websockets.connect(uri) as websocket:
                logger.info(f"Connesso a {uri}")
                
                # Invia un messaggio al server
                message = {"id": "client"}
                await websocket.send(json.dumps(message))
                
                def updateTickers(new_ticker):
                    print(new_ticker)
                    
                    run_time = int(_time.time() * 1000)*1000
                    ds_run_time  = datetime.utcnow().isoformat()

                    symbol = new_ticker["s"]
                    ex = self.symbol_to_exchange_map[symbol]
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
 
                    """

                    self.cur_exe.execute(sql,(ex,symbol,tf_map[new_ticker["tf"]],new_ticker["ts"],new_ticker["o"],
                                              new_ticker["h"],new_ticker["l"],new_ticker["c"],
                                               new_ticker["v"],new_ticker["v"]* new_ticker["c"] , "live",  run_time, ds_run_time))
                    '''
                    self.tickers.clear()
                    for tick in new_tickers:
                        self.tickers[tick["symbol"]] =tick
                    '''

                    #logger.debug(self.tickers)

                # live on last scanner

                # first
                new_tickers = await websocket.recv()
                updateTickers(json.loads(new_tickers))

                self.ready=True
                onStartHandler()

                while True:
                    # Riceve la risposta dal server
                    new_tickers = await websocket.recv()
                    updateTickers(json.loads(new_tickers))

                    #logger.info(f"< Ricevuto: {response}")


        except ConnectionRefusedError:
            logger.error("Errore: Assicurati che il server sia attivo!")
            exit(-1)
        except Exception as e:
            logger.error(f"Errore: {e}")
            exit(-1)


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

    #########
    async def scanner(self,profileName):
        logger.info(f".. Scanner call {time.ctime()}")

        await self.send_batch("scanner",{"name":profileName})
        #await self.batch_client.send_request("tws_batch", {"cmd":"scanner"})
        await self.on_update_symbols()
        logger.info(f".. Scanner call DONE {time.ctime()}")

    #########
    
    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.symbols
    
    async def on_update_symbols(self):
        logger.info(f"UPDATE SYMBOLS ..")#MAX:{self.max_symbols}")

        self.symbols = await self.send_batch("symbols")
        #logger.info(f"<< {df_symbols}")

        #self.monitor = self._live_symbols_dict()
        logger.debug(f" {self.symbols}")

        if len(self.symbols) > 0:
            self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( self.symbols)

        logger.debug(f"Fundamentals \n{self.df_fundamentals}")
                                              
        #logger.debug(f"self.monitor \n{self.monitor} \n{self.df_fundamentals}")
        
        #if self.max_symbols != None:
        #     self.symbols = self.symbols [:self.max_symbols]
        
        self.sql_symbols = str(self.symbols)[1:-1]
        #for s in self.symbols:
        #    self.tickers[s] = Ticker(symbol=s)

        logger.info(f"LISTEN SYMBOLS {self.symbols}")

        self.symbol_to_exchange_map = {}
        for _, row in self.df_fundamentals.iterrows():
            self.symbol_to_exchange_map[row["symbol"]] = row["exchange"]
      

    ##############
    async def _fetch_missing_history(self,cursor, symbol, timeframe, since):
        #since = week_ago_ms()

        try:
            update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
            candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

            logger.info(f">> Fetching history s:{symbol} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
            
            dt_start =  datetime.fromtimestamp(float(since)/1000)
            exchange = self.symbol_to_exchange_map[symbol]
        
            batch_count = 500
            i = 0
            while ( True):
                i=i+1

                #logger.info(f"{i} ASK  {dt_start}")

                ###########
                df = yf.download(
                    tickers=symbol,
                    start=dt_start.strftime("%Y-%m-%d"),
                    #period="1d",
                    interval=timeframe,
                    auto_adjust=False,
                    progress=False,
                )
                df = df.reset_index()
                df.columns = [
                    c[0] if isinstance(c, tuple) else c
                    for c in df.columns
                ]
                #logger.debug(df.head())      
                dateName = "Date"
                if not dateName in df.columns:
                    dateName ="Datetime"
                
                df[dateName] = df[dateName].astype("int64") // 10**9

                #logger.debug(df.head())      
                # 3. Converti i dati in un formato leggibile (List of Dicts)
                # util.df(bars) creerebbe un DataFrame, ma per JSON usiamo una lista
                ohlcv =  [
                    (b[0]*1000, b.Open, b.High, b.Low, b.Close, b.Volume)
                        for b in df.itertuples(index=False)
                ]

                # lì'ultima è parsiale
                ohlcv = ohlcv[:-1]
                #print(data)

                ################

                logger.debug(f"{i} Find rows # {len(ohlcv)}")
                if len(ohlcv) <1:
                    break

                last = ohlcv[-1]
                since = last[0] + 1
                #logger.info(f"last # {last}")

                for o in ohlcv:
                    ts, open_, high, low, close, vol = o
                    
                    #logger.debug(f"add {exchange} {symbol} {timeframe} {ts}")
                    cursor.execute("""
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
                break
        except:
            logger.error("ERROR", exc_info=True)

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
                        if  self.marketZone == MarketZone.LIVE:
        
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


        
    #######################

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
        '''
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
        '''
        df = pd.DataFrame( [ t for k,t in self.tickers.items()])
    
        # sicurezza: timestamp come datetime
        #df["datetime"] = pd.to_datetime(df["timestamp"]/1000, utc=True, errors="coerce")
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df
        
    #######################
    
    def get_df(self,query, params=()):
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    