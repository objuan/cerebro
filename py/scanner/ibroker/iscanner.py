import asyncio
import json
import websockets
import sqlite3
from datetime import datetime
import time
import os
import json
import requests
import urllib3
import yfinance as yf
import pandas as pd

# Disabilita warning HTTPS non verificato (tipico di IBKR localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ibind import IbkrWsKey, IbkrWsClient, ibind_logs_initialize
ibind_logs_initialize(log_to_file=False)

DB_FILE = "db/crypto.db"
CONFIG_FILE = "scanner/ibroker/config.json"
DB_TABLE = "ib_ohlc_live"

RETENTION_HOURS = 48      # quante ore tenere
CLEANUP_INTERVAL = 3600  # ogni quanto pulire (1h)

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        #print(config)
except FileNotFoundError:
    print("File non trovato")
except json.JSONDecodeError as e:
    print("JSON non valido:", e)

# ---------- SQLite ----------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
       CREATE TABLE IF NOT EXISTS ib_contracts (
        conidex NUMBER  PRIMARY KEY,
        symbol TEXT ,
        available_chart_periods TEXT,
        company_name TEXT,
        contract_description_1 TEXT,
        listing_exchange TEXT,
        sec_type TEXT,
        updated_at INTEGER,          
        ds_updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

    ############

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
        base_volume REAL,
        quote_volume REAL,
        base_volume_24h REAL,
        quote_volume_24h REAL,
        updated_at INTEGER, -- epoch ms
        ds_updated_at TEXT, -- epoch ms
        PRIMARY KEY(symbol, timeframe, timestamp)
    )""")

    cur.execute("""
    CREATE INDEX IF NOT EXISTS ib_idx_ohlc_ts
        ON ib_ohlc_live(timestamp)
    """)

#################

TIMEFRAMES = {
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "1h": 3600,
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

# stato rolling
last_stats = {}
agg_cache = {}

def floor_ts(ts_ms, sec):
    # ritorna in ms
    return (ts_ms // (sec*1000)) * (sec*1000)


def update_ohlc(pair, price, d_base, d_quote,d_base_24, d_quote_24, ts_ms):
    for tf, sec in TIMEFRAMES.items():
        t = floor_ts(ts_ms, sec)
        key = (pair, tf, t)
        c = agg_cache.get(key)

        if c is None:
            agg_cache[key] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "base_vol": d_base,
                "quote_vol": d_quote,
                "base_vol_24h": d_base_24,
                "quote_vol_24h": d_quote_24
            }
        else:
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["base_vol"] += d_base
            c["quote_vol"] += d_quote
            c["base_vol_24h"] = d_base_24
            c["quote_vol_24h"] = d_quote_24

        save = agg_cache[key]
        cur.execute("""
        INSERT OR REPLACE INTO ohlc_live VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?, ? , ?)
        """, (
            "binance", normalize_symbol(pair), tf, t,
            save["open"], save["high"], save["low"], save["close"],
            save["base_vol"], save["quote_vol"],save["base_vol_24h"], save["quote_vol_24h"],
            int(time.time() * 1000),
            datetime.utcnow().isoformat()
        ))

async def run():
    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        print("🚀 Binance !ticker@arr connected")

        cleanup = asyncio.create_task(cleanup_task())

        while True:
            msg = json.loads(await ws.recv())

            for t in msg:
                pair = t["s"]
              
                if pair.endswith("USDC") or pair.endswith("BTC"):
                    #print(pair)
                    price = float(t["c"])
                    v = float(t["v"])
                    q = float(t["q"])
                    ts = t["E"]
                    
                    prev = last_stats.get(pair)
                    if prev:
                        d_base = max(0.0, v - prev["v"])
                        d_quote = max(0.0, q - prev["q"])
                    else:
                        d_base = d_quote = 0.0

                    last_stats[pair] = {"v": v, "q": q}

                    update_ohlc(pair, price, d_base, d_quote,v,q, ts)

#asyncio.run(run())



def scan(config):
    pass

######################


#### SCAN #######

def scan(config):
    baseUrl = "https://localhost:5000/v1/api"
    request_url = f"{baseUrl}/iserver/scanner/run"

    json_content = config

    # ⚠️ regulatorySnapshot=False come richiesto
    params = {
        "regulatorySnapshot": "false"
    }

    session = requests.Session()

    response = session.post(
        url=request_url,
        json=json_content,
        params=params,
        verify=False   # necessario per localhost IBKR
    )

    # Controllo risposta
    if response.status_code != 200:
        print("Errore:", response.status_code)
        print(response.text)
    else:
        data = response.json()

        print(f'FIND #{len(data["contracts"])}')
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        run_time = int(time.time() * 1000)
        ds_run_time  = datetime.utcnow().isoformat()
                       
        # inserimento dati
        for c in data["contracts"] :
            print(c)

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
                c["symbol"],
                c["con_id"], #conidex
                c["available_chart_periods"],
                c["company_name"],
                c["contract_description_1"],
                c["listing_exchange"],
                c["sec_type"],
                run_time,
                ds_run_time
            ))
                
            conn.commit()

        conn.close()

        # Scrive risultato su file
        with open("scanner_result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        #print("Scanner result salvato in scanner_result.json")
      
if __name__ =="__main__":

    init_db()

    scan(config["ibroker"])

