import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import sys
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
from fastapi import FastAPI, HTTPException, Request, WebSocket
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
from trade_manager import TradeManager
#from reports.event_manager import EventManager
from reports.report_manager import ReportManager

from reports.db_dataframe import *
from props_manager import PropertyManager
from mulo_live_client import MuloLiveClient
from strategy.strategy_manager import StrategyManager

print(" STAT FROM ",os.getcwd())

#DEF_LAYOUT = "app/layouts/default_layout.json"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

############# LOGS #############
#print(" STAT FROM ",os.getcwd())

#if not os.getcwd().endswith("APP"):
    #os.chdir("APP")
#print(" STAT FROM ",os.getcwd())

os.makedirs(LOG_DIR, exist_ok=True)
if False:
    if os.path.exists(LOG_FILE):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived = os.path.join(LOG_DIR, f"app_{timestamp}.log")
        shutil.move(LOG_FILE, archived)
else:
    os.remove(LOG_FILE)


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

# Rotazione: max 5 MB, tieni 5 backup
file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)

# Console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

########################################

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

#############

logger.info("=====================================")
logger.info("========   CEREBRO V0.1   ===========")
logger.info("=====================================")
#logger.info(f"CONFIG {config}")

logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("ib_insync").setLevel(logging.WARNING)

#############

run_mode = config["live_service"].get("mode","sym") 

#fetcher = MuloJob(DB_FILE,config)
ms = MarketService(config)          # o datetime.now()
market = ms.getMarket("AUTO")

ws_manager = WSManager()
ws_manager_orders = WSManager()

OrderTaskManager.ws = ws_manager_orders
Balance.ws = ws_manager_orders
propManager = PropertyManager()

client = MuloLiveClient(DB_FILE,config,propManager)

orderManager = OrderManager(config,client)

# FORZA IL LOOP COMPATIBILE PRIMA DI TUTTO
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ib=None


OrderTaskManager(config,orderManager=orderManager)

db = DBDataframe(config,client)
report = ReportManager(config,client,db)
#event_manager = EventManager(config,report)
tradeManager = TradeManager(config,client,propManager)
render_page = RenderPage(ws_manager)
#event_manager.render_page=render_page
report.render_page=render_page
strategy = StrategyManager(config,db,client,render_page)


tradeManager.on_trade_changed+= OrderTaskManager.on_update_trade

#layout = Layout(client,db,config)
#layout.read(DEF_LAYOUT)
#layout.set_render_page(render_page)   
#client.on_candle_receive += layout.notify_candles    

async def _on_partial_candle_receive(candle):
    #logger.info(f"candle {candle}")
    await render_page.send({
                   "type" : "candle",
                   "data": candle
               })

client.on_partial_candle_receive += _on_partial_candle_receive

async def _on_ticker_receive(ticker):
    await OrderTaskManager.onTicker(ticker)
    
    await render_page.send({
                   "type" : "ticker",
                   "data": ticker
               })
    
      
client.on_ticker_receive += _on_ticker_receive 

# FORZA IL LOOP COMPATIBILE PRIMA DI TUTTO
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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

'''
if run_mode!= "sym":
    ib.newsBulletinEvent += on_news_bulletin
    ib.tickNewsEvent += on_news_events
'''


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


################################

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")



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

@app.get("/")
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
    
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/ohlc_chart")
async def ohlc_chart(symbol: str, timeframe: str, limit: int = 1000):
    
    try:
        if not timeframe in ["1m","5m"]:
            # live test
            df:pd.DataFrame = await client.ohlc_data(symbol,timeframe,limit)
            df = df.dropna()
            #logger.info(df)
            #logger.debug(f"!!!!!!!!!!!! chart {df}")
            return JSONResponse(df.to_dict(orient="records"))  
        else:
            df1 = db.dataframe(timeframe, symbol)
            #logger.debug(f"{symbol} {timeframe} {df1}")
            df_co = (
                df1[["timestamp","open", "high","low","close","base_volume","quote_volume"]]
                .rename(columns={"timestamp":"t","open": "o", "high":"h","low":"l","close": "c","quote_volume":"qv","base_volume": "bv"})
                .copy().fillna(0)
            )
            #logger.info(f"NAN {df_co.isna().any().any()}")

            #logger.info(df_co.to_dict(orient="records"))
            return JSONResponse(df_co.to_dict(orient="records"))
    except:
        logger.error("Error", exc_info=True)
        return HTMLResponse("error", 500)


@app.get("/api/report")
def ohlc_chart(name: str):
    #layout.components.
    #return JSONResponse(df_co.to_dict(orient="records"))
    pass

@app.get("/api/symbols")
def get_symbols(limit: int = 1000):
    symbols = client.live_symbols()
    return JSONResponse({"symbols":symbols})


