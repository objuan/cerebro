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


class VolumeStrength(Indicator):

    def __init__(self, target_col, price_col: str, volume_col: str, period: int):
        super().__init__([target_col])
        self.price_col = price_col
        self.volume_col = volume_col
        self.target_col = target_col
        self.period = period

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        price = dataframe[self.price_col].to_numpy()
        volume = dataframe[self.volume_col].to_numpy()

        start = max(1, from_local_index)

        for i_idx in range(start, len(symbol_idx)):

            num = 0.0
            den = 0.0

            r = range(max(1, i_idx - self.period + 1), i_idx + 1)

            for j_idx in r:
                curr = symbol_idx[j_idx]
                prev = symbol_idx[j_idx - 1]

                #ret = (price[curr] - price[prev]) / price[prev]
                
                ret = math.log(price[curr] / price[prev])

                vol = volume[curr]

                num += ret * vol
                den += vol

            if den > 0:
                dest[symbol_idx[i_idx]] =  (num / den) * 100
            else:
                dest[symbol_idx[i_idx]] = 0.0

class STRENGHT(Indicator):
  
    def __init__(self,target_col,  timeperiod:int):
        super().__init__([target_col])
        self.target_col=target_col
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        volume = dataframe["base_volume"].to_numpy()
        close = dataframe["close"].to_numpy()
        '''
        strength = 100.0 * (last["close"] - dataframe.iloc[local_index-back]["close"]) /  dataframe.iloc[local_index-5]["close"]
        v=0
        for i  in [0,1,2,3,4]:
            v += dataframe.iloc[local_index-i]["day_volume_history"] * dataframe.iloc[local_index-i]["close"]
        v = v / back
        '''
        for i_idx in range(from_local_index,len(symbol_idx) ):
                    sum=0.0
                    r = range(max(0,i_idx- self.window+1), i_idx+1 )
                    for j_idx in r:
                        sum+= close[symbol_idx[j_idx]] * volume[symbol_idx[j_idx]] 
                    sum=sum/ len(r)
                    #logger.info(f"sum {i_idx} {symbol_idx[i_idx]}= {sum}")
                    dest[symbol_idx[i_idx]] =sum

class CHAIN(Indicator):
  
    def __init__(self,target_col,  source, timeperiod:int):
        super().__init__([target_col])
        self.target_col=target_col
        self.source=source
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source].to_numpy()
        volume = dataframe["base_volume"].to_numpy()
     
        for i_idx in range(from_local_index,len(symbol_idx) ):
            sum=True
            r = range(max(0,i_idx- self.window+1), i_idx+1 )
            for j_idx in r:
                sum = sum and source[symbol_idx[j_idx]] >= source[symbol_idx[j_idx-1]] #and volume[symbol_idx[j_idx]]>0
                 
            dest[symbol_idx[i_idx]] =1 if sum else 0

############################################

class TradeStrategy10S(SmartStrategy):

    async def on_start(self):
        self.volume_min_filter= self.params["volume_min_filter"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        self.trade_last_hh= self.params["trade_last_hh"]

    def populate_indicators(self) :
      
        #max_day = self.addIndicator("1m",MAX_DAY("max_day","close"))

        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        # str= self.addIndicator(self.timeframe,VolumeStrength("str","close","base_volume", 6))
        ema =  self.addIndicator(self.timeframe,EMA("ema","quote_volume",6))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        max= self.addIndicator(self.timeframe,MAX("MAX","close",6*10))

        #chain= self.addIndicator(self.timeframe,CHAIN("chain","close",3))
      
       # self.add_plot(chain, "chain","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(day_volume_history, "day_volume_history","#d3035a", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(str, "str","#f70b03" "sub1", style="Solid", lineWidth=1)

        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)

        #self.add_plot(max_day, "max_day","#009200FF", "main", source="max_day",style="Solid", lineWidth=1)

        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        #if not self.bootstrapMode:
        #     logger.info(f"..\n{dataframe.tail(3)}")
        use_day=True

        if local_index < 2:
            return
   
        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]
        prev2 = dataframe.iloc[local_index-2]

        volume = last["day_volume_history"]           
        #gain2 =  last["gain"] 
        gain = (last["close"] - prev["close"]) / prev["close"] * 100    
        gain2 = (last["close"] - prev2["close"]) / prev2["close"] * 100    

        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(4,0),get_hour_ms(self.trade_last_hh,00),use_day):
        

            if volume > self.volume_min_filter:
                #prev_close = prev["close"]
                #break_max = last["close"] >= MAX and prev_close < MAX
                
                
                #if (last["MAX"]>  prev["MAX"] ):
                #    await self.add_marker(symbol, "SPOT", "MAX10", f"max 10",color="#31F30A", ring="alert1")
            
                '''
                if last["close"] > self.get_meta(symbol,"max_day_price"):
                    await self.add_marker(symbol, "SPOT", "DAY_MAX", f"day max {day_gain:.1f}",color="#31F30A", ring="alert1")  
                '''
                
                if gain2 > self.gain_2_perc:
                    if (gain > gain2/2):
                        await self.add_marker(symbol, "SPOT", "GAIN", f"Gain 10 {gain:.1f}/{gain2:.1f}",color="#575757", ring="alert1")


       