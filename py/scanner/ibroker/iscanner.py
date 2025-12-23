import asyncio
import json
import websockets
import sqlite3
from datetime import datetime
import time
import os
import signal
import json
import requests
import urllib3
import yfinance as yf
import pandas as pd
from utils import *
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Disabilita warning HTTPS non verificato (tipico di IBKR localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ibind import IbkrWsKey, IbkrWsClient, QueueAccessor, ibind_logs_initialize
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


def update_ohlc(conindex,symbol, price, d_base, d_quote,d_base_24, d_quote_24, ts_ms):
    for tf, sec in TIMEFRAMES.items():
        t = floor_ts(ts_ms, sec)
        key = (conindex, tf, t)
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
        INSERT OR REPLACE INTO ib_ohlc_live VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?, ? , ?)
        """, (
            conindex, symbol, tf, t,
            save["open"], save["high"], save["low"], save["close"],
            save["base_vol"], save["quote_vol"],save["base_vol_24h"], save["quote_vol_24h"],
            int(time.time() * 1000),
            datetime.utcnow().isoformat()
        ))


#####################################################


#### SCAN #######

def scan(config):
    baseUrl = "https://localhost:5000/v1/api"
    request_url = f"{baseUrl}/iserver/scanner/run"

    logger.info("SCANNER .... ")
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
        logger.debug(f"Errore:{response.status_code}")
        logger.debug(response.text)
    else:
        data = response.json()

        logger.debug(f'FIND #{len(data["contracts"])}')
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        run_time = int(time.time() * 1000)
        ds_run_time  = datetime.utcnow().isoformat()
                       
        # inserimento dati
        for c in data["contracts"] :
            logger.debug(c)

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

        logger.info("SCANNER DONE ")
        #print("Scanner result salvato in scanner_result.json")                   

#asyncio.run(run())

############################################################

account_id = os.getenv('IBIND_ACCOUNT_ID', 'DUN863926')
cacert = os.getenv('IBIND_CACERT', False)  # insert your cacert path here
ws_client = IbkrWsClient(cacert=cacert, account_id=account_id)
ws_client.start()

    
actual_df=None
conidex_to_symbol=None
actual_requests = []

def clean_up():
    global actual_requests
    logger.debug(f"clean_up {actual_requests}")
    for request in actual_requests:
        ws_client.unsubscribe(**request)
    actual_requests.clear()

def stop(_, _1):
    logger.debug(f"EXIT")
    clean_up()
    ws_client.shutdown()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

queue_accessors = [
    ws_client.new_queue_accessor(IbkrWsKey.MARKET_DATA),
]

class LiveTicker:
    symbol : str
    conid : int
    volume : int
    last_price : float
    last_close : float
    #The difference between the last price and the close on the previous trading day in percentage.
    gap_percent : float
    is_halted: bool
    updated : int
    is_live: bool
    def __init__(self):
        self.last_close=None
        self.last_price=None
        self.volume=None
        self.gap_percent=None

    def __str__(self):
        return f"{self.conid} {self.symbol} l:{self.last_price} c:{self.last_close} v:{self.volume}"


def start_watch(receiveHandler):
     while ws_client.running:
            try:
                for qa in queue_accessors:
                    while not qa.empty():
                        #print("-->",qa)
                        p = parse_market_data(qa.get())
                        receiveHandler(p)
                time.sleep(1)
            except KeyboardInterrupt:
                print('KeyboardInterrupt')
                break

def parse_market_data(_msg: dict):
        if _msg == None:
            return
        data = {}
        logger.debug(f"--> {_msg}")
        msg = _msg[list(_msg.keys())[0]]
        #print("-->",msg)

        tiker = LiveTicker()
        tiker.conid = msg.get("conid")
        #data["symbol"] = msg["symbol"] if "symbol" in msg else None
        #data["bid_price"] = float(msg["bid_price"]) if "bid_price" in msg else None
        #data["bid_size"] = int(msg["bid_size"]) if "bid_size" in msg else None
        tiker.volume = int(msg["volume_long"]) if "volume_long" in msg else None
        tiker.gap_percent = int(msg["change_percent"]) if "change_percent" in msg else None
        
        tiker.updated = msg.get("_updated")
        tiker.last_price = msg.get("last_price") if "last_price" in msg else None
        if tiker.last_price and tiker.last_price.startswith("C"):
            tiker.last_close=tiker.last_price[1:]
            tiker.last_price=None
        if tiker.last_price and tiker.last_price.startswith("H"):
            tiker.is_halted=True
            tiker.last_price=None
            

        marker = msg.get("market_data_marker")
        tiker.is_live= marker is None or marker not in ("q9",)
        tiker.symbol = conidex_to_symbol[tiker.conid ]
        #print(tiker)
        return tiker

#############

def manage_live( conid_list_add, conid_list_remove):
    global actual_requests
    logger.debug(f"manage_live {conid_list_add,conid_list_remove}")
    #https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#market-data-fields
    #31, last price, 73 Market Value , 84 Bid Price, 86 Ask Price, 87 Volume (7762)
    # 82 GAP 83 GAP %
    requests = []
    for conid in conid_list_add:
        requests.append( {'channel': f'md+{conid}', 'data': {'fields': ['31', '7762','83']}},)

    for request in requests:
        logger.debug(f"Subscribe {request}")
        actual_requests.append(request)
        while not ws_client.subscribe(**request):
            time.sleep(1)
            

    requests = []
    for conid in conid_list_remove:
        requests.append( {'channel': f'md+{conid}', 'data': {'fields': ['31', '7762']}},)

    for request in requests:
        logger.debug(f"Unsubscribe {request}")
        for i, d in enumerate(actual_requests):
            if d["channel"] ==  request["channel"]:
                del actual_requests[i]
                break
    
        while not ws_client.unsubscribe(**request):
           time.sleep(1)
  
    logger.debug(f"actual_requests {actual_requests}")
############################################################

def updateLive(config,range_min=None,range_max=None):
    global actual_df
    global conidex_to_symbol
    # get last lives
    
    
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("select max(updated_at) as max from ib_contracts", conn)
    max_date = df.iloc[0]["max"]
    #print("max_date",max_date)
    last_df = pd.read_sql_query(f"select conidex,symbol from ib_contracts where updated_at={max_date}", conn)
    #print("df",last_df)
    conn.close()

    if range_min!=None:
        last_df = last_df.iloc[range_min:range_max]
    
    if not conidex_to_symbol :
        actual_df = last_df
        #manage_live(last_df,[])
        conidex_to_symbol = actual_df.set_index("conidex")["symbol"].to_dict()
        conidex_list = actual_df["conidex"].tolist()
        manage_live(conidex_list,[])
    else:

        delta_removed = actual_df[~actual_df["conidex"].isin(last_df["conidex"])]
        delta_new = last_df[~last_df["conidex"].isin(actual_df["conidex"])]

        actual_df = last_df
        conidex_to_symbol = actual_df.set_index("conidex")["symbol"].to_dict()
        conidex_list = actual_df["conidex"].tolist()

        manage_live(delta_new["conidex"].tolist(),delta_removed["conidex"].tolist())

#############################

if __name__ =="__main__":

   
    #############
    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
            "logs/ibroker.log",
            maxBytes=5_000_000,
            backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    #############

    logger.info("=================================================")
    logger.info("               IBROKER SCANNER V1.0")
    logger.info("=================================================")

    try:
        
        #sched = CronScheduler()
        #def job1():
        #    print("Ogni minuto")
        #sched.add("* * * * *", job1)

        #sched.run()

        
        #scan(config["ibroker"]["scanner"])

        def receive(ticker: LiveTicker):
            print(ticker)
            #if ticker.last_price:
                #update_ohlc(pair, price, d_base, d_quote,v,q, ts)

        #updateLive(config, 0,1)

        #updateLive(config,1,3)
        conidex_to_symbol={}
        conidex_to_symbol[76792991] ="AA"
        manage_live([76792991],[])
        
        start_watch(receive)

    except:
        logger.error("ERROR", exc_info=True)
    clean_up()


