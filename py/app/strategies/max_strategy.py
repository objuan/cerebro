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

########################

class STOCH_RSI(Indicator):
    def __init__(self, target, period=14, smooth_k=3, smooth_d=3):
        super().__init__([target])
        self.target = target
        self.n = period
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d
        self.mem = {}

    def compute_fast(self, symbol, dataframe, symbol_idx, from_local_index):
        dest = dataframe[self.target].to_numpy()
        close = dataframe["close"].to_numpy()

        if symbol not in self.mem:
            self.mem[symbol] = {
                "avg_gain": 0.0,
                "avg_loss": 0.0,
                "count": 0,
                "last_close": None,
                "rsi_buffer": [],
                "stoch_buffer": [],
                "k_buffer": []
            }

        m = self.mem[symbol]
        n = self.n

        for i_idx in range(max(0, from_local_index), len(symbol_idx)):
            idx = symbol_idx[i_idx]

            # --- INIT ---
            if m["last_close"] is None:
                m["last_close"] = close[idx]
                dest[idx] = np.nan
                continue

            delta = close[idx] - m["last_close"]
            m["last_close"] = close[idx]

            gain = max(delta, 0)
            loss = max(-delta, 0)

            m["count"] += 1

            # --- RSI (Wilder / RMA) ---
            if m["count"] < n:
                m["avg_gain"] += gain
                m["avg_loss"] += loss
                dest[idx] = np.nan
                continue

            elif m["count"] == n:
                m["avg_gain"] = (m["avg_gain"] + gain) / n
                m["avg_loss"] = (m["avg_loss"] + loss) / n

            else:
                m["avg_gain"] = (m["avg_gain"] * (n - 1) + gain) / n
                m["avg_loss"] = (m["avg_loss"] * (n - 1) + loss) / n

            # RSI
            if m["avg_loss"] == 0:
                rsi = 100
            else:
                rs = m["avg_gain"] / m["avg_loss"]
                rsi = 100 - (100 / (1 + rs))

            # --- STOCH RSI ---
            m["rsi_buffer"].append(rsi)
            if len(m["rsi_buffer"]) > n:
                m["rsi_buffer"].pop(0)

            if len(m["rsi_buffer"]) < n:
                dest[idx] = np.nan
                continue

            low = min(m["rsi_buffer"])
            high = max(m["rsi_buffer"])

            if high - low == 0:
                stoch = 0.0   # TradingView
            else:
                stoch = (rsi - low) / (high - low)

            stoch *= 100

            # --- %K ---
            m["stoch_buffer"].append(stoch)
            if len(m["stoch_buffer"]) > self.smooth_k:
                m["stoch_buffer"].pop(0)

            if len(m["stoch_buffer"]) < self.smooth_k:
                dest[idx] = np.nan
                continue

            k = sum(m["stoch_buffer"]) / self.smooth_k

            # --- %D ---
            m["k_buffer"].append(k)
            if len(m["k_buffer"]) > self.smooth_d:
                m["k_buffer"].pop(0)

            if len(m["k_buffer"]) < self.smooth_d:
                dest[idx] = np.nan
                continue

            d = sum(m["k_buffer"]) / self.smooth_d

            # OUTPUT TradingView = %K (default)
            dest[idx] = k

#################

class MAX_DAY(Indicator):

    def __init__(self, target_col, price_col: str):
        super().__init__([target_col])
        self.price_col = price_col
        self.target_col = target_col
        self.max ={}
        self.first ={}
       

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        timestamp = dataframe["timestamp"].to_numpy()
        dest = dataframe[self.target_col].to_numpy()
        price = dataframe[self.price_col].to_numpy()
            
        start = max(0, from_local_index)

        if not symbol in self.first:
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,from_local_index, True)
            #logger.info(f"FIRST ENTER {symbol} {first_enter}  ")    
            self.first[symbol] = first_enter

        first_enter = self.first[symbol]
        #logger.info(f"MAX_DAY {symbol} from_local_index {from_local_index}  symbol_idx {symbol_idx}  ")    

        for i_idx in range(start, len(symbol_idx)):
            if not symbol in self.max:
                   self.max[symbol] = price[symbol_idx[i_idx]]
            else:
                if timestamp[symbol_idx[i_idx]] > first_enter and timestamp[symbol_idx[i_idx-1]] < first_enter:
                    self.max[symbol] = price[symbol_idx[i_idx]]
                    #logger.info(f"MAX_DAY INIT {symbol} {price[symbol_idx[i_idx]]}  ")
                else:
                    self.max[symbol]= max(self.max[symbol], price[symbol_idx[i_idx]])

                dest[symbol_idx[i_idx]] =self.max[symbol]
        

