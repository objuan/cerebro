from typing import Dict
from zoneinfo import ZoneInfo
import pandas as pd
import logging
from datetime import datetime,timedelta
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

class BackStrategyMaxDay(SmartStrategy):

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


    async def onBackEnd(self):
        
        #logger.info(f"marker_map {self.marker_map}")

        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")

            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
            
        self._book.end(0,onClose)
        logger.info(f"REPORT {self._book.report()}")
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
    
    '''
    async def get_open_gap(strategy,symbol, lastCandle):
        if not strategy.has_meta(symbol,"get_open_gap"):
            ts = int(lastCandle["timestamp"])/1000
            dt_utc = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC"))

            # 2. Converti a New York
            dt_ny = dt_utc.astimezone(ZoneInfo("America/New_York"))

            # 3. Imposta le 04:00 AM dello stesso giorno NY
            dt_4am_ny = datetime.datetime.combine(
                dt_ny.date(),
                datetime.time(4, 0),
                tzinfo=ZoneInfo("America/New_York")
            )
            dt = dt_4am_ny.astimezone(ZoneInfo("UTC"))
            
            unix_time = int(dt.timestamp()) * 1000


            open_gap = strategy.client.get_price_at_dt(symbol, unix_time)

            logger.info(f"open {symbol} ts:{unix_time} gap:{open_gap}")
            strategy.set_meta(symbol,{"get_open_gap": open_gap})
        return strategy.get_meta(symbol,"get_open_gap")
    '''

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=False

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {dataframe.iloc[local_index]['timestamp']}")  

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        max_day = last["max_day"]
        close = last["close"]
        volume = last["day_volume_history"]    
        sma_20 = last["sma_20"]
        max_day_gain = (last["max_day"] - prev["max_day"] ) / prev["max_day"] * 100  
        open_gap= 0
        # fist enter

        if not self.has_meta(symbol,"first_enter"): 
            first_enter_ts = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter_ts ,"first_close": close ,"first_volume": volume }) 

            logger.info(f"first_enter {symbol} {first_enter_ts}")

        # open gap
        
        last_close = await StrategyUtils.get_last_close(self,symbol, last, True)
        
       
        # troppo presto
        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        
        if  not self.get_meta(symbol,"first_close") > last_close:
            return
        
        #if  not self.get_meta(symbol,"first_volume") > self.volume_min_filter:
        #    return
        

        else:
            if not self.has_meta(symbol,"first_enter_marker"):
                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=close)
                self.set_meta(symbol, {"first_enter_marker": True })
            

        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(4,0),get_hour_ms(13,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop")

            # open_gap = await BackStrategyMaxDay.get_open_gap(self,symbol,last)

            #########
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return

            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    
                if not self.hasCurrentTrade(symbol):
                    if max_day_gain > 0 and close > sma_20:
                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        quantity = self.get_quantity(close)

                        await self.buy(symbol, dt, close,quantity,  f"BUY"  )

                if self.hasCurrentTrade(symbol):
                    
                        gain,ts,pnl = self.buyGain(symbol, last["close"]) 
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000
                
                        if not self.has_meta(symbol,"max_gain"):  self.set_meta(symbol, {"max_gain": gain })
                        max_gain = max(gain,self.get_meta(symbol,"max_gain"))
                        self.set_meta(symbol, {"max_gain": max_gain  })
                        loss_from_max_gain = max_gain -gain

                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        self.set_current_price(symbol, last["close"])   

                        #gain_perc = self.tp_take(symbol,dataframe,local_index   )        
                        gain_perc= self.gain_perc
                        
                        #logger.info(f"{symbol} gain {gain} max_gain { max_gain} loss_from_max_gain {loss_from_max_gain}")

                        #safe se non salgo
                        #if close < sma_20 and time_elapsed_secs > 60*15 :
                        #    trade = await  self.sell(symbol,dt,  last["close"], f"SD"  )

                        if gain < -gain_perc/2:
                            trade = await  self.sell(symbol,dt,  last["close"], f"SL"  )
                 
                        elif gain > gain_perc:
                            if last["close"] < last["open"] :
                                trade = await  self.sell(symbol,dt,  last["close"], f"TP"  )

                         
