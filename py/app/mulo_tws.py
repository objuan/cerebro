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
from config import DB_FILE,CONFIG_FILE
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts
from company_loaders import *
from renderpage import WSManager
from order import OrderManager

use_yahoo=False

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)


ib = IB()
ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)

OrderManager(ib)
# Subscribe to news bulletins
ib.reqNewsBulletins(allMessages=True)

#print(ib.newsBulletins())

def on_news_bulletin(newsBulletin):
    logger.info(f"NEWS BULLETIN {newsBulletin}")
    asyncio.create_task(ws_manager.broadcast({
        "type": "news_bulletin",
        "msgId": newsBulletin.msgId,
        "msgType": newsBulletin.msgType,
        "newsMessage": newsBulletin.newsMessage,
        "originExch": newsBulletin.originExch
    }))

def on_news_events(newsBulletin):
    logger.info(f"NEWS EVT {newsBulletin}")
    asyncio.create_task(ws_manager.broadcast({
        "type": "news",
        "msgId": newsBulletin.msgId,
        "msgType": newsBulletin.msgType,
        "newsMessage": newsBulletin.newsMessage,
        "originExch": newsBulletin.originExch
    }))


ib.newsBulletinEvent += on_news_bulletin
ib.tickNewsEvent += on_news_events

DB_TABLE = "ib_ohlc_live"

ms = MarketService(config)          # o datetime.now()
market = ms.getMarket("AUTO")
symbols = []
live_send_key={}

app = FastAPI(  )

console = Console()
live_display = Live(console=console, refresh_per_second=2)

#Configura le origini permesse
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" permette tutto, utile per test. In produzione metti l'URL specifico.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ws_manager = WSManager()

if use_yahoo:
    ws_yahoo = yf.AsyncWebSocket()

################################

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

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

### Global data structures for ticker history
ticker_history = {}  # symbol -> deque of (ts, price)
intervals = [10, 30, 60, 300]  # seconds for 10s, 30s, 1m, 5m

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

async def do_scanner(config,name, max_symbols):

    
        cfg = config["database"]["scanner"]
        offline_mode = "offline_mode" in cfg and cfg["offline_mode"] =="true"

        logger.info(f'SCANNING DATAS ... {cfg}')

        zone = market.getCurrentZone()
        
        logger.info(f'MARKET ZONE {zone}')

        if offline_mode and "debug_symbols" in cfg:
            logger.info("Use OFFLINE")
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
            if prof["name"] == name:# and zone == MarketZone.LIVE:
                filter = prof
            if prof["name"] == name:# and zone == MarketZone.PRE:
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

            #scarto stocks senza float 
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
            
            pos=0
            # inserimento dati
            #for row in display_with_stock_symbol(scanData).iterrows():
            for contract, details in display_with_stock_symbol(scanData)[["contract", "contractDetails"]].values:
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

async def manage_live( symbol_list_add, symbol_list_remove):
    global actual_requests
    global tickers

    logger.info(f"===== Manage_live add:{symbol_list_add} del: {symbol_list_remove} =======")

    for symbol in symbol_list_add:
        exchange = "SMART"#symbol_map[symbol]
        contract = Stock(symbol, exchange, 'USD')

        logger.info(f"Open  feeds {contract}")
        # Request market data for the contract
        if use_yahoo:
            await ws_yahoo.subscribe(symbol)
            market_data={"symbol":symbol }
        else:
            ib.qualifyContracts(contract)
            market_data = ib.reqMktData(contract)
            amd = Stock(symbol, 'SMART', 'USD')

            #news
            yesterday = datetime.now() - timedelta(days=1)
            startDateTime = yesterday.strftime('%Y%m%d %H:%M:%S'),

            headlines = ib.reqHistoricalNews(amd.conId, "BRFG+BRFUPDN+FLY",startDateTime, '', 10)
            logger.info(f"-----> {headlines}")
            if len(headlines)>0:
                latest = headlines[0]
                print("-------",latest)
                article = ib.reqNewsArticle(latest.providerCode, latest.articleId)
                print("-------",article)
            

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

def on_news(symbol, news_list):
    for news in news_list:
        logger.info(f"NEWS {symbol} {news_list}")
        asyncio.create_task(ws_manager.broadcast({
            "type": "news",
            "symbol": symbol,
            "headline": news.headline,
            "time": news.time,
            "more": news.more
        }))

