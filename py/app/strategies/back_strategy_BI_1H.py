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

class MIN_WAVE(Indicator):

    def __init__(
        self,
        target,
        source,
        window=11,
        polyorder=3,
        atr_period=14,
        threshold_mult=0.15,
    ):
        super().__init__([target])

        self.target = target
        self.source = source

        # Savitzky-Golay
        self.window = window
        self.polyorder = polyorder

        # filtro rumore
        self.atr_period = atr_period
        self.threshold_mult = threshold_mult

    def compute_fast(
        self,
        symbol,
        dataframe: pd.DataFrame,
        symbol_idx,
        from_local_index
    ):

        # array numpy
        dest = dataframe[self.target].to_numpy()

        close = dataframe[self.source].to_numpy()
        high = dataframe["high"].to_numpy()
        low = dataframe["low"].to_numpy()

        # range simbolo
        idxs = np.array(symbol_idx)

        if len(idxs) < self.window:
            return

        # -----------------------------------------
        # PRICE
        # -----------------------------------------

        # OHLC4 -> meno rumore del close
        price = (
            dataframe["open"].to_numpy()[idxs] +
            high[idxs] +
            low[idxs] +
            close[idxs]
        ) / 4.0

        # -----------------------------------------
        # SMOOTHING
        # -----------------------------------------

        # window dispari obbligatoria
        win = self.window
        if win % 2 == 0:
            win += 1

        smooth = savgol_filter(
            price,
            window_length=win,
            polyorder=self.polyorder
        )

        # -----------------------------------------
        # DERIVATE
        # -----------------------------------------

        # prima derivata
        d1 = np.gradient(smooth)

        # seconda derivata = curvatura
        d2 = np.gradient(d1)

        # -----------------------------------------
        # ATR
        # -----------------------------------------

        h = high[idxs]
        l = low[idxs]
        c = close[idxs]

        prev_close = np.roll(c, 1)
        prev_close[0] = c[0]

        tr = np.maximum(
            h - l,
            np.maximum(
                np.abs(h - prev_close),
                np.abs(l - prev_close)
            )
        )

        atr = (
            pd.Series(tr)
            .rolling(self.atr_period)
            .mean()
            .to_numpy()
        )

        # evita divisioni
        atr = np.where(atr == 0, 1e-9, atr)

        # -----------------------------------------
        # CURVATURA NORMALIZZATA
        # -----------------------------------------

        curvature = d2 / atr

        # -----------------------------------------
        # SIGNAL
        # -----------------------------------------

        start = max(2, from_local_index)

        for local_i in range(start, len(idxs)):

            idx = idxs[local_i]

            prev_curv = curvature[local_i - 1]
            curv = curvature[local_i]

            threshold = atr[local_i] * self.threshold_mult

            # NaN protection
            if np.isnan(curv) or np.isnan(prev_curv):
                dest[idx] = 0
                continue

            signal = 0

            # cambio convessità rialzista
            if (
                prev_curv < 0 and
                curv > 0 and
                abs(curv) > threshold
            ):
                signal = 1

            # cambio convessità ribassista
            elif (
                prev_curv > 0 and
                curv < 0 and
                abs(curv) > threshold
            ):
                signal = -1

            dest[idx] = signal

