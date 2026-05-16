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


class BackStrategyIB15_3(SmartStrategy):

    async def on_start(self):
        self.min_day_volume= self.params["min_day_volume"]
        self.max_back_steps= self.params["max_back_steps"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]
        self.gain_perc = self.params["gain_perc"]
        self.drop_time_secs= self.params["drop_time_secs"]
        self.loss_by_trade=100

    def populate_indicators(self) :
      
        max_1w= self.addIndicator(self.timeframe,MAX("max_1w","close", self.max_back_steps))

        #vol_day= self.addIndicator(self.timeframe,SUM("vol_day","quote_volume",1440))
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        self.addIndicator(self.timeframe,SMA("sma_25","close",25))
        sma_vol = self.addIndicator(self.timeframe,SMA("sma_vol","quote_volume",4*24))

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        vwap_trend = self.addIndicator(self.timeframe, W_TREND("vwap_trend","vwap_trend_sign","vwap"))

        vwap_perc_gain = self.addIndicator(self.timeframe,GAIN("vwap_perc_gain","vwap_perc",1))

        #vwap_perc = self.addIndicator(self.timeframe, DIFF_PERC("vwap_perc","vwap","vwap"))

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        self.add_plot(max_1w, "max_1w","#926B00FF", "main",style="Dotted", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        
        self.add_plot(vwap, "vwap_perc","#1bd303","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_pos","#d30337","sub1","vwap_pos", style="Solid", lineWidth=1)

        self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        
        self.add_plot(sma_vol, "sma_vol","#0311d3","sub1","sma_vol", style="Solid", lineWidth=1)

        self.add_plot(vwap_perc_gain, "wpg","#0311d3","sub1","vwap_perc_gain", style="Solid", lineWidth=1)
       
     
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        

        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        last = dataframe.iloc[local_index]
        vol_day = last["vol_day"]    
        gain_day = last["gain_day"] 
        if (vol_day < self.min_day_volume or gain_day < 1):
             return

        prev = dataframe.iloc[local_index-1]

        max_1w = last["max_1w"]
        price = last["close"]
        vol = last["quote_volume"]
        vwap = last["vwap"]
        vwap_down = last["vwap_down"]
        sma_25 = last["sma_25"]
        sma_vol= last["sma_vol"]
        
        trend =  last["vwap_trend"] * last["vwap_trend_sign"]
        last_trend =  prev["vwap_trend"] * prev["vwap_trend_sign"]
        
        vwap_perc = last["vwap_perc"]
        trend_pos =  last["vwap_pos"]

        gain =  (price - prev["close"]) / prev["close"] * 100
        v_gain =  (vol - prev["vol_day"]) / prev["vol_day"] * 100
        vwap_perc_gain =  ( last["vwap_perc"] - prev["vwap_perc"]) / prev["vwap_perc"] * 100
        
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "state": "WAITING"}})
        ai = self.get_meta(symbol,"ai")   

        if not self.hasCurrentTrade(symbol):
            #if price > sma_25 and vwap_perc > 95 and gain > 1 and vol  >  sma_vol* 5:
            if vwap_perc>95 and vwap_perc_gain > 0.5: #and vwap_perc> 5 and vwap_perc_gain > 1 and vol  >  sma_vol* 2:
                q = self.get_quantity( self.loss_by_trade, price    )
                await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

        if self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
            
            #if time_elapsed_secs > 60*15:
            if True:
                if gain < 1 and time_elapsed_secs > self.drop_time_secs:
                    await  self.sell(symbol, dt, last["close"], f"TIME"  )
                    ai["state"] = "WAITING"
                
            
                if price < sma_25:
                    await  self.sell(symbol, dt, last["close"], f"="  )
                    ai["state"] = "WAITING"
                
                if  gain >self.gain_perc:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
            
               
            #if trend_pos < 50 :
            #    await self.sell( symbol, int(last["timestamp"]), price,  "SL" ) 