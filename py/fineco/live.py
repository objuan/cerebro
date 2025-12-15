import yfinance as yf
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone,timedelta
import zoneinfo  # disponibile da Python 3.9 in poi
import threading, time
import signal
import sys
from database import *

#yf.enable_debug_mode()

########################

def save_message(msg: dict):
    """Salva un messaggio proveniente dal WebSocket nel DB"""

    print("Receive " , msg)
    if "price" in msg:
        # ✅ Converti il campo "time" da millisecondi UNIX → formato leggibile
        try:
            ts = int(msg["time"]) / 1000
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            dt_local = dt_utc.astimezone(LOCAL_TZ)

            readable_utc = dt_utc.strftime("%Y-%m-%d %H:%M:%S")
            readable_local = dt_local.strftime("%Y-%m-%d %H:%M:%S")

            #readable_time = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            readable_utc = readable_local = None
    # 🔹 Inserisci nel DB
        cur.execute("""
            INSERT INTO quotes (
                id, price, time_utc, time_local, exchange, quote_type, market_hours,
                change_percent, day_volume, change, last_size, price_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            msg.get("id"),
            msg.get("price"),
            readable_utc,
            readable_local,
            msg.get("exchange"),
            msg.get("quote_type"),
            msg.get("market_hours"),
            msg.get("change_percent"),
            int(msg.get("day_volume", 0)),
            msg.get("change"),
            int(msg.get("last_size", 0)),
            int(msg.get("price_hint", 0))
        ))


        conn.commit()


def aggregate(period):
    """Aggrega solo i nuovi tick in candele 5 minuti e aggiorna la tabella meta"""
    conn = get_connection()
    last_agg = get_last_aggregated(conn,period)

    # Leggi tick recenti (ultimi 3 giorni)
    df = pd.read_sql_query("""
        SELECT id, price, time_utc, day_volume FROM quotes
        WHERE time_utc >= datetime('now', '-3 day')
    """, conn, parse_dates=["time_utc"])

    if df.empty:
        print("⏳ Nessun tick disponibile.")
        conn.close()
        return

    df = df.set_index("time_utc")
    candles_all = []
    updated_meta = {}

    for symbol, g in df.groupby("id"):
        last_ts = last_agg.get(symbol)
        if last_ts:
            cutoff = pd.to_datetime(last_ts)
            g = g[g.index > cutoff]

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
        print("⚙️ Nessuna nuova candela trovata.")
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
    print(f"✅ Salvate {len(candles)} nuove candele. Stato aggiornato per {len(updated_meta)} simboli.")


#yf.enable_debug_mode()
#################################

def get_candles(conn, minutes: int):
    query = f"""
    SELECT
        id,
        datetime(CAST(strftime('%s', timestamp) / ({minutes} * 60) AS INT) * ({minutes} * 60), 'unixepoch') AS period_start,
        MIN(low) AS low,
        MAX(high) AS high,
        (SELECT open FROM candles_5m c2
         WHERE c2.id=c.id AND c2.timestamp = MIN(c.timestamp)) AS open,
        (SELECT close FROM candles_5m c3
         WHERE c3.id=c.id AND c3.timestamp = MAX(c.timestamp)) AS close,
        SUM(volume) AS volume
    FROM candles_5m c
    GROUP BY id, period_start
    ORDER BY id, period_start;
    """
    return pd.read_sql_query(query, conn)


#################################


cur.execute("DELETE FROM QUOTES")
conn.commit()

running=True
def signal_handler(sig, frame):
    global running
    print("\n🛑 CTRL+C rilevato — arresto in corso...")
    running = False

def periodic_candle_builder_5():
    while running:
        try:
            print("📊 Aggiorno le candele 5m...")
            aggregate("5m")
            time.sleep(300)  # ogni 5 minuti
        except Exception as e:
            print("⚠️ Errore in periodic_candle_builder 5:", e)
            time.sleep(5)
    print("✅ Thread terminato correttamente.")

def periodic_candle_builder_1():
    while running:
        try:
            print("📊 Aggiorno le candele 1m...")
            aggregate("1m")
            time.sleep(60)  # ogni 5 minuti
        except Exception as e:
            print("⚠️ Errore in periodic_candle_builder 1:", e)
            time.sleep(5)
    print("✅ Thread terminato correttamente.")

def periodic_candle_builder_30():
    while running:
        try:
            print("📊 Pulisco le candele ")
            conn = get_connection()
            cur = conn.cursor()

            dt = datetime.now()
            dt = dt -  timedelta(minutes=60)
            tt = dt.strftime('%Y-%m-%d %H:%M:%S')
            print(f"CLEAR AT {tt}")
            cur.execute(f"DELETE FROM quotes WHERE time_local < '{tt}'")
            conn.close()
            time.sleep(60 * 30)  
        except Exception as e:
            print("⚠️ Errore in periodic_candle_builder 30:", e)
            time.sleep(5)
    print("✅ Thread terminato correttamente.")

# Imposta il gestore del segnale CTRL+C
signal.signal(signal.SIGINT, signal_handler)

tickers = get_tickers(conn,"prima")
tickers = ["ENI.MI","ENEL.MI","ACE.MI"]
print("tickers",tickers)
#exit(0)

# define your message callback
def message_handler(message):
   save_message(message)

threading.Thread(target=periodic_candle_builder_5, daemon=True).start()
threading.Thread(target=periodic_candle_builder_1, daemon=True).start()
threading.Thread(target=periodic_candle_builder_30, daemon=True).start()

# =======================
# With Context Manager
# =======================

with yf.WebSocket() as ws:
    ws.subscribe(tickers)
    ws.listen(message_handler)

print("END")



