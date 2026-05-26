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
from scipy.signal import savgol_filter
sign = lambda x: math.copysign(1, x) # two will work

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *

class SMA(Indicator):

    def __init__(self, target_col, source_col: str, timeperiod: int):
        super().__init__([target_col])

        self.source_col = source_col
        self.target_col = target_col
        self.window = timeperiod

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        w = self.window

        if len(symbol_idx) == 0:
            return

        # prima esecuzione -> calcolo completo
        if from_local_index == 0:

            rolling_sum = 0.0

            for i in range(len(symbol_idx)):

                idx = symbol_idx[i]

                rolling_sum += source[idx]

                if i >= w:
                    rolling_sum -= source[symbol_idx[i - w]]

                current_window = min(i + 1, w)

                dest[idx] = rolling_sum / current_window

            return

        # ---------------------------
        # aggiornamento incrementale
        # ---------------------------

        i = from_local_index
        idx = symbol_idx[i]

        # ricostruisci somma finestra precedente
        start_window = max(0, i - w + 1)

        rolling_sum = 0.0

        for j in range(start_window, i + 1):
            rolling_sum += source[symbol_idx[j]]

        current_window = min(i + 1, w)

        dest[idx] = rolling_sum / current_window


class TREND_INC(Indicator):
  
    def __init__(self,target_col, signal:int, outlier_std=2):
        super().__init__([target_col])
        self.target_col=target_col
        self.signal=signal
        self.outlier_std = outlier_std
        self.trend_map={}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.signal].to_numpy()

        count = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            if  source[symbol_idx[i_idx]] >source[symbol_idx[i_idx-1]]:
                count=count+1
            else:
                count=0
            dest[symbol_idx[i_idx]] =count

#################################################

