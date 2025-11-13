import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from database import *
import sys, traceback
from zoneinfo import ZoneInfo
from datetime import datetime,time,timedelta
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

def get_ticker( ticker):
    return select(f"SELECT * FROM candles_5m_history where id='{ticker}' ")

def get_history_data( ticker, interval, dt_from,dt_to=None):
    dt_from =  dt_from.strftime('%Y-%m-%d %H:%M:%S')
    if dt_to:
        dt_to =  dt_to.strftime('%Y-%m-%d %H:%M:%S')
    else:
        dt_to = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return select(f"SELECT * FROM candles_{interval}_history where id='{ticker}' and  timestamp>= '{dt_from}' and timestamp<='{dt_to}' order by timestamp ASC")

#########

def get_last_day( ticker):
    dt = get_last_time(ticker)
    return datetime.combine(dt, time.min)#, tzinfo=ZoneInfo('Europe/Rome'))

def get_last_time( ticker):
    ts_str = select(f"SELECT max(timestamp) FROM candles_5m_history where id='{ticker}' ")
    dt = datetime.strptime(ts_str[0], '%Y-%m-%d %H:%M:%S')
    return dt

def markets():
   return select("select distinct exchange from quotes",noPandaMode=True)
  
def tickers(market):
   return select(f"select distinct id from quotes where exchange='{market}'")

def get_market(ticker):
   return select(f"select distinct exchange from quotes where id = '{ticker}'")[0]

def open_close(market):
   ts_str =  select(f"select open_local,close_local from market where name = '{market}'", noPandaMode=True)
   return [datetime.strptime(ts_str[0], '%Y-%m-%d %H:%M:%S'),datetime.strptime(ts_str[1], '%Y-%m-%d %H:%M:%S')]

def update_open_close():
    #print(markets())
    for market_entry in markets():
        market = market_entry["exchange"]
        print("market",market)
        all  = tickers(market)
        ticker = all[0]

        day = get_last_day(ticker)
        # menu uno 
        day = day -  timedelta(days=1)
        print(day)
        to_date = datetime.combine(day, time.max)
        df = get_history_data(ticker,"1m", day,to_date)
        
        print(df)

        # ✅ Prendi il timestamp della prima e ultima riga
        first_ts = df["timestamp"].iloc[0]
        last_ts  = df["timestamp"].iloc[-1]

        print("Primo timestamp:", first_ts)
        print("Ultimo timestamp:", last_ts)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
                UPDATE market
                SET open_local = ?, close_local = ?
                WHERE name = ?
            """, (first_ts, last_ts, market))
        conn.commit()
        conn.close()
        # update table


def plot(ctx):
    df = ctx.data

    df["buy_marker"] = np.where(df["Signal"] == "BUY", df["close"], np.nan)
    df["sell_marker"] = np.where(df["Signal"] == "SELL", df["close"], np.nan)

    buy_plot = mpf.make_addplot(
        df["buy_marker"],  # Y
        type='scatter',
        markersize=20,
        marker='^',
        color='g'
    )
    sell_plot = mpf.make_addplot(
        df["sell_marker"],  # Y
        type='scatter',
        markersize=20,
        marker='v',
        color='r'
    )
    
    mpf.plot(
        df,
        addplot=[buy_plot, sell_plot],
        type="candle",
        style="yahoo",
        volume=True,
        figsize=(10,6),
        title="Grafico"
    )
    
    
    # 4. Sovrapponi i segnali
    #plt.scatter(buy_signals.index,  buy_signals["close"]  , marker="^", color="green",  s=100, label="BUY")
    #plt.scatter(sell_signals.index, sell_signals["close"] , marker="v", color="red",    s=100, label="SELL")
    #plt.gcf().autofmt_xdate()
    plt.legend()
    #plt.show()
    #plt.tight_layout()
    plt.savefig("grafico.png")

if __name__ == "__main__":
    update_open_close()
 