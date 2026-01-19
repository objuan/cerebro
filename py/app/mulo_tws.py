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
from mulo_job import MuloJob
from mulo_scanner import Scanner
from mulo_live import LiveManager

use_yahoo=False
use_display = True

DB_TABLE = "ib_ohlc_live"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("ib_insync").setLevel(logging.WARNING)

run_mode = config["database"]["scanner"].get("mode","sym") 
start_scan =  config["database"]["scanner"].get("start_scan","live") 

fetcher = MuloJob(DB_FILE,config)
ms = MarketService(config)          # o datetime.now()
market = ms.getMarket("AUTO")

ws_manager = WSManager()
ws_manager_orders = WSManager()
OrderManager.ws = ws_manager_orders
OrderTaskManager.ws = ws_manager_orders
Balance.ws = ws_manager_orders

if use_display:
    cmd_console = Console()
    live_display = Live(console=cmd_console, refresh_per_second=2)
else:
    live_display=None

if run_mode!= "sym":
    ib = IB()
    ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)

    OrderManager(config,ib)
    # Subscribe to news bulletins
    ib.reqNewsBulletins(allMessages=True)
    Balance(config,ib)

    scanner = Scanner(ib,config,ms)

    def on_display(table):
        live_display.update(table)
    if use_display:
        live = LiveManager(ib,config,fetcher,scanner,ws_manager,on_display)
    else:
        live = LiveManager(ib,config,fetcher,scanner,ws_manager,None)

else:
    OrderManager(config,None)
    Balance(config,None)
    scanner = Scanner(None,config,ms)
    live = LiveManager(None,config,fetcher,scanner,ws_manager,None)

OrderTaskManager(config)


#print(ib.newsBulletins())

def on_news_bulletin(newsBulletin):
    logger.info(f"NEWS BULLETIN {newsBulletin}")
    '''
    asyncio.create_task(ws_manager.broadcast({
        "type": "news_bulletin",
        "msgId": newsBulletin.msgId,
        "msgType": newsBulletin.msgType,
        "newsMessage": newsBulletin.newsMessage,
        "originExch": newsBulletin.originExch
    }))
    '''

def on_news_events(newsBulletin):
    logger.info(f"NEWS EVT {newsBulletin}")
    '''
    asyncio.create_task(ws_manager.broadcast({
        "type": "news",
        "msgId": newsBulletin.msgId,
        "msgType": newsBulletin.msgType,
        "newsMessage": newsBulletin.newsMessage,
        "originExch": newsBulletin.originExch
    }))
    '''

if run_mode!= "sym":
    ib.newsBulletinEvent += on_news_bulletin
    ib.tickNewsEvent += on_news_events


#symbols = []
#live_send_key={}

sym_time = None
app = FastAPI(  )