#################

class MaxStrategy(SmartStrategy):

    async def on_start(self):

        self.volume_min_filter= 500000# self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        self.max_loss = 5
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_9 = self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        max_day = self.addIndicator(self.timeframe,MAX_DAY("max_day","close" ) )
        rsi = self.addIndicator(self.timeframe,STOCH_RSI("rsi"))

        self.add_plot(sma_9, "sma_9","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max_day, "max_day","#a79600", "main",  lineWidth=1)

        #self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)
        self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=True

        if (local_index < 2):   
            return

        if self.bootstrapMode:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
                return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        max_day = last["max_day"]
        close = last["close"]
        max_gain = (last["max_day"] - prev["max_day"] ) / prev["max_day"] * 100  
        
        ###### FIRST ENTER ########
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        else:
            if not self.has_meta(symbol,"first_enter_marker"):
                self.set_meta(symbol, {"first_enter_marker": True })
                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=close,ring="")
                
         # ##### OPEN CLOSE INFOS #######
        if not self.has_meta(symbol,"compute_open"):
                await StrategyUtils.compute_open(self,symbol,dataframe,local_index, open_count=15, use_day=use_day)



        #######################################
        #  
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(6,0),get_hour_ms(self.trade_last_hh,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop", ring="")

            #########
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return

            volume = last["day_volume_history"]    
            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto
                
                if not self.has_meta(symbol,"volume"):
                    self.set_meta(symbol,{"volume":"OK"})
                    await self.add_marker(symbol,"SPOT","VOL",f"VOL > {self.volume_min_filter}","#BB0B46",position ="atPriceTop",ring="chime")
       

                if self.has_meta(symbol,"compute_open"):
                    if not self.has_meta(symbol,"up_done" ):
                        open_perc_min_max = self.get_meta(symbol,"open_perc_min_max",0)   
                        max_h = self.get_meta(symbol,"open_high",999999 )
                        if last["close"] > max_h and open_perc_min_max>5:
                               self.set_meta(symbol,{"up_done":True})
                               await self.add_marker(symbol,"SPOT","UP","UP","#4C9C00","small_square",position ="atPriceTop")
                                 
                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    
                if not self.hasCurrentTrade(symbol):
                     pass
                    #if max_gain > 1: #close >= max_day and prev["close"] < max_day and 

                    #   quantity = self.get_quantity(close)

                    #    #await self.buy(symbol, dataframe.iloc[local_index]["timestamp"], close,quantity,  f"BUY"  )

                if self.hasCurrentTrade(symbol):
                    
                        gain,ts,pnl = self.buyGain(symbol, last["close"]) 
                        #logger.info(f"ts {ts}")
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000
                        
                        dt = dataframe.iloc[local_index]["timestamp"]

                        self.set_current_price(symbol, last["close"])           
                        logger.info(f"SELL GAIN {symbol} {time_elapsed_secs} gain {gain} pnl {pnl}")

                          #if gain < -self.gain_perc/2:
                        if pnl < -self.max_loss:
                            if self.sl_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                                                
                        elif gain > self.gain_perc:
                            if self.tp_enabled(symbol):
                                #trade = self.close(symbol, last["close"])
                                trade = await  self.sell(symbol, dt, last["close"], f"TP"  )

               
    async def compute_first_enter(self,symbol,dataframe,local_index, use_day,value):
            if not self.has_meta(symbol,"first_enter"): 
                
                first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)

                self.set_meta(symbol, {"first_enter": first_enter }) 

                #logger.info(f"FIRST ENTER {symbol} {first_enter}  ")

                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=first_enter,value=value)
