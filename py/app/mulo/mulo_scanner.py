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
from utils import convert_json
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
from mulo.mulo_job import MuloJob

use_yahoo=False

class ScannerResult:
     df_fundamentals : pd.DataFrame
     df_symbols : pd.DataFrame

     def __str__(self):
         return f"FUNDAMENTALS \n {self.df_fundamentals} SYMBOLS\n{self.df_symbols}"

class Scanner:
        
    def __init__(self,ib,config,ms:MarketService):
        self.ib=ib
        self.market = ms.getMarket("AUTO")
        self.config=config

    def display_with_stock_symbol(self,scanData):
        df = util.df(scanData)
        df["contract"] = df.apply( lambda l:l['contractDetails'].contract,axis=1)
        df["symbol"] = df.apply( lambda l:l['contract'].symbol,axis=1)        
        return df[["rank","contractDetails","contract","symbol"]]

    async def do_scanner(self, name)-> pd.DataFrame:
 
            #offline_mode = "offline_mode" in cfg and cfg["offline_mode"] =="true"

            logger.debug(f'SCANNING DATAS ... ')

            zone = self.market.getCurrentZone()
            
            logger.info(f'MARKET ZONE {zone}')

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

            sub = ScannerSubscription(
                numberOfRows=50,
                instrument=selected_profile["instrument"],
                locationCode=selected_profile["location"],
                scanCode=selected_profile["type"]
                # marketCapAbove= 1_000_000 , abovePrice= 100, aboveVolume= 100000
            )
            filter = selected_profile["filter"]

            #if zone == MarketZone.LIVE:
            if True:
                sub.stockTypeFilter = "COMMON" # solo azione vere, no nETF
                if "price_min" in filter:
                    sub.abovePrice = filter["price_min" ]
                if "price_max" in filter:
                    sub.belowPrice = filter["price_max" ]
                
                # numero di azioni
                # È il volume giornaliero cumulato del titolo nel momento in cui lo scanner gira.
                if "min_volume" in filter:
                    sub.aboveVolume = filter["min_volume" ]

                if "marketCap_min" in filter:
                    sub.marketCapAbove = filter["marketCap_min" ]
                if "marketCap_max" in filter:
                    sub.marketCapBelow = filter["marketCap_max" ]
            '''
            else:
                sub.instrument="STK"
                sub.locationCode="STK.US.MAJOR"
                sub.scanCode="TOP_PERC_GAIN"
                sub.stockTypeFilter = "COMMON" # solo azione vere, no nETF
                sub.abovePrice = 1
                sub.belowPrice = 100
                sub.aboveVolume = 1
                #sub.marketCapAbove = 0
            '''
            float_min = 0
            float_max = 99999999999

            if "float_min" in filter:
                    float_min = filter["float_min" ]

            if "float_max" in filter:
                    float_max = filter["float_max" ]

            #logger.info(f'USED FILTER ...{sub}')

            scanData = self.ib.reqScannerData(sub)

            logger.info(f'FIND #{len(scanData)}')

            if len(scanData)>0:
                conn = sqlite3.connect(DB_FILE)
                #cursor = conn.cursor()

                run_time = int(_time.time() * 1000)
                #run_time = int(_time.time() )
                #ds_run_time  = datetime.utcnow().isoformat()
                
                #logger.info(display_with_stock_symbol(scanData)["symbol"])

                symbols = [] 
                for contract, details in self.display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
                    if contract.conId!=0:
                        symbols.append(contract.symbol)


                logger.info(f"find df_fundamentals \n{symbols}")
                df_fundamentals = await Yahoo(DB_FILE, self.config).get_float_list(symbols)

                #scarto stocks senza float 
                for _, row in df_fundamentals.iterrows():
                    discard=""

                    if not  row["float"] :
                        discard = (f"DISCARD NOT FLOAT STOCK : {row['symbol']}")
                    else:
                        float = int(row["float"])
                        #logger.info(f"{row['symbol']} = {float} [{float_min} {float_max}]")
                        if float < float_min:
                             discard = (f"DISCARD FLOAT MIN : {row['symbol']}")
                        if float > float_max:
                             discard = (f"DISCARD FLOAT MAX : {row['symbol']}")

                    if discard!="":
                        logger.warning(discard)

                        for i,m in  enumerate(symbols):
                            #e = self.monitor[row['symbol']]
                            if m == row['symbol']:
                                del symbols[i]                
                                break

                # filtro df_fundamentals                  
                mask = df_fundamentals.apply(
                    lambda row: not not row["float"],
                    axis=1
                    )
                df_fundamentals = df_fundamentals[mask]
                
                # filtro float

    

                pos=0
                # inserimento dati
                #for row in display_with_stock_symbol(scanData).iterrows():
                for contract, details in self.display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
                        pos=pos+1
                        sql = """
                            INSERT INTO ib_scanner (
                                mode,
                                ts_exec,
                                pos,
                                symbol,
                                conidex,
                                available_chart_periods,
                                company_name,
                                contract_description_1,
                                listing_exchange,
                                sec_type
                            ) VALUES (?,?, ?, ?, ?, ?, ?, ?, ?,?)
                        
                            """
                        
                        conn.execute(sql, (
                            name,
                            run_time,
                            pos,
                            contract.symbol,
                            contract.conId, #conidex
                            "",
                            contract.description,
                            "",
                            contract.exchange,
                            contract.secType
                        ))
                        
                
                        conn.commit()
                    
                        ##### stocks
                        df_stocks = pd.read_sql_query(f"select * from STOCKS where symbol='{contract.symbol}'", conn)
                        if len(df_stocks)==0:
                                
                            logger.info(f"CREATE STOCK ..  {contract}")
                            conn.execute("""
                                INSERT  INTO stocks (symbol, exchange,ib_conid) VALUES (?,?,?) """, (contract.symbol,contract.exchange,contract.conId))
                                
                            conn.commit()
                            
                        sql = f"UPDATE STOCKS SET ib_conid={contract.conId} , currency='{contract.currency}' WHERE symbol ='{contract.symbol}'"
                        conn.execute(sql)
                        conn.commit()

                        
                conn.close()

                #max_symbols=config["database"]["live"]["max_symbols"]
                #if max_symbols != None:
                #    symbols = symbols [:max_symbols]

                #logger.info(f"df_fundamentals \n{df_fundamentals}")
                items=[]
                for symbol in symbols:
                    new_row = {"symbol": symbol}
                    
                    for contract, details in self.display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
                        if contract.symbol == symbol:
                            #print(contract)
                            new_row["conid"]=  contract.conId
                    for _, row in df_fundamentals.iterrows():
                        if  row["symbol"]  == symbol:
                            new_row["listing_exchange"]= row["exchange"] 
        
                    items.append(new_row)

                
                #print(items)
                df = pd.DataFrame(
                    [(o["symbol"], o["conid"], o["listing_exchange"]) for o in items],
                    columns=["symbol", "conidex","listing_exchange"]
                )

                #res = ScannerResult()
                #res.df_fundamentals = df_fundamentals
                #res.df_symbols = df

               # if max_symbols != None:
                #    df_fundamentals = df_fundamentals [:max_symbols]

                return  df

########################################################################

async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    ib = IB()
    ib.connect('127.0.0.1', config["live_service"]["ib_port"], clientId=1)

    ms = MarketService(config)    
    scanner = Scanner(ib,config,ms)
   

    df_symbols = await scanner.do_scanner( "TOP_PERC_GAIN",2)
    
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
   