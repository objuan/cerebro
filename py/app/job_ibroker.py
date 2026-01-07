from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
from datetime import datetime
import time
import logging
from typing import List, Dict
import asyncio
from utils import *
from job import *
from renderpage import RenderPage
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

#from ib.tws_scanner import *
from ib_insync import IB,util,Stock

#from scanner.crypto import ohlc_history_manager

DB_FILE = "../db/crypto.db"

logging.getLogger("yfinance").setLevel(logging.INFO)
logging.getLogger("peewee").setLevel(logging.INFO)

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

logger = logging.getLogger(__name__)

###########

#TIMEFRAMES = ['1m', '5m']
#conn_read = sqlite3.connect(DB_FILE, isolation_level=None)

class IBrokerJob(Job):

    def __init__(self, ib,db_file, config):

        super().__init__(db_file,config, "ib_ohlc_history")

        '''
        self.conn_exe=sqlite3.connect(db_file, isolation_level=None)
        self.cur_exe = self.conn_exe.cursor()
        self.cur_exe.execute("PRAGMA journal_mode=WAL;")
        self.cur_exe.execute("PRAGMA synchronous=NORMAL;")
        '''
        self.ib=ib
        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()
        cur.execute("""
                    
    CREATE TABLE IF NOT EXISTS ib_ohlc_history (
        exchange TEXT,
        symbol TEXT,
        timeframe TEXT,
        timestamp INTEGER,

        open REAL,
        high REAL,
        low REAL,
        close REAL,

        base_volume REAL,
        quote_volume REAL,

        source TEXT,        -- ib | live
        updated_at INTEGER,          
        ds_updated_at TEXT,

        PRIMARY KEY (exchange, symbol, timeframe, timestamp)
    )""")
        conn.close()

if __name__ == "__main__":

    #ib = IB()

    # Co    nnect to TWS (use '127.0.0.1' and port 7497 for demo, 7496 for live trading)
    #ib.connect('127.0.0.1', 7497, clientId=1)

    #############
    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
            "logs/ibroker.log",
            maxBytes=5_000_000,
            backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    #############
    import json

    with open("config/cerebro.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    config = convert_json(config)

    job = IBrokerJob(None, "db/crypto.db",config)
    #await job.on_update_symbols()
 
    async def test():
        await job.ohlc_data("AAPL","1m",1000)
           
        #logger.info(df)   
    asyncio.run(test())
    #logger.info(df)
  
   
