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
        self.name= self.params["name"]
        self.min_volume = self.params["min_volume"]
        self.color =  self.params["color"]
     

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
     
        #logger.info(f"on_symbol_candles   {symbol} {self.min_volume} \n {dataframe.tail(2)}" )

        gain = dataframe.iloc[-1]["gain"]
        day_volume= dataframe.iloc[-1]["day_volume"]

        if (gain > self.min_gain
            and day_volume >  self.min_volume):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            await self.send_event(symbol,
                                  name= self.name,
                                  small_desc=f"{self.eta}m {gain:.1f}>{self.min_gain}%",
                                  full_desc=f"gain {gain:.1f}>{self.min_gain} vol:{day_volume}",
                                  color =self.color)
  