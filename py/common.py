import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from database import *
from utils import *
import sys, traceback
from datetime import datetime, timedelta
from enum import Enum
import logging
logger = logging.getLogger(__name__)

class Candle:
    row:any
    index : any
    i : int

    def __init__(self,i,index,row):
        self.row=row
        self.i=i
        self.index=index

    @property
    def date(self) -> pd.Timestamp:
        return self.index
    
    @property
    def date_only(self):
        return self.date.date()
    

    @property
    def open(self):
        return self.row["open"]
    @property
    def close(self):
        return self.row["close"]
    @property
    def high(self):
        return self.row["high"]
    @property
    def low(self):
        return self.row["low"]
    @property
    def volume(self):
        return self.row["volume"]
    
    def __str__(self):
        return f"{self.date} o:{self.open} c:{self.close} l:{self.low} h:{self.high} v:{self.volume}"


def perc(value,perc):
    return value * ( perc/100)


class OrderType(Enum):
    LONG = 0
    SHORT = 1


class Order:
    id :str
    candle:Candle
    type : OrderType
    take_profit : float
    stop_loss : float
    end_candle : Candle
    rank : float

    def __init__(self,id):
        self.end_candle=None
        self.rank=0
        self.id=id

    def profit(self):
        if (self.end_candle):
            return self.end_candle.close - self.candle.close
        else:
            return 0

    def profit_perc(self):
        #logger.debug(f"{ self.candle.close} -> {self.end_candle.close} ")
        return (self.profit() /  self.candle.close)*100 
    
    def close(self,actual_candle:Candle, msg):
        self.end_candle=actual_candle
        logger.debug(f"{msg} buy:{self.candle.date.strftime('%H:%M:%S')}({self.candle.close}) sell:{self.end_candle.date.strftime('%H:%M:%S')}({self.end_candle.close}) {self.profit_perc()}")

    def __str__(self):
        return f"{self.candle.date}  {self.candle.close} DO {self.type} tp:{self.take_profit} sl:{self.stop_loss} "
