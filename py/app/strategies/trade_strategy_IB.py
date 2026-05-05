from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from balance import Balance, PositionTrade
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *


 


class TradeStrategyIB(SmartStrategy):

    async def on_start(self):
        self.volume_min_filter= 500_1000#self.params["volume_min_filter"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]

    #def extra_dataframes(self)->List[str]:
    #    return ['15m']

    def populate_indicators(self) :
      
        vol_day= self.addIndicator("1m",SUM("vol_day","quote_volume",1440))

        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        max= self.addIndicator(self.timeframe,MAX("MAX","close",6*10))

        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)

        self.add_plot(vol_day, "vol_day","#003000FF", "sub",style="Solid", lineWidth=1)

        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        #if not self.bootstrapMode:
        #     logger.info(f"..\n{dataframe.tail(3)}")
        use_day=True

        if local_index < 2:
            return
   

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]
        prev2 = dataframe.iloc[local_index-2]

        vol_day = last["vol_day"]           
        max = last["MAX"]    

        #gain2 =  last["gain"] 
        gain = (last["close"] - prev["close"]) / prev["close"] * 100    
        gain2 = (last["close"] - prev2["close"]) / prev2["close"] * 100    

        if vol_day > self.volume_min_filter:
            
            if gain >= 2:
                   await self.add_marker(symbol,"SPOT",f"Gain {gain:.1f}",f"Gain {gain}","#F6F7F86F","square",position ="atPriceTop")

            if max > prev["MAX"]:
                   await self.add_marker(symbol,"SPOT",f"MAX",f"MAX","#0861BB6E","square",position ="atPriceTop")
