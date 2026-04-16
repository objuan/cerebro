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

class SUSPEND_INDICATOR(Indicator):
  
    def __init__(self,target_col, window=60):
        super().__init__([target_col])
        self.target_col=target_col
        self.window=window
        self.count_map={}
        self.trend_map={}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        volume = dataframe["base_volume"].to_numpy()
        high= dataframe["high"].to_numpy()
        low = dataframe["low"].to_numpy()

        count = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            idx = symbol_idx[i_idx]
            bad = volume[idx] == 0 and high[idx] == low[idx] 
            if bad:
                if not symbol in self.trend_map:
                    self.trend_map[symbol] = i_idx
                    self.count_map[symbol] = 1

                else:
                     self.count_map[symbol] = 1 + self.count_map[symbol]
                     self.trend_map[symbol] = i_idx

            else:
                if symbol in self.trend_map:
                    if i_idx - self.trend_map[symbol] > self.window:
                        del self.trend_map[symbol]  

            dest[idx] =self.count_map[symbol] if symbol in self.trend_map else 0

class _BackStrategy(SmartStrategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)

    '''
    async def buy(self,symbol,timestamp,price, quantity,label=""):

        self._book.long(symbol, timestamp,price, quantity, f"BUY")    
        await self.add_marker(symbol,"BUY",label,"#000000","arrowUp")
          
        logger.info(f"BUY {datetime.fromtimestamp(timestamp/1000).strftime('%H:%M:%S')} {symbol} {label}  at {price} qty {quantity}     ")
        #self.book.long(symbol, price, 100,label)

        
    async def sell(self,symbol,timestamp, price, label=""):
         
        await   self.add_marker(symbol,"BUY",label,"#000000","arrowDown")
        trade = self.book.close(symbol,timestamp,price)   

        logger.info(f"SELL {datetime.fromtimestamp(timestamp/1000).strftime('%H:%M:%S')} {label}  {symbol}  pnl : {trade.pnl()}")  
          
        #logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        #self.book.close(symbol,price)
        return trade
    '''
    async def onBackEnd(self):
        
        #logger.info(f"marker_map {self.marker_map}")

        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")

            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
            
        self._book.end(0,onClose)

       

        logger.info(f"REPORT {self._book.report()}")
        pass



#################

