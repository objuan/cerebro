import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys, traceback
from datetime import datetime, timedelta

from common import *
from strategy import *
from database import *
from utils import *

from strategies.GIU_Strategy import GIU_Strategy

import logging
import mplfinance as mpf
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- LOGGER CONFIG ---

logger = logging.getLogger(__name__)


ORB_MINUTES = 0
candela = "5m"

STOP_LOSS_PERC = 0.5
MAX_MINUTES = 60 * 10

###############################

class GIU_PRIORITY_Strategy(Strategy) :
    
    interval_low:float
    interval_hi:float

    last_day : Candle
    mode =""

    def __init__(self):
        super().__init__()
        self.last_day=None

    def onStartDay(self,candle:Candle):
        #logger.debug(f"=== onStartDay {candle.date} ===")
        #if (self.last_day):
        #   print("last",self.last_day.date)

        self.start = candle
        self.interval_low = 9999999
        self.interval_hi = -9999999
        self.valid=True
        self.started=False
        self.failed=False

        BACK_DAY = 4
        if ( self.start.date.weekday()< BACK_DAY ): # finesettimana
            BACK_DAY= BACK_DAY+2

        self.total_profit_perc = self.ctx.total_profit_perc(self.start.date ,BACK_DAY, keepFake=True)
        #logger.debug(f"=== onStartDay {candle.date} last_profit:{self.total_profit_perc }===")

    def onEndDay(self,candle:Candle):
        #logger.info("onEndDay",candle.date)
        self.last_day = candle
        self.order=None
        super().onEndDay(candle)
       
    def tick(self,candle:Candle):
        #print(candle)
        if (not self.valid): return
        if (not self.last_day): return

        minutes = int((candle.date - self.start.date).total_seconds()/60  )
        if True:#(minutes > ORB_MINUTES):
            if ( self.total_profit_perc >= 0):
        
                stop_loss = candle.close - perc(candle.close, STOP_LOSS_PERC)
                up_take_profit = candle.close + perc(candle.close, 2*STOP_LOSS_PERC)
                take_profit = up_take_profit#self.last_day.close# + perc(candle.close, 2*STOP_LOSS_PERC)

                
                #take_profit_up = self.last_day.close + perc(self.last_day.close, 2*STOP_LOSS_PERC)
                #take_profit_up_up = self.last_day.close + perc(self.last_day.close, 4*STOP_LOSS_PERC)
                
                #logger.debug(f"EVAL val:{candle.close  }   ld:{self.last_day.close } sl:{stop_loss}  tp:{take_profit} ")
                
                if  not self.order:
                    ## GIU e SU
                    if not  self.failed:
                        if (up_take_profit < self.last_day.close ):
                            logger.debug(f"EVAL [{candle.date.date()}] val:{candle.close  }  ld:{self.last_day.close } sl:{stop_loss}  tp:{take_profit} last% {self.total_profit_perc}")
                            #logger.debug(f"! {candle.close } < {self.last_day.close}")
                            self.order = Order( self.ctx.ticker,fakeOrder=self.total_profit_perc==0 )
                            self.order.candle=candle
                            self.order.type = OrderType.LONG
                            self.order.stop_loss = candle.close - perc(candle.close, STOP_LOSS_PERC)
                            #self.order.take_profit = candle.close + perc(candle.close, 2*STOP_LOSS_PERC)
                            self.order.take_profit = self.last_day.close 
                            self.order.rank = ((self.last_day.close - candle.close) / candle.close) * 100
                            self.ctx.addOrder(self.order,"BUY DOWN")
                            self.mode="DOWN"
    
                else:
                        if (candle.close < self.order.stop_loss):
                            self.ctx.close(candle,"SELL LOSS ")
                            self.valid=False
                            self.order=None

                        elif ( self.mode=="DOWN" and candle.close > self.order.take_profit):
                            self.ctx.close(candle,"SELL TAKE DOWN")
                            self.valid=False    
                            self.order=None
                        '''
                        elif ( self.mode=="UP" and candle.close > take_profit_up_up):
                            self.ctx.close(candle,"SELL TAKE UP")
                            self.valid=False    
                            self.order=None
                        '''
                self.failed=True
        

################################

def compute_prob(ctx:BacktestContext,data_1m ):
    if (len(data_1m)>0):
        logger.info("======== compute_prob ===========")

        s = GIU_PRIORITY_Strategy()
        s.ctx=ctx
        s.backtest(ctx,data_1m)

