from ib_insync import *
import asyncio
import time
import pandas as pd
from datetime import datetime, timedelta
import logging
import json
import math
import sqlite3
from config import DB_FILE,CONFIG_FILE
from utils import convert_json
from renderpage import WSManager
import traceback
from collections import deque

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

#conn = sqlite3.connect(DB_FILE, isolation_level=None)
#cur = conn.cursor()

logging.getLogger("ib_insync").setLevel(logging.WARNING)

class TradeOp:
    def __init__(self,side, price,size,time):
        self.side=side
        self.price=price
        self.size=size
        self.time = time
        
        
class PositionTrade:

    
    def __init__(self, symbol):
        self.symbol = symbol
        self.list=[]

    def appendBuy(self, price,size,time):
        self.list.append(TradeOp("BUY", price,size,time))

    def appendSell(self, price,size,time):
        self.list.append(TradeOp("SELL", price,size,time))
        #self.exit_time = datetime.now()
        #self.exit_price = exit_price
        #self.pnl = (exit_price - self.entry_price) * self.entry_size

    def isClosed(self):
        if len(self.list)>0:
            return self.list[-1].side == "SELL"
        else:
            return False
        
    @property
    def pnl(self):
 
        buys = deque()
        pnl = 0.0

        for op in self.list:
            if op.side == "BUY":
                buys.append([op.size, op.price])

            elif op.side == "SELL":
                sell_size = op.size
                sell_price = op.price

                while sell_size > 0 and buys:
                    buy_size, buy_price = buys[0]

                    matched = min(buy_size, sell_size)

                    pnl += (sell_price - buy_price) * matched

                    buy_size -= matched
                    sell_size -= matched

                    if buy_size == 0:
                        buys.popleft()
                    else:
                        buys[0][0] = buy_size

        return pnl

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "list": [
                {
                    "side": op.side,
                    "price": op.price,
                    "size": op.size,
                    "time": op.time,
                }
                for op in self.list
            ],
            "pnl": self.pnl
        }



###############

class Position:
    position:float
    avgCost:float
    marketPrice:float
    marketValue:float

    def __init__(self,symbol):
        self.symbol=symbol
        self.position=0
        self.avgCost=None
        self.marketPrice=None
        self.marketValue=None

        #self.current_trade: PositionTrade | None = None
        #self.trades: list[PositionTrade] = []

    async def set(self, name, value):
        if name == "position":
            old_position = self.position
            self.position = value

            '''
            logger.info(f"{old_position} -> {value} ")
            # OPEN TRADE: 0 -> >0
            if old_position == 0 and value > 0:
                #self.current_trade = PositionTrade(
                #    self.symbol
                #)
                #self.current_trade.appendBuy( entry_price=self.marketPrice,entry_size=value)
             
                if Balance.ws:
                    msg = {"type": "POSITION_TRADE", "data" : self.current_trade.to_dict() }
                    await Balance.ws.broadcast(msg)

               
            # CLOSE TRADE: >0 -> 0
            elif old_position > 0 and value == 0 and self.current_trade:
                pass
                #self.current_trade.appendSell(self.marketPrice)
                #self.trades.append(self.current_trade)
              
                if Balance.ws:
                    msg = {"type": "POSITION_TRADE", "data" : self.current_trade.to_dict() }
                    await Balance.ws.broadcast(msg)
            
                #self.current_trade = None
            '''

        elif name == "avgCost":
            self.avgCost = value

        elif name == "marketPrice":
            self.marketPrice = value
            

    def to_dict(self):
        return {
            "symbol" :  self.symbol ,
            "position" :  self.position ,
            "avgCost" :  self.avgCost if self.avgCost is not None else None,
            "marketPrice" :  self.marketPrice if self.marketPrice else None,
            "marketValue" :  self.marketValue if self.marketValue else None,
        }
 
    
###############

