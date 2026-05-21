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



class LOW_SUCC(Indicator):
    def __init__(self, target):
        super().__init__([target])
        self.target=target
        self.cum_count = {}   
      
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
      
        dest = dataframe[self.target].to_numpy()
        signal = dataframe["low"].to_numpy()

        start = max(0, from_local_index)
     
        if symbol not in self.cum_count:
            self.cum_count[symbol] = 0

        for i_idx in range(start, len(symbol_idx)):
            idx = symbol_idx[i_idx]
            if idx > 0:
                ok = signal[idx] >signal[symbol_idx[i_idx-1]]
                if ok:
                    self.cum_count[symbol]+=1
                else:
                    self.cum_count[symbol]=0

                dest[idx] = self.cum_count[symbol]
            else:
                self.cum_count[symbol]=0
                dest[idx] = 0


class BackStrategyIB5_moment(SmartStrategy):

    async def on_start(self):
        self.min_day_volume= self.params["min_day_volume"]
        self.max_back_steps= self.params["max_back_steps"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]
        self.gain_perc = 3#self.params["gain_perc"]
        self.drop_time_secs= self.params["drop_time_secs"]
        self.loss_by_trade=100

    def populate_indicators(self) :
      
        max_1w= self.addIndicator(self.timeframe,MAX("max_1w","close", self.max_back_steps))

        #vol_day= self.addIndicator(self.timeframe,SUM("vol_day","quote_volume",1440))
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        sma_25 = self.addIndicator(self.timeframe,SMA("sma_25","close",25))
        low_succ = self.addIndicator(self.timeframe,LOW_SUCC("low_succ"))
        

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        vwap_trend = self.addIndicator(self.timeframe, W_TREND("vwap_trend","vwap_trend_sign","vwap"))

        signal = self.addIndicator(self.timeframe, DIFF_PERC("signal","sma_25","low"))

        ###########

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        #self.add_plot(max_1w, "max_1w","#412F00FF", "main",style="Dotted", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        
        self.add_plot(vwap, "vwap_perc","#003530","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_pos","#271b5f8f","sub1","vwap_pos", style="Solid", lineWidth=1)

        self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        
        self.add_plot(signal, "signal","#0311d3","signal","signal", style="Solid", lineWidth=1)
        
        self.add_plot(low_succ, "low_succ","#035300","low_succ","low_succ", style="Solid", lineWidth=1)
        
    def init_trade_mask(self,symbol):

        df = self.client.get_df("select * from ib_scan_watch where symbol = ? and ts_enter >= ",  (symbol))
        
        logger.info(f"... \n{df}")

        pass

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        if local_index < 25:
            return
        
        last = dataframe.iloc[local_index]
        vol_day = last["vol_day"]    
        gain_day = last["gain_day"] 
        if not self.hasCurrentTrade(symbol) and (vol_day < self.min_day_volume or gain_day < 1):
             return

        #################

        prev = dataframe.iloc[local_index-1]

        max_1w = last["max_1w"]
        price = last["close"]
        vol = last["quote_volume"]
        vwap = last["vwap"]
        vwap_down = last["vwap_down"]
        sma_25 = last["sma_25"]
        low_succ= last["low_succ"]
        signal= last["signal"]
        
        trend =  last["vwap_trend"] * last["vwap_trend_sign"]
        last_trend =  prev["vwap_trend"] * prev["vwap_trend_sign"]
        
        vwap_perc = last["vwap_perc"]
        trend_pos =  last["vwap_pos"]
        trend_pos_low =  (last["low"] - last["vwap_down"]) / (last["vwap_up"] - last["vwap_down"]) * 100

        gain =  (price - prev["close"]) / prev["close"] * 100
        v_gain =  (vol - prev["vol_day"]) / prev["vol_day"] * 100
        
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "state": "WAITING"}})
        ai = self.get_meta(symbol,"ai")   

        
        if not self.hasCurrentTrade(symbol):

            if (ai["state"] =="WAITING" and trend >60) or  ai["state"] =="MID":
                      if abs(trend_pos_low-50) < 2   :   
                        ai["state"] = "MID"
                        ai["close"] = price 
                        ai["open"] = last["open"] 
                        ai["low"] = last["low"]
                        ai["high"] = last["high"]

                        await self.add_marker(symbol,"SPOT","v","v","#FF0000", value =  last["low"])

            if ai["state"] =="MID":
                    #if trend_pos >70  and vol > 10000 :
                    if trend_pos <50:
                        ai["state"] = "WAITING"
                    elif price > last["open"] and trend_pos>=60: #price > ai["high"]
                        ai["state"] = "BUY"
                        q = self.get_quantity( self.loss_by_trade, price    )
                        await self.buy( symbol, int(last["timestamp"]),price,  q, "BUY" )

        elif self.hasCurrentTrade(symbol):
            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
            
            #logger.info(f"gg {gain}")

            if True:#time_elapsed_secs > 4*15:
                
                '''
                if  gain >self.gain_perc:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
            
                elif  gain < -self.gain_perc/2:
                    await  self.sell(symbol, dt, last["close"], f"SL"  )

                '''
                '''
                elif  price < sma_25:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
                '''
            
                   #if gain < 1 and time_elapsed_secs > self.drop_time_secs:
                #    await  self.sell(symbol, dt, last["close"], f"TIME"  )
                #    ai["state"] = "WAITING"
                #logger.info(f"kkK {price} { ai['signal']}")

                '''
                if price < ai["signal"]:
                           ## logger.info("kkK")
                            ai["state"] = "WAITING"
                            await  self.sell(symbol, dt, last["close"], f"SL"  )

                elif ai["state"] =="BUY":
                    if trend_pos > 95:
                        ai["state"] = "UP"

                elif ai["state"] =="UP":
                    if signal <-1:
                          await  self.sell(symbol, dt, last["close"], f"TP1"  )
                          ai["state"] = "WAITING"
                '''
               
                '''
                if price < sma_25:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
                    ai["state"] = "WAITING"
                
                elif  gain >self.gain_perc:
                    await  self.sell(symbol, dt, last["close"], f"TP"  )
            
                elif  gain < -self.gain_perc/2:
                    await  self.sell(symbol, dt, last["close"], f"SL"  )
                '''
                 
            #if trend_pos < 50 :
            #    await self.sell( symbol, int(last["timestamp"]), price,  "SL" ) 