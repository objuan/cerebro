import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from database import *
from utils import *
import sys, traceback
from datetime import datetime, timedelta
from common import *
import logging
logger = logging.getLogger(__name__)

tickers = get_tickers(conn,"prima")

class BacktestContext:
    ticker :str
    result:any
    prob:any
    data:any
    orders: list[Order]
    
    def __init__(self):
        self.orders=[]
        self.order=None
        self.data=None
        self.tag=None
        self.result = pd.DataFrame(columns=["day","profit","buy","sell"])
      
    def get_orders(self, keepFake=False):
        list=[]
        for o in self.orders:
            if not o.fakeOrder or (keepFake and o.fakeOrder ):
                list.append(o)
        return list
    
    def total_profit_perc(self,startDate, back_days = 1, keepFake=False):
        gain=0
        #logger.debug(f"totalGain {startDate.date()}")
        for o in self.orders:
            if not o.fakeOrder or (keepFake and o.fakeOrder ):
                diff_giorni   = int((startDate.date()-o.candle.date.date()  ).days )
                #logger.debug(f"diff_giorni {diff_giorni}")
                if (diff_giorni >0 and diff_giorni  <= back_days ):
                    logger.debug(f"take {o.candle.date.date()} {startDate.date()} {diff_giorni}")
                    gain+= o.profit_perc()
        return gain

    def addOrder(self,order:Order,tag):
        self.orders.append(order)
        self.order = order
        self.tag=tag
        logger.info(f"ORDER {order}")
        self.data.loc[order.candle.index, "Signal"] = "BUY"

    def close(self,actual_candle:Candle, msg):
        if (self.order):
            self.order.close(actual_candle,msg)

            new_row = {"day": actual_candle.date,"profit" : self.order.profit_perc(),"buy": self.tag, "sell":msg}
            self.result = pd.concat([ self.result, pd.DataFrame([new_row])], ignore_index=True)

            self.data.loc[actual_candle.index, "Signal"] = "SELL"

            self.order=None

class Strategy:
    
    started=False
    ctx:BacktestContext 
    order:Order
    valid:bool

    def __init__(self):
        self.order=None
        self.valid=True
        
    def tick(self,candle:Candle):
      pass

    def onStartDay(self,candle:Candle):
        pass

    def onEndDay(self,candle:Candle):
        if (self.valid):
            self.ctx.close(candle,"END DAY ")

    def backtest_day(self,ctx:BacktestContext,df):
        for i, (index, row) in enumerate(df.iterrows()):
            c = Candle(i,index,row)
            #print(f"Riga {i}: {index} -> open={row['open']}, close={row['close']}")
            if (i == 0):
                self.onStartDay(c)
                
            self.tick(c)
            if (i == len(df)-1):
                self.onEndDay(c)


    def backtest_continue(self,ctx:BacktestContext,df):
        last_candle=None
        for i, (index, row) in enumerate(df.iterrows()):
            c = Candle(i,index,row)

            if last_candle == None or c.date_only != last_candle.date_only :
                #print("BEGIN DAY ",c.date)

                if (last_candle!=None):
                    self.onEndDay(last_candle)

                self.onStartDay(c)

                #print(f"Riga {i}: {index} -> open={row['open']}, close={row['close']}")
                     
            self.tick(c)

            last_candle=c
