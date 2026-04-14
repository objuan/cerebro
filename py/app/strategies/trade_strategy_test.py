from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from order_task import OrderTaskManager
from balance import Balance, PositionTrade
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



class TradeStrategyTest(SmartStrategy):

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

    async def on_live_trade_event(self,type, trade:PositionTrade):
        if type =="POSITION_TRADE":

            self.set_meta( trade.symbol, {"last_trade":trade})   
            #trade = Trade.from_dict(data)
            logger.info(f"TRADE EVENT {trade.to_dict()}  ")

    async def buy(self,symbol,timestamp,price, quantity,label=""):
        if self.hasCurrentTrade(symbol):
            return

        logger.info(f"BUY {symbol} {timestamp} {quantity} at {price} [{label}]")
        await self.add_marker(symbol,"BUY","BUY",label,"#3CFF00FF","arrowUp",position="atPriceBottom",ring="chime")

        #if not self.buyMap[symbol]:
        self.book.long(symbol, timestamp, price, quantity,label)

        #super().buy(symbol,label)
        if not self.bootstrapMode:
            await self.orderManager.smart_buy_limit(symbol, quantity,self.client.getTicker(symbol))
            pass
        #    await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#21FF04", ring="news")


    async def sell(self,symbol,timestamp, price, label=""):

        if self.hasCurrentTrade(symbol):
            logger.info(f"SELL  {symbol} {timestamp}")

            trade = self.book.close(symbol,timestamp,price)

            await self.add_marker(symbol, "SELL", "SELL",label, "#FF0404", "arrowDown",position="atPriceBottom")

            if not self.bootstrapMode:
                await self.orderManager.abort_smart(symbol)

                await OrderTaskManager.cancel_orderBySymbol(symbol)

                pos = Balance.get_position(symbol)
                if (pos and pos.position>0):
                    logger.info(f"SELL ALL {symbol} {pos.position} ")
                    ret = await self.orderManager.smart_sell_limit(symbol,pos.position, self.client.getTicker(symbol))


            #    await self.send_event(symbol, "SELL", f"SELL",f"SELL",color="#FF0404", ring="news")
            return trade
        else:   
            return None
    
    def hasCurrentTrade(self,symbol):
        if not self.bootstrapMode and not self.backtestMode:
                if self.has_meta(symbol, "last_trade"):
                    last_trade : PositionTrade = self.get_meta(symbol, "last_trade")
                    return last_trade if last_trade.isClosed()==False else None   
                else:
                    return None    
        else:
           self.book.hasCurrentTrade(symbol)

    def buyGain(self,symbol,close):
        if not self.bootstrapMode and not self.backtestMode:
                if self.has_meta(symbol, "last_trade"):
                    #logger.info(f"BUYGAIN has_meta {symbol} last_trade {self.get_meta(symbol, 'last_trade').to_dict()}")    
                    last_trade : PositionTrade = self.get_meta(symbol, "last_trade")
                    if not last_trade.isClosed():
                        tot = 0.0
                        c=0
                        for op in last_trade.list:
                            if op.side == "BUY":
                                c=c+1
                                gain = 100.0 * ((close - op.price) /  op.price)
                                tot+= gain
                            
                        return tot /   c  
                    else:
                        return 0    
                else:
                    return 0    
        else:
            if self.book.hasCurrentTrade(symbol):
                return self.book.gain(symbol,close)[0]
            else:
                return 0


    ###############################
    def populate_indicators(self) :
      
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_9 = self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        sma_15 = self.addIndicator(self.timeframe,SMA("sma_15","close",timeperiod=15))

        self.add_plot(sma_9, "sma_9","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_15, "sma_15","#a79600", "main",  lineWidth=1)

    
    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        if self.bootstrapMode:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
            return
        
        use_day=True

        #logger.info(f"TRADE_SYMBOL_AT {symbol} {local_index}  {dataframe.iloc[local_index]['timestamp']}")  

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
       
        close = last["close"]
        volume = last["day_volume_history"]    

        if volume> 20_000_000:
            if not self.hasCurrentTrade(symbol):
            
                if last["sma_9"] >last["sma_15"]:
                    await self.buy(symbol,last["timestamp"],close,100,label=f"up")   

            else:
                gain = self.buyGain(symbol,close)

                logger.info(f"SELL GAIN {symbol} {gain}  ")      

                if gain > 2:
                    trade = await self.sell(symbol,last["timestamp"],close,label=f"gain {gain:.2f}%")                  
