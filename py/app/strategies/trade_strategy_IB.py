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
        self.volume_min_filter= 500_000#self.params["volume_min_filter"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]

   # def extra_dataframes(self)->List[str]:
   #     return ['15m']

    def populate_indicators(self) :
      
       # max_1w= self.addIndicator("15m",MAX("MAX_1W","close",4*24*7))

        #vol_day= self.addIndicator("1m",SUM("vol_day","quote_volume",1440))
        #vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        #vol_sma= self.addIndicator(self.timeframe,SMA("vol_sma","quote_volume",1440))

        #self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        max_1h= self.addIndicator(self.timeframe,MAX("MAX_1H","close",60*2))
        max_1d= self.addIndicator(self.timeframe,MAX("MAX_1D","close",60 * 24))

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        self.add_plot(max_1h, "MAX_1H","#926B00FF", "main",style="Dotted", lineWidth=1)
        self.add_plot(max_1d, "MAX_1D","#009266FF", "main", style="Solid", lineWidth=1)

        #self.add_plot(vol_day, "vol_day","#003000FF", "sub",style="Solid", lineWidth=1)

        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        #if not self.bootstrapMode:
        #     logger.info(f"..\n{dataframe.tail(3)}")
        use_day=True

        if local_index < 2:
            return
   
        
        last = dataframe.iloc[local_index]


        if not self.bootstrapMode:
            logger.info(f".. {symbol} {last['datetime']} ")

        vol_day = last["quote_day_volume"]           
       
        # META
        vol_diff = last["base_volume"]     
        vol_quote_diff = last["quote_volume"]     

        await self.set_property(symbol,{"volume_diff":vol_diff, "volume_diff_quote" : vol_quote_diff})

        ###
        
        if vol_day > self.volume_min_filter:
            
            prev = dataframe.iloc[local_index-1]
            prev2 = dataframe.iloc[local_index-2]

            #vol_sma = last["vol_sma"]    
            MAX_1H = last["MAX_1H"]    
            MAX_1D = last["MAX_1D"]    
            
            df_15m= self.df("15m",symbol)
            
           # max_1w = df_15m.iloc[-1]["MAX_1W"]

            #gain2 =  last["gain"] 
            gain = (last["close"] - prev["close"]) / prev["close"] * 100    
            gain2 = (last["close"] - prev2["close"]) / prev2["close"] * 100    

            #last_1d = self.df("1d",symbol).iloc[-1]
            #last_1d = df_1d.iloc[-1]
            #if symbol =="ZECUSDC":
            #     logger.info(f"\n{max_1w}")

            if gain >= 1:
                   await self.add_marker(symbol,"SPOT",f"Gain {gain:.1f}",f"Gain {gain:.1f}","#F6F7F86F","square",position ="atPriceTop")

           # if last["close"] > max_1w and not self.has_meta(symbol,"max_1w" ):
           #        self.set_meta(symbol, {"max_1w":True})
           #        await self.add_marker(symbol,"SPOT",f"MAX 1W",f"MAX 1W","#BB9A086C","square",position ="atPriceTop")
           
            elif MAX_1D > prev["MAX_1D"]:
                   await self.add_marker(symbol,"SPOT",f"MAX 1D",f"MAX 1D","#08BB356D","square",position ="atPriceTop")
            
            #elif MAX_1H > prev["MAX_1H"]:
            #       await self.add_marker(symbol,"SPOT",f"MAX 2H",f"MAX 2H","#0861BB6E","square",position ="atPriceTop",ring="")

            #vol_perc =  (last["quote_volume"]- vol_sma) /vol_sma * 100
            #if gain>0 and vol_perc>100:
            #       await self.add_marker(symbol,"SPOT",f"VOL>{vol_perc:.1f}%",f"VOL>{vol_perc:.1f}%","#BB089D6C","square",position ="atPriceBottom")

