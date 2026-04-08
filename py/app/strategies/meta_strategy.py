from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from market import MarketZone
from bot.indicators import *
from bot.smart_strategy import SmartStrategy

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

class META(Indicator):
  
    def __init__(self,target_col, name:str):
        super().__init__([target_col])
        self.name=name
        self.target_col=target_col

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        for i_idx in range(from_local_index,len(symbol_idx) ):
            dest[symbol_idx[i_idx]] = MetaInfo.get_meta(symbol,self.name)

########################

class MetaStrategy(SmartStrategy):

    async def on_start(self):
        #self.metaInfo = {}
        self.firstTime = {}

        pass

    def populate_indicators(self) :
        
        '''
        last_close = self.addIndicator(self.timeframe,META("last_close","last_close"))
        self.add_legend(last_close,"last_close", "last_close", "#000000")

        pre_gain_LH = self.addIndicator(self.timeframe,META("pre_gain_LH","pre_gain_LH"))
        self.add_legend(pre_gain_LH,"pre_gain_LH", "pre_gain_LH", "#000000")
        '''
        pass

    ######################################

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        zone =  self.client.market.getCurrentZone() 
        #if self.bootstrapMode:
        #    return
        
        if not symbol in  self.firstTime:
            self.firstTime[symbol]=True
            last_close, ts_last_close=  await self.client.last_close(symbol)
            MetaInfo.set(symbol,{"last_close": last_close,"ts_last_close" : ts_last_close})

            #logger.info(f"DO {symbol} {   last_close}")
            #logger.info(f"last_close {symbol} {local_index} \n{dataframe.tail(5)}" )

        if zone != MarketZone.LIVE:
            self.zone = zone
            if  zone in [MarketZone.CLOSED ,MarketZone.PRE] :## not self.has_meta(symbol,"last_open") or
                
                close = dataframe.iloc[local_index]["close"]
                if close:
                    mask = (
                            (dataframe["timestamp"] >= MetaInfo.get(symbol,"ts_last_close"))# &
                            #(dataframe["timestamp"] <=  MetaInfo.get(symbol,"ts_last_open"))
                        )

                    MetaInfo.set(symbol,{"pre_low":  float(dataframe.loc[mask, "low"].min()), 
                                        "pre_high" : float(dataframe.loc[mask, "high"].max())})

                    pre_gain= 100 * (close -   MetaInfo.get(symbol,"last_close")) /   MetaInfo.get(symbol,"last_close")
                    pre_gain_LH= float(100 * (  MetaInfo.get(symbol,"pre_high") -   MetaInfo.get(symbol,"pre_low")) /   MetaInfo.get(symbol,"pre_low"))

                    MetaInfo.set(symbol,{"pre_gain":  pre_gain , "pre_gain_LH" : pre_gain_LH})
                    
                    MetaInfo.set(symbol,{"gap" : pre_gain})

                    #logger.info(f"DO {symbol} {   pre_gain}")

                    #logger.info(f"OPEN {symbol} {  self.get_all_meta(symbol) }")
                   
            '''
            else:
                mask = dataframe["timestamp"] >=  MetaInfo.get(symbol,"ts_last_close")
                MetaInfo.set(symbol,{  "pre_low":  float(dataframe.loc[mask, "low"].min()), 
                                        "pre_high" : float(dataframe.loc[mask, "high"].max())})
            '''
                #logger.info(f"PRE {symbol} {  self.get_all_meta(symbol) }")
        else:
            # OPEN -> last_open, gap
            if not MetaInfo.has(symbol,"last_open"):
                last_open, ts_last_open=  await self.client.last_open(symbol)
                MetaInfo.set(symbol,{"last_open":  last_open, "ts_last_open" : ts_last_open})

                close = dataframe.iloc[local_index]["close"]
                mask = (
                            (dataframe["timestamp"] >= MetaInfo.get(symbol,"ts_last_close")) &
                            (dataframe["timestamp"] <= ts_last_open)
                        )

                MetaInfo.set(symbol,{"pre_low":  float(dataframe.loc[mask, "low"].min()), 
                                        "pre_high" : float(dataframe.loc[mask, "high"].max())})
                pre_gain= 100 * (close -   MetaInfo.get(symbol,"last_close")) /   MetaInfo.get(symbol,"last_close")
                pre_gain_LH= float(100 * (  MetaInfo.get(symbol,"pre_high") -   MetaInfo.get(symbol,"pre_low")) /   MetaInfo.get(symbol,"pre_low"))

                MetaInfo.set(symbol,{"pre_gain":  pre_gain , "pre_gain_LH" : pre_gain_LH})
            

            ## CALCOLO GAP SU close <> last_open
            close = dataframe.iloc[local_index]["close"]
            gap = 100 * (close - MetaInfo.get(symbol,"last_open")) /  MetaInfo.get(symbol,"last_open")
            MetaInfo.set(symbol,{"gap" : gap})

    ###########



            

    
