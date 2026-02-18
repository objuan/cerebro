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

class TEST(Indicator):
    def __init__(self,target_col, timeperiod:int):
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
        
       # logger.info(f"GAIN \n{dataframe.tail(30)}")

        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        dataframe[self.target_col] = (
            dataframe
                .groupby("symbol")["close"]
                .transform(
                    lambda s: (s+0.1)
                )
        )

    def get_render_data(self,dataframe)-> pd.DataFrame:
        return dataframe[["symbol","timestamp",self.target_col]].rename(columns={self.target_col: "value", "timestamp": "time"})
    
       # logger.info(f"GAIN AFTER \n{dataframe.tail(30)}")

#from strategy.order_strategy import *
class SmartStrategy(Strategy):
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []

    def live_indicators(self,symbol,timeframe,since):
     
        if not timeframe:
            timeframe = self.timeframe

        if since:
            df = self.df(timeframe,symbol)
            df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        logger.info(f"out \n{df}")
        o = {"strategy": __name__ , "list" : []}

        for p in  self.plots:
           d = p.copy()
           del d["ind"]
           d["symbol"] = symbol
           d["timeframe"] = timeframe
           df_data = p["ind"].get_render_data(df)
           if symbol:
                df_data = df_data[["time","value"]]
           d["data"] = df_data.to_dict(orient="records")
             
           o["list"].append(d)

        return o

    def add_plot(self,ind : Indicator ,name :str,  color:str,isMain: bool =True):
        self.plots.append({"ind": ind ,"name" : name , "color" : color, "main" : isMain})
        pass

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        i = self.addIndicator(self.timeframe,TEST("test",timeperiod=self.eta))
        self.add_plot(i, "test","#ffffff", True)

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
     
        logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(2)}" )

        '''
        gain = dataframe.iloc[-1]["gain"]

        if (gain > self.min_gain):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            await self.send_event(symbol,
                                  name= f"GAIN_{self.min_gain}",
                                  small_desc=f"{gain:.1f}>{self.min_gain}",
                                  full_desc=f"gain {gain:.1f}>{self.min_gain}",
                                  data = {"color":"#ACAC0A"}
        '''
  