##########################################################

async def updateLive(config,df_symbols, range_min=None,range_max=None):
    global actual_df
    global symbol_map
    global symbol_to_conid_map

    # get last lives
    if df_symbols.empty:
         if actual_df:
            await manage_live([],actual_df["symbol"].to_list())
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

            await manage_live(actual_df["symbol"].to_list(),[])
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
async def scanner(name:str, start: Optional[int] = None, end: Optional[int] = None):
    logger.info(f"scanner {name} s:{start} e:{end}")
    try:
        df_symbols = await do_scanner(config, name,end)
        
        #df_symbols = await scan(config,config["database"]["live"]["max_symbols"])

        #updateLive(config,df_symbols )
                    
        return {"status": "ok","data" : df_symbols.to_dict('records') if df_symbols is not None else []}
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "ko"}

@app.get("/live")
async def do_live( symbols: str ):
    try:
        _symbols = symbols.split(",")
        filter = str(_symbols)[1:-1]

        logger.info(f"live {filter}")
        
        df_symbols = pd.read_sql_query(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})",conn)
        
        await updateLive(config,df_symbols )
     
        return {"status": "ok"}
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "ko"}

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

@app.get("/news")
async def get_news(symbol, start: Optional[str] = None):

    amd = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(amd)

    if not start:
        yesterday = datetime.now() - timedelta(minutes=1)
        startDateTime = yesterday.strftime('%Y%m%d %H:%M:%S'),
    else:
        startDateTime=start

    headlines = ib.reqHistoricalNews(amd.conId, "BRFG+BRFUPDN+FLY", startDateTime, '', 10)
    list=[]
    for new in headlines:
        #print("Headline:", new.headline)
        article = ib.reqNewsArticle(new.providerCode, new.articleId)
        list.append(article)
        #print("Article length:", len(article))
        #print("Article start:", article[:200])  # Print first 200 chars
        #print("Full article:", repr(article))  # To see if it's truncated

    #logger.info(data)
    return {"status": "ok" , "data": list}

####################
# no nsi ferma ?????
@app.get("/order/limit")
async def do_limit_order(symbol, qty,price):
    try:
        OrderManager.order_limit(symbol, qty,price)
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/buy_at_level")
async def do_limit_order(symbol, qty,price):
    try:
        OrderManager.buy_at_level(symbol, qty,price)
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }

@app.get("/order/sell/all")
async def do_sell_order(symbol):
    try:
        OrderManager.sell_all(symbol)
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/list")
async def get_orders(start: Optional[str] = None):
    if not start:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_start.isoformat().replace("T"," ")
    try:
        # Query per ottenere l'ultima riga per ogni trade_id con timestamp >= dt_start
        query = """
        SELECT * FROM ib_orders 
        WHERE id IN (
            SELECT MAX(id) FROM ib_orders 
            WHERE timestamp >= ? 
            GROUP BY trade_id
        )
        ORDER BY timestamp DESC
        """
        cur.execute(query, (start,))
        rows = cur.fetchall()

        logger.info(f"get orders {start}")
        
        # Ottieni i nomi delle colonne
        columns = [desc[0] for desc in cur.description]
        
        # Converti in lista di dizionari
        data = [dict(zip(columns, row)) for row in rows]
        
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/order/cancel")
async def cancel_order(permId: int):
    try:
        result = OrderManager.cancel_order(permId)
        if result:
            return {"status": "ok", "message": f"Order with permId {permId} cancelled"}
        else:
            return {"status": "error", "message": f"No order found with permId {permId}"}
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
    
####################

