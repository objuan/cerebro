import asyncio
import json
import websockets
import sqlite3
from datetime import datetime
import time
import os
import signal
import json
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import IB,util,Stock

#util.startLoop()  # uncomment this line when in a notebook
  
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_FILE = "db/crypto.db"
CONFIG_FILE = "scanner/ibroker/config.json"
DB_TABLE = "ib_ohlc_live"

ib=None
#ib = IB()
async def ib_bootstrap(ib):
   
    #await ib.connect('127.0.0.1', 7497, clientId=1)
    if not ib.isConnected():
        await ib.connectAsync(
            host='127.0.0.1',
            port=7497,
            clientId=1,
            timeout=5
        )

    while True:
        #print("tick")
        try:
           pass
        except Exception as e:
            logger.error("errore pws loop:", exc_info=True)

        await asyncio.sleep(1)

async def _bootstrap():
    
    global ib
    ib = IB()
    await ib.connect('127.0.0.1', 7497, clientId=1)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            #print(config)
    except FileNotFoundError:
        print("File non trovato")
    except json.JSONDecodeError as e:
        print("JSON non valido:", e)


def init_db():

    ################################

    conn = sqlite3.connect(DB_FILE, isolation_level=None)
    cur = conn.cursor()

    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ib_ohlc_live (
            conindex INTEGER,
            symbol TEXT,
            timeframe TEXT,
            timestamp INTEGER, -- epoch ms
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            bid REAL,
            ask REAL,
            volume REAL,
            volume_day REAL,
            updated_at INTEGER, -- epoch ms
            ds_updated_at TEXT, -- epoch ms
            PRIMARY KEY(symbol, timeframe, timestamp)
        )""")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS ib_idx_ohlc_ts
            ON ib_ohlc_live(timestamp)
        """)

last_stats = {}
agg_cache = {}
RETENTION_HOURS = 48      # quante ore tenere
CLEANUP_INTERVAL = 3600  # ogni quanto pulire (1h)

TIMEFRAMES = {
    "30s": 30
    #"1m": 60,
    #"5m": 300,
    #"1h": 3600,
}

async def cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)

        cutoff_ms = int(
            (time.time() - RETENTION_HOURS * 3600) * 1000
        )

        cur.execute("""
        DELETE FROM ib_ohlc_live
        WHERE timestamp < ?
        """, (cutoff_ms,))

        #cur.execute("VACUUM;")  # opzionale, vedi nota sotto

        print(
            f"🧹 cleanup done (< {RETENTION_HOURS}h)"
        )

