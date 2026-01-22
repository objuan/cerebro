from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from ib_insync import Contract, Ticker
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
from renderpage import RenderPage
import warnings
from company_loaders import *
from market import *
from dataclasses import dataclass
warnings.filterwarnings("ignore")
#from scanner.crypto import ohlc_history_manager
from config import TF_SEC_TO_DESC

logger = logging.getLogger(__name__)


class MuloLiveClient:

    def __init__(self,db_file, config, propManager):
        self.db_file = db_file
        self.ready=False
        self.propManager=propManager
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.symbol_to_exchange_map={}

        self.market = MarketService(config).getMarket("AUTO")
        self.sym_mode = config["live_service"]["mode"] =="sym"
            
        self.on_symbols_update = MyEvent()
        self.on_candle_receive = MyEvent()
        self.on_ticker_receive = MyEvent()

        propManager.add_computed("root.sym_mode", lambda: self.sym_mode )
        propManager.add_computed("root.tz", lambda:  MZ_TABLE[self.getCurrentZone()] )

     
     
    async def bootstrap(self):
        
        await self._on_update_symbols()
        if self.sym_mode:
                self.sym_time = await self.send_cmd("/sym/time")
                self.sym_speed = await self.send_cmd("/sym/speed")
                logger.info(f"START SYM TIME: {self.sym_time} sp:{self.sym_speed}")
          
    async def batch(self):
        try:
            uri = "ws://localhost:3000/ws/tickers"
                
            async with websockets.connect(uri) as websocket:
                logger.info(f"Connesso a {uri}")
                
                # Invia un messaggio al server
                message = {"id": "client"}
                await websocket.send(json.dumps(message))
                
                async def updateTickers(new_ticker):
                    #logger.info(f"new_ticker {new_ticker}")

                  
                    if self.sym_mode and "sym" in new_ticker:
                        self.sym_time = new_ticker["sym"]
                        self.sym_speed = new_ticker["speed"]

                    elif "evt" in new_ticker:
                        name = new_ticker["evt"]
                        if name =="on_update_symbols":
                             await self._on_update_symbols()

                    else:
                        new_ticker["tf"]= TF_SEC_TO_DESC[new_ticker["tf"]]
                        #new_ticker["ts"] = new_ticker["ts"]/1000  # to ms
                        #print(new_ticker)
                        await self.on_candle_receive(new_ticker)
                        

                        if new_ticker["tf"]=="10s" and new_ticker["s"] in self.tickers:
                            
                            '''
                            t:Ticker= self.tickers[new_ticker["s"]]
                            t.last = new_ticker["c"]
                            t.volume = new_ticker["day_v"]
                            t.low = new_ticker["l"]
                            t.high = new_ticker["h"]
                            t.bid = new_ticker["bid"]
                            t.ask = new_ticker["ask"]
                            t.time = datetime.fromtimestamp( new_ticker["ts"]  / 1000) 
                            t.gain = ((new_ticker["c"]-t.last_close) / t.last_close) * 100
                            '''
                            t = self.tickers[new_ticker["s"]]
                            t.update({"last": new_ticker["c"],"volume": new_ticker["v"],"ask": new_ticker["ask"],"bid": new_ticker["bid"],
                                      "low": new_ticker["l"],"high": new_ticker["h"],
                                        "gain": ((new_ticker["c"]-t["last_close"]) / t["last_close"]) * 100, "ts":new_ticker["ts"] })
                            
                            #logger.info(f"..  {t}")
                            # send event 
                            await self.on_ticker_receive(t)
                            #logger.info(f"new_ticker {t}")
                        #self.render_page.send({"type":"candle","data":new_ticker}) 
                   
                # live on last scanner

                # first
                new_ticker = await websocket.recv()
                await updateTickers(json.loads(new_ticker))

                self.ready=True
              
                while True:
                    new_ticker = await websocket.recv()
                    await updateTickers(json.loads(new_ticker))


        except ConnectionRefusedError:
            logger.error("Errore: Assicurati che il server sia attivo!")
            exit(-1)
        except Exception as e:
            logger.error(f"Errore: {e}")
            exit(-1)

   
    def getCurrentZone(self):
        return self.market.getCurrentZone()

    #########
    async def setSymTime(self,time):
        await self.send_cmd("/sym/time/set", time)
    
    async  def setSymSpeed(self,speed):
        await self.send_cmd("/sym/speed/set", speed)
        
    def ordered_tickers(self) -> Ticker:
         #logger.info(f"{self.tickers}")
         return sorted(  self.tickers.values(),
                        key=lambda t: t["gain"],
                        reverse=True)
         
    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.symbols
    
    async def _on_update_symbols(self):
        logger.info(f"LIVE >> UPDATE SYMBOLS ..")#MAX:{self.max_symbols}")

        self.symbols = await self.send_cmd("symbols")

        logger.info(f"<< {self.symbols}")

        if len(self.symbols) > 0:
            self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( self.symbols)

        #logger.debug(f"Fundamentals \n{self.df_fundamentals}")
                                              
        self.sql_symbols = str(self.symbols)[1:-1]
   
        self.tickers = {}
        for s in self.symbols:
            ''''
            t = Ticker( contract= Contract(symbol=s))
            t.symbol = s
            t.last_close = await self.last_close(s)
            t.gain = 0
            self.tickers[s] =t
            '''
            self.tickers[s] = { "symbol": s, "gain" : 0, "low":0 , "high":0, "last" : 0, "volume": 0, "ts" : 0, "ask" : 0, "bid":0,
                               "last_close": await self.last_close(s)}
        self.on_symbols_update(self.symbols)

        logger.info(f"UPDATE SYMBOLS DONE {self.tickers}")  

    #######################

    def get_exchange(self,symbol):
        if not symbol in self.symbol_to_exchange_map:
                df = self.get_df(self.db_file,"SELECT exchange FROM STOCKS WHERE SYMBOL = ?",(symbol,))
                if not df.empty:
                    self.symbol_to_exchange_map[symbol] = df.iloc[0]["exchange"]
        return self.symbol_to_exchange_map[symbol]

    def getTicker(self,symbol):
        if symbol in self.tickers:
            return self.tickers[symbol]
        else:
            return None
        
    def getTickersDF(self):
        if not self.tickers:
            return pd.DataFrame(
                columns=["symbol", "timestamp", "price", "bid", "ask", "volume_day","ts"]
            )
        df = pd.DataFrame( [ t for k,t in self.tickers.items()])
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df

        
    def get_fundamentals(self,symbol)->pd.DataFrame:
        return self.df_fundamentals[self.df_fundamentals["symbol"]==symbol  ]
            
    ###############

    async def ohlc_data(self,symbol: str, timeframe: str, limit: int = 1000)-> pd.DataFrame:
        #if timeframe not in ["10s","30s"]:
        #    await self._align_data(symbol,timeframe)

        if self.sym_mode:
            ticker = self.tickers[symbol]
            if not ticker or not "ts" in ticker:
                last_time = 0
            else:
                last_time = ticker["ts"]
            #logger.info(f"last_time {last_time}")
            query = f"""
                SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
                FROM ib_ohlc_history
                WHERE symbol=? AND timeframe=? and timestamp<= {last_time}
                ORDER BY timestamp DESC
                LIMIT ?"""

        else:
            query = f"""
                SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
                FROM ib_ohlc_history
                WHERE symbol=? AND timeframe=?
                ORDER BY timestamp DESC
                LIMIT ?"""
             
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params= (symbol, timeframe, limit))
        df = df.iloc[::-1].reset_index(drop=True)
      
        conn.close()     
        return df

    async def history_data(self,symbols: List[str], timeframe: str, *, since : int=None, limit: int = 1000):

        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        sql_symbols = str(symbols)[1:-1]
     
        conn = sqlite3.connect(self.db_file)
        if since:
            #since = int(dt_from.timestamp()) * 1000
            query = f"""
                SELECT *
                FROM ib_ohlc_history
                WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                and timestamp>= {since}
                ORDER BY timestamp DESC
                LIMIT {limit}"""
                
            #print("since",since)
            df = pd.read_sql_query(query, conn)
        else:
            query = f"""
                SELECT *
                FROM ib_ohlc_history
                WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                ORDER BY timestamp DESC
                LIMIT {limit}"""
          
            df = pd.read_sql_query(query, conn)
            #print(query)

        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()     
        return df


    async def _align_data(self, symbol, timeframe):
    
        try:
            #logger.info(f"align_data {symbol} {timeframe}")

            query_max = f"""
                SELECT max(timestamp) as max
                FROM ib_ohlc_history
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
                        max_dt = int(df_max.iloc[0]["max"]/1000) # ultima data in unix time    
                       
                    #logger.info(f"max_dt {max_dt}")
                    if max_dt:
                        #if  self.marketZone == MarketZone.LIVE:
        
                            last_update_delta_min = datetime.now() - datetime.fromtimestamp(float(max_dt))

                            logger.info(f"LAST UPDATE DELTA {symbol} {timeframe} {last_update_delta_min}")
                            # devo aggiornare ??? 
                            
                            if (timeframe =="1m" and last_update_delta_min.total_seconds()/60 > 1):
                                update=True
                            if (timeframe =="5m" and last_update_delta_min.total_seconds()/60 > 5):
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
                        if True:
                            logger.info(f"UPDATE HISTORY symbol:{symbol} tf:{timeframe} ->  since:{max_dt} {datetime.fromtimestamp(float(max_dt))}")
                            await self._fetch_missing_history(conn,symbol,timeframe,max_dt*1000)
                        else:
                            pass
                        
            conn.close()     
        except: 
            logger.error("ERROR",exc_info=True)

    async def _fetch_missing_history(self,cursor, symbol, timeframe, since):
        #since = week_ago_ms()

        try:
            update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
            candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

            logger.info(f">> Fetching history s:{symbol} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
            
            dt_start =  datetime.fromtimestamp(float(since)/1000)

            exchange = self.get_exchange(symbol)
        
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

    #######################
    
    async def last_close(self,symbol: str)-> float:
        if not self.sym_mode:
            #await self._align_data(symbol,"1m")

            ieri_mezzanotte = (
                (datetime.now()
                - timedelta(days=1))
                .replace(hour=23, minute=59, second=59, microsecond=0)
                
            )
        else:
            
            ieri_mezzanotte = (
                    (self.sym_time
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
        
    def get_df(self,query, params=()):
        conn = sqlite3.connect(self.db_file)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def execute(self,sql, params=()):
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        cur.execute(sql, params)
        line_id = cur.lastrowid
        conn.commit()
        return line_id
    
    async def send_cmd(self,rest_point, msg=None):
        
        url = "http://127.0.0.1:3000/"+rest_point

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
    

    