class MIN_WAVE1(Indicator):
    def __init__(self, target,source):
        super().__init__([target])
        self.target=target
        self.source=source

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        # 1. Riferimenti agli array numpy per le performance ⚡
        dest = dataframe[self.target].to_numpy()
        source = dataframe[self.source].to_numpy()

        # 2. Definiamo il range di calcolo
        # Partiamo da from_local_index per non ricalcolare il passato
        start = max(0, from_local_index)
        
     
        # 4. Assegnazione incrementale
        for i, i_idx in enumerate(range(start, len(symbol_idx))):
            idx = symbol_idx[i_idx]
            if i_idx>0:
                s = 1 if source[idx] > source[symbol_idx[i_idx-1]] else -1
                if sign(s) != sign(dest[symbol_idx[i_idx-1]]):
                    dest[idx] = s
                else:
                    dest[idx] =  dest[symbol_idx[i_idx-1]]+s 
                #dest[idx] = sign
            else:
                dest[idx] =0


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
        self.max_back_steps= self.params["max_back_steps"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]
        self.gain_perc = self.params["gain_perc"]
        self.drop_time_secs= self.params["drop_time_secs"]
        self.loss_by_trade=10

    def populate_indicators(self) :
      
        max_1w= self.addIndicator(self.timeframe,MAX("max_1w","close", self.max_back_steps))

        #vol_day= self.addIndicator(self.timeframe,SUM("vol_day","quote_volume",1440))
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        sma_25= self.addIndicator(self.timeframe,SMA("sma_25","close",25))

        curva= self.addIndicator(self.timeframe,ANGLE_PERC("curva","sma_25",scale = 100))
        smooth= self.addIndicator(self.timeframe,SMOOTH("smooth","curva"))
        sma_trend = self.addIndicator(self.timeframe,TREND_LIMIT("sma_trend","smooth")) 
        sma_trend_inc = self.addIndicator(self.timeframe,TREND_INC("sma_trend_inc","smooth")) 

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        vwap_trend = self.addIndicator(self.timeframe, W_TREND("vwap_trend","vwap_trend_sign","vwap"))

        #vwap_perc = self.addIndicator(self.timeframe, DIFF_PERC("vwap_perc","vwap","vwap"))

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        self.add_plot(max_1w, "max_1w","#926B00FF", "main",style="Dotted", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        
        self.add_plot(vwap, "vwap_perc","#1bd303","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_pos","#d30337","sub1","vwap_pos", style="Solid", lineWidth=1)

        #self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        
        #self.add_plot(curva, "curva","#052500","sub1","curva", style="Solid", lineWidth=1)
        self.add_plot(smooth, "smooth","#052500","sub1","smooth", style="Solid", lineWidth=1)
        self.add_plot(sma_trend, "sma_trend","#052500","sub1","sma_trend", style="Solid", lineWidth=1)
        self.add_plot(sma_trend_inc, "sma_trend_inc","#052500","sub1","sma_trend_inc", style="Solid", lineWidth=1)
        
      
     
        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        

        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        if local_index < 1:
            return
        
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "STATE": "WAITING","MAX_GAIN": 0}})
        ai = self.get_meta(symbol,"ai")   

    
        last = dataframe.iloc[local_index]
        vol_day = last["vol_day"]    
        gain_day = last["gain_day"] 
        sma_25= last["sma_25"] 
        if not self.hasCurrentTrade(symbol)  and ai["STATE"] == "WAITING" and (vol_day < self.min_day_volume and gain_day < 0):
             return

        prev = dataframe.iloc[local_index-1]

        max_1w = last["max_1w"]
        price = last["close"]
        vol = last["quote_volume"]
        vwap = last["vwap"]
        vwap_down = last["vwap_down"]
        
        trend =  last["vwap_trend"] * last["vwap_trend_sign"]
        last_trend =  prev["vwap_trend"] * prev["vwap_trend_sign"]
        
        vwap_perc = last["vwap_perc"]
        trend_pos =  last["vwap_pos"]

        gain_last = (price - prev["close"]) / prev["close"]*100
        gain_v = (vol - prev["quote_volume"]) / prev["quote_volume"]*100
        
        #logger.info(f'{last["datetime"]} {price > last["open"] } {ai["STATE"] }')
        top = (last["close"]  - last["low"]) / (last["high"]-last["low"]) * 100
        is_up = last["close"] > last["open"]
        is_up_prev = prev["close"] > prev["open"]

        sma_trend =  last["sma_trend"]
        sma_trend_inc =  last["sma_trend_inc"]
        
        sma_smooth =  last["smooth"]

        #if  top> 80 and price > last["open"]:
        #    await self.add_marker(symbol,"SPOT",f"{top:.1f}",f"{top:.1f}","#FF0000")
        
    
       # if trend_pos< -10:
       #     await self.add_marker(symbol,"SPOT",f"v",f"v","#FF0000",value= last["low"])
       # if is_up_prev :
       #     await self.add_marker(symbol,"SPOT",f"-",f"-","#FF0000")

        #logger.info(f"  {last['datetime']} {  ai['STATE'] } {trend_pos}")
        
        if not self.hasCurrentTrade(symbol):
            if ai["STATE"] == "WAITING":
                #if sma_trend>7 and prev["smooth"]<30:#  and sma_smooth>30:

                #6/7 107
                
                #if sma_trend>5 and prev["smooth"]>45:#  and sma_smooth>30:
                #46/76	256%
                #if sma_trend_inc>3 and sma_smooth>20:#  and sma_smooth>30:

                #19/18	257%
                if sma_trend_inc>3 and sma_smooth>30:#  and sma_smooth>30:


                #if prev["smooth"]<0  and sma_smooth>10:
                #if sma_trend>7 and prev["smooth"]>40:
                   # ai["STATE"] ="DOWN"
          
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
                
            elif gain< -vwap_perc/4:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"SL"  )
          

        '''
        if not self.hasCurrentTrade(symbol):
            if gain_last > vwap_perc / self.gain_perc:
                q = self.get_quantity( self.loss_by_trade, price    )
                await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

        elif self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
    
            if last["low"] < prev["low"]:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"TP"  )
        '''

        '''
        if not self.hasCurrentTrade(symbol):
            if trend_pos > 95 and price > last["open"]:
                q = self.get_quantity( self.loss_by_trade, price    )
                await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )
    
        elif self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
    
            if last["low"] < prev["low"]:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"TP"  )
        ''' 
        '''

        if not self.hasCurrentTrade(symbol):
            #if ai["STATE"] == "WAITING":
            #   if trend_pos < 50:
            #        ai["STATE"] = "DOWN"
            #        await self.add_marker(symbol,"SPOT","D","D","#FF0000")
            #if ai["STATE"] == "DOWN":
                if price < sma_25:
                    ai["STATE"] = "WAITING"
                #elif last["vwap_pos"] > 50 and last["vwap_pos"]  > prev["vwap_pos"] :
                elif  last["vwap_pos"] > 50 and top> 85 and price > last["open"]:
                    ai["STATE"] = "UP"
                    ai["vwap_perc"] = vwap_perc
                    #await self.add_marker(symbol,"SPOT","U","U","#FF0000")
                    q = self.get_quantity( self.loss_by_trade, price    )
                    await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

        elif self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
        
            await self.add_marker(symbol,"SPOT",f"{gain:.1f}",f"{gain:.1f}","#FF0000")

            if trend_pos < 45:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"SL"  )

            if last["low"] < prev["low"]:
            #elif gain_last> 0:#ai["vwap_perc"]/2:
                ai["STATE"] = "WAITING"      
                await  self.sell(symbol, dt, last["close"], f"TP"  )

        '''

        '''
        #logger.info(f'{last["datetime"]} {price > last["open"] } {ai["STATE"] }')
        if not self.hasCurrentTrade(symbol):
            if ai["STATE"] == "WAITING":
                if gain > 5 and trend_pos> 90:
                    ai["STATE"] = "UP"
                    ai["signal"] = last["vwap"] -  prev["vwap"] * 0.05
                    await self.add_marker(symbol,"SPOT","UP","UP","#FF0000")
                    await self.add_marker(symbol,"SPOT","S","S","#FF0000",value = ai["signal"]  )

            elif ai["STATE"] == "UP" or (last["open"] > price and ai["STATE"] == "DOWN"):
                if last["open"] > price:
                    ai["STATE"] = "DOWN"
                    #ai["signal"] = last["low"] -  last["low"] * 0.01
                    #ai["signal"] = last["vwap"] -  last["vwap"] * 0.01
                    await self.add_marker(symbol,"SPOT",ai["STATE"],ai["STATE"],"#FF0000", value =  last["low"] ) 
                else:
                    await self.add_marker(symbol,"SPOT",".",".","#FF0000", value = last["low"]) 
                    
            elif ai["STATE"] == "DOWN":
                if price > last["open"]:
                    if trend_pos < 33:
                        ai["STATE"] = "BUY"       
                        q = self.get_quantity( self.loss_by_trade, price    )
                        await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )
                    else:
                        ai["STATE"] = "UP"      
                        await self.add_marker(symbol,"SPOT","U2","U2","#FF0000")
                else:
                    await self.add_marker(symbol,"SPOT",".",".","#FF0000", value = last["low"]) 


        elif self.hasCurrentTrade(symbol):

            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   

            if time_elapsed_secs> 60*60*4 and gain <-1:
                await  self.sell(symbol, dt, last["close"], f"TIME"  )
                ai["STATE"] = "WAITING"  

            else:
                if price <  ai["signal"] :
                    await  self.sell(symbol, dt, last["close"], f"SL"  )
                    ai["STATE"] = "WAITING"       

                if trend_pos > 50:
                    ai["STATE"] = "BUY_50"       
                elif  ai["STATE"] == "BUY_50":
                    if trend_pos > 90:
                        await  self.sell(symbol, dt, last["close"], f"TPU"  )
                        ai["STATE"] = "WAITING"      
                    if trend_pos < 50:
                        await  self.sell(symbol, dt, last["close"], f"TPD"  )
                        ai["STATE"] = "WAITING"     
        '''