class BackStrategyIB_1H(SmartStrategy):

    async def on_start(self):
        self.min_day_volume= self.params["min_day_volume"]
        self.gain_perc = self.params["gain_perc"]
        self.stop_loss = self.params["stop_loss"]
        self.smooth_thresold= self.params["smooth_thresold"]
        self.smooth_trend_inc= self.params["smooth_trend_inc"]
        self.sma= self.params["sma"]
        self.min_day_gain= self.params["min_day_gain"]

        self.loss_by_trade=75
        logger.info(f"TRADE USD {self.loss_by_trade}" )

    def populate_indicators(self) :
      
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))

        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        sma_25= self.addIndicator(self.timeframe,SMA("sma_25","close",self.sma))

        #curva= self.addIndicator(self.timeframe,ANGLE_PERC("curva","sma_25",scale = 100))
        curva1= self.addIndicator(self.timeframe,GAIN("curva1","sma_25",timeperiod = 1))
        curva= self.addIndicator(self.timeframe,MULT("curva","curva1",100))

        smooth= self.addIndicator(self.timeframe,SMOOTH("smooth","curva"))

        sma_trend = self.addIndicator(self.timeframe,TREND_LIMIT("sma_trend","smooth")) 
        sma_trend_inc = self.addIndicator(self.timeframe,TREND_INC("sma_trend_inc","smooth")) 

        #self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        #self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        self.add_plot(sma_25, "sma_25","#06a800", "main","sma_25", style="Dotted", lineWidth=1)

        #self.add_plot(curva, "curva","#052500","sub1","curva", style="Solid", lineWidth=1)
        self.add_plot(curva, "curva","#052500","sub1","curva", style="Solid", lineWidth=1)

        self.add_plot(smooth, "smooth","#052500","sub1","smooth", style="Solid", lineWidth=1)
        self.add_plot(sma_trend, "sma_trend","#052500","sub1","sma_trend", style="Solid", lineWidth=1)
        self.add_plot(sma_trend_inc, "sma_trend_inc","#052500","sub1","sma_trend_inc", style="Solid", lineWidth=1)
        

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        self.init_symbol(symbol,dataframe.iloc[local_index])
        
        
        #########################
        
       # if symbol != "MORPHOUSDC":
       #     return
        
        last = dataframe.iloc[local_index]
        #logger.info(f"!! {symbol} {last['datetime']} {last['close']} sma:{last['sma_25'] }")
        #logger.info(f"\n{dataframe.tail(10)}")
        
        if not self.bootstrapMode:
            last = dataframe.iloc[local_index]
            logger.info(f"!! {symbol} {last['datetime']} {last['close']}")

            logger.info(f"\n{dataframe.tail(2)}")
            #logger.info("TICK")
            #return
        
        if local_index < 1:
            return
            
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "STATE": "WAITING","MAX_GAIN": 0}})
        ai = self.get_meta(symbol,"ai")   

    
        last = dataframe.iloc[local_index]
   
        gain_day = last["gain_day"] 
        vol_day = last["vol_day"]
        sma_25= last["sma_25"] 

        if not self.hasCurrentTrade(symbol)  and ai["STATE"] == "WAITING" and vol_day >= self.min_day_volume  and (gain_day < self.min_day_gain):
             return

        prev = dataframe.iloc[local_index-1]

        
        price = last["close"]
        vol = last["quote_volume"]
      
        gain_last = (price - prev["close"]) / prev["close"]*100
        gain_v = (vol - prev["quote_volume"]) / prev["quote_volume"]*100
        
        #logger.info(f'{last["datetime"]} {price > last["open"] } {ai["STATE"] }')
        top = (last["close"]  - last["low"]) / (last["high"]-last["low"]) * 100
        is_up = last["close"] > last["open"]
        is_up_prev = prev["close"] > prev["open"]

        sma_trend =  last["sma_trend"]
        sma_trend_inc =  last["sma_trend_inc"]
        
        sma_smooth =  last["smooth"]
 
        #q = self.get_quantity( self.loss_by_trade, price  )  
        #await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

        if not self.hasCurrentTrade(symbol):
            if ai["STATE"] == "WAITING":
                #if sma_trend>7 and prev["smooth"]<30:#  and sma_smooth>30:

                #6/7 107
                
                #if sma_trend>5 and prev["smooth"]>45:#  and sma_smooth>30:
                #46/76	256%
                #if sma_trend_inc>3 and sma_smooth>20:#  and sma_smooth>30:

                #19/18	257%
                if sma_trend_inc>=self.smooth_trend_inc and sma_smooth>self.smooth_thresold:#  and sma_smooth>30:

                    if prev["smooth"]<self.smooth_thresold:
                    #if sma_trend>7 and prev["smooth"]>40:
                    # ai["STATE"] ="DOWN"
                        logger.info(f"inc: {sma_trend_inc} sma:{sma_smooth} prev:{prev['smooth']}")
                        #ai["STATE"] = "WAITING"      
                        q = self.get_quantity( self.loss_by_trade, price  )  
                        await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

            
                
        elif self.hasCurrentTrade(symbol):
          
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000 
              
            ai["MAX_GAIN"] = max(ai["MAX_GAIN"], gain)
            less_gain =  ai["MAX_GAIN"]  - gain
            
            #if gain> vwap_perc/2:
            #if less_gain>vwap_perc/8:
            
            if ai["STATE"] == "WAITING":
                 if price > sma_25 :
                      ai["STATE"] = "UP"     
                     
            if ai["STATE"] == "UP":
                if price < sma_25 :
                    ai["STATE"] = "WAITING"      
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
            
            #if price < prev["low"]:
            #    ai["STATE"] = "WAITING"        
            #    await  self.sell(symbol, dt, last["close"], f"SL"  )
            #elif gain< self.stop_loss:
            #    ai["STATE"] = "WAITING"      
            #    await  self.sell(symbol, dt, last["close"], f"SL"  )

            if less_gain >self.stop_loss:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"SL"  )
            #elif gain< -vwap_perc/4:
            #    ai["STATE"] = "WAITING"      
            #    await  self.sell(symbol, dt, last["close"], f"SL"  )
          
