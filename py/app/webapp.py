from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import pandas as pd
import sqlite3
from datetime import datetime
import time
from crypto_job import *
import asyncio
import os

DB_FILE = "../db/crypto.db"

fetcher = CryptoJob(DB_FILE,2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(live_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)


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

@app.get("/api/ohlc")
def ohlc(pair: str, timeframe: str, limit: int = 200):
    df = get_df("""
        SELECT *
        FROM ohlc_history
        WHERE pair=? AND timeframe=?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (pair, timeframe, limit))
    df["datetime"] = df["timestamp"].apply(ts_to_local_str)

    return JSONResponse(df.to_dict(orient="records"))

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
def ohlc_chart(pair: str, timeframe: str, limit: int = 300):
    df = get_df("""
        SELECT timestamp as t, open as o, high as h , low as l, close as c, quote_volume as qv, base_volume as bv
        FROM ohlc_history
        WHERE pair=? AND timeframe=?
        ORDER BY timestamp ASC
        LIMIT ?
    """, (pair, timeframe, limit))

    #df["datetime"] = df["timestamp"].apply(ts_to_local_str)

    return JSONResponse(df.to_dict(orient="records"))


@app.get("/health")
def health():
    return {"status": "ok"}

####################
PAIRS = ["BTC/USDC", "ETH/USDC"]
TIMEFRAME = "1m"

class WSManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, message: dict):
        for ws in self.connections:
            await ws.send_json(message)

ws_manager = WSManager()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

async def live_loop():
    while True:
        #print("tick")
        try:
            msg = {
                "type": "heartbeat",
                "ts": int(time.time() * 1000)
            }
            
            await ws_manager.broadcast(msg)
    
            for pair in PAIRS:
                candles = fetcher.fetch_new_candles(pair, TIMEFRAME)
                if candles:
                    print(f"🕯️ {pair} nuove: {len(candles)}")
                    
                    for candle in candles:
                        print(candle)
                        msg = {
                                "type": "candle",
                                "pair":pair,
                                "timeframe": TIMEFRAME,
                                "data": {
                                    "t":  candle["timestamp"],
                                    "o": candle["open"],
                                    "h":  candle["high"],
                                    "l":  candle["low"],
                                    "c":  candle["close"],
                                    "qv":  candle["quote_volume"],
                                    "bv":  candle["base_volume"]
                                }
                        }
                        await ws_manager.broadcast(msg)
                    # qui puoi:
                    # - aggiornare indicatori
                    # - push via websocket
                    # - salvare su history
        except Exception as e:
            print("❌ errore live loop:", e)

        await asyncio.sleep(1)

