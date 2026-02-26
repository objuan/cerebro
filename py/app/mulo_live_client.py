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
from news_service import NewService
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
        self.newService=None
        self.render_page=None
        self.propManager=propManager
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.ib_loop=None
        self.symbol_to_exchange_map={}

        self.market = MarketService(config).getMarket("AUTO")
        self.sym_mode = config["live_service"]["mode"] =="sym"
        self.sym_time = None
        self.sym_start_time = None
        self.sym_start_speed=None
        
        self.on_symbols_update = MyEvent()
        #self.on_symbols_update.debug=True
        self.on_partial_candle_receive = MyEvent()
        self.on_full_candle_receive = MyEvent()
        self.on_ticker_receive = MyEvent()

        propManager.add_computed("root.sym_mode", lambda: self.sym_mode )
        propManager.add_computed("root.tz", lambda:  MZ_TABLE[self.getCurrentZone()] )
        propManager.add_computed("root.sym_start_time", lambda: self.sym_start_time )
        propManager.add_computed("root.sym_start_speed", lambda: self.sym_start_speed )
     
     
    async def bootstrap(self):

        if self.sym_mode:
                self.sym_start_time =  await self.send_cmd("sym/time")
                self.sym_time = datetime.fromtimestamp(self.sym_start_time)
                self.sym_speed = await self.send_cmd("sym/speed")
                self.sym_start_speed = self.sym_speed
                logger.info(f"START SYM TIME: {self.sym_time} sp:{self.sym_speed}")
        await self._on_update_symbols()

    async def batch(self):
        try:
            uri = "ws://localhost:3000/ws/tickers"
                
            async with websockets.connect(uri,
                        ping_interval=30,
                        ping_timeout=60,
                        close_timeout=10,) as websocket:
                logger.info(f"Connesso a {uri}")
                
                # Invia un messaggio al server
                message = {"id": "client"}
                await websocket.send(json.dumps(message))
                
                async def updateTickers(new_ticker):
                    #logger.info(f"new_ticker {new_ticker}")
 
                    if "ticker" in new_ticker:
                        symbol =  new_ticker["ticker"]
                      
                        #logger.info(f"<<TICKER {new_ticker}")

                        t = self.tickers[symbol]
                        t.update({"last": new_ticker["last"],
                                  "day_volume": new_ticker["day_v"],
                                  "volume": new_ticker["v"],
                                  "ask": new_ticker["ask"],"bid": new_ticker["bid"],
                                   "open": new_ticker["open"],
                                   "low": new_ticker["low"],"high": new_ticker["high"],
                                  "gain": ((new_ticker["last"]-t["last_close"]) / t["last_close"]) * 100,
                                  "ts" : int(new_ticker["ts"]*1000)
                                  })
                            
                         #logger.info(f"..  {t}")
                         # send event 
                        await self.on_ticker_receive(t)

                    elif self.sym_mode and "sym" in new_ticker:
                        self.sym_time = new_ticker["sym"]
                        self.sym_speed = new_ticker["speed"]

                    elif "evt" in new_ticker:
                        name = new_ticker["evt"]
                        if name =="on_update_symbols":
                             await self._on_update_symbols()

                    else:
                        mode = new_ticker["m"]
                        new_ticker["tf"]= TF_SEC_TO_DESC[new_ticker["tf"]]
                        #new_ticker["ts"] = new_ticker["ts"]/1000  # to ms
                        #print(new_ticker)
                        # send to UI
                        if mode =="full":
                            await self.on_full_candle_receive(new_ticker)
                            if self.sym_mode:
                                await self.on_partial_candle_receive(new_ticker)
                        else:
                            await self.on_partial_candle_receive(new_ticker)
                       
                        
                        if new_ticker["tf"]=="10s" and new_ticker["s"] in self.tickers:
                            
                            t = self.tickers[new_ticker["s"]]
                            t.update({"last": new_ticker["c"],"volume": new_ticker["v"],"day_volume": new_ticker["day_v"],
                                      "ask": new_ticker["ask"],"bid": new_ticker["bid"],
                                      "low": new_ticker["l"],"high": new_ticker["h"],
                                        "gain": ((new_ticker["c"]-t["last_close"]) / t["last_close"]) * 100, 
                                        "ts":new_ticker["ts"] })
                            
                            #logger.info(f"..  {t}")
                            # send event 
                            await self.on_ticker_receive(t)
                           # logger.info(f"new_ticker {t}")
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
            logger.error(f"Errore", exc_info=True)
           # exit(-1)

   
    def getCurrentZone(self):
        return self.market.getCurrentZone()

    ##########
    '''
    async def scan_for_news(self, symbols=None):
        if symbols:
            await self.newService.scan(symbols)
        else:
            await self.newService.scan(self.symbols)
    '''
    #########
    async def setSymTime(self,time):
        self.sym_start_time = time
        await self.send_cmd("sym/time/set", {"time": time})
    
    async  def setSymSpeed(self,speed):
        self.sym_speed = speed
        self.sym_start_speed = speed
        await self.send_cmd("sym/speed/set", {"value":speed})
        
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

        try:
            new_symbols = await self.send_cmd("symbols")
            _mule_tickers = await self.send_cmd("tickers")

            #new_symbols = [ t["symbol"] for t in _mule_tickers] 
        
            set_new = set(new_symbols)
            set_old = set(self.symbols)

            to_add = list(set_new - set_old)       # presenti in new_symbols ma non prima
            to_remove = list(set_old - set_new)    # presenti prima ma non più
            common = list(set_new & set_old)       # presenti in entrambi

            self.symbols = new_symbols

            logger.info(f"<< {self.symbols} ADD {to_add} DEL {to_remove}")
            
            if len(self.symbols) > 0:
                self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( self.symbols)
                self.fundamentals_map = (
                self.df_fundamentals
                    .set_index("symbol")
                    .to_dict(orient="index")
    )
            #logger.debug(f"Fundamentals \n{self.df_fundamentals}")
                                                
            self.sql_symbols = str(self.symbols)[1:-1]
    
            self.tickers = {}

            for ticker in _mule_tickers:
                ''''
                t = Ticker( contract= Contract(symbol=s))
                t.symbol = s
                t.last_close = await self.last_close(s)
                t.gain = 0
                self.tickers[s] =t
                '''
                last_close=  await self.last_close(ticker["symbol"])
                if (last_close == 0): last_close = 0.000001
                gain =  ((ticker["last"] - last_close) / last_close) * 100
              

                self.tickers[ticker["symbol"]] = { "symbol": ticker["symbol"], 
                                    "gain" : gain, "low":0 , "high":0, "last" : ticker["last"], 
                                    "volume": 0, "ts" : 0,
                                    "ask" : 0, "bid":0,"day_volume" : ticker["last_volume"],
                                    "last_close": last_close}
            
            
            
            logger.info(f">> tickers {self.tickers}")  

            await self.on_symbols_update(self.symbols,to_add,to_remove)

            await self.render_page.send({
                "type" :"symbols",
                "add" : to_add,
                "del" : to_remove
            })

            for symbol in to_add:
                await self.send_event("mule",symbol,"NEW ", "","", {"color": "#00b627"})

            #newss
            
            #await self.scan_for_news(to_add)
            
            await self.newService.on_symbols_update(self.symbols,to_add,to_remove)   
            '''
            for symbol in to_add:
                
                news = await NewService().find(symbol)
                if news:
                    await self.send_news(symbol,news)
            '''


            for symbol in to_remove:
                await self.send_event("mule",symbol,"DEL", "","", {"color": "#ff5084"})

            logger.info(f"UPDATE SYMBOLS DONE {self.tickers}")  
            
        except Exception as e:
            logger.error(f"Errore in _on_update_symbols", exc_info=True)    


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
                columns=["symbol", "timestamp", "price", "bid", "ask", "day_volume","ts"]
            )
        df = pd.DataFrame( [ t for k,t in self.tickers.items()])
        df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df

        
    def get_fundamentals(self,symbol)->pd.DataFrame:
        return self.df_fundamentals[self.df_fundamentals["symbol"]==symbol  ]
            
    def get_fundamentals_dict(self, symbol) -> dict:
        return self.fundamentals_map.get(symbol, {})

    def is_in_white_list(self,symbol):
        df = self.get_df(f"""
                SELECT * from  watch_list
                WHERE symbol='{symbol} and type="day_watch" '
            """)
        if (len(df)>0):
            #2026-02-11 11:57:47
            sdate =  str(df.loc[0, "ds_timestamp"])
            dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
            date = str(dt.date())

            date_str = str(datetime.now().date())

            logger.info("WATCH : "+symbol+ " "+ date +"=="+ date_str)
            
            return (date_str == date)
                    
        else:
            return False
        
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
        if timeframe in ['15m']:
            df = pd.read_sql_query(query, conn, params= (symbol, timeframe, limit))

            df["t"] = pd.to_datetime(df["t"], unit="ms")
            df = df.set_index("t")

            ohlc = df.resample("15T").agg({
                "o": "first",
                "h": "max",
                "l": "min",
                "c": "last",
                "qv": "sum",
                "bv": "sum"
            }).dropna()

        else:
            df = pd.read_sql_query(query, conn, params= (symbol, timeframe, limit))
        df = df.iloc[::-1].reset_index(drop=True)
      
        conn.close()     
        return df

    async def history_data(self,symbols: List[str], timeframe: str, *, since : int=None, limit: int = 1000):

        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        if self.sym_mode:
            sql_symbols = str(symbols)[1:-1]
            conn = sqlite3.connect(self.db_file)

            #logger.info(f"SYM BOOT TIME {self.sym_start_time}")

            query = f"""
                    SELECT *
                    FROM ib_ohlc_history
                    WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                    and timestamp<= {self.sym_start_time*1000}
                    ORDER BY timestamp DESC
                    LIMIT {limit}"""
                    
            #print("since",query)
            df = pd.read_sql_query(query, conn)
            df = df.iloc[::-1].reset_index(drop=True)
            conn.close()    
            return df 

        else:
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
        await self.send_cmd("/chart/align_data",symbol,timeframe)
     

    #######################

    def back_data(self,symbols: List[str], timeframe: str, since : int, to: int ):

        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        
        sql_symbols = str(symbols)[1:-1]
        conn = sqlite3.connect(self.db_file)

        #logger.info(f"SYM BOOT TIME {self.sym_start_time}")

        query = f"""
                    SELECT *
                    FROM ib_ohlc_history
                    WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                    and timestamp>= {since}
                    and timestamp<= {to}
                    ORDER BY timestamp DESC"""
                    
        #print("query",query)

        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 

      
    def back_symbols(self,timeframe:str, since : int, to: int ):
        
        conn = sqlite3.connect(self.db_file)

        query = f"""
                   SELECT 
    symbol,
    MIN(timestamp) AS min_timestamp,
    MAX(timestamp) AS max_timestamp
FROM ib_ohlc_history
WHERE timeframe = '{timeframe}'
  AND timestamp >= {since}
  AND timestamp <= {to}
GROUP BY symbol;
"""
                    
        #print("query",query)

        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 
    
    def back_profiles(self):
        
        conn = sqlite3.connect(self.db_file)
        query = f""" SELECT * from back_profile"""
        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 
    
    def save_profile(self,name,data):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        query = """
            INSERT INTO back_profile (name, data)
            VALUES (?, ?)
            ON CONFLICT(name)
            DO UPDATE SET data = excluded.data
        """

        cursor.execute(query, (name, json.dumps(data)))
        conn.commit()
        conn.close()
    
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
            return  float(df.iloc[0]["close"])
        else:
            return 0.01
        
    ################################

    async def send_error_event(self, data):
        

        logger.error(f"ERROR EVENT {data}")
  
  
        data["type"] = "ERROR"
        data["ts"] =int(time.time() * 1000)

        if not self.sym_mode: 
            query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
            self.execute(query, ("error","", "ERROR",  int(time.time() * 1000), json.dumps(data) ))

        await self.render_page.sendOrder(data)

    async def send_message_event(self, data):
        
        logger.error(f"MESSAGE EVENT {data}")
  
  
        data["type"] = "MESSAGE"
        data["ts"] =int(time.time() * 1000)
        if not self.sym_mode: 
            query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
            self.execute(query, ("message","", "MESSAGE",  int(time.time() * 1000), json.dumps(data) ))

        await self.render_page.sendOrder(data)

    async def send_trade_event(self,type, data):
       
        try:
            #self.client.send_event("order", )
            logger.info(f"SEND t: {type} data: {data}")

            data["type"] = type
            data["ts"] =int(time.time() * 1000)

            if not self.sym_mode: 
                query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
                self.execute(query, ("order",data['data']['symbol'], type,  int(time.time() * 1000), json.dumps(data) ))

            await self.render_page.sendOrder(data)
            '''
            await self.render_page.sendOrder(
                {"type": type, "data" : data}
            )
            '''

            #logger.info(f"SEND DONE")
        except:
            logger.error(f"{data}")
            logger.error("SEND ERROR", exc_info=True)

    async def send_order_event(self,type, data):
       
        try:
            #self.client.send_event("order", )
            logger.info(f"SEND t: {type} data: {data}")

            data["type"] = type
            data["ts"] =int(time.time() * 1000)

            if not self.sym_mode: 
                query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
                self.execute(query, ("order",data["symbol"], type,  int(time.time() * 1000), json.dumps(data) ))

            await self.render_page.sendOrder(data)
            '''
            await self.render_page.sendOrder(
                {"type": type, "data" : data}
            )
            '''

            #logger.info(f"SEND DONE")
        except:
            logger.error(f"{data}")
            logger.error("SEND ERROR", exc_info=True)

 
    async def send_task_order(self,order):
        if self.sym_mode: return
        order["ts"] =int(time.time() * 1000)

        if not self.sym_mode: 
            query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
            self.execute(query, ("task-order",order["symbol"], "TASK_ORDER",  int(time.time() * 1000), json.dumps(order) ))

        await self.render_page.sendOrder(
                {"type": "TASK_ORDER", "data" : order}
            )

    async def send_taskinfo(self,order,message):
         if self.sym_mode: return
         #query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
         #order["message"]=message   
         #self.execute(query, ("task-order",order["symbol"], "TASK_ORDER_MSG",  int(time.time() * 1000), json.dumps(order) ))
         order["ts"] =int(time.time() * 1000)

         await self.render_page.sendOrder(
                {"type": "TASK_ORDER_MSG", "data" : order,"msg":message }
            )


    async def send_event(self,source:str,symbol:str, name:str, small_desc:str,  full_desc:str, data):
       
        try:
            data["small_desc"]= small_desc
            data["full_desc"]= full_desc

            if not self.sym_mode: 
                query = "INSERT INTO events ( source,symbol, name,timestamp,data) values (?,?, ?,?,?)"
                self.execute(query, (source,symbol, name,  int(time.time() * 1000), json.dumps(data) ))

            #logger.info(f"SEND {data}")

            await self.render_page.send(
                {
                    "type" : "event",
                    "source" : source,
                    "symbol": symbol,
                    "name" : name,
                    "timestamp" :  int(time.time() * 1000),
                    "data" : data
                }
            )
            #logger.info(f"SEND DONE")
        except:
            logger.error("SEND ERROR", exc_info=True)

    async def send_ticker_rank(self,  data):
       
        try:
            await self.render_page.send(
                {
                    "type" : "ticker_rank",
                    "timestamp" :  int(time.time() * 1000),
                    "data" : data
                }
            )
        except:
            logger.error("SEND ERROR", exc_info=True)

    
    async def send_news(self,  symbol, data):
       
        try:
            await self.render_page.send(
                {
                    "type" : "news",
                    "timestamp" :  int(time.time() * 1000),
                    "symbol" : symbol,
                    "data" : data
                }
            )
        except:
            logger.error("SEND ERROR", exc_info=True)

    def __str__(self):
        return f"{self.__class__} params:{self.params}"

    ##################################


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
        conn.close()
        return line_id
    
    async def send_cmd(self,rest_point, msg=None):
        
        url = "http://127.0.0.1:3000/"+rest_point

        logger.info(f">> {url} {msg}")
        if msg:
            params = msg
            response = requests.get(url, params=params, timeout=5)
        else:
            response = requests.get(url,  timeout=5)

        if response.ok:
            data = response.json()
            if data["status"] == "ok":
                if "data" in data:
                    return data["data"]
                else:
                    return "{}"
            
            else:
                logger.error(f"Errore: { response.status_code}")
                return None
        else:
            logger.error(f"Errore:{ response.status_code}")
            return None
    

    