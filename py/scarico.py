import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from database import *
import sys, traceback

#yf.enable_debug_mode()
yf.set_tz_cache_location("cache")


#tickers = get_tickers(conn,"prima")
tickers = select("SELECT id from ticker where fineco=1")["id"].to_list()
#tickers = ["ENI.MI"]

print("tickers",tickers)

intervals = ["1d","1h","5m","1m"]
#1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
periods= ["1y","2mo","1mo","5d"]

for idx, interval in enumerate(intervals):
    period = periods[idx]

    for ticker in tickers:
        print("=================================")
        print(f"⬇️  Downloading {ticker} ({interval} / {period})")

        try:
                data = yf.download(ticker, period=period, interval=interval, progress=False,auto_adjust=True)
                
                if data.empty:
                    print(f"⚠️  Nessun dato per {ticker}")
                    continue
              
                data.reset_index(inplace=True)
                #print(data.columns)
                #print(data)
               
                # data["timestamp"] = data["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
                if 'Date' in data.columns:
                    data["timestamp"] = data["Date"].dt.tz_localize(tz='Europe/Rome').dt.strftime("%Y-%m-%d %H:%M:%S")
                elif 'Datetime' in data.columns:
                    data["timestamp"] = data["Datetime"].dt.tz_convert(LOCAL_TZ).dt.strftime("%Y-%m-%d %H:%M:%S")
                #records = data.assign(id=ticker)[["id", "timestamp", "Open", "High", "Low", "Close", "Volume"]].values.tolist()
                print(data)

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
                cur.executemany(f"""
                    INSERT OR IGNORE  INTO candles_{interval}_history (id, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)

                #print(records)

                conn.commit()
                conn.close()

                print(f"✅ Salvate {len(records)} righe per {ticker}")

        except Exception as e:
                print(f"❌ Errore con {ticker}: {e}")
                traceback.print_exc(file=sys.stdout)

