if __name__ =="__main__":
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import time as _time
import os
import json
from typing import Optional
from collections import deque

import pandas as pd
import logging
from logging.handlers import RotatingFileHandler

from utils import convert_json
from rich.console import Console
from rich.table import Table
from rich.live import Live

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, HTMLResponse

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect

from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts

from binance.client import Client

use_yahoo=False

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

INTERVAL_SECONDS = 60
WINDOW_MINUTES = 5
TOP_N = 10


# storico prezzi: {symbol: deque([(timestamp, price), ...])}
price_history = {}

def get_day_top_gainers(client,limit=10):
    tickers = client.get_ticker()

    gainers = []

    for t in tickers:
        symbol = t['symbol']

        # Considera solo coppie contro USDT (più standard)
        if symbol.endswith("USDC"):
            try:
                price_change = float(t['priceChangePercent'])
                gainers.append((symbol, price_change))
            except:
                continue

    # Ordina per crescita
    gainers.sort(key=lambda x: x[1], reverse=True)

    return gainers[:limit]

def get_prices(client):
    tickers = client.get_symbol_ticker()
    prices = {}

    for t in tickers:
        symbol = t["symbol"]
        if symbol.endswith("USDT"):
            prices[symbol] = float(t["price"])

    return prices

def update_history(prices):
    now = datetime.now().timestamp()

    for symbol, price in prices.items():
        if symbol not in price_history:
            price_history[symbol] = deque()

        price_history[symbol].append((now, price))

        # rimuovi dati più vecchi della finestra
        while price_history[symbol] and now - price_history[symbol][0][0] > WINDOW_MINUTES * 60:
            price_history[symbol].popleft()

def compute_gainers():
    gainers = []

    for symbol, history in price_history.items():
        if len(history) < 2:
            continue

        old_time, old_price = history[0]
        new_time, new_price = history[-1]

        if old_price > 0:
            change = ((new_price - old_price) / old_price) * 100
            gainers.append((symbol, change))

    gainers.sort(key=lambda x: x[1], reverse=True)
    return gainers[:TOP_N]


##############

class ScannerResult:
     df_fundamentals : pd.DataFrame
     df_symbols : pd.DataFrame

     def __str__(self):
         return f"FUNDAMENTALS \n {self.df_fundamentals} SYMBOLS\n{self.df_symbols}"

class BinanceScanner:
        
    def __init__(self,client,config,ms:MarketService):
        self.client=client
       # self.market = ms.getMarket("BINANCE")
        self.config=config
        

    def display_with_stock_symbol(self,scanData):
        df = util.df(scanData)
        df["contract"] = df.apply( lambda l:l['contractDetails'].contract,axis=1)
        df["symbol"] = df.apply( lambda l:l['contract'].symbol,axis=1)        
        return df[["rank","contractDetails","contract","symbol"]]

    async def do_scanner(self, name)-> pd.DataFrame:
 
            #offline_mode = "offline_mode" in cfg and cfg["offline_mode"] =="true"

            logger.debug(f'SCANNING DATAS ... ')


            if self.config["live_service"]["mode"]=="offline":
                logger.info("Use OFFLINE")
                symbols = self.config["live_service"]["debug_symbols"]
                items=[]
                conn = sqlite3.connect(DB_FILE)
                for symbol in symbols:
                    df_stocks = pd.read_sql_query(f"select * from STOCKS where symbol='{symbol}'", conn)
                    if len(df_stocks)!=0:
                        items.append({"symbol": symbol, "conid":df_stocks.iloc[0]["ib_conid"],"listing_exchange":df_stocks.iloc[0]["exchange"] })
                conn.close()   
                df = pd.DataFrame(
                    [(o["symbol"], o["conid"], o["listing_exchange"]) for o in items],
                    columns=["symbol", "conidex","listing_exchange"]
                )
                return df

            selected_profile=None
            for prof in self.config["live_service"]["profiles"]:
                logger.debug(f"LOAD PROF {prof}")
                if prof["name"] == name:# and zone == MarketZone.LIVE:
                    selected_profile = prof
                if prof["name"] == name:# and zone == MarketZone.PRE:
                    selected_profile = prof
            
            logger.info(f'selected_profile ...{selected_profile}')

            ##########

            top = get_day_top_gainers(self.client,50)

            #for i, (symbol, gain) in enumerate(top, start=1):
            #        logger.info(f"{i}. {symbol} → {gain:.2f}%")


            df = pd.DataFrame(
                    [(o[0],0,"BINANCE") for o in top],
                    columns=["symbol", "conidex","listing_exchange"]
                )

            '''
            prices = get_prices(self.client)
            update_history(prices)

            gainers = compute_gainers()
            
            for i, (symbol, change) in enumerate(gainers, 1):
                logger.info(f"{i}. {symbol} → {change:.2f}%")
            '''
            return df


########################################################################

async def main():


    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    client = Client()

    live_mode = config["general"]["live_mode"] == "true"
    #port=config["general"]["ib_port_live"] if live_mode else config["general"]["ib_port_paper"]   
   
    ms = MarketService(config)    
    scanner = Scanner(client,config,ms)
   
    df_symbols = await scanner.do_scanner( "GAIN")
    
    print(df_symbols)

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
   