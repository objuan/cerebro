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

from telegram import send_telegram_message

#################

class TradeStrategyDown(SmartStrategy):

    async def on_start(self):

        
        self.inPeriod=False
        self.volume_min_filter= self.params["volume_min_filter"]
        self.gain_perc = self.params["gain_perc"]   
        self.min_open_gain= self.params["min_open_gain"]
        self.chain_up_max= self.params["chain_up_max"]

        self.trade_last_hh= self.params["trade_last_hh"]
        
        self.trade_first_hh= 5#self.params["trade_first_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 50#capital * trade_risk
        self.max_loss  = 5
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   

        self.max_price= {}
        self.max_gain= {}

        pass

    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))


        date = self.addIndicator(self.timeframe,TRADE_DATE("date"))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma20 = self.addIndicator(self.timeframe,SMA("sma20","close",timeperiod=20))
        #ema9 = self.addIndicator(self.timeframe,SMA("ema9","close",timeperiod=9))
        #vwap = self.addIndicator(self.timeframe,VWAP("vwap_history","close","base_volume"))
        rsi = self.addIndicator(self.timeframe,STOCH_RSI("rsi"))
        chain_up = self.addIndicator(self.timeframe,CHAIN("chain_up",True))
        chain_down = self.addIndicator(self.timeframe,CHAIN("chain_down",False))
      
        
        #gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
      
        self.add_plot(sma20, "sma20","#a70000", "main", style="SparseDotted", lineWidth=1)
        #self.add_plot(ema9 , "ema9 ","#4800a7", "main", style="SparseDotted", lineWidth=1)

        #self.add_plot(vwap , "vwap_history ","#00a732", "main", style="SparseDotted", lineWidth=1)
       
        #self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        self.add_plot(rsi, "rsi","#d3035a", "sub1", style="Solid", lineWidth=1)

        #self.add_plot(bad, "bad","#0318d3", "sub1", style="Solid", lineWidth=1)


    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        if (local_index < 2):   
            return
        
          
        if self.bootstrapMode and self.orderManager:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
                return
            
        #if symbol =="SKYQ":
        #    logger.info(f"TRADE_SYMBOL_AT \n{symbol} {dataframe.iloc[local_index]}")  


        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        close = last["close"]
        sma20 = last["sma20"]
   
        rsi = last["rsi"]
        volume = last["day_volume_history"]    
        #chain_up = int(last["chain_up"]   )
        chain_up = int(last["chain_up"]) if pd.notna(last["chain_up"]) else 0
        chain_down = int(last["chain_down"]) if pd.notna(last["chain_down"]) else 0
        #chain_down = int(prev["chain_down"]   )

        ###### FIRST ENTER ########
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        else:
            if not self.has_meta(symbol,"first_enter_marker"):
                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=close,sendEvent=False)
                self.set_meta(symbol, {"first_enter_marker": True })

         # ##### OPEN CLOSE INFOS #######
        #if not self.has_meta(symbol,"compute_open"):
        #        await self.compute_open(symbol,dataframe,local_index, open_count=3, use_day=use_day)


        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(self.trade_first_hh,0),get_hour_ms(self.trade_last_hh,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop", sendEvent=False)

            #########

            if chain_up>=2 and chain_up <= self.chain_up_max:
                #logger.info(f"chain_len {chain_len}")
                chain_start = dataframe.iloc[local_index-chain_up+1]

                diff = last["high"] - chain_start["low"]
                chain_gain =  (diff) / prev["low"] * 100  
                fibo_66 = chain_start["low"] + diff * 0.66
                half = chain_start["low"] + diff * 0.5
                low = chain_start["low"] 
                
                if chain_gain > self.min_open_gain:

                    await self.add_marker(symbol,"SPOT",f"Ch {chain_gain:.1f}",f"Ch {chain_gain}","#F6F7F86F","square",position ="atPriceTop")
                    await self.add_marker(symbol,"SPOT",f"half",f"half","#F6F7F86F","square",position ="atPriceTop", value = half,sendEvent=False)

                    self.set_meta(symbol,{"chain_gain" : chain_gain,
                                           "chain_len" : chain_up,
                                           "fibo_66": fibo_66,
                                           "half":half,
                                           "timestamp" : int(last["timestamp"]),
                                           "state" : 0,"low": low} )
                    
                    if not self.bootstrapMode:
                        send_telegram_message(f"UP UP {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {symbol}  {chain_gain:.1f} %")
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return
            #open_volume = self.get_meta(symbol,"open_volume",0) 
            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto
                
                if not self.hasCurrentTrade(symbol):

                    if self.has_meta(symbol, "state"):
                        state =self.get_meta(symbol,"state") 
                        low=self.get_meta(symbol,"low")
                        low = low + low * 0.05

                        if state == 0:
                            signal = self.get_meta(symbol,"half")
                            #logger.info(f"{symbol} {close} < {fibo_66}")
                            if close < signal:
                                self.set_meta(symbol,{"state" : 1})
                                state =1
                                await self.add_marker(symbol,"SPOT",f"Down",f"DOwn","#008F5F6E","square",position ="atPriceTop",sendEvent=True)
                            
                        if state == 1:
                            signal = self.get_meta(symbol,"half")
                            time_elapsed_secs = (int(last["timestamp"]) - self.get_meta(symbol,"timestamp")) / 1000    
                            
                            if close > last["open"]  and close <signal:# and time_elapsed_secs < 60*60:
                                await self.add_marker(symbol,"SPOT",f"V",f"FIND","#8500A76D","square",position ="atPriceTop", ring="chime")
                            
                                if last["close"] > sma20 and prev["rsi"] < 5  and  rsi  > 5 :
                                    sl = last["low"] - last["low"]* 0.01
                                    self.set_meta(symbol,{"sl": sl })

                                    quantity = self.get_quantity(self.loss_by_trade,close)
                                    self.max_price[symbol] =close
                                    self.max_gain[symbol] =0
                                   # await self.buy(symbol, int(dataframe.iloc[local_index]["timestamp"]), close,quantity,  f"BUY"  )

                                '''
                                if last["close"] > low and prev["rsi"] < 5  and  rsi  > 5 :
                                    sl = last["low"] - last["low"]* 0.01
                                    self.set_meta(symbol,{"sl": sl })

                                    quantity = self.get_quantity(self.loss_by_trade,close)
                                    self.max_price[symbol] =close
                                    await self.buy(symbol, int(dataframe.iloc[local_index]["timestamp"]), close,quantity,  f"BUY"  )
                                '''

                if self.hasCurrentTrade(symbol):

                        sl = self.get_meta(symbol,"sl")
                      


                        gain,ts,pnl = self.buyGain(symbol, last["close"]) 
                        #logger.info(f"ts {ts}")
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000    
                        #self.max_price[symbol] = max(self.max_price[symbol] , close)
                        #self.max_gain[symbol] = max(self.max_gain[symbol] , gain)

                        #
                        trade = self.getCurrentTrade(symbol)

                        #price_diff = self.max_price[symbol]- close
                        #loss_from_max = price_diff * trade.quantity

                        #price_diff =  self.max_price[symbol]  - trade.price

                       # SL = trade.price - self.max_loss/trade.quantity + price_diff/2
                        
                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        self.set_current_price(symbol, last["close"])           

                        #logger.info(f"SELL GAIN {symbol} {time_elapsed_secs} gain {gain} pnl {pnl} sl {sl}")
                        #logger.info(f"SELL GAIN {symbol} {time_elapsed_secs} gain {gain} price_diff {price_diff} loss_from_max {loss_from_max}")
                        #logger.info(f"SELL GAIN {symbol} {time_elapsed_secs} gain {gain} close {close} max {self.max_price[symbol]} gmax {self.max_gain[symbol]} SL {SL} ")

                        #if loss_from_max > self.max_loss:
                        '''
                        if close < SL:
                            if self.sl_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                                self.del_meta(symbol,"state")
                               
                        '''
                        '''
                        if time_elapsed_secs > 60*2:
                            if self.sl_enabled(symbol):
                                await  self.sell(symbol, dt, last["close"], f"TIME"  )
                                self.del_meta(symbol,"state")
                        '''
                        '''
                        if gain < self.max_gain[symbol] * 0.66 and time_elapsed_secs > 5*60:
                           if self.sl_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"GAIN"  )
                                self.del_meta(symbol,"state")         
                        '''
                        if sl and close < sl:#-self.magain_percx_loss:
                            if self.sl_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                                self.del_meta(symbol,"state")

                        
                        elif gain > self.gain_perc:
                            if self.tp_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"TP"  )
                                self.del_meta(symbol,"state")