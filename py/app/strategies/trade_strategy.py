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

class VWAP(Indicator):
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
                    lambda s: (s)
                )
        )

    def get_render_data(self,dataframe)-> pd.DataFrame:
        return dataframe[["symbol","timestamp",self.t
                          
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
                    lambda s: (s)
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
        self.marker_map= {}

    def marker(self,timeframe:str, symbol:str = None)-> pd.DataFrame:
        if timeframe in self.df_map:
            if not symbol:
                return self.marker_map[timeframe]
            else:
                return self.marker_map[timeframe][self.marker_map[timeframe]["symbol"] == symbol]
        else:
            return  pd.DataFrame()
         
    def buy(self,  symbol, label):
        self.add_marker(symbol,"BUY",label,"#00FF00","arrowUp")

    #shapes : arrowUp, arrowDown, circle
    def add_marker(self, symbol,type, label,color,shape, position ="aboveBar", _timeframe=None):
        timeframe = self.timeframe if _timeframe==None else _timeframe
        
        logger.info(f"self.trade_index {self.trade_index}")
        candle =  self.trade_dataframe.loc[self.trade_index]
        
        timestamp =  candle["timestamp"]
        value = candle["close"]

        logger.info(f"marker idx {self.trade_index} {type} {symbol} ts: {timestamp} val: {value}")

        if not timeframe in self.marker_map:
            self.marker_map[timeframe] = pd.DataFrame(
                    columns=["symbol","timeframe","type", "timestamp", "value", "desc","color","shape","position"]
                )

        self.marker_map[timeframe].loc[len(self.marker_map[timeframe])] = [
                symbol,               # symbol
                timeframe,                # type
                type,               # symbol
                timestamp,       # timestamp
                value,              # value
                label,           # desc
                color,
                shape,
                position
            ]

       # self.marker_map["symbol"].append({"type":"buy", "symbol" : symbol, "ts": int(timestamp), "value": price, "desc": label})
     
    def live_markers(self,symbol,timeframe,since):
        if not timeframe:
            timeframe = self.timeframe
        if since:
            df = self.marker(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
        else:
            df = self.marker(timeframe,symbol)
        if df.empty:
            return []
        else:
            logger.info(f"live_markers since:{since}\n{df}")
            return df.to_dict(orient="records")
       
    def live_indicators(self,symbol,timeframe,since):
     
        if not timeframe:
            timeframe = self.timeframe

        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        if df.empty:
            return{"strategy": __name__ ,"markers": self.live_markers(symbol,timeframe,since)}
        
        #logger.info(f"out \n{df}")
        o = {"strategy": __name__ ,"markers": self.live_markers(symbol,timeframe,since), "list" : []}

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

########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))
        i = self.addIndicator(self.timeframe,TEST("test",timeperiod=self.eta))
        i = self.addIndicator(self.timeframe,VWAP("VWAP",timeperiod=self.eta))
        self.add_plot(i, "test","#ffffff", True)

    def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        #logger.info(f"trade_symbol_at   {symbol} index {index} \n {dataframe.tail(1)}" )
        try:
            gain = dataframe.loc[global_index]["gain"]
            if (gain > 0):
                self.buy(symbol,f"BUY")
                #logger.info(f"trade_symbol_at   {symbol} index {global_index} {gain} " )
        except:
            logger.error(f"trade_symbol_at   {symbol} index {global_index} \n {dataframe.tail(1)}", exc_info=True )
            #exit(0)

    
    '''
    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
        
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(1)}" )

        
        gain = dataframe.iloc[-1]["gain"]

        if (gain > -1):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            self.buy(symbol,f"buy1 gain {gain}")
    '''        
  
