from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategy.indicators import *
from strategy.strategy import Strategy
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from strategy.order_strategy import *

class GainStrategy(Strategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
     
        logger.debug(f"on_symbol_candle  {symbol} \n {dataframe.tail(2)}" )

        gain = dataframe.iloc[-1]["gain"]

        if (gain > self.min_gain):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            await self.send_event(symbol,
                                  name= f"GAIN_{self.min_gain}",
                                  small_desc=f"{gain:.4f}>{self.min_gain}",
                                  full_desc=f"gain {gain:.4f}>{self.min_gain}",
                                  data = {"color":"#AAAA00"})
        
##############################################

class LowFlowStrategy(Strategy):

    async def on_start(self):
        self.avg_df ="1m"
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        self.min_rel_vol_5m= self.params["min_rel_vol_5m"]
        self.avg_5m_eta = self.params["avg_5m_eta"]

    def extra_dataframes(self)->List[str]:
        return [self.avg_df]
    
    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))
        self.addIndicator(self.avg_df,AVG("avg_base_volume","base_volume",timeperiod=self.avg_5m_eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
      
        #logger.info(f"on_symbol_candle \n{dataframe}")
      
        gain = dataframe.iloc[-1]["gain"]

        df_5m = self.df(self.avg_df,symbol)

        avg_base_volume = df_5m.iloc[-1]["avg_base_volume"]
        volume_5m = df_5m.iloc[-1]["base_volume"]
        rel_vol_5m=volume_5m / avg_base_volume

        if (gain > self.min_gain and rel_vol_5m >= self.min_rel_vol_5m):
            #logger.info(f"FIND {gain} > {self.min_gain} v:{rel_vol_5m}")
            await self.send_event(symbol,
                                  name=f"LOW FLOW",
                                  small_desc=f"{gain:.4f}>{self.min_gain:.1f} v:({rel_vol_5m:.1})",
                                  full_desc=f"gain {gain:.4f} > {self.min_gain:.1f} rel_vol_5m:({rel_vol_5m:.1})",
                                  data= {"color":"#62C050"})
        
class MidFloatStrategy(Strategy):

    async def on_start(self):
        self.avg_df ="1m"
        self.max_price= self.params["max_price"]
        self.min_float= self.params["min_float"]
        self.max_float= self.params["max_float"]
        self.min_rel_vol_5m= self.params["min_rel_vol_5m"]
        self.avg_5m_eta = self.params["avg_5m_eta"]

    def extra_dataframes(self)->List[str]:
        return [self.avg_df]
    
    def populate_indicators(self) :
        self.addIndicator( self.avg_df , FLOAT("float"))
        self.addIndicator(self.avg_df,AVG("avg_base_volume","base_volume",timeperiod=self.avg_5m_eta))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict):

        df_5m = self.df(self.avg_df,symbol)
        logger.info(f"on_symbol_candle \n{df_5m}")
      

        avg_base_volume = df_5m.iloc[-1]["avg_base_volume"]
        volume_5m = df_5m.iloc[-1]["base_volume"]
        rel_vol_5m=volume_5m / avg_base_volume
        current_float= df_5m.iloc[-1]["float"]

        logger.info(f"{avg_base_volume} {volume_5m} {rel_vol_5m} {current_float}")

        if self.min_float <= current_float <=self.max_float:
            if ( rel_vol_5m >= self.min_rel_vol_5m):
                #logger.info(f"FIND {gain} > {self.min_gain} v:{rel_vol_5m}")
                await self.send_event(symbol,name=f"MID FLOAT",
                                      small_desc=f"  v:({rel_vol_5m:.1})",
                                      full_desc=f" float:{current_float} rel_vol_5m:({rel_vol_5m:.1}>{self.min_rel_vol_5m:.1})",
                                      data={"color":"#FF71B3"})
        
class MomoStrategy(Strategy):

    async def on_start(self):
        self.rank_map=None
        self.rank_map_old=None
        self.diff=None
        self.min_gain= self.params["min_gain"]
        self.eta_gain= self.params["eta_gain"]
        self.min_rel_vol_24= self.params["min_rel_vol_24"]
        self.avg_1d_eta = self.params["avg_1d_eta"]

    def extra_dataframes(self)->List[str]:
        return ["1d"]
    
    def populate_indicators(self) :
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta_gain))
        self.addIndicator(self.timeframe,SORT_POS("pos","gain"))
 
        self.addIndicator("1d",AVG("avg_base_volume","base_volume",timeperiod=self.avg_1d_eta))

    async def on_all_candle(self, dataframe: pd.DataFrame, metadata: dict) :

        last_rows = (
            dataframe
            .sort_index()
            .groupby("symbol")
            .tail(1)
        )
        if (self.rank_map):
            self.rank_map_old = self.rank_map.copy()
        self.rank_map = last_rows.set_index("symbol")["pos"].to_dict()

        if (self.rank_map_old):
           
            def rank_delta(old: dict, new: dict) -> dict:
                result = {}

                for symbol, new_pos in new.items():
                    old_pos = old.get(symbol)

                    if old_pos is None:
                        result[symbol] = {
                            "new_pos": new_pos,
                            "old_pos": None,
                            "delta": None,
                            "is_new": True,
                        }
                    else:
                        result[symbol] = {
                            "new_pos": new_pos,
                            "old_pos": old_pos,
                            "delta": old_pos - new_pos,  # positivo = sale in classifica
                            "is_new": False,
                        }

                return result
            self.diff = rank_delta(self.rank_map ,self.rank_map_old )
           
        #ogger.info(f"on_all_candle \n{self.rank_map}")

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict):

        if not self.diff:
            return
        
        df_1d = self.df("1d",symbol)

        logger.debug(f"on_symbol_candle \n{self.rank_map} diff : {self.diff}")
      
        gain = dataframe.iloc[-1]["gain"]

        avg_base_volume = df_1d.iloc[-1]["avg_base_volume"]
        volume_1d = df_1d.iloc[-1]["base_volume"]
        rel_vol_1d=volume_1d / avg_base_volume

        logger.debug(f"g:{gain:.2} {volume_1d}/{avg_base_volume} =_> {rel_vol_1d} ")

        if rel_vol_1d <=self.min_rel_vol_24:
            if gain >= self.min_gain:
                #logger.info(f"FIND {gain} > {self.min_gain} v:{rel_vol_5m}")
                if (self.diff[symbol]["delta"]>0):
                    await self.send_event(symbol,name=f"MOMO",
                                          small_desc=f"p:{self.diff[symbol]['new_pos']} v:({rel_vol_1d:.1})",
                                          full_desc=f"pos:{self.diff[symbol]['new_pos']} v:({rel_vol_1d:.1}>{self.min_rel_vol_24:.1})",
                                          data = {"color":"#8AFFAD"})
                elif (self.diff[symbol]["is_new"]):
                    await self.send_event(symbol,name=f"MOMO",
                                          small_desc=f"p:NEW v:({rel_vol_1d:.1})",
                                          full_desc=f"pos:NEW v:({rel_vol_1d:.1}>{self.min_rel_vol_24:.1})",
                                          data = {"color":"#757776"})
        