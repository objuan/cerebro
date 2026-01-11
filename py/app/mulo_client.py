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
from renderpage import RenderPage
import warnings
from company_loaders import *
from market import *
from dataclasses import dataclass
warnings.filterwarnings("ignore")
#from scanner.crypto import ohlc_history_manager
from config import TF_SEC_TO_DESC

logger = logging.getLogger(__name__)


class MuloClient:

    def __init__(self,db_file, config):
        
        self.ready=False
        self.config=config
        self.symbols=[]
        self.tickers = {}
        self.db_file=db_file
        self.table_name="ib_ohlc_history"
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
        self.on_symbols_update = MyEvent()
        self.on_candle_receive = MyEvent()
        self.on_ticker_receive = MyEvent()
        self.sym_mode = config["database"]["scanner"]["mode"]   == "sym"
        self.sym_time = None
        # live feeds

    async def bootstrap(self, onStartHandler):
        uri = "ws://localhost:2000/ws/tickers"
        
        try:
            # Ci si connette al server
            await self.update_symbols()

            async with websockets.connect(uri) as websocket:
                logger.info(f"Connesso a {uri}")
                
                # Invia un messaggio al server
                message = {"id": "client"}
                await websocket.send(json.dumps(message))
                
                async def updateTickers(new_ticker):
                    if self.sym_mode and "sym" in new_ticker:
                        self.sym_time = new_ticker["sym"]
                    else:
                        new_ticker["tf"]= TF_SEC_TO_DESC[new_ticker["tf"]]
                        #new_ticker["ts"] = new_ticker["ts"]/1000  # to ms
                        #print(new_ticker)
                        await self.on_candle_receive(new_ticker)
                        

                        if new_ticker["tf"]=="10s":
                            t= self.tickers[new_ticker["s"]]
                            t.update({"last": new_ticker["c"],"day_v": new_ticker["day_v"],"ask": new_ticker["ask"],"bid": new_ticker["bid"],
                                        "gain": ((new_ticker["c"]-t["last_close"]) / t["last_close"]) * 100, "ts":new_ticker["ts"] })
                            # send event 
                            await self.on_ticker_receive(t)
                            #print(self.tickers)
                        #self.render_page.send({"type":"candle","data":new_ticker}) 
                   
                # live on last scanner

                # first
                new_ticker = await websocket.recv()
                await updateTickers(json.loads(new_ticker))

                self.ready=True
                onStartHandler()

                while True:
                    new_ticker = await websocket.recv()
                    await updateTickers(json.loads(new_ticker))

                    #logger.info(f"< Ricevuto: {response}")

        except ConnectionRefusedError:
            logger.error("Errore: Assicurati che il server sia attivo!")
            exit(-1)
        except Exception as e:
            logger.error(f"Errore: {e}")
            exit(-1)


    async def send_cmd(self,rest_point, msg=None):
        
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
        await self.update_symbols()
        logger.info(f".. Scanner call DONE {time.ctime()}")

    #########
    
    def live_symbols(self)->List[str]:
        ''' get array '''
        return  self.symbols
    
    async def update_symbols(self):
        logger.info(f"UPDATE SYMBOLS ..")#MAX:{self.max_symbols}")

        self.symbols = await self.send_cmd("symbols")

        logger.debug(f" {self.symbols}")

        if len(self.symbols) > 0:
            self.df_fundamentals = await Yahoo(self.db_file, self.config).get_float_list( self.symbols)

        logger.debug(f"Fundamentals \n{self.df_fundamentals}")
                                              
        self.sql_symbols = str(self.symbols)[1:-1]

        self.symbol_to_exchange_map = {}
        for _, row in self.df_fundamentals.iterrows():
            self.symbol_to_exchange_map[row["symbol"]] = row["exchange"]

        self.tickers = {}
        for s in self.symbols:
            self.tickers[s] = { "symbol": s, "last_close": self.last_close(s)}
        self.on_symbols_update(self.symbols)

        logger.info(f"UPDATE SYMBOLS DONE {self.tickers}")  


    async def ohlc_data(self,symbol: str, timeframe: str, limit: int = 1000):
       
        if self.sym_mode:
            ticker = self.tickers[symbol]
            last_time = ticker["ts"]
            logger.info(f"last_time {last_time}")
            query = f"""
                SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
                FROM {self.table_name}
                WHERE symbol=? AND timeframe=? and timestamp<= {last_time}
                ORDER BY timestamp DESC
                LIMIT ?"""

        else:
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
        
    def get_fundamentals(self,symbol)->pd.DataFrame:
        return self.df_fundamentals[self.df_fundamentals["symbol"]==symbol  ]
            
    #######################
    
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
    