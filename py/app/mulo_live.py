import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import time as _time
import math
import os
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
from utils import AsyncScheduler, convert_json
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
from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts

from company_loaders import *
from renderpage import WSManager
from order import OrderManager
from balance import Balance
from order_task import OrderTaskManager
from mulo_job import MuloJob
from mulo_scanner import Scanner

use_yahoo=False
intervals = [10, 30, 60, 300]  # seconds for 10s, 30s, 1m, 5m
#use_display = True

'''
if use_display:
    console = Console()
    live_display = Live(console=console, refresh_per_second=2)
'''

class LiveManager:

    def __init__(self,ib,config,fetcher:MuloJob,scanner:Scanner,ws_manager,on_display):
        self.ib=ib
        self.on_display=on_display
        self.config=config["database"]
        self.scanner = scanner
        self.fetcher=fetcher
        self.ws_manager=ws_manager
        #print(self.config)
        self.max_symbols =   self.config["live"]["max_symbols"]
        self.run_mode = config["database"]["scanner"].get("mode","sym") 

        logger.info(f"RUN MODE {self.run_mode}")
        self.actual_df=None
        self.symbol_map=None
        self.symbol_to_conid_map=None
        self.tickers={}

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
                
                if contract:
                    self.tickers[contract.symbol].cancelled = False

                return  # ignorato
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
             symbols = [x.contract.symbol for x in to_remove]
             logger.info(f"REMOVE LAST symbols {symbols}")

             await self.manage_live([],symbols )

    ######################


    async def updateLive(self,df_symbols):#, range_min=None,range_max=None):

        # cut
        if self.max_symbols != None:
             df_symbols= df_symbols [:self.max_symbols]

        if not self.symbol_map:
            self.actual_df = df_symbols
            await self.manage_live(self.actual_df["symbol"].to_list(),[])
        else:
            delta_new = df_symbols[~df_symbols["symbol"].isin(self.actual_df["symbol"])]

            logger.info(f"DELTA {delta_new}")
            self.actual_df = pd.concat([self.actual_df, delta_new], ignore_index=True)

            logger.info(f"NEW LIST  {self.actual_df }")
            #in append
            await self.manage_live(delta_new["symbol"].to_list(),[])

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
          
                market_data = self.ib.reqMktData(contract)#, reqId=reqId)
                market_data.gain = 0
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

        for symbol in symbol_list_remove:
            exchange = "SMART"#symbol_map[symbol]
            contract = Stock(symbol, exchange, 'USD')
            logger.info(f">> Close  feeds {contract}")
            try:
                self.ib.cancelMktData(contract)
            except:
                logger.error("CANCEL ERROR", exc_info=True)
            self.ib.sleep(1)

            del  self.tickers[symbol]
            
        #logger.info(f"tickers {self.tickers}")

        ###
        
        #offline_mode =  self.run_mode=="offline" #:#config["database"]["scanner"]["offline_mode"]
        symbols=[]
        for symbol, ticker  in self.tickers.items():
            if (ticker.time  and  not math.isnan(ticker.last)) or self.run_mode=="offline":
                symbols.append(symbol)

        await self.fetcher.on_update_symbols(symbols,True)

        await self.ws_manager.broadcast({"evt":"on_update_symbols"})
        

    ##########################################################

    async def add_ticker(self,symbol,ticker, table):
                #logger.info(f"!!!!!!! {symbol}")
                data=[]
                #table = Table("Symbol", "Last", "Ask", "Bid", "10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                if use_yahoo:
                    ts = ticker.time#_time.time()
                else:
                    ts = ticker.time.timestamp()

                # Update history
                if symbol not in self.ticker_history:
                    self.ticker_history[symbol] = deque()
                self.ticker_history[symbol].append((ts, ticker.last, ticker.volume))
                # Remove old entries older than 5 minutes
                while self.ticker_history[symbol] and self.ticker_history[symbol][0][0] < ts - 300:
                    self.ticker_history[symbol].popleft()

                ticker.gain = ((ticker.last - ticker.last_close)/ ticker.last_close) * 100

                await OrderTaskManager.onTicker(symbol,ticker.last)
                
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
                toSend=True
                for interval in intervals:
                    start = ts - (ts % interval)
                    start_time = datetime.fromtimestamp(start).strftime("%H:%M:%S")

                    prices = [p for t, p, v in self.ticker_history[symbol] if t >= start]
                    volumes = [v for t, p, v in self.ticker_history[symbol] if t >= start]
                    
                    remaining = interval - (ts % interval)
                    time_str = f"{int(remaining // 60)}:{int(remaining % 60):02d}"
                    
                    vol_diff = volumes[-1] - volumes[0] if len(volumes) >= 2 else 0#(volumes[0] if volumes else 0)
                    if not use_yahoo: 
                        vol_diff=vol_diff*100
                    if prices:
                        open_p = prices[0]
                        close_p = prices[-1]
                        high = max(prices)
                        low = min(prices)
                        data = {"s":symbol, "tf":interval,  "o":open_p,"c":close_p,"h":high,"l":low, "v":vol_diff, "ts":int(start)*1000, "dts":start_time  }

                        pack = f"o:{open_p:.2f} h:{high:.2f} l:{low:.2f} c:{close_p:.2f} v:{vol_diff:.0f} ({start_time}, {time_str})"
                    else:
                        pack = f"- ({start_time}, {time_str})"

                    key = symbol+str(interval)

                    if prices:
                        if key in self.live_send_key:
                            toSend = self.live_send_key[key] != pack

                        if toSend:
                            self.live_send_key[key]=pack

                            data["bid"]=ticker.bid
                            data["ask"]=ticker.ask  
                            if not use_yahoo: 
                                data["day_v"]=ticker.volume*100
                            else:
                                data["day_v"]=ticker.volume
                            #logger.info(f"SEND {data}")
                            # TO DB
                            await self.fetcher.db_updateTicker(data)
                            # TO WS
                            if self.ws_manager:
                                await self.ws_manager.broadcast(data)

                    hls.append(pack)

                data = sanitize(data)
                #data.append({"symbol": symbol, "last": ticker.last, "bid": ticker.bid, "ask": ticker.ask, "low": ticker.low, "high": ticker.high, "volume": ticker.volume*100, "ts": ticker.time.timestamp()})
                
                if self.on_display:
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
               
                        #for symbol, ticker in self.tickers.items():
                        for ticker in self.ordered_tickers():
                            if ticker.time and not math.isnan(ticker.last):
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
        self.sym_speed = min(10,max(0.1,speed))
      
    async def sym_tick_tickers(self):
                #boot
                self.sym_start_time= 9999999999999
                #last_time={}
                for symbol,ticker in self.tickers.items():
                    df = self.fetcher.get_df(f"SELECT MIN(timestamp) FROM ib_ohlc_history WHERE timeframe='10s' and symbol='{symbol}'")
                    #print(df)
                    if len(df)>0 and df.iloc[0][0]!=None:
                        ts_start =  int(df.iloc[0][0] )
                        logger.info(f"SYMBOL TICKER BOOT {symbol} from {ts_start}") 
                        #last_time[symbol] =ts_start
                        self.sym_start_time = min(self.sym_start_time,ts_start)

                for symbol,ticker in self.tickers.items():
                    ticker.last_close = await self.fetcher.last_close(symbol,datetime.fromtimestamp(self.sym_start_time/1000))
                    ticker.gain = 0    
                    ticker.symbol = symbol
                    logger.info(f"Start ticker {ticker} last_close{ticker.last_close}")

                self.sym_current_time = int(_time.time())    
              
                logger.info(f"SYM TIME  BEGIN AT  {datetime.fromtimestamp(self.sym_start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}") 
                if self.on_display:
                    table = Table("Symbol", "Last", "Ask", "Bid","Last Close", "Gain","10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                else:
                    table=None

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

                                remaining = interval - (ts % interval)
                                time_str = f"{int(remaining // 60)}:{int(remaining % 60):02d}"

                                #logger.info(f".. {symbol} {start} interval {interval}   ts {ts}")   
                                
                                df = self.fetcher.get_df(f"SELECT * FROM ib_ohlc_history WHERE timeframe='{TF_SEC_TO_DESC[interval]}' and symbol='{symbol}' and timestamp<={ts*1000} ORDER BY timestamp DESC LIMIT 1")
                                if len(df)>0:
                                    row = df.iloc[0]
                                    ts = datetime.fromtimestamp(row["timestamp"]/1000)

                                    if interval == 10:
                                        ticker.last =float(row["close"])
                                        ticker.volume= int(row["base_volume"])
                                        ticker.time=ts
                                        ticker.ask=0
                                        ticker.bid=0 
                                        ticker.gain = ((ticker.last - ticker.last_close)/ ticker.last_close) * 100
                                    
                                    #logger.info(f"{ts}")   
                                    data = {"s":symbol, "tf":interval,  "o":float(row['open']),"c":float(row['close']),"h":float(row['high']),"l":float(row['low']), "v":int(row['base_volume']), "ts":int(start)*1000, "dts":start_time  }
                                     
                                    pack = f"o:{row['open']:.2f} h:{row['high']:.2f} l:{row['low']:.2f} c:{row['close']:.2f} v:{row['base_volume']:.0f} ({start_time}, {time_str})"
                                    hls[i] = pack
                                    ##await add_ticker(symbol,t)
                                    
                                    key = symbol+str(interval)

                                    if key in self.live_send_key:
                                        toSend = self.live_send_key[key] != pack

                                    if toSend:
                                        self.live_send_key[key]=pack

                                        data["bid"]=0
                                        data["ask"]=0
                                        data["day_v"]=ticker.volume

                                        #logger.info(f"SEND {data}")
                                        if self.ws_manager:
                                            await self.ws_manager.broadcast({"sym":self.sym_time,"speed" : self.sym_speed})

                                            await self.ws_manager.broadcast(data)

                                    #data = sanitize(data)
                                    
                            if table:
                                table.add_row(symbol, f"{ticker.last:.6f}", 
                                        datetime.fromtimestamp(self.sym_time).strftime('%Y-%m-%d %H:%M:%S'),
                                        hls[0], hls[1], hls[2], hls[3])

                            #live_display.update(table)
              
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

            symbols =  self.config["scanner"]["debug_symbols"]   
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
                    max_symbols=self.config["live"]["max_symbols"]

                    df = df [:max_symbols]
                    symbols =  df["symbol"].tolist()

                    logger.info(f"START LAST SESSION {symbols}")
                    filter = str(symbols)[1:-1]

                    df_symbols =self.fetcher.get_df(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})")
                    
                    await self.updateLive(df_symbols )
            else:
                sched_data = self.config["scanner"]["scheduler"]
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

                scheduler_cfg = self.config["scanner"]["scheduler"]

                self.scheduler.schedule_every(int(scheduler_add["update_time"]),on_scan)


########################################################################

async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    ib = IB()
    ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)

    ms = MarketService(config)    
    scanner = Scanner(ib,config,ms)
    fetcher = MuloJob(DB_FILE,config)
    
    
    console = Console()
    live_display = Live(console=console, refresh_per_second=2)
    live_display.start()

    def on_display(table):
        live_display.update(table)

    live = LiveManager(ib,config,fetcher,scanner,None,on_display)

    _tick_tickers = await live.start_batch()
    
    
    if False:
        await live.scanData("TOP_PERC_GAIN")

        await asyncio.sleep(10) 

        await live.scanData("MOST_ACTIVE")
    
    await live.bootstrap("live")

    await asyncio.wait(
                [_tick_tickers],
                return_when=asyncio.FIRST_COMPLETED
            )

    while True:
        ib.sleep(0.1)
    #ib.run()
    #df_symbols = await scanner.do_scanner( "TOP_PERC_GAIN",2)
    
    #print(df_symbols)

    logger.info("DONE")

    
if __name__ =="__main__":

    #############
    # Rotazione: max 5 MB, tieni 5 backup
  
    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    asyncio.run(main())
   