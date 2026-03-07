from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from ib_insync import Stock,util
import asyncio
import websockets
import time as _time
import pandas as pd
import sqlite3
from datetime import datetime, timedelta,time,timezone
import time
import logging
from typing import List, Dict
import requests
from message_bridge import *
from utils import *
#from job_cache import JobCache
#from job import *
from renderpage import RenderPage
import warnings
from company_loaders import *
from market import *
from dataclasses import dataclass
from config import TF_SEC_TO_DESC
from mulo_job import MuloJob 
import threading
import time

logger = logging.getLogger(__name__)
   
def date():
        return datetime.utcnow().date().isoformat()  # es. "2026-03-06"

class CandleLoader:
    def __init__(self, ib, symbol,fetcher:MuloJob):
        logger.info(f"NEW CANDLE LOADER {symbol}")
        self._running = True
        self.symbol=symbol
        self.ib=ib
        self.fetcher=fetcher
        self._running = True
        self.thread = None
        self.contract =  Stock(symbol, 'SMART', 'USD')
        self.start()

    def start(self):
        #self.task = asyncio.create_task(self._loop_update())
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.run(self._loop_update())

    def stop(self):
        self._running = False
        if self.task:
            self.task.cancel()

    async def _loop_update(self):
        last_minute = None
        logger.info(f"START")
        #self.fetcher._align_data(self.symbol,"1m")
        logger.info(f"START")

        while self._running:
            try:
                now = datetime.utcnow()
                logger.info(f"tick {now.second} {now.minute } {last_minute}")
                if now.second >= 5 and now.minute != last_minute:
                    await self.update()
                    last_minute = now.minute

            except Exception:
                logger.error("ERR", exc_info=True)

            #time.sleep(1)
            await asyncio.sleep(1)
    
    async def update(self):
        logger.info(f"Update called1 {self.ib}")
        
        bars = await  self.ib.reqHistoricalDataAsync(
            self.contract,
            endDateTime="",
            durationStr="60 S",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=2
        )
        logger.info(f"last {bars}")

        df = util.df(bars)

        try:
            logger.info(f">> #{len(bars)}")
            df = df.rename(columns={
                                "open": "Open",
                                "high": "High",
                                "low": "Low",
                                "close": "Close",
                                "volume": "Volume",
                                "date" :"Datetime",
                                "average" : "VWAP"
            })

            logger.info(f"df \n{df}")
            
            #await self.process_data(exchange,symbol, timeframe, cursor, df)
                            
        except:
            logger.error("ERROR", exc_info=True)
        

#################################

class MuloCandleUpdater:

    def __init__(self,ib, config,fetcher:MuloJob):
        self.config=config
        self.ib=ib
        self.fetcher=fetcher
        #check_same_thread=False serve perché SQLite di default non permette l'uso da thread diversi.
        self.conn = sqlite3.connect(fetcher.db_file, isolation_level=None, check_same_thread=False)

        self.offline_tickers={}
     
        self.day_tickers = self.get_day_symbols()
        logger.info(f"DAY SYMBOLS  {self.day_tickers}")

        self.day_feeds = {}

        # start background thread
      
        #self.thread.start()

        #    self.start_realtime_bars(sym)

    def start(self):
          for sym in self.day_tickers:
            self.day_feeds[sym]  = CandleLoader(self.ib, sym,self.fetcher)

    def stop(self):
        for sym,v in self.day_feeds.items():
            v.stop()

    ######################


    def get_day_symbols(self):
        df = self.get_df("SELECT symbol from ib_day_watch where date = ?", (date(),))
        symbols = df["symbol"].tolist()
        return symbols

    def add_day_symbol(self, profile, symbol):
        today = date() # es. "2026-03-06"
        self.conn.execute("""
                        INSERT INTO ib_day_watch (
                            profile,  symbol, date,count
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(date,symbol)
                        DO UPDATE SET
                            count = excluded.count+1
                    """, (
                        profile,symbol,today,1)
                    )

    def get_df(self,query, params=()):
        df = pd.read_sql_query(query, self.conn, params=params)
        return df
    