#Configura le origini permesse
'''
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" permette tutto, utile per test. In produzione metti l'URL specifico.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''
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

################################

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

###
#trade_mode=None
#pre_ts_date={}

#last_stats = {}
#agg_cache = {}
#RETENTION_HOURS = config["database"]["live"]["RETENTION_HOURS"]      # quante ore tenere
#CLEANUP_INTERVAL = config["database"]["live"]["CLEANUP_INTERVAL_HOURS"] * 3600   # ogni quanto pulire (1h)
'''
TIMEFRAMES = {
    "10s": 10,
    "1m": 60,
    "5m": 300,
    #"1h": 3600,
}
'''

#######################################################

sym_time = None

#######################################################


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



##################################################
@app.get("/market")
def health(symbol):
    logger.info(f"Market {symbol}")

    exchange = fetcher.get_exchange(symbol)
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
        df_symbols = await scanner.do_scanner(config, name,end)
        
        #df_symbols = await scan(config,config["database"]["live"]["max_symbols"])

        #updateLive(config,df_symbols )
                    
        return {"status": "ok","data" : df_symbols.to_dict('records') if df_symbols is not None else []}
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error"}

'''
@app.get("/live")
async def do_live( symbols: str ):
    try:
        _symbols = symbols.split(",")
        filter = str(_symbols)[1:-1]

        logger.info(f"live {filter}")
        
        df_symbols = pd.read_sql_query(f"SELECT symbol,ib_conid as conidex , exchange as listing_exchange FROM STOCKS where symbol in ({filter})",conn)
        
        await live.updateLive(config,df_symbols )
     
        return {"status": "ok"}
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "ko"}
'''
@app.get("/conId")
async def conId(symbol,exchange,currency):

    contract = Stock(symbol,exchange,currency)
    ib.qualifyContracts(contract)
    
    logger.info(f"....... {contract.conId}")
    return {"status": "ok" , "data": { "conId" : str(contract.conId)}}

@app.get("/symbols")
async def get_symbols():
    return {"status": "ok" , "data": [ x.symbol for x in live.ordered_tickers()]}

@app.get("/tickers")
async def get_tickers():
    offline_mode = run_mode!="live" #:#config["database"]["scanner"]["offline_mode"] 
    data=[]
    for  ticker  in live.ordered_tickers():
        if (ticker.time  and  not math.isnan(ticker.last)) or offline_mode:
            data.append({"symbol": ticker.symbol, "last": ticker.last, "bid" : ticker.bid , "ask": ticker.ask,"low": ticker.low , "high" : ticker.high,"volume": ticker.volume*100, "ts":   ticker.time .timestamp()  })
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
async def do_buy_at_level(symbol:str, qty:float,price:float):
    try:
        logger.info(f"do_buy_at_level {symbol}")
        order_mode = config["order"]["mode"]
        zone = fetcher.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.add_at_level(symbol,"buy_at_level", qty,price,desc)
        else:
            OrderManager.buy_at_level(symbol, qty,price)
            
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }

@app.get("/order/bracket")
async def do_bracket(symbol:str,timeframe:str):
    try:
        logger.info(f"do_bracket {symbol} {timeframe}")
        order_mode = config["order"]["mode"]

        zone = fetcher.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.bracket(symbol,timeframe)
        else:
            pass
            #OrderManager.buy_at_level(symbol, qty,price)
            
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/sell_at_level")
async def do_sell_at_level(symbol:str, qty:float,price:float,desc:str):
    try:
        order_mode = config["order"]["mode"]
        zone = fetcher.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.add_at_level(symbol,"sell_at_level", qty,price,desc)
        else:
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

#############

@app.get("/order/clear_all")
async def clar_all_orders(symbol: str):
    try:

        pos = Balance.get_position(symbol)
        if (pos and pos.position>0):
            logger.info(f"SELL ALL {symbol} {pos.position} ")
            OrderManager.smart_sell_limit(symbol,pos.position, live.getTicker(symbol))

        OrderManager.cancel_orderBySymbol(symbol)
        result = await OrderTaskManager.cancel_orderBySymbol(symbol, )
      
        if result:
            return {"status": "ok", "message": f"Orders cancelled {symbol}"}
        else:
            return {"status": "warn", "message": f"No order founds fo {symbol}"}
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
    
####################################

@app.get("/order/task/list")
async def get_task_orders(start: Optional[str] = None,
                          onlyReady: bool = False):
    if not start:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_start.isoformat().replace("T"," ")
    try:

        if onlyReady:
            query="""SELECT * FROM task_orders 
            WHERE id IN (
                SELECT MAX(o.id)
                FROM task_orders o
                GROUP BY task_id
            )
            AND status =='READY'
            AND ds_timestamp >= ? 
            """
        else:
            query =f"""
            SELECT * FROM task_orders 
            WHERE ds_timestamp >= ? 
            ORDER BY timestamp DESC
            """

        cur.execute(query, (start,))
        rows = cur.fetchall()

        logger.info(f"get task orders {start}")
        
        # Ottieni i nomi delle colonne
        columns = [desc[0] for desc in cur.description]
        
        # Converti in lista di dizionari
        data = [dict(zip(columns, row)) for row in rows]
        
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/order/task/symbol")
async def get_task_symbol_orders(symbol:str, 
                                start: Optional[str] = None,
                          onlyReady: bool = False):
    if not start:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_start.isoformat().replace("T"," ")
    try:

        if onlyReady:
            query="""SELECT * FROM task_orders 
            WHERE id IN (
                SELECT MAX(o.id)
                FROM task_orders o
                GROUP BY task_id
            )
            AND status =='READY'
            AND ds_timestamp >= ? 
            AND SYMBOL = ?
            """
        else:
            query =f"""
            SELECT * FROM task_orders 
            WHERE ds_timestamp >= ? 
            AND SYMBOL = ?
            ORDER BY timestamp DESC
            """

        cur.execute(query, (start,symbol,))
        rows = cur.fetchall()

        logger.info(f"get task orders {start}")
        
        # Ottieni i nomi delle colonne
        columns = [desc[0] for desc in cur.description]
        
        # Converti in lista di dizionari
        data = [dict(zip(columns, row)) for row in rows]
        
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
     
#######################

@app.get("/account/summary")
async def account_summary():
    try:
        summary = ib.accountSummary()

        def get_value(tag):
            return next((float(x.value) for x in summary if x.tag == tag), None)

        balance = {
            "cash": get_value("AvailableFunds"),
            "equity": get_value("EquityWithLoanValue"),
            "netLiquidation": get_value("NetLiquidation"),
            "buyingPower": get_value("BuyingPower"),
            "initialMargin": get_value("InitMarginReq"),
            "maintenanceMargin": get_value("MaintMarginReq"),
            "dayTradesRemaining": get_value("DayTradesRemaining"),
        }
        return balance
    

    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/account/values")
async def account_values():
    try:
        values  = ib.accountValues()

        cash_usd = next(
            float(v.value)
            for v in values
            if v.tag == "CashBalance" and v.currency == "USD"
        )
        return cash_usd

    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
      
@app.get("/account/positions")
async def account_positions():
    try:
        balance =  Balance.to_dict()
        return balance
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
    
###############################

@app.get("/monitor/open")
async def open_monitor(symbol:str):
    try:
        await fetcher._align_data(symbol,"10s")
        await fetcher._align_data(symbol,"30s")
        await fetcher._align_data(symbol,"1m")
        await fetcher._align_data(symbol,"5m")
        await fetcher._align_data(symbol,"1h")
        await fetcher._align_data(symbol,"1d")
        return {"status": "ok"}
    
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
    

####################

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

########

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
    
#################

@app.websocket("/ws/orders")
async def ws_tickers(ws: WebSocket):
    await ws_manager_orders.connect(ws)

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
           
           
    except WebSocketDisconnect:
        ws_manager_orders.disconnect(ws)

##################################################

async def bootstrap():
    # start live ?? 
   
    await live.bootstrap(start_scan)

    await OrderManager.bootstrap()
    await OrderTaskManager.bootstrap()
    await Balance.bootstrap()

#############   

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
    logger.info(f"RUN MODE {run_mode}")   

    async def main():

        try:
            
            #test
            #print("dd")
            #await do_scanner(config,"PRE",999)
            #exit(0)
            if use_display:
                live_display.start()

            u_config = uvicorn.Config(
                app=app, 
                host="0.0.0.0", 
                port=2000,
                log_level="info",
                #access_log=False
            )
            server = uvicorn.Server(u_config)

         
            _server_task = asyncio.create_task(server.serve())
          
            _tick_tickers = await live.start_batch()

            await bootstrap()

            _tick_orders = asyncio.create_task(OrderManager.batch())

            await asyncio.wait(
                [_server_task, _tick_tickers,_tick_orders],
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


    asyncio.run(main())

