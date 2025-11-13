
import time
import json
import csv
from typing import List, Dict, Any, Optional
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import warnings
import schedule

import logging
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- LOGGER CONFIG ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = "quotes.db"
UPDATE_TIME = 10 # secs

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_connection()
cur = conn.cursor()

div_name ='//*[@id="main-app"]/div[2]/div/div/div[5]'
table_xpath = '//*[@id="main-app"]/div[2]/div/div/div[5]/div/div/div[2]/div/div[1]/div/div/table'
html=""
driver=None
last_tick_time = None
last_tick_time_1m = None
last_tick_time_5m = None

def init(drv):
    global html
    global driver
    global last_tick_time
    global last_tick_time_1m
    global last_tick_time_5m

    driver=drv
    html = driver.page_source
    last_tick_time = datetime.now()
    last_tick_time_1m= datetime.now()
    last_tick_time_5m= datetime.now()
    update_data()
    aggregate("1m")
    #aggregate("5m")

def tick():
    global last_tick_time
    global last_tick_time_1m
    global last_tick_time_5m
    delay =  (datetime.now()-last_tick_time).total_seconds()
    #print(datetime.now().second )
    if (delay > UPDATE_TIME):
       last_tick_time = datetime.now()
       update_data()

        # check for 1 min to 5 min 
    if (datetime.now().second < 5 and (datetime.now()-last_tick_time_1m).total_seconds() > 30 ):
        aggregate("1m")
        last_tick_time_1m = datetime.now()
        
    #if (datetime.now().minute in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55] and datetime.now().second > 5  and (datetime.now()-last_tick_time_5m).total_seconds() > 60*4 ):
    #    aggregate("5m")
    #    last_tick_time_5m = datetime.now()

    

def update_data():
    #print(html)
    try:
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            logger.info("UPDATE")

            #els = driver.find_elements(By.XPATH, table_xpath)
            tables = soup.find_all("table")
            results = []

            for table in tables:
                    
                    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                    rows = table.find_all("tr")
                    for r in rows:
                        cols = [td.get_text(strip=True) for td in r.find_all("td")]
                        if not cols:
                            continue
                        # proviamo a mappare prima due colonne a symbol/nome
                        entry = {}
                        if len(cols) >= 1:
                            entry["col0"] = cols[0]
                        if len(cols) >= 2:
                            entry["col1"] = cols[1]
                        # se troviamo intestazioni sensate usale
                        if headers:
                            for i,h in enumerate(headers):
                                entry[h] = cols[i] if i < len(cols) else ""
                        results.append(entry)

                        #print(entry)
                        #break
            #print(results)

       
            for row in results:
                 if "descrizione" in row and "prezzo" in row:
                     
                      save(row,".MI")


    except Exception as ex:
        logger.error(ex )

def save(row,postfix):
    try:
        desc = row["descrizione"].replace("EQ","").strip()
        prezzo = float(row["prezzo"].strip().replace(".","").replace(",","."))
        volume = row["volume"].strip().replace(".","")
        if (volume.endswith("M")): volume = volume[:-1]+"000"
        time = row["data/ora"].strip()
        if (time!=""):
            varPerc = row["var %"].strip()
            symbol = row["simbolo"].strip()+postfix
            #print(desc,symbol,prezzo,volume,time)
            readable_utc=  datetime.now().strftime("%Y-%m-%d")+" " +time
            readable_local = readable_utc
            cur.execute("""
                INSERT OR IGNORE  INTO quotes (
                    id, price, time_utc, time_local, exchange, quote_type, market_hours,
                    change_percent, day_volume, change, last_size, price_hint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                prezzo,
                readable_utc,
                readable_local,
                "MIL",
                "",
                "0",
                varPerc,
                int(volume),
                "",
            "",
                "")
            )
            conn.commit()

    except Exception as ex:
        logger.error(ex ) 


def aggregate(period):

    logger.info(f"aggregate {period} ")
    """Aggrega solo i nuovi tick in candele 5 minuti e aggiorna la tabella meta"""
    conn = get_connection()
    last_agg = get_last_aggregated(conn,period)

    # Leggi tick recenti (ultimi 3 giorni)
    df = pd.read_sql_query("""
        SELECT id, price, time_utc, day_volume FROM quotes
        WHERE time_utc >= datetime('now', '-1 day')
    """, conn, parse_dates=["time_utc"])

    if df.empty:
        logger.info("⏳ Nessun tick disponibile.")
        conn.close()
        return

    df = df.set_index("time_utc")
    candles_all = []
    updated_meta = {}

    now = datetime.now()
    
    if (period =="1m"):
        last_ts = now.replace(minute=now.minute - 2, second=59, microsecond=0)
    if (period =="5m"):
        minute_floor = (now.minute // 5) * 5 -5
        print(minute_floor)
        last_ts = now.replace(minute= minute_floor - 1, second=59, microsecond=0)
        #last_ts = datetime.now() - timedelta(minutes=10)

    for symbol, g in df.groupby("id"):
        print(f"==> {period} symbol {symbol} last_ts: {last_ts}")
        #last_ts = last_agg.get(symbol)

        if last_ts:
            cutoff = pd.to_datetime(last_ts)
            g = g[g.index > cutoff]

        print(g)
        if g.empty:
            continue

        p ="5T"
        if period == "1m":
            p ="1T"
        c = g.resample(p).agg({
            "price": ["first", "max", "min", "last"],
            "day_volume": "sum"
        }).dropna()

        c.columns = ["open", "high", "low", "close", "volume"]
        c["id"] = symbol
        c["timestamp"] = c.index

        candles_all.append(c)
        updated_meta[symbol] = c.index[-1].strftime("%Y-%m-%d %H:%M:%S")

    if not candles_all:
        logger.info("⚙️ Nessuna nuova candela trovata.")
        conn.close()
        return

    candles = pd.concat(candles_all)
    candles.reset_index(drop=True, inplace=True)


    # 🔹 Inserisci solo nuove righe
    cur = conn.cursor()
    cur.executemany(f"""
        INSERT OR IGNORE INTO candles_{period}
        (id, timestamp, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (row.id, row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
         row.open, row.high, row.low, row.close, int(row.volume))
        for row in candles.itertuples()
    ])
    conn.commit()

    # 🔹 Aggiorna meta
    update_last_aggregated(conn, period,updated_meta)

    conn.close()
    logger.info(f"✅ Salvate {len(candles)} nuove candele. Stato aggiornato per {len(updated_meta)} simboli.")

def get_last_aggregated(conn,period):
    """Restituisce un dizionario {id: last_timestamp}"""
    cur = conn.cursor()
    cur.execute(f"SELECT id, last_aggregated_{period} FROM meta")
    rows = cur.fetchall()
    return {r[0]: r[1] for r in rows if r[1]}

def update_last_aggregated(conn, period, updates: dict):
    """Aggiorna la tabella meta per ciascun simbolo"""
    cur = conn.cursor()
    for symbol, ts in updates.items():
        cur.execute(f"""
            INSERT INTO meta (id, last_aggregated_{period})
            VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET last_aggregated_{period}=excluded.last_aggregated_{period}
        """, (symbol, ts))
    conn.commit()

print("START")

