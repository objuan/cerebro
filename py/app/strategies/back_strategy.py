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

        self.book.long(symbol, price, self.get_quantity(price), f"BUY")    
        self.add_marker(symbol,"BUY",label,"#000000","arrowUp")
          
        #logger.info(f"BUY {symbol} {label}")
        #self.book.long(symbol, price, 100,label)

        
    def sell(self,symbol,price,label):
         
        self.add_marker(symbol,"BUY",label,"#000000","arrowDown")
        trade = self.book.close(symbol,price)     
        #logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        #self.book.close(symbol,price)
        return trade

    def onBackEnd(self):
        
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
        self.book.end(onClose)

        logger.info(f"REPORT {self.book.report()}")
        pass


#################

class BackStrategy(_BackStrategy):

    async def on_start(self):

        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
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

                        logger.info(f"BUY {symbol} {dt} q:{self.get_quantity(buy_price)} at: {buy_price}")
                        self.buy(symbol, buy_price, f"BUY"  )

                        #logger.info(f"BUY {symbol} {dt} q:{self.get_quantity(buy_price)} at: {buy_price}")
                        #self.book.long(symbol, buy_price, self.get_quantity(buy_price), f"BUY")    
                        #self.add_marker(symbol,"BUY","BUY","#000000","arrowUp")
                  
                
                if self.book.hasCurrentTrade(symbol):
                    
                        
                        gain = self.book.gain(symbol, last["close"]) 
                        dt = dataframe.iloc[local_index]["datetime"]

                        self.book.set_current_price(symbol, last["close"])           
                        #logger.info(f"gain {symbol} {dt} gain {gain}")

                        if gain < -self.gain_perc:
                            #trade = self.book.close(symbol, last["close"])
                            
                            trade = self.sell(symbol,  last["close"], f"SL"  )
                            logger.info(f"SELL SL  {symbol}  {dt}  gain {gain} pnl : {trade.pnl()}")  
                            #self.add_marker(symbol,"BUY","SL","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  
                        
                        elif gain > self.gain_perc:
                            #trade = self.book.close(symbol, last["close"])
                            trade = self.sell(symbol,  last["close"], f"TP"  )

                            logger.info(f"SELL TP  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   
                            

                            #self.add_marker(symbol,"BUY","TP","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  

                        '''
                        logger.info(f"TIME  {symbol}  {dt}  ") 

                        if not self.market.is_in_time(last["datetime"],
                             get_hour_ms(0,0),get_hour_ms(self.trade_last_hh,0),use_day):
                                
                                trade = self.book.close(symbol, last["close"])
                                logger.info(f"SELL TIME  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   

                                self.add_marker(symbol,"BUY","TM","#000000","arrowDown")
                        '''
