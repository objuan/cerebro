import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime, timedelta,time,timezone
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
import uvicorn

from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts, convert_json,AsyncScheduler,candles_from_seconds
from company_loaders import *
from renderpage import WSManager
#from order import OrderManager
from balance import Balance
#from order_task import OrderTaskManager
from mulo.mulo_job import MuloJob,since_to_durationStr
from mulo.mulo_scanner import Scanner
from mulo.mulo_candle_updater import MuloCandleUpdater

intervals = [10,  60, 300]  # seconds for 10s, 30s, 1m, 5m
#intervals = [10]  # seconds for 10s, 30s, 1m, 5m
#use_display = True

LOG_FILE="logs/tws_brokerlive.log"

use_yahoo=False
use_display = False

logger = logging.getLogger()

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("ib_insync").setLevel(logging.WARNING)

run_mode = config["live_service"].get("mode","sym") 
start_scan =  config["live_service"].get("start_scan","live") 

'''
if use_display:
    cmd_console = Console()
    live_display = Live(console=cmd_console, refresh_per_second=2)
else:
    live_display=None
'''

if use_yahoo:
    ws_yahoo = yf.AsyncWebSocket()

sym_time = None

#####################

class LiveScanner:
    def __init__(self, fetcher,config):
        self.fetcher=fetcher
        self.config=config
        self.name=config["name"]
        self.actual_df=None
        self.symbol_map=None
        self.symbol_to_conid_map=None
        self.merge_weight = config["merge_weight"]
        self.discard_rule = config["discard_rule"]

    # opera su manage_live
    async def updateLive(self,df_symbols, manage_live)-> bool:#, range_min=None,range_max=None):

        logger.info(f"UpdateLive {self.name} \n{df_symbols.tail(2)}")

        # filter on blacklist
        mask = df_symbols["symbol"].apply(lambda s: not self.fetcher.is_in_blacklist(s))
        df_symbols = df_symbols[mask]
        
        logger.info(f"updateLive BLACKED #{len(df_symbols)}")

        #df = df_symbols

        # cut
        if self.max_symbols != None:
             df_symbols= df_symbols [:self.max_symbols]

        '''
        #add white list 
        white = self.fetcher.get_day_white_list()    
        for symbol in white:
            contract = Stock(symbol, "SMART", 'USD')
            self.ib.qualifyContracts(contract)

            logger.info(f"ADD WATCH {symbol} {contract}")
            
            df_symbols.loc[len(df_symbols)] = [symbol, contract.conId,contract.primaryExchange]
        '''
        
        logger.info(f"PROCESS  max:{self.max_symbols} \n{df_symbols}")
        logger.info(f"ACTUAL {self.actual_df}")

        changed=False
        if len(df_symbols) == 0 or (self.actual_df is not None and self.actual_df.empty):
            self.actual_df = df_symbols
            self.symbol_map =={}
            self.symbol_to_conid_map = {}
        else:
            if not self.symbol_map:
                self.actual_df = df_symbols
                await manage_live(self, self.actual_df["symbol"].to_list(),[])
                changed= True
            else:
                delta_prev = self.actual_df[~self.actual_df["symbol"].isin(df_symbols["symbol"])]
                logger.info(f"PREV DELTA {delta_prev}")
                to_remove= []
                for s in delta_prev["symbol"].to_list():
                    #if self.discard_rule =="IMMEDIATE":
                    #if  fetcher.is_in_blacklist(s):
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
                len(delta_new["symbol"].to_list())>0 or len(to_remove) >0

                changed = await manage_live(self, delta_new["symbol"].to_list(),to_remove)

        self.symbol_map = self.actual_df.set_index("symbol")["listing_exchange"].to_dict()
        self.symbol_to_conid_map = self.actual_df.set_index("symbol")["conidex"].to_dict()
        return changed

   
#####################################