@app.get("/api/fundamentals")
def get_fundamentals(symbol:str):
    try:
        df =  client.get_fundamentals(symbol)
        if not df.empty:
            return JSONResponse(df.iloc[0].to_dict())
        else:
            return JSONResponse({})
    except:
        return JSONResponse({})

#################################

@app.get("/api/props/find")
def read_props(path: str):
    data = propManager.get(path)
   
    result = [
        {"path": k, "value": v}
        for item in data
        for k, v in item.items()
    ]

    logger.info(f"data {result}")
    return JSONResponse(result)

@app.post("/api/props/save")
async def write_props(payload:dict):
    logger.info(f"write_props {payload}" )

    async def on_computed_changed(comp):
        for k, v in comp.items():
            msg =  {"type":"props", "path": k, "value": v()}
        logger.info(f"send {msg}")
        await render_page.send(msg)
        await tradeManager.on_property_changed(k,v(),render_page)

    await propManager.set(payload["path"], payload["value"],on_computed_changed)
    
    #for k,val in payload.items():
    #    propManager.setProp(k,val)
    return JSONResponse("ok")

######################

@app.post("/api/chart/indicator/save")
def save_chart_indicator(payload: dict):
    logger.info(f"SAVE CHART IND {payload}")   
   
    name = payload["name"]
    data = payload["data"]
      
    logger.info(f"name {name} data {data}")   
   
    client.execute("""
        INSERT INTO chart_indicator (name, data)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                data = excluded.data
    """, (
        name,
        json.dumps(data)
    ))

@app.get("/api/chart/indicator/list")
def list_chart_indicator():
    df = client.get_df("""
        SELECT name,data
        FROM chart_indicator
    """)
    return JSONResponse(df.to_dict(orient="records"))

@app.post("/api/chart/save")
def save_chart_line(payload: dict):
    #logger.info(f"SAVE CHART LINE {payload}")   
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
        guid = payload["guid"]
        data = payload["data"]
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Campo mancante: {e.args[0]}"
        )
    client.execute("""
        INSERT INTO chart_lines (guid,symbol, timeframe, type, data)
        VALUES (?, ?, ?, ?,?)
    """, (
        guid,
        symbol,
        timeframe,
        data.get("type"),
        json.dumps(data)
    ))

    return {"status": "ok"}

@app.delete("/api/chart/delete")
def delete_chart_line(payload: dict  ):
    try:
        guid = payload["guid"]
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Campo mancante: {e.args[0]}"
        )

    #logger.info(f"DELETE CHART LINE {guid}")
    client.execute("""
        DELETE FROM chart_lines WHERE guid = ?
    """, (guid,))
    return {"status": "ok" }

@app.delete("/api/chart/delete/all")
def delete_chart_all(payload: dict  ):
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Campo mancante: {e.args[0]}"
        )

    #logger.info(f"DELETE ALL CHART LINES {symbol} {timeframe}")
    client.execute("""
        DELETE FROM chart_lines WHERE symbol = ? and timeframe= ?   
    """, (symbol,timeframe))
    return {"status": "ok" }

