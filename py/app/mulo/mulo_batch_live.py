import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import time as _time
import math
import os
import re
import signal
import json
from typing import Optional
from collections import deque
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import *
from rich.console import Console
from rich.table import Table
from rich.live import Live
#from message_bridge import *
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect

util.startLoop()  # uncomment this line when in a notebook

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts, convert_json,AsyncScheduler
from company_loaders import *
from renderpage import WSManager
#from order import OrderManager
from balance import Balance
#from order_task import OrderTaskManager
from mulo.mulo_job import MuloJob
from mulo.mulo_scanner import Scanner

intervals = [10, 30, 60, 300]  # seconds for 10s, 30s, 1m, 5m
#intervals = [10]  # seconds for 10s, 30s, 1m, 5m
#use_display = True

LOG_FILE="logs/tws_brokerlive.log"

use_yahoo=False
use_display = False

if False:
    if os.path.exists(LOG_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived = os.path.join(LOG_DIR, f"app_{timestamp}.log")
        shutil.move(LOG_FILE, archived)
else:
    os.remove(LOG_FILE)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("ib_insync").setLevel(logging.WARNING)

run_mode = config["live_service"].get("mode","sym") 
start_scan =  config["live_service"].get("start_scan","live") 

if use_display:
    cmd_console = Console()
    live_display = Live(console=cmd_console, refresh_per_second=2)
else:
    live_display=None

ws_manager = WSManager()

app = FastAPI(  )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js / React
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def add_referrer_policy(request, call_next):
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

if use_yahoo:
    ws_yahoo = yf.AsyncWebSocket()

sym_time = None

#####################


class LiveManager:

    def __init__(self,ib,config,fetcher:MuloJob,scanner:Scanner,ws_manager,on_display):
        self.ib=ib
        fetcher.ib = ib
        self.on_display=on_display
        self.config=config
        self.scanner = scanner
        self.fetcher=fetcher
        self.conn = sqlite3.connect(fetcher.db_file)
        self.ws_manager=ws_manager
        #print(self.config)
        self.max_symbols =   config["live_service"]["max_symbols"]
        self.run_mode = config["live_service"].get("mode","sym") 

        logger.info(f"RUN MODE {self.run_mode}")
        self.actual_df=None
        self.symbol_map=None
        self.symbol_to_conid_map=None
        self.tickers={}
        self.ticker_contracts={}

        self.ticker_history ={}  # symbol -> deque of (ts, price)
        #self.ticker_map = {}
        self.live_send_key={}
        self.reqId2contract = {}
        self.scheduler = AsyncScheduler()
        self.sym_time=0
        self.sym_start_time=0
        self.sym_speed = float(1)
    
        def onError( reqId, errorCode, errorString, contract):
            if errorCode == 162:
                contract = contract or self.reqId2contract.get(reqId)

                logger.warning(f"LIVE cancelled (reqId={reqId} {errorString} c:{contract})")
                
                if contract and contract.symbol in self.tickers:
                    self.tickers[contract.symbol].cancelled = False

                return  # ignorato
            elif errorCode ==10168:
                logger.error(f"{errorCode} reqId={reqId}: {errorString} {contract}")
                '''
                Error 10168, reqId 4: Requested market data is not subscribed. Delayed market data is not enabled., contract: Stock(conId=822082077, symbol='TCGL', exchange='SMART', primaryExchange='AMEX', currency='USD', localSymbol='TCGL', tradingClass='TCGL')
                :param contract: Description
                '''
                       
                logger.error(f"DISCARD {contract.symbol} 10168")    

                self.fetcher.add_blacklist(contract.symbol,f"{10168} {errorString}")

            elif errorCode == 10089:
                logger.error(f"{errorCode} reqId={reqId}: {errorString}")
                part = errorString.split("market data is available.", 1)[1].strip()
                symbol = part.split()[0]
                logger.error(f"DISCARD {symbol} 10089")    
                self.fetcher.add_blacklist(symbol,f"{10089} {errorString}")
            elif errorCode == 2104:
                logger.warning(f"reqId={reqId}: {errorString}")
            else:
                logger.error(f"{errorCode} reqId={reqId}: {errorString}")
        if ib:
            ib.errorEvent += onError

    def getTicker(self,symbol)-> Ticker:
         return self.tickers[symbol]
    
    async def scanData(self, profile_name):
        logger.info(f"========== SCAN ========== {profile_name} ===========")
        df_symbols = await self.scanner.do_scanner(profile_name)
        #logger.info(f"SCANNED \n{df_symbols}")
        await self.updateLive(df_symbols)

        await self.discard_last()

        # 
        if self.ws_manager:
            await self.ws_manager.broadcast({"evt":"on_update_symbols"})

    def ordered_tickers(self):
         return sorted(  self.tickers.values(),
                        key=lambda t: t.gain,
                        reverse=True)
         
    async def discard_last(self):
        logger.info(f"========== DISCARD LAST ========== ")
     
        # ordino i tickers

        if len(self.tickers) > self.max_symbols:
             o_tickers = self.ordered_tickers()

             #logger.info(f"..{o_tickers}")
             to_remove = o_tickers[self.max_symbols:]
             
             #symbols = [x.contract.symbol for x in to_remove]
             symbols = [
                x.contract.symbol
                for x in to_remove
                if ((datetime.now() - x.start_time).total_seconds() > 60
                and not self.fetcher.is_in_white_list(x.contract.symbol))
            ]

             logger.info(f"REMOVE LAST symbols {symbols}")

             if len(symbols)>0:
                     self.actual_df = self.actual_df[
                        ~self.actual_df["symbol"].isin(symbols)
                        ].reset_index(drop=True)
                     
             await self.manage_live([],symbols )

    ######################


    async def updateLive(self,df_symbols):#, range_min=None,range_max=None):

        logger.info(f"updateLive \n{df_symbols.tail(3)}")

        # filter on blacklist
        mask = df_symbols["symbol"].apply(lambda s: not fetcher.is_in_blacklist(s))
        df_symbols = df_symbols[mask]

        logger.info(f"updateLive BLACKED #{len(df_symbols)}")

        # cut
        if self.max_symbols != None:
             df_symbols= df_symbols [:self.max_symbols]

        #add white list 
        white = self.fetcher.get_day_white_list()    
        for symbol in white:
            contract = Stock(symbol, "SMART", 'USD')
            self.ib.qualifyContracts(contract)

            logger.info(f"ADD WATCH {symbol} {contract}")
            
            df_symbols.loc[len(df_symbols)] = [symbol, contract.conId,contract.primaryExchange]

        
        logger.info(f"PROCESS  {df_symbols}")
        logger.info(f"ACTUAL {self.actual_df}")

        if len(df_symbols)==0:
            self.actual_df = df_symbols
            self.symbol_map =={}
            self.symbol_to_conid_map = {}
        else:
            if not self.symbol_map:
                self.actual_df = df_symbols
                await self.manage_live(self.actual_df["symbol"].to_list(),[])
            else:
                delta_prev = self.actual_df[~self.actual_df["symbol"].isin(df_symbols["symbol"])]
                logger.info(f"PREV DELTA {delta_prev}")
                to_remove= []
                for s in delta_prev["symbol"].to_list():
                    if  fetcher.is_in_blacklist(s):
                        to_remove.append(s)
                    
                logger.info(f"TO  REMOVED {to_remove}")
                    
                delta_new = df_symbols[~df_symbols["symbol"].isin(self.actual_df["symbol"])]

                logger.info(f"NEW ADDED {delta_new}")

                if len(to_remove)>0:
                     self.actual_df = self.actual_df[
                        ~self.actual_df["symbol"].isin(to_remove)
                        ].reset_index(drop=True)

                self.actual_df = pd.concat([self.actual_df, delta_new], ignore_index=True)
                
                logger.info(f"NEW LIST  {self.actual_df }")
                #in append
                await self.manage_live(delta_new["symbol"].to_list(),to_remove)

            self.symbol_map = self.actual_df.set_index("symbol")["listing_exchange"].to_dict()
            self.symbol_to_conid_map = self.actual_df.set_index("symbol")["conidex"].to_dict()


    async def manage_live(self, symbol_list_add, symbol_list_remove):
     
        logger.info(f"===== Manage_live add:{symbol_list_add} del: {symbol_list_remove} =======")

        if self.run_mode== "sym":
            symbols=[]
            for symbol in symbol_list_add:
                symbols.append(symbol)
                self.tickers[symbol] = Ticker()
                self.tickers[symbol].time = datetime.now()   
            await self.fetcher.on_update_symbols(symbols,False)
            return

        #########

        for symbol in symbol_list_add:
            exchange = "SMART"#symbol_map[symbol]
            contract = Stock(symbol, exchange, 'USD')

            logger.info(f">> Open  feeds {contract}")

            # Request market data for the contract

            if use_yahoo:
                pass
                #await ws_yahoo.subscribe(symbol)
                #market_data={"symbol":symbol }
            else:
 
                self.ib.qualifyContracts(contract)
             
                #reqId = self.ib.client.getReqId()
                #self.reqId2contract[reqId] = contract
          
                market_data = self.ib.reqMktData(contract, "", False, False, [])#, reqId=reqId)
                market_data.gain = 0
                market_data.last = 0
                market_data.start_time = datetime.now()
                market_data.last_close = await self.fetcher.last_close(symbol)
                market_data.symbol = symbol
                

                '''
                amd = Stock(symbol, 'SMART', 'USD')

                #news
                yesterday = datetime.now() - timedelta(days=1)
                startDateTime = yesterday.strftime('%Y%m%d %H:%M:%S'),

                headlines = self.ib.reqHistoricalNews(amd.conId, "BRFG+BRFUPDN+FLY",startDateTime, '', 10)
                logger.info(f"-----> {headlines}")
                if headlines and len(headlines)>0:
                    latest = headlines[0]
                    print("-------",latest)
                    article = self.ib.reqNewsArticle(latest.providerCode, latest.articleId)
                    print("-------",article)
                '''

            self.tickers[symbol]  = market_data
            self.ticker_contracts[symbol]  = contract

        for symbol in symbol_list_remove:
            #exchange = "SMART"#symbol_map[symbol]
            contract = self.ticker_contracts[symbol]# Stock(symbol, exchange, 'USD')
            logger.info(f">> Close  feeds {contract}")
            try:
                self.ib.cancelMktData(contract)
            except:
                logger.error("CANCEL ERROR", exc_info=True)
            self.ib.sleep(1)

            del  self.tickers[symbol]
            
        logger.info(f"tickers {self.tickers}")

        ###
        
        #offline_mode =  self.run_mode=="offline" #:#config["database"]["scanner"]["offline_mode"]
        symbols=[]
        for symbol, ticker  in self.tickers.items():
            #if (ticker.time  and  not math.isnan(ticker.last)) or self.run_mode=="offline":
            #if (ticker.time  ) or self.run_mode=="offline":
                symbols.append(symbol)

        await self.fetcher.on_update_symbols(symbols,True)

        #check
        to_remove = []

        for symbol in self.tickers.keys():
            f = self.fetcher.df_fundamentals[
                self.fetcher.df_fundamentals["symbol"] == symbol
            ]

            if f.empty:
                to_remove.append(symbol)

        for s in to_remove:
            logger.warning(f"REMOVE BAD SYMBOL {s}")
            del self.tickers[s]

                                  
        #if self.ws_manager:
        #    await self.ws_manager.broadcast({"evt":"on_update_symbols"})
        

    ##########################################################

    async def add_ticker(self,symbol,ticker, table):
                #logger.info(f"!!!!!!! {symbol}")
                data=[]
                #table = Table("Symbol", "Last", "Ask", "Bid", "10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                if use_yahoo:
                    ts = ticker.time#_time.time()
                else:
                    ts = ticker.time.timestamp()

                if math.isnan(ticker.last ):
                    return

                
                # Update history
                if symbol not in self.ticker_history:
                    self.ticker_history[symbol] = {}

                history = self.ticker_history[symbol] 

                #self.ticker_history[symbol].append((ts, ticker.last, ticker.volume))
                # Remove old entries older than 5 minutes
                #while self.ticker_history[symbol] and self.ticker_history[symbol][0][0] < ts - 300:
                #    self.ticker_history[symbol].popleft()

                #if symbol =="USAR":
                #    logger.info(f" onTicker{ticker.volume}")

                volume = ticker.volume
                volume = max(0,0 if math.isnan(volume) else volume)

                if ticker.last_close>0:
                    ticker.gain = ((ticker.last - ticker.last_close)/ ticker.last_close) * 100
                else:
                    ticker.gain=0
                    
                hls=None
                if not math.isnan(ticker.gain):

                    #await OrderTaskManager.onTicker(symbol,ticker)
                    
                    '''
                    if not symbol in self.ticker_map:
                        self.ticker_map[symbol] ={}
                    tick = self.ticker_map[symbol]
                    tick["last"] = ticker.last
                    tick["ask"] = ticker.ask
                    tick["bid"] = ticker.bid
                    tick["volume"] = ticker.volume
                    tick["ts"] = ts
                    '''

                    # Compute OHLC for each interval
                    hls = []
           
                    for interval in intervals:
                        
                        if interval not in history:
                            history[interval]= None

                        start = ts - (ts % interval)
                        start_time = datetime.fromtimestamp(start).strftime("%H:%M:%S")

                        candle = history[interval]
                        
 
                        # ===== NUOVA CANDELA =====
                        if candle is None or candle["start"] != start:
                            if candle is not None:  # se esisteva, va inviata
                                #logger.info("send")
                                # send
                                v = volume - candle["last_volume"]
                                
                                data = {
                                    "m": "full",
                                    "s": symbol,
                                    "tf": interval,
                                    "o": candle["open"],
                                    "c": candle["close"],
                                    "h": candle["high"],
                                    "l": candle["low"],
                                    "v": v if use_yahoo else v * 100,
                                    "ts": int(candle["start"]) * 1000,
                                    "dts": start_time,
                                    "bid": ticker.bid,
                                    "ask": ticker.ask,
                                    "day_v": volume if use_yahoo else volume * 100
                                }

                                #logger.info(f"add {data} \n{ticker}")
                                await self.fetcher.db_updateTicker(data)

                                if self.ws_manager:
                                    await self.ws_manager.broadcast(data)
                                ###

                            #reinit
                            candle = {
                                "start": start,
                                "open": ticker.last,
                                "high": ticker.last,
                                "low": ticker.last,
                                "close": ticker.last,
                                "volume": 0,
                                "last_volume": volume
                            }

                            history[interval] = candle
                            
                        # ===== AGGIORNA CANDELA CORRENTE =====
                        else:
                             # check ticker changed
                            
                            if  ticker.last !=  candle["close"]:
                                candle["high"] = max(candle["high"], ticker.last)
                                candle["low"] = min(candle["low"], ticker.last)

                                #vol_diff = ticker.volume - candle["last_volume"]
                                candle["volume"]  = max(0,volume - candle["last_volume"])
                                candle["close"] = ticker.last

                                data = {
                                        "m": "partial",
                                        "s": symbol,
                                        "tf": interval,
                                        "o": candle["open"],
                                        "c": candle["close"],
                                        "h": candle["high"],
                                        "l": candle["low"],
                                        "v": candle["volume"] if use_yahoo else  candle["volume"] * 100,
                                        "ts": int(candle["start"]) * 1000,
                                        "dts": start_time,
                                        "bid": ticker.bid,
                                        "ask": ticker.ask,
                                        "day_v": volume if use_yahoo else volume * 100
                                    }

                            
                                if self.ws_manager:
                                        await self.ws_manager.broadcast(data)

                        remaining = interval - (ts % interval)
                        time_str = f"{int(remaining // 60)}:{int(remaining % 60):02d}"

                        
                        pack = (
                            f"o:{candle['open']:.2f} "
                            f"h:{candle['high']:.2f} "
                            f"l:{candle['low']:.2f} "
                            f"c:{candle['close']:.2f} "
                            f"v:{candle['volume']:.0f} "
                            f"({start_time}, {time_str})"
                        )

                        #logger.info(f"candle t:{start_time} l:{ticker.last} v:{ticker.volume} --> {pack}")

                        hls.append(pack)

                  

                data = sanitize(data)
                #data.append({"symbol": symbol, "last": ticker.last, "bid": ticker.bid, "ask": ticker.ask, "low": ticker.low, "high": ticker.high, "volume": ticker.volume*100, "ts": ticker.time.timestamp()})
                
                if self.on_display and hls:
                    table.add_row(symbol, f"{ticker.last:.6f}", f"{ticker.ask:.6f}", f"{ticker.bid:.6f}",
                                   f"{ticker.last_close:.6f}", f"{ticker.gain:.1f}%",hls[0], hls[1], hls[2], hls[3])           
                    #live_display.update(table)
          
    async def ib_tick_tickers(self):
           
        while True:
                    try:
                        #ts = _time.time()
                        #data=[]
                        if self.on_display:
                            table = Table("Symbol", "Last", "Ask", "Bid","Last Close", "Gain","10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                        else:
                             table=None

                        #logger.info(f" ordered_tickers{self.ordered_tickers()}")
                        #for symbol, ticker in self.tickers.items():
                        for ticker in self.ordered_tickers():
                            if ticker.time :#and not math.isnan(ticker.last):
                                await self.add_ticker(ticker.symbol,ticker,table)

                        if self.on_display:
                            self.on_display(table)

                        await self.scheduler.tick()
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(0.1)


    async def yahoo_tick_tickers(self):
                pass
                '''
                async def message_handler(message):
                    #print("Received message from YAHOO:", message)
                    t = Ticker(last= message["price"], volume= int(message["day_volume"]), time=int(message["time"]), ask=0, bid=0 )
                    await self.add_ticker(message["id"],t)
                
                await  ws_yahoo.listen(message_handler)
                '''
               
    #########################
    def setSymTime(self,time):
        logger.info(f"SET SYM TIME TO {time}")
        self.sym_start_time = time
        self.sym_current_time = int(_time.time())  
    
    def setSymSpeed(self,speed):
        logger.info(f"SET SYM SPEED TO {speed}")
        self.sym_current_time = int(_time.time())  
        self.sym_speed = min(10,max(0,speed))
      
    async def sym_tick_tickers(self):
                #boot
                self.sym_start_time= 0

                if config["live_service"]["start_sym_time"]:
                    dt  =  datetime.strptime(config["live_service"]["start_sym_time"], "%Y-%m-%d %H:%M:%S")
                    self.sym_start_time =  int(dt.timestamp())*1000
                    pass
                else:
                    #last_time={}
                    for symbol,ticker in self.tickers.items():
                        df = self.fetcher.get_df(f"SELECT MIN(timestamp) as min FROM ib_ohlc_history WHERE timeframe='10s' and symbol='{symbol}'")
                        print(df)
                        if len(df)>0 and df.iloc[0]["min"]!=None:
                            ts_start =  int(df.iloc[0]["min"] )
                            logger.info(f"SYMBOL TICKER BOOT {symbol} from {datetime.fromtimestamp(ts_start/1000)}") 
                            #last_time[symbol] =ts_start
                            self.sym_start_time = max(self.sym_start_time,ts_start)

                logger.info(f"SYM TIME  BEGIN AT  {datetime.fromtimestamp(self.sym_start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}") 

                for symbol,ticker in self.tickers.items():
                    ticker.last_close = await self.fetcher.last_close(symbol,datetime.fromtimestamp(self.sym_start_time/1000))
                    ticker.gain = 0    
                    ticker.volume=0
                    ticker.last = 0
                    ticker.symbol = symbol
                    ticker.last_tick_time = {}
                    logger.info(f"Start ticker {ticker} last_close{ticker.last_close}")

                self.sym_current_time = int(_time.time())    

                if use_display:
                    table = Table("Symbol", "Last", "Ask", "Bid","Last Close", "Gain","10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                else:
                    table=None

                #cicle
                while True:
                    try:
                        delta = int(_time.time())  -self.sym_current_time
                        delta = self.sym_speed * delta 
                        
                        self.sym_time = int((self.sym_start_time + delta*1000) / 1000)

                        #logger.info(f"SYMBOL TICKER CHECK DELTA {delta} {self.sym_time}")   
                        
                        for symbol,ticker in self.tickers.items():
                            
                            ts_check = self.sym_time
                            hls = ["","","","",""]
                            i=-1
                            toSend=True
                            for interval in intervals:

                                i=i+1
                                ts = ts_check
                                start = ts - (ts % interval)
                                start_time = datetime.fromtimestamp(start).strftime("%H:%M:%S")

                                if not interval in ticker.last_tick_time:
                                    ticker.last_tick_time[interval] = datetime.fromtimestamp(0)
                                last_tick_time = ticker.last_tick_time[interval]

                                if last_tick_time != start_time:
                                    

                                    ticker.last_tick_time[interval]=start_time
                                    
                                    remaining = interval - (ts % interval)
                                    time_str = f"{int(remaining // 60)}:{int(remaining % 60):02d}"

                                    #logger.info(f".. {symbol} {start} interval {interval}   ts {ts}")   
                                    
                                    #logger.info(f"..{ts_check} {symbol} {interval}")

                                    #self.conn. df = pd.read_sql_query(query, conn, params=params)
                                    df = pd.read_sql_query(f"SELECT * FROM ib_ohlc_history WHERE  symbol='{symbol}' and timeframe='{TF_SEC_TO_DESC[interval]}'  and timestamp<={ts*1000} ORDER BY timestamp DESC LIMIT 1",
                                                        self.conn)
                                    #df = self.fetcher.get_df(f"SELECT * FROM ib_ohlc_history WHERE timeframe='{TF_SEC_TO_DESC[interval]}' and symbol='{symbol}' and timestamp<={ts*1000} ORDER BY timestamp DESC LIMIT 1")
                                    if len(df)>0:
                                        
                                        row = df.iloc[0]
                                        ts = datetime.fromtimestamp(row["timestamp"]/1000)

                                        if row['day_volume'] is None:
                                            day_volume = 0
                                        else:
                                            day_volume = max(0,int(row['day_volume']))

                                        if row['base_volume'] is None:
                                            base_volume = 0
                                        else:
                                            base_volume = max(0,int(row['base_volume']))

                                        if interval == 10:
                                            ticker.last = float(row.get("close") or 0)
                                            ticker.volume=  base_volume
                                            ticker.time=ts
                                            ticker.ask=0
                                            ticker.bid=0 
                                            ticker.gain = ((ticker.last - ticker.last_close)/ ticker.last_close) * 100
                                        
                                        #logger.info(f"{row}")   
                                    
                                        try:
                                            data = {"s":symbol, "tf":interval,  "o":float(row['open']),"c":float(row['close']),"h":float(row['high']),"l":float(row['low']), 
                                                    "v":base_volume, "ts":int(start)*1000, "dts":start_time  }
                                    
                                        
                                            pack = f"o:{row['open']:.2f} h:{row['high']:.2f} l:{row['low']:.2f} c:{row['close']:.2f} v:{base_volume:.0f} ({start_time}, {time_str})"
                                            hls[i] = pack
                                        except:
                                            logger.error(f"{row} {base_volume}")   
                                        ##await add_ticker(symbol,t)
                                        
                                        key = symbol+str(interval)

                                        if key in self.live_send_key:
                                            toSend = self.live_send_key[key] != pack

                                        if toSend:
                                            self.live_send_key[key]=pack

                                            data["bid"]=0
                                            data["ask"]=0
                                            data["day_v"]=day_volume
                                            data["m"]="full"

                                            #logger.info(f"SEND {data}")
                                            if self.ws_manager:
                                                await self.ws_manager.broadcast({"sym":self.sym_time,"speed" : self.sym_speed})

                                                await self.ws_manager.broadcast(data)

                                        #data = sanitize(data)
                                    
                                    
                            if table:
                               
                                table.add_row(symbol, f"{ticker.last:.6f}", 
                                        datetime.fromtimestamp(self.sym_time).strftime('%Y-%m-%d %H:%M:%S'),
                                        hls[0], hls[1], hls[2], hls[3])

                            if use_display:
                                live_display.update(table)
              
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(1)


    async def start_batch(self): 
        logger.info(f"LIVE mode {self.run_mode}")
        if self.run_mode != "sym":
            if use_yahoo:
                _tick_tickers = asyncio.create_task(self.yahoo_tick_tickers())
            else:
               _tick_tickers = asyncio.create_task(self.ib_tick_tickers())
        else:
            _tick_tickers = asyncio.create_task(self.sym_tick_tickers())

        return _tick_tickers
    
    ###########

    async def bootstrap(self,start_scan):
        if start_scan=="debug":

            symbols =  self.config["live_service"]["debug_symbols"]   
            filter = str(symbols)[1:-1]
            df_symbols = self.fetcher.get_df(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})")   
            await self.updateLive(df_symbols )
        else:
            if  start_scan== "keep_last_session":

                logger.info(f"Keep last session")
                df = self.fetcher.get_df("""SELECT * FROM ib_scanner
                    WHERE ts_exec = (
                        SELECT MAX(ts_exec) FROM ib_scanner where mode ="TOP_PERC_GAIN" 
                    )
                    ORDER BY pos ASC""")
                if len(df)>0:
                    max_symbols=self.config["live_service"]["max_symbols"]

                    df = df [:max_symbols]
                    symbols =  df["symbol"].tolist()

                    logger.info(f"START LAST SESSION {symbols}")
                    filter = str(symbols)[1:-1]

                    df_symbols =self.fetcher.get_df(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})")
                    
                    await self.updateLive(df_symbols )
                else:
                    logger.error("COULD NOT FOUND SCANNER LAST")
            else:
                sched_data = self.config["live_service"]["scheduler"]
                scheduler_add = next(
                    (s for s in sched_data if s.get("live_mode") == "ADD"),
                    None
                )
                logger.info(f"START {scheduler_add}")

                await self.scanData(scheduler_add["name"])
                #await self.scanner(df_symbols )
        
                ### run scheduler

                async def on_scan():
                    try:
                        await self.scanData(scheduler_add["name"])
                    except:
                        logger.error("Error", exc_info=True)

   
                self.scheduler.schedule_every(int(scheduler_add["update_time"]),on_scan)


########################################################################

fetcher = MuloJob(DB_FILE,config)
ms = MarketService(config)    

if run_mode!= "sym":
        ib = IB()
        ib.connect('127.0.0.1', config["live_service"]["ib_port"], clientId=config["live_service"]["ib_client"])

        #OrderManager(config,ib)
    
        scanner = Scanner(ib,config,ms)

        def on_display(table):
            live_display.update(table)
        if use_display:
            live = LiveManager(ib,config,fetcher,scanner,ws_manager,on_display)
        else:
            live = LiveManager(ib,config,fetcher,scanner,ws_manager,None)

else:
        #OrderManager(config,None)
        #Balance(config,None)
        scanner = Scanner(None,config,ms)
        live = LiveManager(None,config,fetcher,scanner,ws_manager,None)

@app.get("/symbols")
async def get_symbols():
    return {"status": "ok" , "data": [ x.symbol for x in live.ordered_tickers()]}

@app.get("/tickers")
async def get_tickers():
    logger.info(f"get_tickers {live.ordered_tickers()}")

    list =  [
            {
                "symbol": x.symbol,
                "last": getattr(x, "last", None), 
                "last_volume": getattr(x, "volume", None),
            }
            for x in live.ordered_tickers()]

    logger.info(f"list {list}")

    return {
        "status": "ok",
        "data":list,
    }

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/admin/add_to_black")
async def add_to_black(mode,symbol):
    fetcher.add_blacklist(symbol,"USER SETTING", mode)
    return {"status": "ok"}
    
@app.get("/admin/add_to_watch")
async def add_to_watch(name,type,symbol):
   fetcher.add_watch(name,type,symbol)
   return {"status": "ok"}

@app.get("/admin/clear_day_watch")
async def clear_day_watch(name,type,symbol):
   fetcher.clear_day_watch(name,type,symbol)
   return {"status": "ok"}


@app.get("/admin/scan")
async def admin_scan(profile_name):
    await live.scanData(profile_name)
    return {"status": "ok"}

@app.get("/chart/align_data")
async def _align_data(mode,symbol,timeframe):
    logger.info(f"_align_data {symbol} {timeframe}" )
    await fetcher._align_data(symbol,timeframe)
    return {"status": "ok"}

#############

@app.get("/sym/time")
async def get_sym_time():
    return {"status": "ok", "data": live.sym_time}

@app.get("/sym/speed")
async def get_sym_speed():
    return {"status": "ok", "data": live.sym_speed}

@app.get("/sym/time/set")
async def set_sym_time(time:int):
    live.setSymTime(time)
    return {"status": "ok"}

@app.get("/sym/speed/set")
async def set_sym_speed(value:float):
    live.setSymSpeed(value)
    return {"status": "ok"}

@app.websocket("/ws/tickers")
async def ws_tickers(ws: WebSocket):
    print("HEADERS:", ws.headers)
    print("QUERY:", ws.query_params)

    await ws_manager.connect(ws)

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
            try:
                data = json.loads(message)

            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    

async def main():

    logger.info("=================================================")
    logger.info("               IBROKER MULE TICKERS V1.0")
    logger.info("=================================================")
    logger.info(f"RUN MODE {run_mode}")   

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    if False:
        await live.scanData("TOP_PERC_GAIN")

        await asyncio.sleep(10) 

        await live.scanData("MOST_ACTIVE")
    
    try:
            
            if use_display:
                live_display.start()

            u_config = uvicorn.Config(
                app=app, 
                host="0.0.0.0", 
                port=3000,
                log_level="info",
                #access_log=False
            )
            server = uvicorn.Server(u_config)

            _server_task = asyncio.create_task(server.serve())
          
            await live.bootstrap(start_scan)
    
            _tick_tickers = await live.start_batch()

            #_tick_orders = asyncio.create_task(OrderManager.batch())

            await asyncio.wait(
                [_server_task, _tick_tickers],#_tick_orders
                return_when=asyncio.FIRST_COMPLETED
            )


    except:
            logger.error("ERROR", exc_info=True)
            if use_display:
                live_display.stop()
        
            if run_mode!= "sym":
                print("Disconnecting from TWS...")
                ib.disconnect()
            exit(0)


    logger.info("DONE")

    
if __name__ =="__main__":

    #############
    # Rotazione: max 5 MB, tieni 5 backup
  
    # Console
    file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    asyncio.run(main())
   