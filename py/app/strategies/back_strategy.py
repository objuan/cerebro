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

class BackStrategy(Strategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
     
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(2)}" )
        time = dataframe.iloc[-1]["timestamp"]

        gain = dataframe.iloc[-1]["gain"]
        if gain > 1:
            logger.info(f"{symbol} gain {gain} {ts_to_local_str(time)}")

  