@app.get("/api/chart/read")
def read_chart_lines(symbol: str, timeframe: str):
    df = client.get_df("""
        SELECT guid, symbol, timeframe, type, data
        FROM chart_lines
        WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe))

   # logger.info(f"READ CHART LINES {symbol} {timeframe} -> {df} ")    
    
    return JSONResponse(df.to_dict(orient="records"))

##############################

@app.post("/api/trade/marker/add")
async def save_chart_marker(payload: dict):
    logger.info(f"ADD TRADE  {payload}")   
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
        data = payload["data"]

        timeframe = payload["timeframe"]
        order = await tradeManager.add_order(symbol,timeframe,data)

        if order:
                return {"status": "ok", "data" : order}
        else:
                return  {"status": "ko"}
    except :
        logger.error("ERROR", exc_info=True)
        return  {"status": "ko"}
    
@app.post("/api/trade/marker/update")
async def save_chart_marker(payload: dict):
    logger.info(f"UPDATE TRADE  {payload}")   
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
        data = payload["data"]

        timeframe = payload["timeframe"]
        order = await tradeManager.update_order(symbol,timeframe,data)

        if order:
                return {"status": "ok", "data" : order}
        else:
                return  {"status": "ko"}
    except :
        logger.error("ERROR", exc_info=True)
        return  {"status": "ko"}   

@app.get("/api/trade/marker/read")
def read_chart_lines(symbol: str, timeframe: str):
    df = client.get_df("""
        SELECT  symbol, timeframe,  data
        FROM trade_marker
        WHERE symbol = ? AND timeframe = ?
    """, (symbol, timeframe))

    #logger.info(f"READ TRADE MARKER {symbol} {timeframe} -> {df} ")    
    
    if df.empty:
        return JSONResponse({})
    else:
        return JSONResponse(df.iloc[0].to_dict())

@app.delete("/api/trade/marker/delete")
def delete_trade_marker(payload: dict  ):
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Campo mancante: {e.args[0]}"
        )

    client.execute("DELETE FROM trade_marker WHERE symbol=? AND timeframe=?",
            (symbol, timeframe))
    return {"status": "ok" }

#################

@app.get("/market")
def health(symbol):
    logger.info(f"Market {symbol}")

    exchange = client.get_exchange(symbol)
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

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/conId")
async def conId(symbol,exchange,currency):

    contract = Stock(symbol,exchange,currency)
    ib.qualifyContracts(contract)
    
    logger.info(f"....... {contract.conId}")
    return {"status": "ok" , "data": { "conId" : str(contract.conId)}}

@app.get("/symbols")
async def get_symbols():
    return {"status": "ok" , "data": [ x["symbol"] for x in client.ordered_tickers()]}

@app.get("/tickers")
async def get_tickers():
    offline_mode = run_mode!="live" #:#config["database"]["scanner"]["offline_mode"] 
    data=[]
    for  ticker  in client.ordered_tickers():
      
        if (ticker["ts"]  and  not math.isnan(ticker["last"])) or offline_mode:
            data.append({"symbol": ticker["symbol"], "last": ticker["last"], "bid" : ticker["bid"] , "ask": ticker["ask"],"low": ticker["low"] , "high" : ticker["high"],"volume": ticker["volume"]*100, "ts":   ticker["ts"]/1000 })
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
async def do_limit_order(symbol, qty):
    try:
        logger.info(f"/order/limit {symbol} {qty}")
        await orderManager.smart_buy_limit(symbol, qty,client.getTicker(symbol))
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/buy_at_level")
async def do_buy_at_level(symbol:str, qty:float,price:float):
    try:
        logger.info(f"do_buy_at_level {symbol}")
        order_mode = config["order"]["mode"]
        zone = client.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.add_at_level(symbol,"buy_at_level", qty,price,"")
        else:
            orderManager.buy_at_level(symbol, qty,price)
            
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }

@app.get("/order/bracket")
async def do_bracket(symbol:str,timeframe:str):
    try:
        logger.info(f"do_bracket {symbol} {timeframe}")
        order_mode = config["order"]["mode"]

        zone = client.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.bracket(symbol,timeframe)
        else:
            pass
            #orderManager.buy_at_level(symbol, qty,price)
            
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/sell_at_level")
async def do_sell_at_level(symbol:str, qty:float,price:float,desc:str):
    try:
        order_mode = config["order"]["mode"]
        zone = client.getCurrentZone()
        if zone != MarketZone.LIVE or order_mode=="task_all":
            await OrderTaskManager.add_at_level(symbol,"sell_at_level", qty,price,desc)
        else:
            orderManager.buy_at_level(symbol, qty,price)
            
        return {"status": "ok" }
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error" }
    
@app.get("/order/sell/all")
async def do_sell_order(symbol):
    try:
        orderManager.sell_all(symbol)
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
        result = orderManager.cancel_order(permId)
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

        await OrderTaskManager.cancel_orderBySymbol(symbol)

        pos = Balance.get_position(symbol)
        if (pos and pos.position>0):
            logger.info(f"SELL ALL {symbol} {pos.position} ")
            ret = await orderManager.smart_sell_limit(symbol,pos.position, client.getTicker(symbol))

        #OrderManager.cancel_orderBySymbol(symbol)
            
      
            if not ret:
                return {"status": "ok", "message": f"Orders cancelled {symbol}"}
            else:
                return {"status": "warn", "message": f"No order founds fo {symbol}"}
        else:
            return {"status": "ok", "message": f"Orders cancelled {symbol}"}
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
            AND status in ('READY', 'STEP')
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
###################


@app.get("/api/report/get")
async def get_report():
    await report.send_current()
    return {"status": "ok"}

@app.get("/api/event/get")
async def get_events():
    
    try:
        # Query per ottenere l'ultima riga per ogni trade_id con timestamp >= dt_start
        query = """
        SELECT * FROM events 
        ORDER BY id DESC limit 10
        """
        df = client.get_df(query)

        return JSONResponse(df.to_dict(orient="records"))
    
    
    except:
        logger.error("ERROR", exc_info=True)
        return {"status": "error"}

###################################

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
    

@app.get("/trade/history")
def trade_history(symbol: str):

    list = []
    trades = orderManager.getTradeHistory(symbol)
    for trade in trades:
        #logger.info(f"trade {trade.to_dict()}")
        list.append(trade.to_dict())

    return list

@app.get("/trade/last")
def trade_history(symbol: str):


    return orderManager.getLastTrade(symbol)
###############################

@app.get("/monitor/open")
async def open_monitor(symbol:str):
    try:
        await client._align_data(symbol,"10s")
        await client._align_data(symbol,"30s")
        await client._align_data(symbol,"1m")
        await client._align_data(symbol,"5m")
        await client._align_data(symbol,"1h")
        await client._align_data(symbol,"1d")
        return {"status": "ok"}
    
    except Exception as e:
        logger.error("ERROR", exc_info=True)
        return {"status": "error", "message": str(e)}
    

####################

@app.get("/sym/time")
async def get_sym_time():
    return {"status": "ok", "data": client.sym_time}

@app.get("/sym/speed")
async def get_sym_speed():
    return {"status": "ok", "data": client.sym_speed}

@app.get("/sym/time/set")
async def set_sym_time(time:int):
    await client.setSymTime(time)
    return {"status": "ok"}

@app.get("/sym/speed/set")
async def set_sym_speed(value:float):
    await  client.setSymSpeed(value)
    return {"status": "ok"}

########

@app.websocket("/ws/live")
async def ws_tickers(ws: WebSocket):
    print("HEADERS:", ws.headers)
    print("QUERY:", ws.query_params)

    await ws_manager.connect(ws)

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
           
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


#############   

if __name__ =="__main__":

    #############

    logger.info(f"RUN MODE {run_mode}")   

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    async def main():
        ancora=True


        if run_mode!= "sym":
        
            ib = IB()
            util.patchAsyncio()
            #ib.connect('127.0.0.1', config["general"]["ib_port"], clientId=config["general"]["ib_client"])
            await ib.connectAsync(
                    host="127.0.0.1",
                    port=config["general"]["ib_port"],
                    clientId=config["general"]["ib_client"],
                    timeout=10
                )
            
            contract = Stock(
                "NVDA",
                "SMART",
                "USD",
                primaryExchange="NASDAQ"
            )

            # ✅ QUALIFY ASYNC
            contracts = await ib.qualifyContractsAsync(contract)
            contract = contracts[0]

            logger.info(f"TEST CONTACT : {contract}")

            #orderManager.ib = ib
            #orderManager.ws = ws_manager_orders
            await orderManager.bootstrap(ib,ws_manager_orders)
            # Subscribe to news bulletins
            ib.reqNewsBulletins(allMessages=True)
            Balance(config,ib)

        else:
            #orderManager.ws = ws_manager_orders
            await orderManager.bootstrap(None,ws_manager_orders)
            Balance(config,None)

        try:
        
            u_config = uvicorn.Config(
                app=app, 
                host="0.0.0.0", 
                port=8000,
                log_level="info",
                #access_log=False
            )
            server = uvicorn.Server(u_config)
         
            _server_task = asyncio.create_task(server.serve())
          
            #_tick_tickers = await live.start_batch()
            async def bootstrap():
                # start live ?? 
                
                await client.bootstrap()
                
                await db.bootstrap()
          
                await report.bootstrap()
                
               # await event_manager.bootstrap()

                await strategy.bootstrap()
                
                #await orderManager.bootstrap()
                
                await OrderTaskManager.bootstrap()
                
                await Balance.bootstrap()
                logger.info("BOOT DONE")

            await bootstrap()
            
            _tick_orders = asyncio.create_task(orderManager.batch())

            _tick_tickers = asyncio.create_task(client.batch())

            ########

            async def tick():
                while(ancora):
                    try:
                        #logger.info("1 sec")
                        
                        
                        if (client.sym_mode):
                            msg = {
                                "path": "root.clock",
                                "data": client.sym_time 
                            }
                        else:
                            msg = {
                                "path": "root.clock",
                                "data": int(time.time() * 1000)
                            }
                            
                        
                        await ws_manager.broadcast(msg)
                        
                        #await db.tick()

                        await report.tick()
                            
                        #await event_manager.tick(render_page)
                        
                        #await layout.tick(render_page)
                        
                        
                    except:
                        logger.error("ERROR", exc_info=True)
                    
                    await asyncio.sleep(1)

            _tick_tick = asyncio.create_task(tick())
            
            await asyncio.wait(
                [_server_task, _tick_orders,_tick_tickers], #_tick_tickers
                return_when=asyncio.FIRST_COMPLETED
            )

        except:
            logger.error("ERROR", exc_info=True)
            ancora=False
            if run_mode!= "sym":
                print("Disconnecting from TWS...")
                ib.disconnect()
            exit(0)
            logger.error("EXIT")


    asyncio.run(main())

