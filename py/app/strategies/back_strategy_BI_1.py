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


#################

class BackStrategyBinance1(SmartStrategy):

    async def on_start(self):

        '''
        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.min_open_gain= self.params["min_open_gain"]
        self.trade_first_hh= 5#self.params["trade_first_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        '''

        self.loss_by_trade = 100#capital * trade_risk
        pass


    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)


    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))

        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history",volume_name="quote_volume"))
        sma_20 = self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        sma_50 = self.addIndicator(self.timeframe,SMA("sma_50","close",timeperiod=50))
        gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
      
        self.add_plot(sma_20, "sma_20","#a70000", "main", style="SparseDotted", lineWidth=1)
        self.add_plot(sma_50 , "sma_50 ","#4800a7", "main", style="SparseDotted", lineWidth=1)
       
        self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(bad, "bad","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        #if symbol != "YGGUSDC":
        #    return
        
        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
        day_volume_history = last["day_volume_history"]    
        if (day_volume_history < 1_000_000):
             return

        
        prev = dataframe.iloc[local_index-1]

        close = last["close"]
        sma_20 = last["sma_20"]
        sma_50 = last["sma_50"]
        quote_volume = last["quote_volume"]    

        if (local_index ==20):   
            logger.info(f"dataframe \n{dataframe.columns}")      

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {last['datetime']} {last['day_volume']}")  

        if not self.hasCurrentTrade(symbol):
            if quote_volume > 100_000 and close > last['open']:
                #if sma_20>sma_50 and close > sma_20:

                    quantity = self.get_quantity(last["close"])  
                    await self.buy(symbol, int(last["timestamp"]), last["close"], quantity, "buy")
                   

        elif self.hasCurrentTrade(symbol):

                    gain,ts,pnl = self.buyGain(symbol, last["close"]) 

                    self.set_current_price(symbol, last["close"])         
        
                   #logger.info(f"SELL GAIN {symbol}  gain {gain} ts{ts} pnl {pnl}")

                    dt = int(dataframe.iloc[local_index]["timestamp"])
                    #self.set_current_price(symbol, last["close"])         
                    time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
                    
                   
                    #self.max_gain[symbol] = max(self.max_gain[symbol] , gain)
                    
                    logger.info(f"SELL GAIN {symbol}  {last['datetime']} secs: {time_elapsed_secs} gain {gain} pnl {pnl}  ")

                 
                    #if last["close"] < sma_20 : #or gain > 10: or chain_down>=3 
                    if gain > 5:
                        trade = await  self.sell(symbol, dt, last["close"], f"TP"  )
                    if gain < -2.5:
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                     