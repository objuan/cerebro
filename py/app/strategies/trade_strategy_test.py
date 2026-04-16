from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from order_task import OrderTaskManager
from balance import Balance, PositionTrade
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



class TradeStrategyTest(SmartStrategy):

    async def on_start(self):

        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.trade_first_hh= 5#self.params["trade_first_hh"]
        
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   

        await self.set_property( "__general", {"trade_enabled": True, "test" : "gg"}  )

        await self.sync_properties()
        pass

    ###############################

    def populate_indicators(self) :
      
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_9 = self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        sma_15 = self.addIndicator(self.timeframe,SMA("sma_15","close",timeperiod=15))

        self.add_plot(sma_9, "sma_9","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_15, "sma_15","#a79600", "main",  lineWidth=1)

    
    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        if self.bootstrapMode:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
                return
        
        '''
        if not self.bootstrapMode:
            tp_enable =self.props.get(f"strategy.{symbol}.tp",True)
            sl_enable =self.props.get(f"strategy.{symbol}.sl",True)

            logger.info(f"{symbol}  tp {tp_enable} sl {sl_enable}")
        '''
        use_day=True

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {dataframe.iloc[local_index]['timestamp']}")  

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
       
        close = last["close"]
        volume = last["day_volume_history"]    

        if volume> 1_000_000:
            if not self.hasCurrentTrade(symbol):
            
                #if last["sma_9"] >last["sma_15"]:
                    await self.buy(symbol,last["timestamp"],close,100,label=f"up")   

            else:
                gain, ts = self.buyGain(symbol,close)

                time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000
                self.set_current_price(symbol, last["close"])   

                logger.info(f"SELL GAIN {symbol} {gain}  time_elapsed_secs {time_elapsed_secs} ")      

                if gain > 1:
                    if (self.tp_enabled(symbol)):

                        trade = await self.sell(symbol,last["timestamp"],close,label=f"gain {gain:.2f}%")                  