class BackStrategyOpen1(_BackStrategy):

    async def on_start(self):

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
        pass



    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_20 = self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        max_day = self.addIndicator(self.timeframe,MAX_DAY("max_day","close" ) )
        bad = self.addIndicator(self.timeframe,SUSPEND_INDICATOR("bad",30));

        self.add_plot(sma_20, "sma_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max_day, "max_day","#a79600", "main",  lineWidth=1)

        self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(bad, "bad","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {dataframe.iloc[local_index]['timestamp']}")  

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        max_day = last["max_day"]
        close = last["close"]
        sma_20 = last["sma_20"]
        volume = last["day_volume_history"]    
        bad = last["bad"]
         
        max_day_gain = (last["max_day"] - prev["max_day"] ) / prev["max_day"] * 100  

        ###### FIRST ENTER ########
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

         # ##### OPEN CLOSE INFOS #######
        if not self.has_meta(symbol,"compute_open"):
                await self.compute_open(symbol,dataframe,local_index, open_count=15, use_day=use_day)


        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(self.trade_first_hh,0),get_hour_ms(self.trade_last_hh,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop")

            #########
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return
            #open_volume = self.get_meta(symbol,"open_volume",0) 
            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    
                if not self.hasCurrentTrade(symbol):

                    if self.has_meta(symbol,"compute_open"):
                        if not self.has_meta(symbol,"up_done" ):
                            open_perc_min_max = self.get_meta(symbol,"open_perc_min_max",0)   
                            max_h = self.get_meta(symbol,"open_high",999999 )

                            if  last["close"] > max_h and open_perc_min_max>self.min_open_gain:
                                    
                                if self.market.is_in_time(last["datetime"],# mi fermo 30 minuti prima
                                        get_hour_ms(self.trade_first_hh,0),get_hour_ms(self.trade_last_hh-1,30),use_day):
                                    self.set_meta(symbol,{"up_done": False} )

                                    quantity = self.get_quantity(close)
                                    dt = int(dataframe.iloc[local_index]["timestamp"])
                                    #await self.add_marker(symbol,"SPOT","UP","UP","#004726","small_square",position ="atPriceTop")
                                    await self.buy(symbol, dt, close,quantity,  f"BUY"  )
                                   
                #### sell logic
                
                if self.hasCurrentTrade(symbol):
                    
                        gain,ts = self.buyGain(symbol, last["close"]) 
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000
                
                        if not self.has_meta(symbol,"max_gain"):  self.set_meta(symbol, {"max_gain": gain })
                        max_gain = max(gain,self.get_meta(symbol,"max_gain"))
                        self.set_meta(symbol, {"max_gain": max_gain  })
                        loss_from_max_gain = max_gain -gain

                        dt = int(dataframe.iloc[local_index]["timestamp"])

                        self.set_current_price(symbol, last["close"])   

                        #gain_perc = self.tp_take(symbol,dataframe,local_index   )        
                        gain_perc= self.gain_perc
                        
                        logger.info(f"{symbol} gain {gain} max_gain { max_gain} loss_from_max_gain {loss_from_max_gain}")

                        h = self.get_meta(symbol,"open_high",999999 )

                        #safe se non salgo
                        if close < h and time_elapsed_secs > 60*5 :
                            trade = await  self.sell(symbol,dt,  last["close"], f"SD"  )

                        elif gain > gain_perc:
                            if last["close"] < last["open"] :
                                trade = await  self.sell(symbol,dt,  last["close"], f"TP"  )
        
        else:
           if not self.has_meta(symbol,"exit_time"):
                self.set_meta(symbol, {"exit_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","Y","Exit Time","#F6F7F86F","square",position ="atPriceTop")

                if self.hasCurrentTrade(symbol):
                     await  self.sell(symbol,int(dataframe.iloc[local_index]["timestamp"]),  last["close"], f"SD"  )

                         
    async def compute_open(self,symbol,dataframe,local_index,open_count = 15, use_day=True):
        trade_last_hh = self.trade_last_hh
        last = dataframe.iloc[local_index]
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(9,00),get_hour_ms(trade_last_hh,00),use_day):
            #logger.info(f'{last["datetime"]}')

            if self.market.is_in_time(last["datetime"],
                get_hour_ms(9,30),get_hour_ms(trade_last_hh,00),use_day):
                #logger.info(f'{last["datetime"]}')

                is_inside=True
                if not self.has_meta(symbol,"open_gap"):
                    last_close = MetaInfo.get(symbol,"last_close")
                    if not last_close:
                        last_close, ts_last_close=  await self.client.last_close(symbol,last["datetime"] ) 
                    
                    #logger.info(f'last_close {last_close}')

                    if last_close:
                        self.set_meta(symbol,{"open_gap": 100.0* (last["close"] - last_close) / last["close"] })

                        #pre_gain = MetaInfo.get(symbol,"pre_gain")
                        #logger.info(f"{symbol} t:{last['datetime']} {self.get_meta(symbol,'open_gap')} close:{last['close']} last_close:{last_close}")

                ###### 15 perc ######

                if self.market.is_in_time(last["datetime"],
                        get_hour_ms(9,45),get_hour_ms(trade_last_hh,00),use_day):

                    if not self.has_meta(symbol,"open_perc"):
                        window = dataframe.iloc[local_index-open_count:local_index]
                        if len(window)>0:   
                            low = window["low"].min()
                            high = window["high"].max()

                            l_h_perc = 100.0 * (high - low) / low

                            first = window.iloc[0]
                            last = window.iloc[-1]

                            perc = 100.0 * (last["close"] - first["open"]) / first["open"]
                            '''
                            first = dataframe.iloc[local_index-15]
                        
                            low = min(first["low"] , prev["low"])
                            high = max(first["high"] , prev["high"])
                                    
                            l_h_perc = 100.0* (high-low) / low
                            perc =  100.0 * (prev["close"]- first["open"]) / first["open"]
                            '''
                            #logger.info(f"OPEN {symbol} t:{last['datetime']}  OPEN 15M O:{first['open']}  C:{last['close']} perc:{perc} l_h_perc:{l_h_perc} local_index:{local_index} last_idx: { last.name}")

                            self.set_meta(symbol, 
                                    {
                                        "compute_open" : True,
                                    "open_high" : high,
                                    "open_low": low,
                                    "open_perc" : perc, 
                                    "open_perc_min_max":l_h_perc,
                                    "open_close_idx": local_index,
                                    "open_volume": last["day_volume_history"]   
                                    } )
        return self.has_meta(symbol,"open_high" )