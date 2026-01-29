from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategy.indicators import GAIN, Indicator
from strategy.strategy import Strategy
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


class GainStrategy(Strategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.gain_limit= self.params["gain_limit"]
        pass

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:

        logger.info(f"populate_indicators ")

        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

        ##dataframe[f'sma_fast'] = ta.SMA(dataframe["low"], timeperiod=7)
        return dataframe
    
    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        logger.info(f"on_symbol_candle  {symbol} \n {dataframe.tail(5)}" )

        gain = dataframe.iloc[-1]["gain"]

        await self.send_event(symbol,f"GAIN_{self.gain_limit}/{self.eta}s",f"{gain:.2f} > {self.gain_limit} ({self.eta})",{"color":"#AAAA00"})

        if (gain > self.gain_limit):
            logger.info(f"FIND {gain} > {self.gain_limit}")
            await self.send_event(symbol,f"GAIN_{self.gain_limit}",f"{gain:.2f} > {self.gain_limit}",{"color":"#AAAA00"})
        pass
    