class Balance:
    
    ws :WSManager = None
    positionMap : dict[str,Position]

    def __init__(self,config,ib,props):
        Balance.props=props
        Balance.ib=ib
        Balance.positionMap={}
        Balance.run_mode = config["live_service"].get("mode","sym") 
        Balance.cash_usd=0
        Balance.cash_eur=0
       
        if ib:
            Balance.ib.updatePortfolioEvent  += Balance.onUpdatePortfolio
            Balance.ib.positionEvent   += Balance.onPositionEvent 
            Balance.ib.accountSummaryEvent     += Balance.onAccountSummaryEvent   
            Balance.ib.accountValueEvent     += Balance.onAccountValueEvent 
            
            
            #d = {v.tag: v.value for v in values}
            #logger.info(f"accountValues: {values}") 

    async def bootstrap():
        
        if  Balance.run_mode  != "sym":
            for value in Balance.ib.accountValues():    
                    #logger.info(f"accountValues: {v}") 
                    if value.tag == "CashBalance" and value.currency == "USD":
                        Balance.cash_usd = float(value.value)
                    
                    if value.tag == "CashBalance" and value.currency == "EUR":
                        Balance.cash_eur = float(value.value)

            positions  = Balance.ib.positions()
            logger.info(f"positions: {positions}")  
            #list = []
            for p in positions:
                await Balance.update(p.contract.symbol,{"symbol": p.contract.symbol, "position": p.position, "avgCost":p.avgCost})
                #list.append({"symbol": p.contract.symbol, "position": p.position, "avgCost":p.avgCost})

            def get_cash_usd ():
                return Balance.cash_usd 
            Balance.props.add_computed("account.cash_usd", get_cash_usd)

            def get_cash_eur ():
                return Balance.cash_eur
            Balance.props.add_computed("account.cash_eur", get_cash_eur)
         
    
    def to_dict():
        return  [ v.to_dict() for k,v in Balance.positionMap.items()]

    def get_position(symbol)-> Position:
        if symbol in Balance.positionMap:
            return Balance.positionMap[symbol]
        else:
            return Position(symbol)
    
    async def update(symbol, data):

        logger.info(f"BALANCE  {data}")
        if not symbol in Balance.positionMap:
            Balance.positionMap[ symbol] = Position(symbol)

        if "marketPrice" in data :
            #Balance.positionMap[symbol].avgCost = data["avgCost"]
            await Balance.positionMap[symbol].set("marketPrice",data["marketPrice"])

        if "avgCost" in data :
            #Balance.positionMap[symbol].avgCost = data["avgCost"]
            await Balance.positionMap[symbol].set("avgCost",data["avgCost"])
   
        if "position" in data :
            await Balance.positionMap[symbol].set("position",data["position"])
     
        #if "marketPrice" in data and data["marketPrice"]:
        #    Balance.positionMap[symbol].marketPrice = data["marketPrice"]
        #if "marketValue" in data and data["marketValue"]:
        #    Balance.positionMap[symbol].marketValue = data["marketValue"]
    
    async def onUpdatePortfolio(portfoglio : PortfolioItem):
        #logger.info(f"onUpdatePortfolio: {portfoglio}")

      
        msg = {"type": "UPDATE_PORTFOLIO", "symbol" : portfoglio.contract.symbol , "position" : portfoglio.position, "marketPrice": portfoglio.marketPrice, "marketValue" : portfoglio.marketValue}
        await Balance.update(portfoglio.contract.symbol,msg)
        if Balance.ws:
            ser = json.dumps(msg)
            await Balance.ws.broadcast(msg)

    async def onPositionEvent(position : Position):
        
        #logger.info(f"onPositionEvent: {position}")
      
        msg = {"type": "POSITION", "symbol" : position.contract.symbol , "position" : position.position, "avgCost": position.avgCost}
        #await Balance.update(position.contract.symbol,msg)
        if Balance.ws:
            ser = json.dumps(msg)
            await Balance.ws.broadcast(msg)

        
    async def sym_change(symbol, quantity, price):
        logger.info(f"sym_change: {symbol} {quantity} {price}")
        if not symbol in Balance.positionMap:
            Balance.positionMap[ symbol] = Position(symbol)

        pos = Balance.get_position(symbol)
        logger.info(f" pos.position: { pos.position}")
        
        msg = {"type": "POSITION", "symbol" : symbol , "position" : float(pos.position) + float(quantity), "avgCost": price}
        
        await Balance.update(symbol,msg)
        if Balance.ws:
            ser = json.dumps(msg)
            await Balance.ws.broadcast(msg)

    async def onAccountSummaryEvent(value : AccountValue):
        logger.info(f"onAccountSummaryEvent: {value}")

    async def onAccountValueEvent(value : AccountValue):
        #logger.info(f"onAccountValueEvent: {value.tag}")
        #TODO
        if value.tag == "CashBalance" and value.currency == "USD":
            Balance.cash_usd = float(value.value)
            if Balance.ws:
                await Balance.ws.broadcast({"type":"props", "path": "account.cash_usd", "value":Balance.cash_usd } )
        
        if value.tag == "CashBalance" and value.currency == "EUR":
            Balance.cash_eur = float(value.value)
            if Balance.ws:
                await Balance.ws.broadcast({"type":"props", "path": "account.cash_eur", "value":Balance.cash_eur } )