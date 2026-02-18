from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import Strategy
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

#from strategy.order_strategy import *

class GainStrategy(Strategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
     
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(2)}" )

        gain = dataframe.iloc[-1]["gain"]

        if (gain > self.min_gain):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            await self.send_event(symbol,
                                  name= f"GAIN_{self.min_gain}",
                                  small_desc=f"{gain:.1f}>{self.min_gain}",
                                  full_desc=f"gain {gain:.1f}>{self.min_gain}",
                                  data = {"color":"#ACAC0A"})
  