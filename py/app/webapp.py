from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
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
from job_ibroker import *
#from ib_insync import IB,util
from layout import *

#if sys.platform == 'win32':
    #asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CONFIG_FILE = "../config/cerebro.json"
DB_FILE = "../db/crypto.db"
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

formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

########################################

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

        #print(config)
except FileNotFoundError:
    print("File non trovato")
except json.JSONDecodeError as e:
    print("JSON non valido:", e)


config = convert_json(config)

logger.info("=====================================")
logger.info("========   CEREBRO V0.1   ===========")
logger.info("=====================================")
logger.info(f"CONFIG {config}")

#############

#fetcher = CryptoJob(DB_FILE,2,historyActive=False,liveActive=True)

fetcher = IBrokerJob(None,DB_FILE,config)

db = DBDataframe(config,fetcher)

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
        asyncio.create_task(db.bootstrap())

        live_task = asyncio.create_task(live_loop())
        #thread_h = asyncio.create_task(hourly_task())

        yield

        print("DONE")
    except:
        logger.error("ERROR", exc_info=True)
    finally:
        # 4️⃣ Chiudi la connessione allo spegnimento
        #print("Chiusura connessione IBKR...")
        #ib.disconnect()
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

######################

'''
def fetch_all_new(fetcher, symbols, timeframe):
    all_new = []

    for symbol in symbols:
            candles = fetcher.fetch_new_candles(symbol, timeframe)
            if candles:
                all_new.extend(candles)

    return all_new

 '''
def get_df(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

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
        '''
        df = get_df("""
            SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
            FROM ib_ohlc_history
            WHERE symbol=? AND timeframe=?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (symbol, timeframe, limit))
        '''
       
        
    
        
        if False:
            df = await fetcher.ohlc_data(symbol,timeframe,limit)
         
            #logger.debug(f"!!!!!!!!!!!! chart {df}")
        
            return JSONResponse(df.to_dict(orient="records"))
        else:
            df1 = db.dataframe(timeframe, symbol)
            df_co = (
                df1[["timestamp","open", "high","low","close","base_volume","quote_volume"]]
                .rename(columns={"timestamp":"t","open": "o", "high":"h","low":"l","close": "c","quote_volume":"qv","base_volume": "bv"})
                .copy()
            )
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
    symbols = fetcher.live_symbols()
    print(symbols)
    return JSONResponse({"symbols":symbols})

##############################

    
@app.get("/api/price")
def get_price(symbol: str):
  
    print("get_price", symbol)

    return JSONResponse({"symbol":symbol,  "price":fetcher.last_price(symbol)})


@app.get("/api/quote")
async def get_quote(symbol: str):
  
    last_price = fetcher.last_price(symbol)
    last_close = fetcher.last_close(symbol)
    print(last_price,last_close)
    if last_close!=0:
        perc = ((last_price- last_close) / last_close) * 100
        return JSONResponse({"symbol":symbol,  "change":(last_close-last_price),"percent_change":perc})
    else:
        return JSONResponse({"symbol":symbol,  "change":0,"percent_change":0})

DECODE_INTERVAL = {
    "1day" :"1d",
    "1min" :"1m"
}
@app.get("/api/time_series")
async def get_timeseries(symbol: str,interval: str,outputsize: str):
    
    #logger.info(f"get_timeseries {symbol} {interval} {outputsize}")

    #return JSONResponse({"symbol":symbol,"values":[0,0,0,0,0]}) 
    timeframe = DECODE_INTERVAL[interval]
    limit = outputsize
    df = await fetcher.ohlc_data(symbol,timeframe,limit)
    if len(df)>0:
        #logger.info(df)
        return JSONResponse({"symbol":symbol,"values":df["c"].tolist()})    
    else:
        
        return JSONResponse({"symbol":symbol,"values":[0,0,0,0,0]})

####################


ws_manager = WSManager()

render_page = RenderPage(ws_manager)
layout = Layout(fetcher,db)
layout.read(DEF_LAYOUT)

#layout.setDefault()

@app.get("/api/layout/select")
async def load_layout():
    await layout.load(render_page)
    return {"status": "ok"}

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
    try:
        while True:
            message = await ws.receive_text()
            logger.info(f"Messaggio ricevuto: {message}")
            # {"action":"subscribe","params":{"symbols":"NVDA,AAPL"}}
            # {"action":"unsubscribe","params":{"symbols":"*"}}

            #await ws.send_text(f"Echo: {message}")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


'''
async def hourly_task():
    while True:
        await asyncio.sleep(60 * 60)  # 1 ora
        try:
            #print("Task eseguito")
            fetcher.update_stats()
        except Exception as e:
            logger.error("❌ errore hourly_task:", exc_info=True)
        
'''     

async def live_loop():
    while True:
        #print("tick")
        try:
            msg = {
                "type": "heartbeat",
                "ts": int(time.time() * 1000)
            }
            
            
            await ws_manager.broadcast(msg)

            '''
            msg1 = {
                "type": "price_update",
                "symbol": "NVDA",
                "price" : 222
            }

            await ws_manager.broadcast(msg1)
            '''

            
            new_candles = await fetcher.fetch_live_candles()

            #logger.info(f"NEW # {len(new_candles)}")

            if len(new_candles) < 500:
                await layout.notify_candles(new_candles,render_page)

            await db.tick()
            
            await layout.tick(render_page)
           
        except Exception as e:
            logger.error("errore live loop:", exc_info=True)

        await asyncio.sleep(0.5)