def floor_ts(ts_ms, sec):
    # ritorna in ms
    return (ts_ms // (sec*1000)) * (sec*1000)


def update_ohlc(conindex,symbol, price,bid,ask, volume, ts_ms):
    volume=volume*100
    for tf, sec in TIMEFRAMES.items():
        t = floor_ts(int(ts_ms)*1000, sec)
        #print(ts_ms,t)
        key = (conindex, tf, t)
        c = agg_cache.get(key)
        
        if c is None:
            agg_cache[key] = {
                "timeframe" : t,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume, #volume in giornata
                "volume_acc": 0, #volume in giornata
                "bid" : 0,
                "ask" : 0,
            }
        else:
            if (t != c["timeframe"]):
                c["volume_acc"]=0

            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume_acc"] =  (c["volume_acc"] + (volume- c["volume"]))
            c["volume"] = volume
            c["bid"] = bid
            c["ask"] = ask

        save = agg_cache[key]
        cur.execute("""
        INSERT OR REPLACE INTO ib_ohlc_live VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conindex, symbol, tf, t,
            save["open"], save["high"], save["low"], save["close"],
            save["bid"],save["ask"],
            save["volume_acc"], save["volume"], 
            int(time.time() * 1000),
            datetime.utcnow().isoformat()
        ))


############################

def display_with_stock_symbol(scanData):
    df = util.df(scanData)
    df["contract"] = df.apply( lambda l:l['contractDetails'].contract,axis=1)
    df["symbol"] = df.apply( lambda l:l['contract'].symbol,axis=1)
    return df[["rank","contractDetails","contract","symbol"]]

def scan(config):
    sub = ScannerSubscription(
        numberOfRows=50,
        instrument='STK',
        locationCode='STK.US.MAJOR',
        scanCode='TOP_PERC_GAIN', marketCapAbove= 1_000_000 , abovePrice= 100, aboveVolume= 100000
    )

    scanData = ib.reqScannerData(sub)

    #df = util.df(scanData)

    logger.debug(f'FIND #{len(scanData)}')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    run_time = int(time.time() * 1000)
    ds_run_time  = datetime.utcnow().isoformat()

            
    print(display_with_stock_symbol(scanData))
    # inserimento dati
    #for row in display_with_stock_symbol(scanData).iterrows():
    for contract, details in display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
            #contract = row["contract"]
            #details = row["contractDetails"]

            #logger.debug(contract.symbol)
            #details = contract.contractDetails

            '''
            data =  ib.reqMktData(
                contract=contract,
                genericTickList="",
                snapshot=True,
                regulatorySnapshot=False
            )
            ib.sleep(2)
            '''
            #print(data)
            '''
            print(details.validExchanges)
            print(details.longName)
            print(details.industry)
            print(details.category)
            print(details.subcategory)
            print(details.lastTradeTime)
            print(details.stockType)
            print(details.minSize)
            '''


            sql = """
                INSERT INTO ib_contracts (
                    symbol,
                    conidex,
                    available_chart_periods,
                    company_name,
                    contract_description_1,
                    listing_exchange,
                    sec_type, 
                    updated_at,
                    ds_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?,?)
                ON CONFLICT(conidex) DO UPDATE SET
                    conidex = excluded.conidex,
                    available_chart_periods = excluded.available_chart_periods,
                    company_name = excluded.company_name,
                    contract_description_1 = excluded.contract_description_1,
                    listing_exchange = excluded.listing_exchange,
                    sec_type = excluded.sec_type,
                    updated_at = excluded.updated_at,
                    ds_updated_at = excluded.ds_updated_at
                """
            
            conn.execute(sql, (
                contract.symbol,
                contract.conId, #conidex
                "",
                contract.description,
                "",
                contract.exchange,
                contract.secType,
                run_time,
                ds_run_time
            ))
                
            conn.commit()
           
            

    conn.close()

#######################################################


actual_df=None
#conidex_to_symbol=None
symbol_map=None
symbol_to_conid_map=None

actual_requests = []
tickers = {}

#######################################################

def manage_live( symbol_list_add, symbol_list_remove):
    global actual_requests
    global tickers

    logger.debug(f"manage_live {symbol_list_add,symbol_list_remove}")

    for symbol in symbol_list_add:
        exchange = symbol_map[symbol]
        contract = Stock(symbol, exchange, 'USD')

        # Request market data for the contract
        market_data = ib.reqMktData(contract)
        tickers[symbol]  = market_data
    

##########################################################

def updateLive(config,range_min=None,range_max=None):
    global actual_df
    global symbol_map
    global symbol_to_conid_map
    # get last lives
    
    
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("select max(updated_at) as max from ib_contracts", conn)
    max_date = df.iloc[0]["max"]
    #print("max_date",max_date)
    last_df = pd.read_sql_query(f"select conidex,symbol,listing_exchange from ib_contracts where updated_at={max_date}", conn)
    #print("df",last_df)
    conn.close()

    if range_min!=None:
        last_df = last_df.iloc[range_min:range_max]
    
    if not symbol_map :
        actual_df = last_df
        #manage_live(last_df,[])
        symbol_map = actual_df.set_index("symbol")["listing_exchange"].to_dict()
        symbol_to_conid_map = actual_df.set_index("symbol")["conidex"].to_dict()

        manage_live(actual_df["symbol"].to_list(),[])
    else:

        delta_removed = actual_df[~actual_df["symbol"].isin(last_df["symbol"])]
        delta_new = last_df[~last_df["symbol"].isin(actual_df["symbol"])]

        actual_df = last_df
        symbol_map = actual_df.set_index("symbol")["listing_exchange"].to_dict()
        symbol_to_conid_map = actual_df.set_index("symbol")["conidex"].to_dict()

        manage_live(delta_new["symbol"].to_list(),delta_removed["symbol"].to_list())
        

######################

def start_watch(receiveHandler):
    # Stream market data in a loop
    try:
        while True:
            ib.sleep(1)  # Sleep for 1 second and wait for updates
            for symbol, ticker  in tickers.items():
            
                receiveHandler(symbol,ticker)  # Print the latest market data
    except KeyboardInterrupt:
        # Gracefully disconnect on exit
        print("Disconnecting from TWS...")
        ib.disconnect()
