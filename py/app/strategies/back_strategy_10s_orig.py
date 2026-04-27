from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from telegram import send_telegram_message
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

class BackStrategy10s_Orig(SmartStrategy):

    async def on_start(self):

        self.sub_timeframe = "30s"
        self.min_gain = 20
        self.min_volume = 10000
        self.min_day_volume= 500_000

        self.loss_by_trade=50
        
        self.max_gain={}
        self.last_trade={}
        pass

    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)

 
    def populate_indicators(self) :
        self.addIndicator(self.timeframe,MAX("high_max","high",timeperiod=3))
        self.addIndicator(self.timeframe,MAX("low_max","low",timeperiod=3))
        self.addIndicator(self.timeframe,SMA("sma_20","close",20))
        self.addIndicator(self.timeframe,CHAIN("chain_down",False))

        self.addLocalIndicator(CHAIN("chain_up",True))
        day_volume_history = self.addLocalIndicator(DAY_VOLUME("day_volume_history"))
       
        self.addLocalIndicator(GAIN("GAIN","close",timeperiod=1))

        #self.addLocalPlot(chain, "chain_up","#a70000", "sub1", style="Solid", lineWidth=1)

        self.addLocalPlot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)

        pass


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
        
        '''
        if symbol != "BIRD":
            return
            '''
        
        self.compute_local_df(self.sub_timeframe,symbol,dataframe, local_index)
        
        ####################################

        if (local_index < 2):   
            return
        
        last = dataframe.iloc[local_index]


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

        df = self.local_df[symbol]
        if len(df)<2:
            return
        last_1m =  df.iloc[-1]
        prev_1m =  df.iloc[-2]

        chain_up = int(last_1m["chain_up"])
        sma_20 = last["sma_20"]
        day_volume_history = last_1m["day_volume_history"]
        
        if day_volume_history < self.min_day_volume:
            return
        
        #if row_1m:
        #    logger.info(f"{last_1m}")

        #return

        last_trade_time = 999999
        if (symbol in self.last_trade):
            last_trade_time = (int(last["timestamp"]) - self.last_trade[symbol]) / 1000
            #logger.info(last_trade_time)
        
        #if row_1m:
        if not self.hasCurrentTrade(symbol) and last_trade_time > 60*10:
            #df = self.local_df[symbol]
            #last_1m =  df.iloc[-1]
            
            #logger.info(f"{last_1m}")

            if chain_up>=2 :#and chain_up <=4:

                chain_start = df.iloc[-chain_up+1]
             
                
                #diff = last_1m["high"] - chain_start["low"]
                #chain_gain =  (diff) / chain_start["low"] * 100  
                #if chain_gain>=self.min_gain and last["close"] > sma_20:

                diff = last_1m["close"] - chain_start["open"]
                chain_gain =  (diff) / chain_start["open"] * 100  

                if chain_gain>=20 and last["close"] > sma_20:

                    #logger.info(df.head(10))    
                    await self.add_marker(symbol,"SPOT",f"Ch {chain_gain:.1f}",f"Ch {chain_gain}","#F6F7F86F","square",position ="atPriceTop")

                    volume = last_1m["base_volume"]
                    if volume > self.min_volume :

                        quantity = self.get_quantity(self.loss_by_trade,last["close"])
                        logger.info(f"BUY {symbol}  {last['datetime']} chain_up {chain_up} {chain_gain} ")#\n{last_1m}")

                        await self.buy(symbol, int(last["timestamp"]), last["close"], quantity, "buy")
                        self.max_gain[symbol] =0
                        self.last_trade[symbol] = int(last["timestamp"])

                        if not self.bootstrapMode:
                            send_telegram_message(f"BUY {symbol} {last['datetime']} q:{quantity} g:{chain_gain:.1f} %")
            

        elif self.hasCurrentTrade(symbol):

                    gain,ts,pnl = self.buyGain(symbol, last["close"]) 

                    gain_30s =( last_1m["close"] - prev_1m["close"]) / prev_1m["close"] * 100

                    #logger.info(f"SELL GAIN {symbol}  gain {gain} ts{ts} pnl {pnl}")

                    dt = int(dataframe.iloc[local_index]["timestamp"])
                    self.set_current_price(symbol, last["close"])         
                    time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
                    
                    chain_down = last ["chain_down"]

                    self.max_gain[symbol] = max(self.max_gain[symbol] , gain)
                    
                    logger.info(f"SELL GAIN {symbol}  {last['datetime']} secs: {time_elapsed_secs} gain {gain} pnl {pnl} max {self.max_gain[symbol] } chain_down {chain_down}")

                    # giu subito
                    if (gain_30s<=0 and not self.has_meta(symbol,"done")):
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
                    if last["close"] < sma_20 or chain_down>=3 : #or gain > 10: or chain_down>=3 
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                        if not self.bootstrapMode:
                            send_telegram_message(f"SELL {symbol}  {last['datetime']} g:{gain:.1f} %")