from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


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

    def gain(self):
        return 100.0 * (self.exit_price - self.entry_price) / self.entry_price
    
    def pnl(self):
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity

    def toDict(self):
        return {"symbol" : self.symbol,"side" : self.side, "entry_price":self.entry_price, "exit_price": self.exit_price,
                "quantity": self.quantity , "gain":  self.gain()  }
  
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

    def has_any_trade(self):
        return bool(self.currentOrder)

    def get_first_trade(self):
        return next(iter(self.currentOrder.values()), None)
    
    def long(self, symbol, price, quantity, label):

        if self.position.open_long(symbol, float(price), float(quantity)):

            order = Order(symbol, "long",float(price), float(quantity), label)
            self.orders.append(order)
            self.currentOrder[symbol] = order
            return order

    def short(self, symbol, price, quantity, label):

        if self.position.open_short(symbol, float(price), float(quantity)):

            order = Order(symbol, "short",float(price), float(quantity), label)
            self.orders.append(order)
            return order

    def close(self, symbol, price):

        if symbol not in self.position.positions:
            return

        qty = self.position.positions[symbol]
        entry = self.position.entry_price[symbol]

        side = "long" if qty > 0 else "short"

        trade = Trade(symbol, entry, float(price), abs(qty), side)

        self.trades.append(trade)

        self.position.close(symbol, float(price))

        del self.currentOrder[symbol]

    def gain(self, symbol, actual_price):

        if symbol not in self.position.positions:
            return None
       
        qty = self.position.positions[symbol]
        entry = self.position.entry_price[symbol]

        return 100.0 * (actual_price- entry) / entry

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
                ),
                "trade" : [ x.toDict() for x in trades]
            }

        report["by_symbol"] = symbol_report

        return report
    

            
  
  