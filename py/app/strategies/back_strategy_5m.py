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
from telegram import send_telegram_message

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
#from strategy.order_strategy import *


class BackStrategy5m(SmartStrategy):

    async def on_start(self):

        self.min_gain = 20
        self.min_volume = 50000
        self.min_day_volume= 500_000

        self.loss_by_trade=50
        self.last_trade = {}
        self.max_gain={}
        pass

    def populate_indicators(self) :
        self.addIndicator(self.timeframe,MAX("high_max","high",timeperiod=3))
        self.addIndicator(self.timeframe,MAX("low_max","low",timeperiod=3))
        self.addIndicator(self.timeframe,SMA("sma_20","close",20))
        self.addIndicator(self.timeframe,CHAIN("chain_down",False))
     
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
       
        self.addLocalPlot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)


    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        #########################
        if self.bootstrapMode and self.orderManager:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
            return
        
        ####################################

        if (local_index < 2):   
            return
        
        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        ###### FIRST ENTER ########
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        
        if not self.has_meta(symbol,"first_enter_marker"):
            await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=last["close"],sendEvent=False)
            self.set_meta(symbol, {"first_enter_marker": True })

        ###################

       
        sma_20 = last["sma_20"]
        day_volume_history = last["day_volume_history"]
        gain = (last["close"]-prev["close"]) / prev["close"] * 100
        
        if day_volume_history < self.min_day_volume:
            return

        last_trade_time = 999999
        if (symbol in self.last_trade):
            last_trade_time = (int(last["timestamp"]) - self.last_trade[symbol]) / 1000
            #logger.info(last_trade_time)
        
        #if row_1m:
        if not self.hasCurrentTrade(symbol) and last_trade_time > 60*10*50:
            #df = self.local_df[symbol]
            #last_1m =  df.iloc[-1]
            
            #logger.info(f"{last_1m}")

            #if gain>10:

                if last["close"] > sma_20:

                    #logger.info(df.head(10))    
                    await self.add_marker(symbol,"SPOT",f"Ch {gain:.1f}",f"Ch {gain}","#F6F7F86F","square",position ="atPriceTop")

                    quantity = self.get_quantity(self.loss_by_trade,last["close"])
                    logger.info(f"BUY {symbol}  {last['datetime']} chain_up {gain} ")#\n{last_1m}")

                    await self.buy(symbol, int(last["timestamp"]), last["close"], quantity, "buy")
                    self.max_gain[symbol] =0
                    self.last_trade[symbol] = int(last["timestamp"])

                    if not self.bootstrapMode:
                        send_telegram_message(f"BUY {symbol} {last['datetime']} q:{quantity} g:{chain_gain:.1f} %")
            

        elif self.hasCurrentTrade(symbol):

                    gain,ts,pnl = self.buyGain(symbol, last["close"]) 

                  
                    #logger.info(f"SELL GAIN {symbol}  gain {gain} ts{ts} pnl {pnl}")

                    dt = int(dataframe.iloc[local_index]["timestamp"])
                    self.set_current_price(symbol, last["close"])         
                    time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
                    
                    chain_down = last ["chain_down"]

                    self.max_gain[symbol] = max(self.max_gain[symbol] , gain)
                    
                    logger.info(f"SELL GAIN {symbol}  {last['datetime']} secs: {time_elapsed_secs} gain {gain} pnl {pnl} max {self.max_gain[symbol] } chain_down {chain_down}")

                    # giu subito
                    if (gain<=0 and not self.has_meta(symbol,"done")):
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                        if not self.bootstrapMode:
                            send_telegram_message(f"SELL {symbol}  {last['datetime']} g:{gain:.1f} %")
                    else:
                        self.set_meta(symbol, {"done":True})

                    #max gain
                    if self.max_gain[symbol]>40 and self.max_gain[symbol]-gain > 10 :
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                        if not self.bootstrapMode:
                            send_telegram_message(f"SELL {symbol}  {last['datetime']} g:{gain:.1f} %")

                    # to low
                    if last["close"] < sma_20  : #or gain > 10: or chain_down>=3 
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                        if not self.bootstrapMode:
                            send_telegram_message(f"SELL {symbol}  {last['datetime']} g:{gain:.1f} %")