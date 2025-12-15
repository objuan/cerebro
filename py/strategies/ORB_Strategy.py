from common import *
from strategy import *
from database import *
from utils import *

import logging
import mplfinance as mpf
import warnings

# --- LOGGER CONFIG ---

logger = logging.getLogger(__name__)

ORB_MINUTES = 0
candela = "5m"

STOP_LOSS_PERC = 0.5
MAX_MINUTES = 60 * 10

###############################

###############################

class ORB_Strategy(Strategy) :
    
    interval_low:float
    interval_hi:float

    def onStartDay(self,candle:Candle):
        self.start = candle
        self.interval_low = 9999999
        self.interval_hi = -9999999

    def tick(self,candle:Candle):
        #print(candle)
        if (not self.valid): return

        if (not self.started):

            self.interval_low = min(self.interval_low , candle.low)
            self.interval_hi = max(self.interval_hi , candle.high)

            minutes = int((candle.date - self.start.date).total_seconds()/60  )
            if (minutes > ORB_MINUTES):
                self.started=True
            
                print(f"START {candle.i}: {self.interval_low } {self.interval_hi }")
        else:
            if  not self.order:
                time = (candle.date - self.start.date).total_seconds()/60
                if (time < MAX_MINUTES):
                    if (candle.close > self.interval_hi):
                        print(f"! {candle.close } > {self.interval_hi}")
                        self.order = Order()
                        self.order.candle=candle
                        self.order.type = OrderType.LONG
                        self.order.stop_loss = candle.close - perc(candle.close, STOP_LOSS_PERC)
                        self.order.take_profit = candle.close + perc(candle.close, 2*STOP_LOSS_PERC)
                        self.ctx.addOrder(self.order)
                else:
                    print("SKIP TOO TIME")
                    self.valid=False
                    
            else:
                if (candle.close < self.order.stop_loss):
                    self.ctx.close(candle,"SELL LOSS ")
                    self.valid=False
                    self.order=None
                if (candle.close > self.order.take_profit):
                    self.ctx.close(candle,"SELL TAKE ")
                    self.valid=False
                    self.order=None