class LiveManager:

    def __init__(self,ib,config,fetcher:MuloJob,scanner:Scanner,ws_manager,ms:MarketService,on_display):
        self.ib=ib
        fetcher.ib = ib
        self.ms=ms
        self.on_display=on_display
        self.config=config
        self.scanner = scanner
        self.fetcher=fetcher
        self.conn = sqlite3.connect(fetcher.db_file)
        self.ws_manager=ws_manager
        #print(self.config)
        self.live_max_symbols =   config["live_service"]["live_max_symbols"]
        self.feed_max_symbols =   config["live_service"]["feed_max_symbols"]
        self.run_mode = config["live_service"].get("mode","sym") 

        self.scanner_map = {}

        #self.actual_df=None
        #self.symbol_map=None
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

                logger.debug(f"LIVE cancelled (reqId={reqId} {errorString} c:{contract})")
                
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
    
    def ordered_tickers(self):
         return sorted(  self.tickers.values(),
                        key=lambda t: t.gain,
                        reverse=True)
         
    ################

    async def scanData(self, live: LiveScanner)-> bool:
        logger.info(f"========== SCAN ========== {live.name} ===========")
        df_symbols = await self.scanner.do_scanner(live.name)

        if df_symbols is None:
            return

        #logger.info(f"SCANNED \n{df_symbols}")
        ret =  await live.updateLive(df_symbols, self.manage_live)

        ret  = ret or await self.discard_last()
        return ret

    # 
    '''
    def get_scanners(symbol):
        scanners_found = [
            scanner.name 
            for scanner in live.scanner_map.values() 
            if scanner.actual_df is not None 
            and "symbol" in scanner.actual_df.columns
            and symbol in scanner.actual_df["symbol"].values
        ]
        return scanners_found
    '''

    def remove_ticker(self,symbol):
        contract = self.ticker_contracts[symbol]# Stock(symbol, exchange, 'USD')
        logger.info(f">> Close  feeds {contract}")
        try:
            self.ib.cancelMktData(contract)
        except:
            logger.error("CANCEL ERROR", exc_info=True)
        self.ib.sleep(1)

        if symbol in self.tickers:
            del  self.tickers[symbol]

    async def discard_last(self)-> bool:
        
        logger.info(f"========== DISCARD LAST ========== ")
     
        if len(self.tickers) > self.feed_max_symbols:

            to_del_tickers = self.ordered_tickers()[ self.feed_max_symbols:]
            '''
            to_del_tickers =  {
                    symbol: ticker
                    for symbol, ticker in self.tickers.items()
                    if not ticker.scan_list
            }
            '''
            if len(to_del_tickers)>0:

                logger.info(f"CHECK TICKERS TO DELETE {to_del_tickers}")

                #o_tickers = self.ordered_tickers()

                #logger.info(f"..{o_tickers}")
                to_remove = to_del_tickers#.values() # to_remove = o_tickers[self.max_symbols:]
                
                #symbols = [x.contract.symbol for x in to_remove]
                symbols = [
                    x.contract.symbol
                    for x in to_remove
                    if ((datetime.now() - x.start_time).total_seconds() > 60
                    and not self.fetcher.is_in_white_list(x.contract.symbol))
                ]

                logger.info(f"REMOVE LAST symbols {symbols}")

                for symbol in symbols:
                        
                        logger.info(f"REMOVE symbol {symbol}")
                        
                        '''
                        self.actual_df = self.actual_df[
                            ~self.actual_df["symbol"].isin(symbols)
                            ].reset_index(drop=True)
                        
                        '''
                        #exchange = "SMART"#symbol_map[symbol]
                        contract = self.ticker_contracts[symbol]# Stock(symbol, exchange, 'USD')
                        logger.info(f">> Close  feeds {contract}")
                        try:
                            self.ib.cancelMktData(contract)
                        except:
                            logger.error("CANCEL ERROR", exc_info=True)
                        self.ib.sleep(1)

                        if symbol in self.tickers:
                            del  self.tickers[symbol]
                        
                        
               # await self.manage_live([],symbols )

    ######################

    def _align_batch(self, symbols):

        logger.info(f"BATCH DOWNLOAD {symbols}")

        '''
        tasks = {}

        for symbol in symbols:

            contract = self.ticker_contracts[symbol]

            tasks[symbol] = self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=" ",
                durationStr="1 Day",
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=False,
                formatDate=2
            )

        results = await asyncio.gather(*tasks.values())

        for symbol in symbols:
            self.fetcher._align_data(symbol,"1m")
        '''
       
    def need_update(self,symbol):
        toupdate=True
        df = self.fetcher.get_df("SELECT * FROM ib_ohlc_history WHERE exchange='exchange' and SYMBOL = ? and timeframe ='1d' order by timestamp desc limit 1",(symbol,))
        if not df.empty:
            if df.iloc[0]["ds_updated_at"]:
                                           
                last_date = datetime.fromisoformat( df.iloc[0]["ds_updated_at"])
                time_to_update_days = (datetime.now() - last_date).total_seconds()/(60*60*24)

                logger.info(f"time to update {symbol} {time_to_update_days}")

                toupdate=time_to_update_days > 1 
            else:
                toupdate=True
        return toupdate
    
    async def align_symbols(self, symbols):
        
        for symbol in symbols:

            #await self.fetcher._align_data(symbol, "1d")
            if self.need_update(symbol):

                max_ts = self.fetcher.get_max_time(symbol, "1d")
                if not max_ts:
                    dt_end = datetime.utcnow()
                    dt_start = dt_end - timedelta(365)
                else:
                    dt_start =  datetime.utcfromtimestamp(max_ts/1000)
                
                logger.info(f"1D dt_start {dt_start}")
                df = yf.download(
                                tickers=symbol,
                                start=dt_start.strftime("%Y-%m-%d"),
                                interval="1d",
                                auto_adjust=False,
                                prepost=True,        # include premarket + afterhours
                                progress=False,
                            )

                logger.info(f"df \n{df}")
                if not df.empty:
                    await self.fetcher.process_data("exchange",symbol, "1d", self.fetcher.conn, df,True)
                
        ############

        sem = asyncio.Semaphore(20)
        #end = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S')
                                       
        async def task(symbol):

            async with sem:
                return await self.fetcher.align_data(symbol)
            
        tasks = [task(s) for s in symbols]

        results = await asyncio.gather(*tasks)

        # id 
      
        
        for symbol, data in dict(results).items():
            logger.info(f"{symbol} \n{data}")

            exchange = self.fetcher.get_exchange(symbol)
            await self.fetcher.process_data_batch(exchange,symbol, "1m",self.fetcher.conn_exe, data,False)
        #logger.info(dict(results))

        '''
        loop = asyncio.get_running_loop()

        batches = [symbols[i:i+2] for i in range(0, len(symbols), 2)]

        tasks = []

        for batch in batches:
            tasks.append(
                loop.run_in_executor(
                    None,
                    self._align_batch,
                    batch
                )
            )

        await asyncio.gather(*tasks)
        '''

    ###
    # MANAGE live tickers
    ###
    async def manage_live(self, scan : LiveScanner, symbol_list_add, symbol_list_remove)-> bool:
     
        logger.info(f"===== Manage_live n:{scan.name if scan else ''} add:{symbol_list_add} del: {symbol_list_remove} =======")

        if self.run_mode== "sym":
            symbols=[]
            for symbol in symbol_list_add:
                symbols.append(symbol)
                self.tickers[symbol] = Ticker()
                self.tickers[symbol].time = datetime.now()   
            await self.fetcher.on_update_live_symbols(symbols,False)
            return

        #########

        to_add=[]
        for symbol in symbol_list_add:
            ticker = self.tickers[symbol] if symbol in self.tickers else None

            if  ticker:
                '''
                logger.info(f"UPDATE TICKER {symbol}")
                if not (scan in ticker.scan_list ):
                    ticker.scan_list.append(scan)
                else:
                     logger.warning("DOUBLE TICKER SCAN")
                '''
            else:
                logger.info(f"ADD TICKER {symbol}")
                to_add.append(symbol)

        if self.ib:
            await self.align_symbols(to_add)

        logger.info(f"START FEEDs")

        for symbol in to_add:
                ticker = self.tickers[symbol] if symbol in self.tickers else None

                '''
                if  ticker:
                    logger.info(f"UPDATE TICKER {symbol}")
                    if not (scan in ticker.scan_list ):
                        ticker.scan_list.append(scan)
                    else:
                        logger.warning("DOUBLE TICKER SCAN")
                else:
                '''
                logger.info(f"NEW TICKER {symbol}")

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
            
                    ticker = self.ib.reqMktData(contract, "", snapshot=False, regulatorySnapshot=False,mktDataOptions=[])#, reqId=reqId)
                    ticker.gain = 0
                    ticker.last = 0
                    ticker.start_time = datetime.now()
                    ticker.last_close = await self.fetcher.last_close(symbol)
                    ticker.symbol = symbol
                    '''
                    if scan:
                        ticker.scan_list = [scan]
                    else:
                        ticker.scan_list = []
                    '''

                    ticker.is_live = True
                    if self.config["live_service"]["mode"] != "offline":
                        ticker.updateEvent += self.on_tick
                    
                self.tickers[symbol]  = ticker
                self.ticker_contracts[symbol]  = contract

                if scan:
                    self.fetcher.add_day_symbol(scan.name,symbol)

        #####

        '''
        for symbol in symbol_list_remove:
            # cancello logico
            #scan_list = self.tickers[symbol].scan_list
            #if scan in scan_list:
            #    scan_list.remove(scan)
            #else:
            #    logger.error(f"not found in scan list !!!! ")
        '''            
        #logger.info(f"tickers {self.tickers}")

        ###
        
        #offline_mode =  self.run_mode=="offline" #:#config["database"]["scanner"]["offline_mode"]
        symbols=[]
        for symbol, ticker  in self.tickers.items():
            #if (ticker.time  and  not math.isnan(ticker.last)) or self.run_mode=="offline":
            #if (ticker.time  ) or self.run_mode=="offline":
                symbols.append(symbol)

        await self.fetcher.on_update_live_symbols(symbols,True)

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

                                  
        if len(to_add)>0 and self.ws_manager:
            await self.ws_manager.broadcast({"evt":"on_update_symbols"})
        
    async def on_tick(self,ticker):
        #logger.info(f"on_tick {ticker}")

        await self.add_ticker(ticker.symbol,ticker,None)
        #logger.info(f"on_tick {ticker}")


    async def add_to_black(self,mode,symbol):
        self.fetcher.add_blacklist(symbol,"USER SETTING", mode)

        changed=False
        for s,ticker in self.tickers.items():
            if s == symbol:
                changed=True
                self.remove_ticker(symbol)
                break
        if changed:
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

                day_volume = ticker.volume #day volume
              
                day_volume = max(0, 0 if math.isnan(day_volume) else day_volume)

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
                                volume = day_volume - candle["last_volume"]
                                volume = max(0,volume)
                                if volume == day_volume:
                                    volume = 0
                                
                                data = {
                                    "m": "full",
                                    "s": symbol,
                                    "tf": interval,
                                    "o": ticker.last if candle["open"] == 0 else candle["open"],
                                    "c": ticker.last if candle["close"] == 0 else candle["close"],
                                    "h":  ticker.last if candle["high"] == 0 else candle["high"],
                                    "l":  ticker.last if candle["low"] == 0 else candle["low"],
                                    "v": volume if use_yahoo else volume * 100,
                                    "ts": int(candle["start"]) * 1000,
                                    "dts": start_time,
                                    "bid": ticker.bid if ticker.bid  else 0,
                                    "ask": ticker.ask if ticker.ask  else 0, #bidSize,askSize,minTick
                                    "day_v": day_volume if use_yahoo else day_volume * 100
                                }

                                #logger.info(f"add {data} \n{ticker}")
                                if (intervals != 300):
                                    await self.fetcher.db_updateTicker(data)

                                if self.ws_manager  :
                                    #logger.info(f"NEW CANDLE {data}")
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
                                "last_volume": day_volume
                            }

                            history[interval] = candle
                            
                        # ===== AGGIORNA CANDELA CORRENTE =====
                        else:
                             # check ticker changed
                            
                            if  ticker.last !=  candle["close"]:
                                candle["high"] = max(candle["high"], ticker.last)
                                candle["low"] = min(candle["low"], ticker.last)

                                #vol_diff = ticker.volume - candle["last_volume"]
                                candle["volume"]  = max(0,day_volume - candle["last_volume"])
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
                                        "day_v": day_volume if use_yahoo else day_volume * 100
                                    }

                            
                                if self.ws_manager:
                                        #logger.info(f"NEW PARTIAL {data}")
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
                        '''
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
                        '''
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
                        df = self.fetcher.get_df(f"SELECT MIN(timestamp) as min FROM ib_ohlc_history WHERE exchange='exchange' and timeframe='10s' and symbol='{symbol}'")
                        print(df)
                        if len(df)>0 and df.iloc[0]["min"]!=None:
                            ts_start =  int(df.iloc[0]["min"] )
                            logger.info(f"SYMBOL TICKER BOOT {symbol} from {datetime.fromtimestamp(ts_start/1000)}") 
                            #last_time[symbol] =ts_start
                            self.sym_start_time = max(self.sym_start_time,ts_start)

                logger.info(f"SYM TIME  BEGIN AT  {datetime.fromtimestamp(self.sym_start_time/1000).strftime('%Y-%m-%d %H:%M:%S')}") 

                for symbol,ticker in self.tickers.items():
                    ticker.last_close = 0 #//await self.fetcher.last_close(symbol,datetime.fromtimestamp(self.sym_start_time/1000))
                    ticker.gain = 0    
                    ticker.volume=0
                    ticker.last = 0
                    ticker.symbol = symbol
                    ticker.last_tick_time = {}
                    logger.info(f"Start sym ticker {ticker} last_close{ticker.last_close}")

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
                                    df = pd.read_sql_query(f"SELECT * FROM ib_ohlc_history WHERE symbol='{symbol}' and timeframe='{TF_SEC_TO_DESC[interval]}'  and timestamp<={ts*1000} ORDER BY timestamp DESC LIMIT 1",
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
                                            if self.run_mode !="sym":
                                                ticker.gain = ((ticker.last - ticker.last_close)/ ticker.last_close) * 100
                                        
                                        #logger.info(f"{row}")   
                                    
                                        try:
                                            data = {"m":"full", "s":symbol, "tf":interval,  "o":float(row['open']),"c":float(row['close']),"h":float(row['high']),"l":float(row['low']), 
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
            for symbol in symbols:
                await self.fetcher._align_data(symbol,"1m")

            await self.manage_live(None,symbols , [])
            #await self.updateLive(df_symbols )
        else:
            if  start_scan== "keep_last_session":

                logger.info(f"Keep last session")
                '''
                df = self.fetcher.get_df("""SELECT * FROM ib_scanner
                    WHERE ts_exec = (
                        SELECT MAX(ts_exec) FROM ib_scanner where mode ="TOP_PERC_GAIN" 
                    )
                    ORDER BY pos ASC""")
                '''
                df = self.fetcher.get_df("""SELECT distinct symbol FROM ib_day_watch
                    WHERE date = (
                        SELECT MAX(date) FROM ib_day_watch
                    )""")
                if len(df)>0:
                    #max_symbols=self.config["live_service"]["live_max_symbols"]

                    df = df [:self.feed_max_symbols]
                    symbols =  df["symbol"].tolist()

                    logger.info(f"START LAST SESSION {symbols}")
                    filter = str(symbols)[1:-1]

                    df_symbols =self.fetcher.get_df(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})")
                    
                    
                    await self.manage_live(None,symbols , [])

                    '''
                    if config["live_service"]["mode"] != "offline":
                        await self.updateLive(df_symbols )
                    else:
                        #for symbol in symbols:
                        #    await self.fetcher._align_data(symbol,"1m")
                        #self.actual_df = df_symbols
                        #self.symbol_map = self.actual_df.set_index("symbol")["listing_exchange"].to_dict()
                        #self.symbol_to_conid_map = self.actual_df.set_index("symbol")["conidex"].to_dict()
                        await self.updateLive(df_symbols )
                    '''
                        #logger.info(f"SYMBOLS {df_symbols}")
                   
                else:
                    logger.error("COULD NOT FOUND SCANNER LAST")
            else:
                # LIVE
    
                #self.candle_updater = MuloCandleUpdater(self.ib,config,self.fetcher)
                #self.candle_updater.start()


                await self.manage_live(None,self.fetcher.get_day_symbols() , [])

                sched_data = self.config["live_service"]["scheduler"]
                '''
                scheduler_add = next(
                    (s for s in sched_data if s.get("live_mode") == "ADD"),
                    None
                )
                '''
                #max_symbols = config["live_service"]["max_symbols"]

                for d in sched_data:
                    self.scanner_map[d["name"]] = LiveScanner(self.fetcher,d)

                total_allocated = 0

                # Converto in lista per poter fare slicing
                items = list(self.scanner_map.items())

                # Itero su tutti tranne l'ultimo
                for name, scan in items[:-1]:
                 
                    #print(name,data["merge_weight"])

                    if scan.merge_weight .endswith("%"):
                        perc = float(scan.merge_weight [:-1]) / 100  # ⚠️ dividi per 100!
                        scan.max_symbols = int(perc * self.live_max_symbols)
                        total_allocated += scan.max_symbols
                    else:
                        scan.max_symbols = 1
                        total_allocated += 1

                # Ultimo elemento prende il resto
                last_key = items[-1][0]
                self.scanner_map[last_key].max_symbols = self.live_max_symbols - total_allocated

                logger.info(f"scanner_map { self.scanner_map}")

                for name,scan in self.scanner_map.items():
                   
                    logger.info(f"START {name} ")
                    
                    await self.scanData(scan)

                if self.ws_manager:
                    await self.ws_manager.broadcast({"evt":"on_update_symbols"})
                #await self.scanner(df_symbols )
        
                ### run scheduler

                async def on_scan(scan):
                    try:
                        logger.info(f"on_scan ")
                        if await self.scanData(scan):
                            if self.ws_manager:
                                await self.ws_manager.broadcast({"evt":"on_update_symbols"})
                    except:
                        logger.error("Error", exc_info=True)

                for name,scan in self.scanner_map.items():
                    
                    self.scheduler.schedule_every(int(scan.config["update_time"]),on_scan,scan)


