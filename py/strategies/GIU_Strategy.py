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


class GIU_Strategy(Strategy) :
    
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
            if (True):
        
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
                            logger.debug(f"EVAL val:{candle.close  }   ld:{self.last_day.close } sl:{stop_loss}  tp:{take_profit} ")
                            #logger.debug(f"! {candle.close } < {self.last_day.close}")
                            self.order = Order( self.ctx.ticker,False )
                            self.order.candle=candle
                            self.order.type = OrderType.LONG
                            self.order.stop_loss = candle.close - perc(candle.close, STOP_LOSS_PERC)
                            #self.order.take_profit = candle.close + perc(candle.close, 2*STOP_LOSS_PERC)
                            self.order.take_profit = self.last_day.close 
                            self.order.rank = ((self.last_day.close - candle.close) / candle.close) * 100
                            self.ctx.addOrder(self.order,"BUY DOWN")
                            self.mode="DOWN"
                        '''
                        elif (candle.close > take_profit_up):
                            logger.debug(f"EVAL val:{candle.close  }   ld:{self.last_day.close } sl:{stop_loss}  tp:{take_profit} ")
                            #logger.debug(f"! {candle.close } < {self.last_day.close}")
                            self.order = Order()
                            self.order.candle=candle
                            self.order.type = OrderType.LONG
                            self.order.stop_loss = candle.close - perc(candle.close, STOP_LOSS_PERC)
                            #self.order.take_profit = candle.close + perc(candle.close, 2*STOP_LOSS_PERC)
                            self.order.take_profit = self.last_day.close 
                            self.ctx.addOrder(self.order,"BUY UP")
                            self.mode="UP"
                        '''
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
        
