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


class _BackStrategy(SmartStrategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)


    async def buy(self,symbol,datetime,price, quantity,label=""):

        self.book.long(symbol, datetime,price, quantity, f"BUY")    
        await self.add_marker(symbol,"BUY",label,"#000000","arrowUp")
          
        logger.info(f"BUY {symbol} {label}  at {price} qty {quantity}     ")
        #self.book.long(symbol, price, 100,label)

        
    async def sell(self,symbol,datetime, price, label=""):
         
        await   self.add_marker(symbol,"BUY",label,"#000000","arrowDown")
        trade = self.book.close(symbol,datetime,price)   

        logger.info(f"SELL {label}  {symbol}  pnl : {trade.pnl()}")  
          
        #logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        #self.book.close(symbol,price)
        return trade

    async def onBackEnd(self):
        
        #logger.info(f"marker_map {self.marker_map}")

        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")

            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
            
        self.book.end(0,onClose)

       

        logger.info(f"REPORT {self.book.report()}")
        pass



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

class BackStrategy2(_BackStrategy):

    async def on_start(self):

        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.trade_first_hh= 5#self.params["trade_first_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_20 = self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        max_day = self.addIndicator(self.timeframe,MAX_DAY("max_day","close" ) )

        self.add_plot(sma_20, "sma_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max_day, "max_day","#a79600", "main",  lineWidth=1)

        self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    def tp_take(self,symbol,dataframe: pd.DataFrame,local_index):
        last = dataframe.iloc[local_index]
        gain,ts = self.book.gain(symbol, last["close"]) 
        #logger.info(f"tp_take {symbol} gain {gain} ts {ts}  "   )

        max_time = 120*60
        min_time = 5*60

        # numero secondi trascorsi dall'entrata in posizione    
        time_elapsed = (int(last["timestamp"]) - ts) / 1000
        time_elapsed = max(min_time,time_elapsed)
        time_elapsed = min(max_time,time_elapsed)

        scale = (max_time - time_elapsed) / (max_time - min_time)

        sgain = self.gain_perc * scale

        logger.info(f"tp_take {symbol} time_elapsed {time_elapsed} gain {gain} sgain {sgain} ")    

        return sgain
        
        

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=False

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        max_day = last["max_day"]
        close = last["close"]
        max_day_gain = (last["max_day"] - prev["max_day"] ) / prev["max_day"] * 100  
        
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        else:
            if not self.has_meta(symbol,"first_enter_marker"):
                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=close)
                self.set_meta(symbol, {"first_enter_marker": True })
            

        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(self.trade_first_hh,0),get_hour_ms(self.trade_last_hh,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop")

            #########
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return

            volume = last["day_volume_history"]    
            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    
                if not self.book.hasCurrentTrade(symbol):
                    if max_day_gain > 0:#close >= max_day and prev["close"] < max_day : #max_gain > 0: #
                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        quantity = self.get_quantity(close)

                        await self.buy(symbol, dt, close,quantity,  f"BUY"  )

                if self.book.hasCurrentTrade(symbol):
                    
                        gain,ts = self.book.gain(symbol, last["close"]) 
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000
                
                        if not self.has_meta(symbol,"max_gain"):  self.set_meta(symbol, {"max_gain": gain })
                        max_gain = max(gain,self.get_meta(symbol,"max_gain"))
                        self.set_meta(symbol, {"max_gain": max_gain  })
                        loss_from_max_gain = max_gain -gain

                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        self.book.set_current_price(symbol, last["close"])   

                        #gain_perc = self.tp_take(symbol,dataframe,local_index   )        
                        gain_perc= self.gain_perc
                        
                        logger.info(f"{symbol} gain {gain} max_gain { max_gain} loss_from_max_gain {loss_from_max_gain}")

                        #safe se non salgo
                        if max_gain > 5 and gain<5 and time_elapsed_secs > 60*20:
                            trade = await  self.sell(symbol,dt,  last["close"], f"SD"  )

                        elif gain < -gain_perc/2:
                            trade = await  self.sell(symbol,dt,  last["close"], f"SL"  )
                 

                        elif gain > gain_perc:
                            if last["close"] < last["open"] :
                                trade = await  self.sell(symbol,dt,  last["close"], f"TP"  )

                         
