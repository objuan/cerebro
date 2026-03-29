from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
from company_loaders import *
from collections import deque
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
#from strategy.order_strategy import *

########################


class _BackStrategy(SmartStrategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []
        self.legend = []
        self.marker_map= {}

        self.position = Position(10000)
        self.book = OrderBook( self.position )

    def buy(self,  symbol, price, label):
        logger.info(f"BUY {symbol} {label}")
        self.book.long(symbol, price, 100,label)

        
    def sell(self,symbol,price,label):
        logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        self.book.close(symbol,price)
        pass

    def onBackEnd(self):
        
        self.book.end()

        logger.info(f"REPORT {self.book.report()}")
        pass


#################

class BackStrategy(_BackStrategy):

    async def on_start(self):

        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        pass

    def populate_indicators(self) :
        pass
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        if not self.backtestMode and self.bootstrapMode:
            return

        use_day=False

        last = dataframe.iloc[local_index]
        
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(0,00),get_hour_ms(self.trade_last_hh,00),use_day):
        
            #########
            
            volume = last["day_volume_history"]    
            
            if volume > self.volume_min_filter:

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

                if  not self.has_meta(symbol,"valid") and not self.book.hasCurrentTrade(symbol):
                    self.set_meta(symbol, {"valid": True }) 

                    gain = last["gain"]
                    if gain < self.gain_perc/2:
                        
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        logger.info(f"BUY {symbol} {dt} {buy_price}")
                        self.book.long(symbol, buy_price, 100, f"BUY")    
                        self.add_marker(symbol,"BUY","BUY","#000000","arrowUp")
                  
                
                if self.book.hasCurrentTrade(symbol):
                    
                        
                        gain = self.book.gain(symbol, dataframe.iloc[local_index]["close"]) 
                        dt = dataframe.iloc[local_index]["datetime"]

                        self.book.set_current_price(symbol, last["close"])           
                        #logger.info(f"gain {symbol} {dt} gain {gain}")

                        if gain < -self.gain_perc:
                            self.book.close(symbol, dataframe.iloc[local_index]["close"])
                            logger.info(f"SELL SL  {symbol}  {dt}  gain {gain}")  

                            self.add_marker(symbol,"BUY","SL","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  
                        
                        if gain > self.gain_perc:
                            self.book.close(symbol, dataframe.iloc[local_index]["close"])
                            logger.info(f"SELL TP  {symbol}  {dt}   gain {gain}")   

                            self.add_marker(symbol,"BUY","TP","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  

       
        