def compute_continue(ctx:BacktestContext ):
    if (len(ctx.data)>0):
        try:
            ctx.data["timestamp"] = pd.to_datetime(ctx.data["timestamp"])
            ctx.data.set_index("timestamp", inplace=True)
            
            #logger.info("======== compute_continue ===========")

            s = GIU_Strategy()
            s.ctx=ctx
            s.backtest_continue(ctx,ctx.data)
        except Exception as e:
            logger.error("ERROR ", exc_info=True)

###################

def scan_open_prob(tickers, first_day, last_day , useHistory, maxDayOrders=6):

    total = pd.DataFrame(columns=["ticker","profit","count","ok"])
    ctx_list = []
    t=0
    min_date=max_date = None
    for ticker in tickers:
        print("===================")
      
        market = "MIL"#get_market(ticker)

        logger.info(f"ticker {ticker} market {market}")

        logger.info(f"SCAN FROM {first_day} to {last_day}")

        ctx = BacktestContext()
        ctx_list.append(ctx)
        ctx.ticker = ticker
        if useHistory:
            ctx.data = get_history_data(ticker, candela,first_day,last_day )
        else:
            ctx.data = get_live_5m_data(ticker, first_day,last_day )

        ctx.data ["Signal"] = np.nan
       
        logger.info(f"LOAD DATA #{len(ctx.data)}")
        #print(ctx.data)
        #exit()
        compute_continue(ctx)
 
        logger.info (f"======== {ticker} ============")

        logger.info(ctx.result)

        logger.info(f"total { ctx.result['profit'].sum() }" )
        
        orders = ctx.get_orders(keepFake=False)
        #if (ctx.result['profit'].sum())>0:
        #if  len(ctx.result)>0:
        if len(orders) > 0:
            real_gain = ctx.total_profit_perc (datetime.now() , 9999, keepFake=False)

            new_row = {"ticker":ticker,"profit" :real_gain,"count" : len(ctx.result),"ok" : len(orders)}
            t=t+  len(ctx.result)
            total = pd.concat([ total, pd.DataFrame([new_row])], ignore_index=True)
        #exit(0)
    logger.info("======== TOTALE ===========")
    logger.info(total)
    logger.info(f"sum :{total['profit'].sum()} #{t}")

    # analisi a priorita
    logger.info("====== PRIORITA =============")
    racc = {}
    #logger.info(f"range {min_date} {max_date}")
    for ctx in ctx_list:
        for order in  ctx.orders:
            dt = order.candle.date
            if not dt in racc:
                racc[dt ] = []
            if not order.fakeOrder:
                racc[dt ].append(order)
            #print(dt)

    #logger.info(f"{racc}")

    count=0
    total_gain=0
    for k in racc.keys():
        list = racc[k]
        gain=0
        if (len(list) > 0  and len(list)<maxDayOrders):
            
            ordinati = sorted(list, key=lambda p: p.rank, reverse=True) # desc
            
            for o in ordinati:
                #print(k, o.rank,o.profit_perc())
                if not o.fakeOrder:
                    gain = gain + o.profit_perc()
                    count=count+1

            total_gain=total_gain+gain
            #count=count+len(list)
            logger.info(f"{k} #{len(list)} gain:{gain}")

    logger.info(f"count {count} profit :{total_gain}")
    #plot(ctx)
    return racc


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    #tickers = get_tickers(conn,"prima")
    tickers = select("SELECT id from ticker where fineco=1 and market_cap = 'Large Cap' ")["id"].to_list()
    tickers = select("SELECT id from ticker where fineco=1 and market_cap = 'Mid Cap' ")["id"].to_list()
    tickers = select("SELECT id from ticker where fineco=1 ")["id"].to_list()
    #tickers = select("SELECT id from ticker where fineco=1  ")["id"].to_list()
    tickers = select("SELECT distinct id from live_quotes ")["id"].to_list()

    NUM_DAYS = 60

    #last_day = get_last_day(ticker); 
    last_day = datetime.now()
    #last_day =(last_day - timedelta(days=1))
    first_day =(last_day - timedelta(days=NUM_DAYS))
    logger.info(f"SCAN FROM {first_day} to {last_day}")

    #tickers = ["DDOG"]
    logger.info(f"USER {tickers}")

    scan_open_prob(tickers,first_day,last_day,True,maxDayOrders=4)

    