@app.websocket("/ws/tickers")
async def ws_tickers(ws: WebSocket):
    await ws_manager.connect(ws)

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
            try:
                data = json.loads(message)
                action = data.get("action")
                if action == "subscribe":
                    symbols = data.get("params", {}).get("symbols", "")
                    if symbols:
                        symbol_list = symbols.split(",")
                        # Create df_symbols from symbol_list
                        df_symbols = pd.DataFrame({
                            "symbol": symbol_list,
                            "conidex": [symbol_to_conid_map.get(s, 0) for s in symbol_list],
                            "listing_exchange": [symbol_map.get(s, "SMART") for s in symbol_list]
                        })
                        await updateLive(config, df_symbols)
                elif action == "unsubscribe":
                    symbols = data.get("params", {}).get("symbols", "")
                    if symbols == "*":
                        # Unsubscribe all
                        await updateLive(config, pd.DataFrame())
                    else:
                        # For partial, but for now, ignore
                        pass
            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
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
    logger.info("               IBROKER MULE V1.0")
    logger.info("=================================================")
  
    async def main():

        try:
            
            #test
            #print("dd")
            #await do_scanner(config,"PRE",999)
            #exit(0)

            live_display.start()

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

                      
                        
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(0.5)

            async def tick_tickers():
                while True:
                    try:
                        #ts = _time.time()
                        #data=[]
                        for symbol, ticker in tickers.items():
                            if ticker.time and not math.isnan(ticker.last):
                                await add_ticker(symbol,ticker)
                    except:
                        logger.error("ERR", exc_info=True)
                    await asyncio.sleep(0.1)

            async def add_ticker(symbol,ticker):
                #logger.info(f"!!!!!!! {symbol} ticker {ticker}")
                data=[]
                table = Table("Symbol", "Last", "Ask", "Bid", "10s OHLC", "30s OHLC", "1m OHLC", "5m OHLC", title="LIVE TICKERS")
                if use_yahoo:
                    ts = ticker.time#_time.time()
                else:
                    ts = ticker.time.timestamp()

                # Update history
                if symbol not in ticker_history:
                    ticker_history[symbol] = deque()
                ticker_history[symbol].append((ts, ticker.last, ticker.volume))
                # Remove old entries older than 5 minutes
                while ticker_history[symbol] and ticker_history[symbol][0][0] < ts - 300:
                    ticker_history[symbol].popleft()

                # Compute OHLC for each interval
                hls = []
                toSend=True
                for interval in intervals:
                    start = ts - (ts % interval)
                    start_time = datetime.fromtimestamp(start).strftime("%H:%M:%S")

                    prices = [p for t, p, v in ticker_history[symbol] if t >= start]
                    volumes = [v for t, p, v in ticker_history[symbol] if t >= start]
                    
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
                        data = {"s":symbol, "tf":interval,  "o":open_p,"c":close_p,"h":high,"l":low, "v":vol_diff, "ts":int(start), "dts":start_time  }

                        pack = f"o:{open_p:.2f} h:{high:.2f} l:{low:.2f} c:{close_p:.2f} v:{vol_diff:.0f} ({start_time}, {time_str})"
                    else:
                        pack = f"- ({start_time}, {time_str})"

                    key = symbol+str(interval)

                    if prices:
                        if key in live_send_key:
                            toSend = live_send_key[key] != pack

                        if toSend:
                            live_send_key[key]=pack

                            #logger.info(f"SEND {data}")

                            await ws_manager.broadcast(data)

                    hls.append(pack)

                #data.append({"symbol": symbol, "last": ticker.last, "bid": ticker.bid, "ask": ticker.ask, "low": ticker.low, "high": ticker.high, "volume": ticker.volume*100, "ts": ticker.time.timestamp()})
                table.add_row(symbol, f"{ticker.last:.6f}", f"{ticker.ask:.6f}", f"{ticker.bid:.6f}", hls[0], hls[1], hls[2], hls[3])
                data = sanitize(data)

                live_display.update(table)

            server_task = asyncio.create_task(server.serve())
             #_tick_candles = asyncio.create_task(tick_candles())
            
          
            async def yahoo_tick_tickers():
                async def message_handler(message):
                    #print("Received message from YAHOO:", message)
                    t = Ticker(last= message["price"], volume= int(message["day_volume"]), time=int(message["time"]), ask=0, bid=0 )
                    await add_ticker(message["id"],t)
                print("1")
                await  ws_yahoo.listen(message_handler)
                print("2")
                
            if use_yahoo:
                _tick_tickers = asyncio.create_task(yahoo_tick_tickers())
            else:
                _tick_tickers = asyncio.create_task(tick_tickers())

            await asyncio.wait(
                [server_task, _tick_tickers],
                return_when=asyncio.FIRST_COMPLETED
            )


        except:
            logger.error("ERROR", exc_info=True)
            live_display.stop()
        
            print("Disconnecting from TWS...")
            ib.disconnect()
            exit(0)


    asyncio.run(main())

