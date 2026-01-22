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

    def to_dict(self):
        return {
            "symbol" :  self.symbol ,
            "position" :  self.position ,
            "avgCost" :  self.avgCost if self.avgCost else None,
            "marketPrice" :  self.marketPrice if self.marketPrice else None,
            "marketValue" :  self.marketValue if self.marketValue else None,
        }

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

    def get_position(symbol):
        if symbol in Balance.positionMap:
            return Balance.positionMap[symbol]
        else:
            return Position(symbol)
    
    def update(symbol, data):

        logger.info(f"BALANCE  {data}")
        if not symbol in Balance.positionMap:
            Balance.positionMap[ symbol] = Position(symbol)
        
        if "position" in data and data["position"]:
            Balance.positionMap[symbol].position = data["position"]
        if "avgCost" in data and data["avgCost"]:
            Balance.positionMap[symbol].avgCost = data["avgCost"]
        if "marketPrice" in data and data["marketPrice"]:
            Balance.positionMap[symbol].marketPrice = data["marketPrice"]
        if "marketValue" in data and data["marketValue"]:
            Balance.positionMap[symbol].marketValue = data["marketValue"]
    
    async def onUpdatePortfolio(portfoglio : PortfolioItem):
        #logger.info(f"onUpdatePortfolio: {portfoglio}")

      
        msg = {"type": "UPDATE_PORTFOLIO", "symbol" : portfoglio.contract.symbol , "position" : portfoglio.position, "marketPrice": portfoglio.marketPrice, "marketValue" : portfoglio.marketValue}
        Balance.update(portfoglio.contract.symbol,msg)
        if Balance.ws:
            ser = json.dumps(msg)
            await Balance.ws.broadcast(msg)

    async def onPositionEvent(position : Position):
        #logger.info(f"onPositionEvent: {position}")

        msg = {"type": "POSITION", "symbol" : position.contract.symbol , "position" : position.position, "avgCost": position.avgCost}
        Balance.update(position.contract.symbol,msg)
        if Balance.ws:
            ser = json.dumps(msg)
            await Balance.ws.broadcast(msg)

    async def onAccountValueEvent(value : AccountValue):
        logger.info(f"onAccountValueEvent: {value}")

    async def onAccountSummaryEvent(value : AccountValue):
        logger.info(f"onAccountSummaryEvent: {value}")