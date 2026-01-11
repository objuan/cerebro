from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request,HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pandas as pd
import sqlite3
from datetime import datetime
import time
import asyncio
import os
import logging
import sys
import json
import shutil

from utils import *
#from job_binance import *
#from job_ibroker import *
#from ib_insync import IB,util
from layout import *
from mulo_client import MuloClient
from trade_manager import TradeManager

#if sys.platform == 'win32':
    #asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from config import DB_FILE,CONFIG_FILE
from props_manager import PropertyManager

DEF_LAYOUT = "./layouts/default_layout.json"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


############# LOGS #############
#print(" STAT FROM ",os.getcwd())

#if not os.getcwd().endswith("APP"):
    #os.chdir("APP")
#print(" STAT FROM ",os.getcwd())

os.makedirs(LOG_DIR, exist_ok=True)

# 🔁 Archivia log precedente all'avvio
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

formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

########################################

try:
    with open("../"+CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

        #print(config)
except FileNotFoundError:
    logger.error("Config File non trovato")
except json.JSONDecodeError as e:
    logger.error("JSON non valido:", e)


config = convert_json(config)

logger.info("=====================================")
logger.info("========   CEREBRO V0.1   ===========")
logger.info("=====================================")
logger.info(f"CONFIG {config}")

logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)


#############

client = MuloClient("../"+DB_FILE,config)
#fetchclienter = CryptoJob(DB_FILE,2,historyActive=False,liveActive=True)

#fetcher = IBrokerJob(None,"../"+DB_FILE,config)

db = DBDataframe(config,client)

propManager = PropertyManager()
tradeManager = TradeManager(propManager)
# FORZA IL LOOP COMPATIBILE PRIMA DI TUTTO
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@asynccontextmanager
async def lifespan(app: FastAPI):
  
    '''
    loop = asyncio.get_running_loop()
    print(f"--- Lifespan loop: {type(loop).__name__} ---")
    ib = IB()
    
    # Forza IB a usare il loop corrente (opzionale ma consigliato se l'errore persiste)
    util.patchAsyncio() # Solo se usi versioni vecchie, di solito non serve più
    '''
    try:
        # 3️⃣ Connetti usando il contesto async
        '''
        print("Connessione a IBKR in corso...")
        if ib.isConnected():
             ib.disconnect()

        await ib.connectAsync(
            host="127.0.0.1",
            port=7497,
            clientId=2,
            timeout=10
        )
        app.state.ib = ib
        print("IBKR Connesso con successo!")
        '''

        #await db.bootstrap()
        job_db=None
        live_task=None

        def on_job_started():
            global job_db
            global live_task

            job_db=  asyncio.create_task(db.bootstrap())
            live_task = asyncio.create_task(live_loop())
          
        job_task = asyncio.create_task(client.bootstrap(on_job_started))
        
       
        #thread_h = asyncio.create_task(hourly_task())

        yield

        logger.info("DONE")
    except:
        logger.error("ERROR", exc_info=True)
    finally:
        # 4️⃣ Chiudi la connessione allo spegnimento
        #print("Chiusura connessione IBKR...")
        #ib.disconnect()
        job_task.cancel()
        job_db.cancel()
        live_task.cancel()
        #thread_h.cancel()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

###################### CORS ######################

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


###################################################################
# API
###################################################################

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
        


        if True:

            df = await client.ohlc_data(symbol,timeframe,limit)
         
            #logger.debug(f"!!!!!!!!!!!! chart {df}")
        
            return JSONResponse(df.to_dict(orient="records"))
        else:
            df1 = db.dataframe(timeframe, symbol)
            #logger.debug(f"{symbol} {timeframe} {df1}")
            df_co = (
                df1[["timestamp","open", "high","low","close","base_volume","quote_volume"]]
                .rename(columns={"timestamp":"t","open": "o", "high":"h","low":"l","close": "c","quote_volume":"qv","base_volume": "bv"})
                .copy()
            )
            logger.debug(df_co.isna().any().any())

            logger.info(df_co)
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
    df =  client.get_fundamentals(symbol).iloc[0]
    return JSONResponse(df.to_dict())

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

    await propManager.set(payload["path"], payload["value"],on_computed_changed)
    #for k,val in payload.items():
    #    propManager.setProp(k,val)
    return JSONResponse("ok")

######################

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

@app.post("/api/trade/marker")
def save_chart_marker(payload: dict):
    #logger.info(f"SAVE TRADE  {payload}")   
    try:
        symbol = payload["symbol"]
        timeframe = payload["timeframe"]
        data = payload["data"]
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Campo mancante: {e.args[0]}"
        )
    client.execute("DELETE FROM trade WHERE symbol=? AND timeframe=?",
            (symbol, timeframe))
    client.execute("""
        INSERT INTO trade (symbol, timeframe,  data)
        VALUES (?, ?, ?)
    """, (
        symbol,
        timeframe,
        json.dumps(data)
    ))

    return {"status": "ok"}

@app.get("/api/trade/marker/read")
def read_chart_lines(symbol: str, timeframe: str):
    df = client.get_df("""
        SELECT  symbol, timeframe,  data
        FROM trade
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

    client.execute("DELETE FROM trade WHERE symbol=? AND timeframe=?",
            (symbol, timeframe))
    return {"status": "ok" }

####################

ws_manager = WSManager()

render_page = RenderPage(ws_manager)
layout = Layout(client,db,config)
layout.read(DEF_LAYOUT)
layout.set_render_page(render_page)   
client.on_candle_receive += layout.notify_candles    

async def _on_ticker_receive(ticker):
    await render_page.send({
                   "type" : "ticker",
                   "data": ticker
               })
      
client.on_ticker_receive += _on_ticker_receive    

#layout.setDefault()

@app.get("/api/layout/select")
async def load_layout():
    all = await layout.load()
    return {"status": "ok", "data": json.dumps(all)}

@app.post("/api/layout/save")
async def save_layout(request: Request):
    dati_json = await request.json()
    #logger.info(f"data {dati_json}")
    layout.from_data(dati_json)
    return {"status": "ok"}

@app.post("/api/layout/cmd")
async def layout_cmd(request: Request):
    dati_json = await request.json()
    logger.info(f"cmd {dati_json}")
    if dati_json["scope"] =="layout":
        await layout.process_cmd(dati_json, render_page)
    return {"status": "ok"}

###################################

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws_manager.connect(ws)

    #logger.info(f"Start WS socket")
    #render_page.connected=False

    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
            # {"action":"subscribe","params":{"symbols":"NVDA,AAPL"}}
            # {"action":"unsubscribe","params":{"symbols":"*"}}

            #await ws.send_text(f"Echo: {message}")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    

async def live_loop():
    ticker_time = 0
    scheduler = AsyncScheduler()
    
    async def one_second_timer():
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
            
            await db.tick()
                
            await layout.tick(render_page)
            
        except:
            logger.error("ERROR", exc_info=True)

    scheduler.schedule_every(1,one_second_timer)

    ########## main ###############

    while True:
        try:
          
            '''
            if fetcher.marketZone:
                msg = {
                    "path": "root.tz",
                    "data": MZ_TABLE[fetcher.marketZone]
                }
                #await ws_manager.broadcast(msg)
            '''
            
            #await db.tick()
            
            #await layout.tick(render_page)

            await scheduler.tick()
           
        except Exception as e:
            logger.error("errore live loop:", exc_info=True)

        await asyncio.sleep(0.5)


