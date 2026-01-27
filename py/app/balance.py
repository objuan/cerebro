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


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

#conn = sqlite3.connect(DB_FILE, isolation_level=None)
#cur = conn.cursor()

logging.getLogger("ib_insync").setLevel(logging.WARNING)


class PositionTrade:
    def __init__(self, symbol, entry_price, entry_size):
        self.symbol = symbol
        self.entry_time = datetime.now()
        self.entry_price = entry_price
        self.entry_size = entry_size

        self.exit_time = None
        self.exit_price = None
        self.pnl = None

    def close(self, exit_price):
        self.exit_time = datetime.now()
        self.exit_price = exit_price
        self.pnl = (exit_price - self.entry_price) * self.entry_size

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "entry_time": int(self.entry_time.timestamp() * 1000) if self.entry_time else None,
            "entry_price": self.entry_price,
            "entry_size": self.entry_size,
            "exit_time": int(self.exit_time.timestamp() * 1000) if self.exit_time else None,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
        }

    def getHistory(self):
        h = []
        for trade in self.trades:
            h.append(trade.to_dict())
        return h

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

        self.current_trade: PositionTrade | None = None
        self.trades: list[PositionTrade] = []

    async def set(self, name, value):
        if name == "position":
            old_position = self.position
            self.position = value

            logger.info(f"{old_position} -> {value}  {self.current_trade}")
            # OPEN TRADE: 0 -> >0
            if old_position == 0 and value > 0:
                self.current_trade = PositionTrade(
                    self.symbol,
                    entry_price=self.marketPrice,
                    entry_size=value
                )
             
                if Balance.ws:
                    msg = {"type": "POSITION_TRADE", "data" : self.current_trade.to_dict() }
                    await Balance.ws.broadcast(msg)

               
            # CLOSE TRADE: >0 -> 0
            elif old_position > 0 and value == 0 and self.current_trade:
                self.current_trade.close(self.marketPrice)
                self.trades.append(self.current_trade)
              
                if Balance.ws:
                    msg = {"type": "POSITION_TRADE", "data" : self.current_trade.to_dict() }
                    await Balance.ws.broadcast(msg)
            
                self.current_trade = None


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
    def get_history()
    
###############

class Balance:
    
    ws :WSManager = None
    positionMap : dict[str,Position]

    def __init__(self,config,ib):
        Balance.ib=ib
        Balance.positionMap={}
        Balance.run_mode = config["live_service"].get("mode","sym") 

        if ib:
            Balance.ib.updatePortfolioEvent  += Balance.onUpdatePortfolio
            Balance.ib.positionEvent   += Balance.onPositionEvent 
            #OrderManager.ib.accountValueEvent    += OrderManager.onAccountValueEvent  
            Balance.ib.accountSummaryEvent     += Balance.onAccountSummaryEvent   

    async def bootstrap():
        
        if  Balance.run_mode  != "sym":
            positions  = Balance.ib.positions()

            #list = []
            for p in positions:
                Balance.update(p.contract.symbol,{"symbol": p.contract.symbol, "position": p.position, "avgCost":p.avgCost})
                #list.append({"symbol": p.contract.symbol, "position": p.position, "avgCost":p.avgCost})

        pass 
    
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

    async def onAccountValueEvent(value : AccountValue):
        logger.info(f"onAccountValueEvent: {value}")

    async def onAccountSummaryEvent(value : AccountValue):
        logger.info(f"onAccountSummaryEvent: {value}")