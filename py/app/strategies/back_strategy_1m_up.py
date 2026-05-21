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


class BackStrategyIB_1m_up(SmartStrategy):

    async def on_start(self):
        self.min_day_volume= self.params["min_day_volume"]
        self.max_back_steps= self.params["max_back_steps"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]
        self.gain_perc = 5#self.params["gain_perc"]
        self.drop_time_secs= self.params["drop_time_secs"]
        self.loss_by_trade=100

    def populate_indicators(self) :
      
       
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        sma_25 = self.addIndicator(self.timeframe,SMA("sma_25","close",25))
       

         #self.add_plot(max_1w, "max_1w","#412F00FF", "main",style="Dotted", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        

        self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        last = dataframe.iloc[local_index]
        vol_day = last["vol_day"]    
        gain_day = last["gain_day"] 
        if not self.hasCurrentTrade(symbol) and (vol_day < self.min_day_volume or gain_day < 1):
             return

        #################

        prev = dataframe.iloc[local_index-1]

      
        price = last["close"]
        vol = last["quote_volume"]
       
       
        gain =  (price - prev["close"]) / prev["close"] * 100
         
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "state": "WAITING"}})
        ai = self.get_meta(symbol,"ai")   

        if not self.hasCurrentTrade(symbol):
            if  gain > 2:

                q = self.get_quantity( self.loss_by_trade, price    )
                await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )


        elif self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
            
            #logger.info(f"gg {gain}")

            if time_elapsed_secs > 5:
                
                if  gain >self.gain_perc:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
            
                elif  gain < -self.gain_perc/2:
                    await  self.sell(symbol, dt, last["close"], f"SL"  )

             