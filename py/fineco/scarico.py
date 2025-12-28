import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from database import *
import sys, traceback
import logging
import requests
logger = logging.getLogger(__name__)

#yf.enable_debug_mode()
yf.set_tz_cache_location("cache")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def get_yahoo_session():
    s = requests.Session()
    r = s.get("https://finance.yahoo.com", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return s

def get_floating_shares(symbol):
    session = get_yahoo_session()

    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {
        "modules": "defaultKeyStatistics"
    }

    r = session.get(url, headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()

    stats = r.json()["quoteSummary"]["result"][0]["defaultKeyStatistics"]

    return {
        "floatShares": stats["floatShares"]["raw"],
        "sharesOutstanding": stats["sharesOutstanding"]["raw"]
    }


def cerca_ticker(query):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    data = r.json()

    risultati = []
    for item in data.get("quotes", []):
        risultati.append({
             "exchange" : item.get("exchange"),
            "symbol": item.get("symbol"),
            "shortname": item.get("shortname"),
            "longname": item.get("longname"),
            "exchDisp": item.get("exchDisp")
        })
    return risultati

def scarico_history(ticker , period,interval, isHistory):

    
        logger.info("=================================")
        logger.info(f"⬇️  Downloading {ticker} ({interval} / {period})")

        try:
                data = yf.download(ticker, period=period, interval=interval, progress=False,auto_adjust=True)
                
                if data.empty:
                    logger.warn(f"⚠️  Nessun dato per {ticker}")
                    return
              
                data.reset_index(inplace=True)
                #print(data.columns)
                #print(data)
               
                # data["timestamp"] = data["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
                if 'Date' in data.columns:
                    data["timestamp"] = data["Date"].dt.tz_localize(tz='Europe/Rome').dt.strftime("%Y-%m-%d %H:%M:%S")
                elif 'Datetime' in data.columns:
                    data["timestamp"] = data["Datetime"].dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d %H:%M:%S")
                #records = data.assign(id=ticker)[["id", "timestamp", "Open", "High", "Low", "Close", "Volume"]].values.tolist()
                #print(data)

                #print(data)
                # Normalizza colonne e salva
                records = []
                for ts,row in data.iterrows():
                    #print(row)
                    #timestamp = datetime.fromtimestamp(ts.timestamp()).isoformat(sep=' ')
                    records.append((
                        ticker,
                        row['timestamp'].iloc[0],
                        float(row['Open'].iloc[0] if hasattr(row['Open'], "iloc") else row['Open']),
                        float(row['High'].iloc[0] if hasattr(row['High'], "iloc") else row['High']),
                        float(row['Low'].iloc[0] if hasattr(row['Low'], "iloc") else row['Low']),
                        float(row['Close'].iloc[0] if hasattr(row['Close'], "iloc") else row['Close']),
                        float(row['Volume'].iloc[0] if hasattr(row['Volume'], "iloc") else row['Volume']),
                    ))
                
                
                conn = get_connection()
                cur = conn.cursor()    
                #OR IGNORE 
                post=""
                if (isHistory):
                     post="_history"
                cur.executemany(f"""
                    INSERT OR IGNORE  INTO candles_{interval}{post} (id, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)

                #print(records)

                conn.commit()
                rows = cur.rowcount

                conn.close()

                logger.info(f"✅ Salvate {rows} righe per {ticker}")

        except Exception as e:
                logger.error(e, exc_info=True)
                
if __name__ == "__main__":
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
        
    get_floating_shares("NVDA")
    exit()
    
    #search 
    for r in cerca_ticker("apple"):
        print(r)
    exit()

    #tickers = get_tickers(conn,"prima")
    #tickers = select("SELECT id from ticker where fineco=1")["id"].to_list()
    tickers = select("SELECT distinct id from live_quotes ")["id"].to_list()
    #tickers = ["ENI.MI"]
    #tickers = ["AAPL"]
    

    print("tickers",tickers)

    #intervals = ["1d","1h","5m","1m"]
    intervals = ["5m"]
    #1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
    #periods= ["1y","2mo","1mo","5d"]
    periods= ["60d"]
        
    for idx, interval in enumerate(intervals):
        period = periods[idx]

        for ticker in tickers:
            scarico_history(ticker,period,interval,True)