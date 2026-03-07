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
from mulo.mulo_live_manager import  LiveScanner,LiveManager

#intervals = [10, 30, 60, 300]  # seconds for 10s, 30s, 1m, 5m
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
    if os.path.exists(LOG_FILE):
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

########################################################################

fetcher = MuloJob(DB_FILE,config)
ms = MarketService(config)    

live = None

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

@app.get("/tickers/info")
async def get_tickers_info():
    tickers = live.ordered_tickers()
    logger.info(f"get_tickers info {tickers}")

    response_data = []
    for x in tickers:
        # Troviamo i nomi degli scanner che contengono questo simbolo
        # Assumiamo che il controllo avvenga su 'actual_df' (se è un DataFrame) 
        # o su 'symbol_map' (se è un dizionario/lista)
        scanners_found = [
            scanner.name 
            for scanner in live.scanner_map.values() 
            if scanner.actual_df is not None 
            and "symbol" in scanner.actual_df.columns
            and x.symbol in scanner.actual_df["symbol"].values
        ]

        response_data.append({
            "symbol": x.symbol,
            "last": getattr(x, "last", None), 
            "last_volume": getattr(x, "volume", None),
            "scan": scanners_found  # Restituisce una lista di nomi, es: ["GAP_UP", "HIGH_VOL"]
        })
    logger.info(f"list {response_data}")

    return {
        "status": "ok",
        "data":response_data,
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
    if await live.scanData(profile_name):
        if live.ws_manager:
            await live.ws_manager.broadcast({"evt":"on_update_symbols"})
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

    global live
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
            
            if run_mode!= "sym":
                    ib = IB()
                    ib.connect('127.0.0.1', config["live_service"]["ib_port"], clientId=config["live_service"]["ib_client"])

                    #OrderManager(config,ib)
                
                    scanner = Scanner(ib,config,ms)

                    def on_display(table):
                        live_display.update(table)
                    if use_display:
                        live = LiveManager(ib,config,fetcher,scanner,ws_manager,ms,on_display)
                    else:
                        live = LiveManager(ib,config,fetcher,scanner,ws_manager,ms,None)

            else:
                    #OrderManager(config,None)
                    #Balance(config,None)
                    scanner = Scanner(None,config,ms)

                    #ib = IB()
                    #ib.connect('127.0.0.1', config["live_service"]["ib_port"], clientId=config["live_service"]["ib_client"])

                    live = LiveManager(None,config,fetcher,scanner,ws_manager,None)


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
            if _tick_tickers:
                await asyncio.wait(
                    [_server_task, _tick_tickers],#_tick_orders
                    return_when=asyncio.FIRST_COMPLETED
                )
            else:
                await asyncio.wait(
                    [_server_task],#_tick_orders
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
    formatter = logging.Formatter("%(asctime)s - %(levelname)s -  Th:%(thread)d " "[%(filename)s:%(lineno)d] \t%(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    asyncio.run(main())
   