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

        super().__init__(db_file,config, "ib_ohlc_history","ib_ohlc_live")

        self.conn_exe=sqlite3.connect(db_file, isolation_level=None)
        self.cur_exe = self.conn_exe.cursor()
        self.cur_exe.execute("PRAGMA journal_mode=WAL;")
        self.cur_exe.execute("PRAGMA synchronous=NORMAL;")

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

    async def scanner(self):
        logger.info(f".. Scanner call {time.ctime()}")

        await self.send_batch("scanner",{})
        #await self.batch_client.send_request("tws_batch", {"cmd":"scanner"})
        await self.on_update_symbols()
        logger.info(f".. Scanner call DONE {time.ctime()}")

    def tick(self):
       pass 


    async def on_update_symbols(self):
        await super().on_update_symbols()

        #dict = self.df_fundamentals.to_dict(orient="records")
        #logger.debug(dict)

        self.symbol_to_conid_map = {}
        self.symbol_to_exchange_map = {}
        for _, row in self.df_fundamentals.iterrows():
            
            self.symbol_to_conid_map[row["symbol"]] = row["ib_conid"]
            self.symbol_to_exchange_map[row["symbol"]] = row["exchange"]

        #logger.info(f"symbol_map {self.symbol_map}")
        #logger.info(f"symbol_to_conid_map {self.symbol_map}")
        #self.symbol_map = last_df.set_index("symbol")["listing_exchange"].to_dict()
        #self.symbol_to_conid_map = last_df.set_index("symbol")["conidex"].to_dict()

    async def fetch_live_candles(self):
        
      
        key = "all"
        if not key in  self.last_ts:

            last_date = datetime.now() - timedelta(minutes=10)
            last_seen = datetime_to_unix_ms(last_date)

            logger.info(f"START LIVE FROM {last_date}")
            self.last_ts[key] =last_seen
        
        last_seen= self.last_ts[key]
        self.marketZone = self.market.getCurrentZone()

        await self.updateTickers()
   
        if self.liveActive and self.marketZone == MarketZone.LIVE:
          
            #print(self.sql_symbols,last_seen)
          
            sql=f"""
            INSERT OR REPLACE INTO ib_ohlc_history
            SELECT
                exchange,
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                volume_day,
                'live',
                updated_at,
                ds_updated_at
            FROM ib_ohlc_live
            WHERE symbol in ({self.sql_symbols})
                AND updated_at >  {last_seen}
            """
 
            self.cur_exe.execute(sql)
   
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # get 
            cur.execute(f"""
                SELECT symbol, timeframe as tf ,updated_at as ts, timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
                FROM ib_ohlc_history
                WHERE  updated_at >= {last_seen}
                ORDER BY updated_at ASC
            """)

            rows = cur.fetchall()
           

            #print(rows)
            if rows:
                self.last_ts[key] = rows[-1]["ts"]

            #### tickers
            '''
            cur.execute(f"""
                  SELECT l.*
                        FROM ib_ohlc_live l
                        JOIN (
                            SELECT symbol, MAX(timestamp) AS max_ts
                            FROM ib_ohlc_live
                            WHERE symbol IN  ({self.sql_symbols})
                            AND timeframe = '1m'
                            GROUP BY symbol
                        ) t
                        ON l.symbol = t.symbol
                        AND l.timestamp = t.max_ts
                        WHERE l.timeframe = '1m'
                        ORDER BY l.symbol;
                """)
            tickers_rows = cur.fetchall()
            conn.close()
            symbol =""
            for r in tickers_rows:
                    symbol = r["symbol"]
                    ticker = Ticker(symbol)
                    ticker.ask = r["ask"]
                    ticker.bid = r["bid"]
                    ticker.price = r["close"]
                    ticker.volume_day = r["volume_day"]
                    ticker.timestamp = r["timestamp"]
                    #logger.debug(ticker)
                    self.updateTicker(ticker)
            '''
            return [dict(r) for r in rows]
        else:
            # PRE ZONE
            '''
            if self.liveActive:
                conn = sqlite3.connect(self.db_file)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # get 
                cur.execute(f"""
                    SELECT   exchange,   symbol,   timeframe as tf ,updated_at as ts, timestamp as t, open as o, high as h , low as l, close as c, volume as qv, volume as bv
                    FROM ib_ohlc_live_pre
                    WHERE symbol in ({self.sql_symbols})
                    and tf='1m'
                    ORDER BY timestamp desc LIMIT 3
                """)
                rows = cur.fetchall()
                conn.close()
                if rows:
                    #logger.debug(rows)
                    return [dict(r) for r in rows]
                else:
                    return  []
                
                
            else:
                return  []
                '''
            return  []

    async def _fetch_missing_history(self,cursor, symbol, timeframe, since):
        #since = week_ago_ms()

        try:
            update_delta_min = datetime.now() - datetime.fromtimestamp(float(since)/1000)
            candles= candles_from_seconds(update_delta_min.total_seconds(),timeframe)

            logger.info(f">> Fetching history s:{symbol} tf:{timeframe} s:{since} d:{update_delta_min} #{candles}")
            
            dt_start =  datetime.fromtimestamp(float(since)/1000)
            exchange = self.symbol_to_exchange_map[symbol]
        
            batch_count = 500
            i = 0
            while ( True):
                i=i+1

                #logger.info(f"{i} ASK  {dt_start}")

                ###########
                df = yf.download(
                    tickers=symbol,
                    start=dt_start.strftime("%Y-%m-%d"),
                    #period="1d",
                    interval=timeframe,
                    auto_adjust=False,
                    progress=False,
                )
                df = df.reset_index()
                df.columns = [
                    c[0] if isinstance(c, tuple) else c
                    for c in df.columns
                ]
                #logger.debug(df.head())      
                dateName = "Date"
                if not dateName in df.columns:
                    dateName ="Datetime"
                
                df[dateName] = df[dateName].astype("int64") // 10**9

                #logger.debug(df.head())      
                # 3. Converti i dati in un formato leggibile (List of Dicts)
                # util.df(bars) creerebbe un DataFrame, ma per JSON usiamo una lista
                ohlcv =  [
                    (b[0]*1000, b.Open, b.High, b.Low, b.Close, b.Volume)
                        for b in df.itertuples(index=False)
                ]

                # lì'ultima è parsiale
                ohlcv = ohlcv[:-1]
                #print(data)

                ################

                logger.debug(f"{i} Find rows # {len(ohlcv)}")
                if len(ohlcv) <1:
                    break

                last = ohlcv[-1]
                since = last[0] + 1
                #logger.info(f"last # {last}")

                for o in ohlcv:
                    ts, open_, high, low, close, vol = o
                    
                    #logger.debug(f"add {exchange} {symbol} {timeframe} {ts}")
                    cursor.execute("""
                INSERT INTO ib_ohlc_history (
                        exchange,
                        symbol,
                        timeframe,
                        timestamp,
                        open,
                        high,
                        low,
                        close,
                        base_volume,
                        quote_volume,
                        source,
                        updated_at,
                        ds_updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exchange, symbol, timeframe, timestamp)
                    DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        base_volume = excluded.base_volume,
                        quote_volume = excluded.quote_volume,
                        source = excluded.source,
                        updated_at = excluded.updated_at,
                        ds_updated_at = excluded.ds_updated_at
                    
                                
                    """, (
                        exchange,
                        symbol,
                        timeframe,
                        ts,
                        open_,
                        high,
                        low,
                        close,
                        vol,
                        vol * close,
                        "yahoo",
                        int(time.time() * 1000),
                        datetime.utcnow().isoformat()
                    ))
        
                    
                    cursor.commit()
                break
        except:
            logger.error("ERROR", exc_info=True)

 
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
  
   
