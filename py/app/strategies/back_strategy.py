from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
from company_loaders import *
from collections import deque
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

#from strategy.order_strategy import *

########################

class Order:
    def __init__(self, symbol, side, price, quantity, label):
        self.symbol = symbol
        self.side = side
        self.price = price
        self.quantity = quantity
        self.label = label

    def value(self):
        return self.price * self.quantity

class Trade:
    def __init__(self, symbol, entry_price, exit_price, quantity, side):
        self.symbol = symbol
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.quantity = quantity
        self.side = side

    def pnl(self):
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity
  
class Position:

    def __init__(self, budget):
        self.start_budget = budget
        self.budget = budget
        self.positions = {}
        self.entry_price = {}

    def open_long(self, symbol, price, quantity):

        cost = price * quantity

        if cost > self.budget:
            print("Not enough budget")
            return False

        self.budget -= cost

        self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        self.entry_price[symbol] = price

        return True

    def open_short(self, symbol, price, quantity):

        gain = price * quantity

        self.budget += gain

        self.positions[symbol] = self.positions.get(symbol, 0) - quantity
        self.entry_price[symbol] = price

        return True

    def close(self, symbol, price):

        if symbol not in self.positions:
            return None

        qty = self.positions[symbol]
        entry = self.entry_price[symbol]

        if qty > 0:
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * abs(qty)

        self.budget += abs(qty) * price

        self.positions.pop(symbol)
        self.entry_price.pop(symbol)

        return pnl

    def equity(self):
        return self.budget


class OrderBook:

    def __init__(self, position):

        self.orders = []
        self.trades = []
        self.position = position
        self.currentOrder={}

    def lastOrder(self):
        return self.orders[-1] if self.orders else None
    
    def hasCurrentTrade(self,symbol):
        return symbol in self.currentOrder

    def long(self, symbol, price, quantity, label):

        if self.position.open_long(symbol, price, quantity):

            order = Order(symbol, "long", price, quantity, label)
            self.orders.append(order)
            self.currentOrder[symbol] = order
            return order

    def short(self, symbol, price, quantity, label):

        if self.position.open_short(symbol, price, quantity):

            order = Order(symbol, "short", price, quantity, label)
            self.orders.append(order)
            return order

    def close(self, symbol, price):

        if symbol not in self.position.positions:
            return

        qty = self.position.positions[symbol]
        entry = self.position.entry_price[symbol]

        side = "long" if qty > 0 else "short"

        trade = Trade(symbol, entry, price, abs(qty), side)

        self.trades.append(trade)

        self.position.close(symbol, price)

        del self.currentOrder[symbol]

    def report(self):

        total_pnl = sum(t.pnl() for t in self.trades)

        wins = [t for t in self.trades if t.pnl() > 0]
        losses = [t for t in self.trades if t.pnl() <= 0]

        win_rate = len(wins) / len(self.trades) if self.trades else 0

        avg_gain = sum(t.pnl() for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl() for t in losses) / len(losses) if losses else 0

        profit_factor = (
            sum(t.pnl() for t in wins) /
            abs(sum(t.pnl() for t in losses))
            if losses else 0
        )

        # -------- REPORT GLOBALE --------
        report = {
            "start_budget": self.position.start_budget,
            "final_equity": self.position.equity(),
            "total_pnl": total_pnl,
            "trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_gain": avg_gain,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor
        }

        # -------- REPORT PER SYMBOL --------
        trades_by_symbol = defaultdict(list)

        for t in self.trades:
            trades_by_symbol[t.symbol].append(t)

        symbol_report = {}

        for symbol, trades in trades_by_symbol.items():

            wins = [t for t in trades if t.pnl() > 0]
            losses = [t for t in trades if t.pnl() <= 0]

            pnl_total = sum(t.pnl() for t in trades)

            symbol_report[symbol] = {
                "trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) if trades else 0,
                "total_pnl": pnl_total,
                "avg_gain": sum(t.pnl() for t in wins) / len(wins) if wins else 0,
                "avg_loss": sum(t.pnl() for t in losses) / len(losses) if losses else 0,
                "profit_factor": (
                    sum(t.pnl() for t in wins) /
                    abs(sum(t.pnl() for t in losses))
                    if losses else 0
                )
            }

        report["by_symbol"] = symbol_report

        return report
##################################


class _BackStrategy(SmartStrategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []
        self.legend = []
        self.marker_map= {}

        self.position = Position(10000)
        self.book = OrderBook( self.position )

    def buy(self,  symbol, price, label):
        logger.info(f"BUY {symbol} {label}")
        self.book.long(symbol, price, 100,label)

        
    def sell(self,symbol,price,label):
        logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        self.book.close(symbol,price)
        pass

    def onBackEnd(self):

        logger.info(f"REPORT {self.book.report()}")
        pass


#################

class BackStrategy(_BackStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :
        
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))

        self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))


    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :

       
    
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(2)}" )

    
        time = dataframe.iloc[-1]["timestamp"]
        close = dataframe.iloc[-1]["close"]
        sma_9 = dataframe.iloc[-1]["sma_9"]
        sma_20 = dataframe.iloc[-1]["sma_20"]

        #logger.info(f"{symbol} {sma_9} {sma_20}")

        if (sma_9 > sma_20 and not self.book.hasCurrentTrade(symbol)):
            self.buy(symbol, close, "BUY")

        if (sma_9 < sma_20 and self.book.hasCurrentTrade(symbol)):
            self.sell(symbol, close, "SELL")

        #gain = dataframe.iloc[-1]["gain"]
        #if gain > 1:
        #    logger.info(f"{symbol} gain {gain} {ts_to_local_str(time)} {sma_9} {sma_20}")

  