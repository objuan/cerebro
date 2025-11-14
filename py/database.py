import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone
import zoneinfo  # disponibile da Python 3.9 in poi
import threading, time
import signal
import sys

LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Rome")
yf.set_tz_cache_location("cache")

DB_PATH = "quotes.db"

# Connessione (crea file se non esiste)
#conn = sqlite3.connect("quotes.db")
def get_connection():
    # Ogni thread crea la propria connessione
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_connection()
cur = conn.cursor()

###################################


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


def get_tickers(conn, watchlistName):
    conn = get_connection()
    query = f"""
    SELECT ticker from watchlist where name = '{watchlistName}' and enabled=1
    """
    cur = conn.cursor()
    cur.execute(query)
    for row in  cur.fetchall():    
        #print(row[0])
        return [ r.replace("\"","") for r in row[0].split(",") ]
    return []

def select(query, noPandaMode=False):
    #print(query)
    conn = get_connection()
    df =  pd.read_sql(query,conn)
    conn.close()
    if len(df) == 1:
        arr = df.to_numpy()[0]
        return arr
    else:
        if noPandaMode:
            return df.to_dict(orient="records")
        else:
            return df
        
def execute(query):
    #print(query)
    conn    = get_connection()
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()
    conn.close()
   