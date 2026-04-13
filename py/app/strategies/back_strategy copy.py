from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategies.strategy_utils import StrategyUtils
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
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


    async def buy(self,  symbol, price, label):

        self.book.long(symbol, price, self.get_quantity(price), f"BUY")    
        await self.add_marker(symbol,"BUY",label,"#000000","arrowUp")
          
        #logger.info(f"BUY {symbol} {label}")
        #self.book.long(symbol, price, 100,label)

        
    async  def sell(self,symbol,price,label):
         
        await   self.add_marker(symbol,"BUY",label,"#000000","arrowDown")
        trade = self.book.close(symbol,price)     
        #logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        #self.book.close(symbol,price)
        return trade

    def onBackEnd(self):
        
        logger.info(f"marker_map {self.marker_map}")

        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
        self.book.end(onClose)

        logger.info(f"REPORT {self.book.report()}")
        pass



#################

class MAX_DAY(Indicator):

    def __init__(self, target_col, price_col: str,from_timestamp=0):
        super().__init__([target_col])
        self.price_col = price_col
        self.target_col = target_col
        self.max ={}
        self.from_timestamp=from_timestamp
       

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        timestamp = dataframe["timestamp"].to_numpy()
        dest = dataframe[self.target_col].to_numpy()
        price = dataframe[self.price_col].to_numpy()
            
        start = max(0, from_local_index)

        #logger.info(f"MAX_DAY {symbol} from_local_index {from_local_index}  symbol_idx {symbol_idx}  ")    

        for i_idx in range(start, len(symbol_idx)):
            if timestamp[symbol_idx[i_idx]] > self.from_timestamp:
                if not symbol in self.max:
                    self.max[symbol] = price[symbol_idx[i_idx]]
                    logger.info(f"MAX_DAY INIT {symbol} {price[symbol_idx[i_idx]]}  ")
                else:
                    self.max[symbol]= max(self.max[symbol], price[symbol_idx[i_idx]])

            
                dest[symbol_idx[i_idx]] =self.max[symbol]
            else:
                dest[symbol_idx[i_idx]] =0

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
        sma_9 = self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        max_day = self.addIndicator(self.timeframe,MAX_DAY("max_day","close" ))

        self.add_plot(sma_9, "sma_9","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max_day, "max_day","#a79600", "main",  lineWidth=1)

        self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        if not self.backtestMode and self.bootstrapMode:
            return

        use_day=False

        last = dataframe.iloc[local_index]
        
        if not self.has_meta(symbol,"first_enter"): 
            await self.compute_first_enter(symbol, dataframe,local_index, use_day )

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return

        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(0,00),get_hour_ms(self.trade_last_hh,00),use_day):
        
            #########
            
            volume = last["day_volume_history"]    
            
            if volume > self.volume_min_filter and last["timestamp"]:

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

                
                if  not self.has_meta(symbol,"valid") and not self.book.hasCurrentTrade(symbol):
                    self.set_meta(symbol, {"valid": True }) 

                    gain = last["gain"]
                    if gain < self.gain_perc/2:
                        
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        logger.info(f"BUY {symbol} {dt} q:{self.get_quantity(buy_price)} at: {buy_price}")
                        await self.buy(symbol, buy_price, f"BUY"  )

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
                            
                            trade = await  self.sell(symbol,  last["close"], f"SL"  )
                            logger.info(f"SELL SL  {symbol}  {dt}  gain {gain} pnl : {trade.pnl()}")  
                            #self.add_marker(symbol,"BUY","SL","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  
                        
                        elif gain > self.gain_perc:
                            #trade = self.book.close(symbol, last["close"])
                            trade = await  self.sell(symbol,  last["close"], f"TP"  )

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

    async def compute_first_enter(self,symbol,dataframe,local_index, use_day):
            if not self.has_meta(symbol,"first_enter"): 
                
                first_enter = await StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)

                self.set_meta(symbol, {"first_enter": first_enter }) 

                #logger.info(f"FIRST ENTER {symbol} {first_enter}  ")

                await self.add_marker(symbol,"SPOT","X","#060806","square",position ="atPriceTop",timestamp=first_enter)
