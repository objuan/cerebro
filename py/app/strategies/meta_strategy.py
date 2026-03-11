from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager



########################

class MetaStrategy(SmartStrategy):

    async def on_start(self):
        #self.metaInfo = {}
        pass

    def populate_indicators(self) :
        pass

    ######################################

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        return
    
        if self.bootstrapMode:
            return
            
        if not self.has_meta(symbol,"last_close"):
            
            last_close, ts_last_close=  await self.client.last_close(symbol)
            self.set_meta(symbol,{"last_close": last_close,"ts_last_close" : ts_last_close})

            #logger.info(f"DO {symbol} {   self.get_meta(symbol) }")

        #logger.info(f"DO {symbol} {global_index} \n{dataframe.tail(5)}" )

        if not self.has_meta(symbol,"last_open"):
            if self.client.market.isLiveZone():
                last_open, ts_last_open=  await self.client.last_open(symbol)
                self.set_meta(symbol,{"last_open":  last_open, "ts_last_open" : ts_last_open})

                mask = (
                        (dataframe["timestamp"] >= self.get_meta(symbol,"ts_last_close")) &
                        (dataframe["timestamp"] <=  self.get_meta(symbol,"ts_last_open"))
                    )

                self.set_meta(symbol,{"low":  float(dataframe.loc[mask, "low"].min()), "high" : float(dataframe.loc[mask, "high"].max())})

                pre_gain= 100 * (last_open -   self.get_meta(symbol,"last_close")) /   self.get_meta(symbol,"last_close")
                pre_gain_LH= float(100 * (  self.get_meta(symbol,"high") -   self.get_meta(symbol,"low")) /   self.get_meta(symbol,"low"))

                self.set_meta(symbol,{"pre_gain":  pre_gain , "pre_gain_LH" : pre_gain_LH})

                logger.info(f"OPEN {symbol} {  self.get_all_meta(symbol) }")
               
            else:
                mask = dataframe["timestamp"] >=  self.get_meta(symbol,"ts_last_close")
                self.set_meta(symbol,{"low":  float(dataframe.loc[mask, "low"].min()), "high" : float(dataframe.loc[mask, "high"].max())})

                #logger.info(f"PRE {symbol} {  self.get_all_meta(symbol) }")
        else:
            close = dataframe.iloc[-1]["close"]
            gap = 100 * (close - self.get_meta("last_open")) /  self.get_meta("last_open")
            self.set_meta(symbol,{"gap" : gap})

    
