from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategies.strategy_utils import StrategyUtils
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from company_loaders import *
from collections import deque
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
#from strategy.order_strategy import *

     

#################

class BackStrategyBinance1(SmartStrategy):

    async def on_start(self):

        '''
        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.min_open_gain= self.params["min_open_gain"]
        self.trade_first_hh= 5#self.params["trade_first_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        '''

        self.loss_by_trade = 100#capital * trade_risk
        pass


   

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))

        #day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history",volume_name="quote_volume"))
        vol_day= self.addIndicator(self.timeframe,SUM("vol_day","quote_volume",1440))
        #max_1d= self.addIndicator(self.timeframe,MAX("MAX_1D","close",60 * 24))

        #sma_20 = self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        sma_50 = self.addIndicator(self.timeframe,SMA("sma_50","close",timeperiod=50))
        sma_200 = self.addIndicator(self.timeframe,SMA("sma_200","close",timeperiod=200))
        #gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=1))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
      
        #self.add_plot(sma_20, "sma_20","#a70000", "main", style="Solid", lineWidth=1)
        #self.add_plot(sma_50 , "sma_50","#4800a7", "main", style="Solid", lineWidth=1)
        self.add_plot(sma_200 , "sma_200","#00a7a7", "main", style="Solid", lineWidth=1)
       
        #self.add_plot(vol_day, "vol_day","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(bad, "bad","#0318d3", "sub1", style="Solid", lineWidth=1)

        #self.addIndicator(self.timeframe, EMA("ema9", "close", 9))
        #self.addIndicator(self.timeframe, EMA("ema21", "close", 21))
        #rsi = self.addIndicator(self.timeframe, STOCH_RSI("rsi", 14,3,3))
        #self.addIndicator(self.timeframe, SMA("vol_sma", "quote_volume", 20))

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        vwap_trend = self.addIndicator(self.timeframe, W_TREND("vwap_trend","vwap_trend_sign","vwap"))

        #vwap_perc = self.addIndicator(self.timeframe, DIFF_PERC("vwap_perc","vwap","vwap"))

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        
        #self.add_plot(vwap, "vwap_perc","#1bd303","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_perc","#1bd303","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_pos","#d30337","sub1","vwap_pos", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        #if symbol != "YGGUSDC":
        #    return
        
        #if (local_index < 1440):   
        #    return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]
        
        vol_day = last["vol_day"]    
        #if (vol_day < 100_000):
        #     return
        #
        #if not self.has_meta(symbol,"first"):
        #    self.set_meta(symbol, {"first": True})
        #    await self.add_marker(symbol,"SPOT",f"F",f"F","#08BB266C","square",position ="atPriceTop")

        #close = last["close"]
        #sma_20 = last["sma_20"]
        sma_50 = last["sma_50"]
        sma_200 = last["sma_200"]
        #quote_volume = last["quote_volume"]    

        #MAX_1D = last["MAX_1D"]   
        
        price = last["close"]
        #ema9 = last["ema9"]
        #ema21 = last["ema21"]
        #rsi = last["rsi"]
        vol = last["quote_volume"]
        #vol_sma = last["vol_sma"]
        vwap = last["vwap"]
        vwap_up = last["vwap_up"]
        vwap_down = last["vwap_down"]

        trend_gain =  last["vwap_perc"]
        trend_pos =  last["vwap_pos"]
        trend =  last["vwap_trend"] * last["vwap_trend_sign"]
        last_trend =  prev["vwap_trend"] * prev["vwap_trend_sign"]

        # 🔵 FILTRI BASE (edge vero)
        #trend_up = ema9 > ema21
        #trend_down = ema9 < ema21

        #volume_spike = vol > vol_sma * 1.5

        #base = dataframe.iloc[local_index-60*4]

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {last['datetime']} {last['day_volume']}")  

        if not self.has_meta(symbol,"momentum"):
            self.set_meta(symbol, {"momentum": {"list": [], "prev" : None,"first_mid" : None}})
    
        mode="LOW"

        if True:
                momentum = self.get_meta(symbol, "momentum")
  
                prev_mom = momentum["prev"]
                last_list_mom = momentum["list"][-1] if len(momentum["list"]) >0 else None

                new_mom=None
                if trend_pos < 5:
                    new_mom = {"type": "m", "ts": last["timestamp"] ,"close": price, "mid" :  vwap_down + (vwap-vwap_down)/2}
                    momentum["first_mid"] =None
                if trend_pos > 45 and trend_pos < 55:
                    new_mom = {"type": "=", "ts": last["timestamp"]  ,"close": price,"mid" : vwap }
                if trend_pos > 95:
                    new_mom = {"type": "M", "ts": last["timestamp"]  ,"close": price,"mid" :vwap + (vwap_up -vwap)/2 }
                    momentum["first_mid"] =None

                #[if last_list_mom != None and last_list_mom["type"] != "=" and new_mom != None and new_mom["type"] == "=":
                 #   await self.add_marker(symbol,"SPOT","B","B","#BB08946C","square",position ="atPriceTop")

                if prev_mom==None and new_mom!=None:
                    if last_list_mom != None and last_list_mom["type"] != "=" and new_mom["type"] == "=":
                        momentum["first_mid"] = new_mom
                       #await self.add_marker(symbol,"SPOT","B","B","#BB08946C","square",position ="atPriceTop")

                if prev_mom!=None and new_mom==None:
                    
                    if last_list_mom == None or (last_list_mom and last_list_mom["type"] != prev_mom["type"]):
                        # è cambiato
                        skip=False
                        if prev_mom["type"] == "=":
                            if last_list_mom != None:
                                if last_list_mom["type"]  == "M" and price > last_list_mom["close"]:# and price > last_list_mom["mid"] :
                                    skip=True
                                if last_list_mom["type"]  == "m" and price < last_list_mom["close"]:# and price > last_list_mom["mid"] :
                                    skip=True
                        
                        if not skip:
                            momentum["list"].append(prev_mom)
                            if prev_mom["type"] =="=" and  momentum["first_mid"]:
                                first =  momentum["first_mid"]
                                await self.add_marker(symbol,"SPOT","B","B","#BB08946C","square",position ="atPriceTop",value= first["close"], timestamp=first["ts"])

                            await self.add_marker(symbol,"SPOT",prev_mom["type"],prev_mom["type"],"#BB08946C","square",position ="atPriceTop")
                

                momentum["prev"] = new_mom

        if not self.hasCurrentTrade(symbol):
            if trend > 60*2 and vol_day > 500_000:
                await self.buy( symbol, int(last["timestamp"]),price,  1, "BUY" )
                
        if False:
            '''
                if trend>60*6 :#mode == "LOW":
                    await self.buy( symbol, int(last["timestamp"]),price,  1, "BUY" )

                    
                    ########
                    body = last["close"]- last["open"] 
                    range_ = last["high"]- last["low"] 
                    lowerwick = min(last["open"],last["close"])-  last["low"] 
                    upperwick =  last["high"] - max(last["open"],last["close"]) 
                    bullish_reversal = (
                        last["close"]  > last["open"]  and
                        lowerwick > body * 2.0 and
                        upperwick < body and
                        last["close"]  > prev["close"] and
                        last["close"]  > ( last["low"]  + range_ * 0.7)
                    )
                    ########

                    if last_trend<60*6 and trend_pos <=-100 and bullish_reversal:
                        await self.add_marker(symbol,"SPOT",f"D",f"D","#08BB266C","square",position ="atPriceTop")
                
                        #await self.buy( symbol, int(last["timestamp"]),price,  1, "BUY" )
            '''
            #34 %
            '''
            in rialzo, toggo il centro
            if last_trend>60*6 and trend_pos <=55 :#and last["close"] > sma_200 :
            #if trend_pos > 100 and 
                 
                self.del_meta(symbol, "over")
               await self.buy( symbol, int(last["timestamp"]),price,  1, "BUY" )
            '''  
             # pullback + trend
            '''
            if (
                trend_up and
                prev["close"] < prev["ema9"] and   # pullback
                price > ema9 and                  # ritorno sopra EMA
                volume_spike and
                rsi < 70 and
                near_vwap
            ):
                quantity = 100#self.getQuantity(symbol, price)

               await self.buy( symbol, int(last["timestamp"]),price,  1, "BUY" )
            '''
            '''
            MAX_1D_PREV = prev["MAX_1D"]   

            max_perc = (last["close"]- MAX_1D_PREV ) /MAX_1D_PREV * 100
            if max_perc> 0.1  and last["close"] > sma_20:
                quantity = self.get_quantity(last["close"])  
                await self.buy(symbol, int(last["timestamp"]), last["close"], quantity, "buy")
            '''
            '''
            prev_200 = dataframe.iloc[local_index-60]["sma_200"]
            prev_50 = dataframe.iloc[local_index-60]["sma_200"]
            prev_2 = dataframe.iloc[local_index-2]["close"]

            trend_200_1h_perc = (sma_200 -  prev_200) / prev_200 * 100
            trend_50_1h_perc = (sma_50 -  prev_50) / prev_50 * 100

            gain_prev = (prev["close"] - prev_2 )/prev_2*100
            gain = (close - prev["close"] )/prev["close"]*100

            if quote_volume > 10_000 and trend_200_1h_perc>0.5 and trend_50_1h_perc > 0.5 :
                #if sma_50> sma_200 and sma_10 > sma_50 and close > sma_10  and close > last['open']:
                #if sma_20>sma_50 and close > sma_20:
                    if gain_prev > 2 and gain>0.1 :
                        quantity = self.get_quantity(last["close"])  
                        await self.buy(symbol, int(last["timestamp"]), last["close"], quantity, "buy")
            '''
                   

        elif self.hasCurrentTrade(symbol):
                return
                gain,ts,pnl = self.buyGain(symbol, last["close"]) 

                self.set_current_price(symbol, last["close"])         
        
                #logger.info(f"SELL GAIN {symbol}  gain {gain} ts{ts} pnl {pnl}")

                dt = int(dataframe.iloc[local_index]["timestamp"])
                #self.set_current_price(symbol, last["close"])         
                time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
                    
                   
                #self.max_gain[symbol] = max(self.max_gain[symbol] , gain)
                    
                #logger.info(f"SELL GAIN {symbol}  {last['datetime']} secs: {time_elapsed_secs} gain {gain} pnl {pnl}  ")

                if mode =="LOW":
                    if trend_pos > 45:  
                         await  self.sell(symbol, dt, last["close"], f"TP"  )
                    if  gain < -trend_gain/10:
                            trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
        
                if mode =="TREND":
                    if self.has_meta(symbol,"over"):
                         if last["close"]< sma_50:
                            await  self.sell(symbol, dt, last["close"], f"TP"  )
                    else:
                        if trend_pos > 90:  
                            #trade = await  self.sell(symbol, dt, last["close"], f"TP"  )
                            self.set_meta(symbol, {"over": True})
                        #elif trend_pos< 50:
                        elif  gain < -trend_gain/10:
                            trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                    #elif gain < -5:
                    #    trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                    #elif trend_down:
                    #    trade = await  self.sell(symbol, dt, last["close"], f"TR"  )
                    
                    '''
                    #elif gain > 3:
                    #    trade = await  self.sell(symbol, dt, last["close"], f"TP"  )
                    elif gain < -5:
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                    '''
                     