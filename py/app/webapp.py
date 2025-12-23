from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import pandas as pd
import sqlite3
from datetime import datetime
import time
import asyncio
import os
import logging

############# LOGS #############

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Rotazione: max 5 MB, tieni 5 backup
file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=5_000_000,
        backupCount=5
)
file_handler.setLevel(logging.DEBUG)

# Console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

#############

from job_binance import *
from layout import *

DB_FILE = "../db/crypto.db"
DEF_LAYOUT = "./layouts/default_layout.json"

fetcher = CryptoJob(DB_FILE,10,historyActive=False,liveActive=True)
db = DBDataframe(fetcher)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(live_loop())
    task1 = asyncio.create_task(hourly_task())
    yield
    task.cancel()
    task1.cancel()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

def fetch_all_new(fetcher, pairs, timeframe):
    all_new = []

    for pair in pairs:
            candles = fetcher.fetch_new_candles(pair, timeframe)
            if candles:
                all_new.extend(candles)

    return all_new

def ts_to_local_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

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

@app.get("/api/top_volume")
def top_volume(timeframe: str = "5m", limit: int = 20):
    df = get_df("""
        SELECT pair, SUM(quote_volume) AS volume
        FROM ohlc_history
        WHERE timeframe=?
        GROUP BY pair
        ORDER BY volume DESC
        LIMIT ?
    """, (timeframe, limit))
    df["datetime"] = df["timestamp"].apply(ts_to_local_str)

    return JSONResponse(df.to_dict(orient="records"))


@app.get("/api/ohlc_chart")
def ohlc_chart(pair: str, timeframe: str, limit: int = 1000):
    '''
    df = get_df("""
        SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
        FROM ohlc_history
        WHERE pair=? AND timeframe=?
        ORDER BY timestamp ASC
        LIMIT ?
    """, (pair, timeframe, limit))
    '''
    #df = fetcher.ohlc_data(pair,timeframe,limit)
    
    df1 = db.dataframe(timeframe, pair)
    df_co = (
            df1[["timestamp","open", "high","low","close","base_volume","quote_volume"]]
            .rename(columns={"timestamp":"t","open": "o", "high":"h","low":"l","close": "c","quote_volume":"qv","base_volume": "bv"})
            .copy()
    )
    
    #print("chart",df_co)
    
    return JSONResponse(df_co.to_dict(orient="records"))

@app.get("/api/report")
def ohlc_chart(name: str):
    #layout.components.
    #return JSONResponse(df_co.to_dict(orient="records"))
    pass

@app.get("/api/symbols")
def get_symbols(limit: int = 1000):
    pairs = fetcher.live_symbols()
    print(pairs)
    return JSONResponse({"pairs":pairs})

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
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


async def hourly_task():
    while True:
        await asyncio.sleep(60 * 60)  # 1 ora
        try:
            #print("Task eseguito")
            fetcher.update_stats()
        except Exception as e:
            logger.error("❌ errore hourly_task:", exc_info=True)
        
     

async def live_loop():
    while True:
        #print("tick")
        try:
            msg = {
                "type": "heartbeat",
                "ts": int(time.time() * 1000)
            }
            
           

            await ws_manager.broadcast(msg)

            
            new_candles = await fetcher.fetch_live_candles()

            #logger.info(f"NEW # {len(new_candles)}")

            if len(new_candles) < 500:
                await layout.notify_candles(new_candles,render_page)

            db.tick()
            
            await layout.tick(render_page)
           
        except Exception as e:
            logger.error("errore live loop:", exc_info=True)

        await asyncio.sleep(1)

