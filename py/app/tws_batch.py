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
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import *
from utils import convert_json
#from message_bridge import *
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
util.startLoop()  # uncomment this line when in a notebook
from config import DB_FILE,CONFIG_FILE
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts
from company_loaders import *
from renderpage import WSManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

ib = IB()
ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)

DB_TABLE = "ib_ohlc_live"


ms = MarketService(config)          # o datetime.now()
market = ms.getMarket("AUTO")
symbols = []

app = FastAPI(  )

'''
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js / React
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''
'''
@app.middleware("http")
async def add_referrer_policy(request, call_next):
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
'''

#Configura le origini permesse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" permette tutto, utile per test. In produzione metti l'URL specifico.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_manager = WSManager()

################################

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
    CREATE TABLE IF NOT EXISTS ib_ohlc_live (
        conindex INTEGER,
        symbol TEXT,
        exchange TEXT,
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
    CREATE TABLE IF NOT EXISTS ib_ohlc_live_pre (
        mode  TEXT,
        conindex INTEGER,
        symbol TEXT,
        exchange TEXT,
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

cur.execute("""
    CREATE INDEX IF NOT EXISTS ib_idx_ohlc_ts_pre
        ON ib_ohlc_live_pre(timestamp)
    """)

###
trade_mode=None
pre_ts_date={}

last_stats = {}
agg_cache = {}
RETENTION_HOURS = config["database"]["live"]["RETENTION_HOURS"]      # quante ore tenere
CLEANUP_INTERVAL = config["database"]["live"]["CLEANUP_INTERVAL_HOURS"] * 3600   # ogni quanto pulire (1h)

TIMEFRAMES = {
    "10s": 10,
    "1m": 60,
    "5m": 300,
    #"1h": 3600,
}

async def cleanup_task():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)

        cutoff_ms = int(
            (_time.time() - RETENTION_HOURS * 3600) * 1000
        )

        logger.info(f"CLEAN UP {cutoff_ms}")
        cur.execute("""
        DELETE FROM ib_ohlc_live
        WHERE timestamp < ?
        """, (cutoff_ms,))

        #cur.execute("VACUUM;")  # opzionale, vedi nota sotto

        print(
            f"🧹 cleanup done (< {RETENTION_HOURS}h)"
        )
       

def update_ohlc(conindex,symbol, exchange,price,bid,ask, volume, ts_ms, trade_mode:MarketZone):
    #volume=volume*100 # ????

    #logger.info(f"<< {symbol} {price} {volume} {ts_ms}" )
    for tf, sec in TIMEFRAMES.items():
            if trade_mode != MarketZone.LIVE and tf !="1m":
                continue

            t = floor_ts(int(ts_ms)*1000, sec)
            #t = floor_ts(int(ts_ms)*1000, sec) / 1000
            #logger.info(f"{ts_ms} {t}")
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
            if trade_mode==MarketZone.LIVE:
                cur.execute(f"""
                INSERT OR REPLACE INTO ib_ohlc_live VALUES (?,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conindex, symbol, exchange,  tf, t,
                    save["open"], save["high"], save["low"], save["close"],
                    save["bid"],save["ask"],
                    save["volume_acc"], save["volume"], 
                    int(_time.time() * 1000),
                    #int(_time.time() ),
                    datetime.utcnow().isoformat()
                ))
            else:
                cur.execute(f"""
                INSERT OR REPLACE INTO ib_ohlc_live_pre VALUES (?, ?,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "CLOSE" if trade_mode == MarketZone.CLOSED else "PRE",
                    conindex, symbol, exchange,  tf, t,
                    save["open"], save["high"], save["low"], save["close"],
                    save["bid"],save["ask"],
                    save["volume_acc"], save["volume"], 
                    int(_time.time() * 1000),
                    #int(_time.time() ),
                    datetime.utcnow().isoformat()
                ))


############################

def display_with_stock_symbol(scanData):
    df = util.df(scanData)
    df["contract"] = df.apply( lambda l:l['contractDetails'].contract,axis=1)
    df["symbol"] = df.apply( lambda l:l['contract'].symbol,axis=1)
    return df[["rank","contractDetails","contract","symbol"]]

async def scan(config,max_symbols):

    cfg = config["database"]["scanner"]
    logger.info(f'SCANNING DATAS ... {cfg}')

    zone = market.getCurrentZone()
    
    logger.info(f'MARKET ZONE {zone}')

    if "debug_symbols" in cfg:
        symbols = cfg["debug_symbols"]
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

    filter=None
    for prof in cfg["profiles"]:
        print(prof)
        if prof["name"] == "LIVE" and zone == MarketZone.LIVE:
            filter = prof
        if prof["name"] == "PRE" and zone == MarketZone.PRE:
            filter = prof
    
    logger.info(f'filter ...{filter}')


    sub = ScannerSubscription(
        numberOfRows=50,
        instrument=filter["instrument"],
        locationCode=filter["location"],
        scanCode=filter["type"]
        # marketCapAbove= 1_000_000 , abovePrice= 100, aboveVolume= 100000
    )

    #if zone == MarketZone.LIVE:
    if True:
        sub.stockTypeFilter = "COMMON" # solo azione vere, no nETF
        if "abovePrice" in filter:
            sub.abovePrice = filter["abovePrice" ]
        if "belowPrice" in filter:
            sub.belowPrice = filter["belowPrice" ]
        if "aboveVolume" in filter:
            sub.aboveVolume = filter["aboveVolume" ]
        if "marketCapAbove" in filter:
            sub.marketCapAbove = filter["marketCapAbove" ]
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
       
    logger.info(f'FILTER ...{sub}')

    scanData = ib.reqScannerData(sub)

    logger.info(f'FIND #{len(scanData)}')

    if len(scanData)>0:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        run_time = int(_time.time() * 1000)
        #run_time = int(_time.time() )
        ds_run_time  = datetime.utcnow().isoformat()
        
        #logger.info(display_with_stock_symbol(scanData)["symbol"])

        symbols = [] 
        for contract, details in display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
            if contract.conId!=0:
                symbols.append(contract.symbol)

        logger.info(f"find df_fundamentals \n{symbols}")
        df_fundamentals = await Yahoo(DB_FILE, config).get_float_list(symbols)

        #scarto stocke senza float 
        for _, row in df_fundamentals.iterrows():
            if not  row["float"] :
                logger.warning(f"DISCARD STOCK : {row['symbol']}")
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
        
        # inserimento dati
        #for row in display_with_stock_symbol(scanData).iterrows():
        for contract, details in display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:

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
        if max_symbols != None:
             symbols = symbols [:max_symbols]

        logger.info(f"df_fundamentals \n{df_fundamentals}")
        items=[]
        for symbol in symbols:
            new_row = {"symbol": symbol}
            
            for contract, details in display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
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
        return df

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

    logger.info(f"===== Manage_live add:{symbol_list_add} del: {symbol_list_remove} =======")

    for symbol in symbol_list_add:
        exchange = "SMART"#symbol_map[symbol]
        contract = Stock(symbol, exchange, 'USD')

        logger.info(f"Open  feeds {contract}")
        # Request market data for the contract
        market_data = ib.reqMktData(contract)
        tickers[symbol]  = market_data

    for symbol in symbol_list_remove:
        contract = Stock(symbol, exchange, 'USD')
        logger.info(f"Remove  feeds {contract}")
        try:
            ib.cancelMktData(contract)
        except:
            logger.error("CANCEL ERROR", exc_info=True)
        ib.sleep(1)

        del  tickers[symbol]
        
    logger.info(f"tickers {tickers}")

##########################################################

def updateLive(config,df_symbols, range_min=None,range_max=None):
    global actual_df
    global symbol_map
    global symbol_to_conid_map

    # get last lives
    if df_symbols.empty:
         if actual_df:
            manage_live([],actual_df["symbol"].to_list())
         actual_df=None
    else:
        if range_min!=None:
            df_symbols = df_symbols.iloc[range_min:range_max]

        logger.info(f"START LISTENING")
        if not symbol_map :
            actual_df = df_symbols
            #manage_live(last_df,[])
            symbol_map = actual_df.set_index("symbol")["listing_exchange"].to_dict()
            symbol_to_conid_map = actual_df.set_index("symbol")["conidex"].to_dict()

            manage_live(actual_df["symbol"].to_list(),[])
        else:

            delta_removed = actual_df[~actual_df["symbol"].isin(df_symbols["symbol"])]
            delta_new = df_symbols[~df_symbols["symbol"].isin(actual_df["symbol"])]

            actual_df = df_symbols
            symbol_map = actual_df.set_index("symbol")["listing_exchange"].to_dict()
            symbol_to_conid_map = actual_df.set_index("symbol")["conidex"].to_dict()

            manage_live(delta_new["symbol"].to_list(),delta_removed["symbol"].to_list())
        

##################################################
@app.get("/market")
def health(symbol):
    logger.info(f"Market {symbol}")

    exchange = symbol_map[symbol]
    contract = Stock(symbol, exchange, 'USD')
    ib.qualifyContracts(contract)

    ticker = ib.reqMktData(contract, '', False, False)
    ib.sleep(2)

    print("Last:", ticker.last)
    print("Bid:", ticker.bid)
    print("Ask:", ticker.ask)
    print("Volume:", ticker.volume)
    print("High:", ticker.high)
    print("Low:", ticker.low)

    logger.info(f"Market1 {symbol}")

    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/scanner")
async def scanner():
    df_symbols = await scan(config,config["database"]["live"]["max_symbols"])

    updateLive(config,df_symbols )
                   
    return {"status": "ok"}

@app.get("/scannerLimit")
async def scanner_limit(start:int,end:int):
    logger.info(f"scanner_limit s:{start} e:{end}")
    df_symbols = await scan(config, end)

    updateLive(config,df_symbols,start, end)
                   
    return {"status": "ok"}

@app.get("/conId")
async def conId(symbol,exchange,currency):

    contract = Stock(symbol,exchange,currency)
    ib.qualifyContracts(contract)
    
    logger.info(f"....... {contract.conId}")
    return {"status": "ok" , "data": { "conId" : str(contract.conId)}}

@app.get("/symbols")
async def get_symbols():
    offline_mode = config["database"]["scanner"]["offline_mode"]
    '''
    logger.info(f"get symbols {actual_df}")

    rows = actual_df[["symbol", "conidex", "listing_exchange"]].to_dict(orient="records")
    '''
    data=[]
    for symbol, ticker  in tickers.items():
        if (ticker.time  and  not math.isnan(ticker.last)) or offline_mode:
            data.append(symbol)
    
    return {"status": "ok" , "data": data}

@app.get("/tickers")
async def get_tickers():
    offline_mode = config["database"]["scanner"]["offline_mode"]
    data=[]
    for symbol, ticker  in tickers.items():
        if (ticker.time  and  not math.isnan(ticker.last)) or offline_mode:
            data.append({"symbol": symbol, "last": ticker.last, "bid" : ticker.bid , "ask": ticker.ask,"low": ticker.low , "high" : ticker.high,"volume": ticker.volume*100, "ts":   ticker.time .timestamp()  })
    data = sanitize(data)
    #logger.info(data)
    return {"status": "ok" , "data": data}

####################


@app.websocket("/ws/tickers")
async def ws_tickers(ws: WebSocket):
    await ws_manager.connect(ws)

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
            # {"action":"subscribe","params":{"symbols":"NVDA,AAPL"}}
            # {"action":"unsubscribe","params":{"symbols":"*"}}
            #await ws.send_text(f"Echo: {message}")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    

##################################################


if __name__ =="__main__":

    #############
    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
            "logs/tws_broker.log",
            maxBytes=5_000_000,
            backupCount=5
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
    #############

    logger.info("=================================================")
    logger.info("               IBROKER SCANNER V1.0")
    logger.info("=================================================")


    cur.execute("""
        DELETE FROM ib_ohlc_live""")

    async def main():
        trade_mode
        try:

            max_symbols=config["database"]["live"]["max_symbols"]
            df_symbols = await scan(config,max_symbols)
            #await cleanup_task()
            logger.info("-------------------")
            logger.info(f" Start with synbols : \n{df_symbols}")
            logger.info("-------------------")

           
            #updateLive(config, df_symbols, 0,2)
            updateLive(config, df_symbols)
            
            
            def receive(symbol, ticker: Ticker):
                '''
                live receive
                '''
                #logger.info(ticker)
                #print(">>", symbol_to_conid_map[symbol] , symbol, ticker.last,ticker.volume, ticker.time )
                
                if trade_mode != MarketZone.AFTER:#trade_mode == MarketZone.LIVE or trade_mode == MarketZone.PRE:

                    if ticker.time  and  not math.isnan(ticker.last):
                        '''
                        Ticker(contract=Stock(symbol='AEHL', exchange='SMART', currency='USD'), time=datetime.datetime(2025, 12, 30, 7, 49, 31, 129975, tzinfo=datetime.timezone.utc), minTick=0.0001, bid=1.71, bidSize=300.0, ask=1.72, askSize=200.0, last=1.71, lastSize=100.0, volume=1490.0, close=1.13, halted=0.0, bboExchange='9c0001', snapshotPermissions=3)
                        Ticker(contract=Stock(symbol='AEHL', exchange='SMART', currency='USD'), time=datetime.datetime(2025, 12, 30, 7, 50, 7, 622112, tzinfo=datetime.timezone.utc), minTick=0.0001, bid=1.71, bidSize=300.0, ask=1.72, askSize=300.0, last=1.71, lastSize=100.0, prevAskSize=200.0, volume=1490.0, close=1
                        '''
                        #logger.info(ticker)
                        ts = ticker.time .timestamp()
                        if symbol in symbol_to_conid_map:
                            update_ohlc(symbol_to_conid_map[symbol] , symbol,symbol_map[symbol], ticker.last,ticker.bid, ticker.ask, ticker.volume*100,ts,trade_mode)
                        else:
                            logger.warning(f"Ticker not removed !!! {symbol}")
                     
            #start_watch(receive)
            #asyncio.run(start_watch(receive))

            u_config = uvicorn.Config(
                app=app, 
                host="0.0.0.0", 
                port=2000,
                log_level="info",
                #access_log=False
            )
            server = uvicorn.Server(u_config)

            async def tick_candles():
                global trade_mode
                global last_stats
                global agg_cache
                while True:
                    try:
                        if market.getCurrentZone() != trade_mode:
                            trade_mode = market.getCurrentZone()
                            logger.info(f"TRADE MODE CHANGED {trade_mode}")
                            
                            last_stats = {}
                            agg_cache = {}

                        #print("TICK",tickers)
                        for symbol, ticker  in tickers.items():
                            receive(symbol,ticker)  # Print the latest market data
                        
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(0.5)

            async def tick_tickers():
                while True:
                    try:
                        data=[]
                        for symbol, ticker  in tickers.items():
                            if ticker.time  and  not math.isnan(ticker.last):
                                data.append({"symbol": symbol, "last": ticker.last, "bid" : ticker.bid , "ask": ticker.ask,"low": ticker.low , "high" : ticker.high,"volume": ticker.volume*100, "ts":   ticker.time .timestamp()  })
                        data = sanitize(data)
                        #logger.info(f">> {data}")
                        await ws_manager.broadcast(data)
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(0.1)

            server_task = asyncio.create_task(server.serve())
            _tick_candles = asyncio.create_task(tick_candles())
            _tick_tickers = asyncio.create_task(tick_tickers())
            _cleanup_task = asyncio.create_task(cleanup_task())


            await asyncio.wait(
                [server_task, _tick_tickers,_tick_candles],
                return_when=asyncio.FIRST_COMPLETED
            )

        except:
            logger.error("ERROR", exc_info=True)
        
            print("Disconnecting from TWS...")
            ib.disconnect()
            exit(0)


    asyncio.run(main())

    #clean_up()
