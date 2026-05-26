import sys


if __name__ =="__main__":
    sys.argv.append("BINANCE")

import random
from typing import List
from fastapi import HTTPException
from ib_insync import *
import asyncio
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
import logging
import json
import math
import sqlite3
from config import DB_FILE,CONFIG_FILE,BINANCE_MODE
from utils import convert_json
from renderpage import WSManager
from balance import Balance, PositionTrade
import traceback
from decimal import Decimal, ROUND_DOWN
from binance import AsyncClient, BinanceAPIException,BinanceSocketManager
from mulo_live_client import MuloLiveClient
import pymysql

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

#conn = sqlite3.connect(DB_FILE, isolation_level=None)


logging.getLogger("ib_insync").setLevel(logging.WARNING)

def format_qty(qty, step_size):
    qty = Decimal(str(qty))
    step = Decimal(str(step_size))

    return float((qty // step) * step)

def format_price(price, tick_size):
    import math
    
    d_tick_size = Decimal(tick_size)
    precision = len(tick_size.split(".")[1])
    price = math.floor(price / d_tick_size) * d_tick_size

    return Decimal(f"{price:.{precision}f}")

##########################

class OrderManager:
    def __init__(self,config,client):
        self.config=config
        self.client=client

    async def bootstrap(self,ib):
        pass
    
    def close_order_from_external(self, symbol,action):
        logger.info(f"close_order_from_external {symbol}")

        trade_id =  random.randint(10**9, 10**10 - 1)

        utc_now = datetime.now(timezone.utc).isoformat()
        log = [ {"time": utc_now, "status": "Filled", "fee": 0 , "message": "", "errorCode": 0}]
        data = {"trade_id": trade_id, "orderId": trade_id, "symbol": symbol, "exchange": "BINANCE", "action":action, "orderType": "MARKET", "totalQuantity": 0, "lmtPrice": 0.0, "status": "Filled", "filled": True, "remaining": 0.0, "avgFillPrice": 0.011733, "lastFillPrice": 0, "log": log}

        ser = json.dumps(data)
        
        self.client.execute(f'''INSERT INTO  {self.order_table} (trade_id, symbol, side,status, event_type, data)
                    VALUES (%s, %s, %s, %s, %s,%s)''',
                (trade_id, symbol,action, "Filled","STATUS",ser))
         

    async def _addOrder(self,data,type):
        #data =  trade_to_dict(trade)
        action = data["action"]
        ser = json.dumps(data)

        # 🔍 Controllo duplicato
        exists = self.client.get_df(f'''SELECT 1 FROM  {self.order_table} 
                    WHERE trade_id=%s AND symbol=%s AND side=%s 
                    AND status=%s AND event_type=%s AND data=%s 
                    LIMIT 1''',
                    (data["trade_id"],
                    data["symbol"],
                    action,
                    data["status"],
                    type,
                    ser))

        
        if len(exists)>0:
            logger.info("Duplicate order detected → skipping insert & event")
            return  # 🚫 STOP: niente insert e niente send

        self.client.execute(f'''INSERT INTO  {self.order_table} (trade_id, symbol, side,status, event_type, data)
                    VALUES (%s, %s, %s, %s, %s,%s)''',
                (data["trade_id"], data["symbol"],action, data["status"],type,ser))
        
        #if self.ws:
            #data["type"] = "ORDER"
        ser = json.dumps(data)
        await self.client.send_order_event("ORDER",
                 { "trade_id": data["trade_id"], 
                    "symbol":data["symbol"],
                    "status" :data["status"],
                    "event_type":type,  
                    "timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") ,
                    "data" : data 
                   }
                 )


        if action =="BUY" and data["status"] =="Filled" and type=="STATUS":
                msg = { "data" :self.getLastTrade(data["symbol"]).to_dict()}
                #await self.ws.broadcast(msg)

                await self.client.send_trade_event("POSITION_TRADE",msg)
                if self.strategyManager:
                    await self.strategyManager.on_live_trade_event("POSITION_TRADE",self.getLastTrade(data["symbol"]))
            
        if action =="SELL" and data["status"] =="Filled" and type=="STATUS":
                if self.getLastTrade(data["symbol"]):
                    msg = { "data" :self.getLastTrade(data["symbol"]).to_dict()}
                    #await self.ws.broadcast(msg)

                    await self.client.send_trade_event("POSITION_TRADE",msg)
                    if self.strategyManager:
                        await self.strategyManager.on_live_trade_event("POSITION_TRADE",self.getLastTrade(data["symbol"]))

    ####################################

    def getTradeByTradeID(self,trade_id)-> PositionTrade:
        
        df = self.client.get_df(f"""
                select * from  {self.order_table} 
                WHERE trade_id = '{trade_id}' 
                AND status = 'Filled' AND event_type = 'STATUS'
                order by id desc 
                LIMIT 10
                """)
        
        trades = self.rebuild_trades(df)
        
        #PositionTrade
        if len(trades)>0:
            return trades[-1]
        else:
            return None
        

    def rebuild_trades(self, df) -> List[PositionTrade]:
        trades = []

        # group per symbol
        for symbol, g in df.groupby("symbol"):
            current = None

            # scorri dall'ultima riga alla prima
            for row in g.iloc[::-1].itertuples(index=False):
                side = row.side
                data = json.loads(row.data)

                #logger.info(f"rebuild_trades row {data}")

                price = data["avgFillPrice"]
                size = data["totalQuantity"]
                trade_id = data["trade_id"]

                time = data["log"][-1]["time"]
                dt = datetime.fromisoformat(time)
                unix_time = dt.timestamp()

                pnl=0
                comm=0
                if BINANCE_MODE:
                    for l in data["log"]:
                        #logger.info(l)
                        if "fee" in l:
                            comm+= l["fee"]
                else:
                    df = self.client.get_df(f""" select * from ib_order_commissions  
                        WHERE trade_id = '{trade_id}'  """)
                    if len(df)>0:
                        pnl = + df.iloc[0]["pnl"]
                        comm =  df.iloc[0]["commission"]

                if side == "BUY":
                    if current is None:
                        current = PositionTrade(symbol)
                        trades.append(current)

                    current.appendBuy(price, size, unix_time,pnl,comm)
                    
                elif side == "SELL":
                    if current is not None:
                        current.appendSell(price, size, unix_time,pnl,comm)

                        if current.isClosed:
                            current = None

        #logger.info(f"trades {len(trades)}")
        return trades

    
    def getTradeHistory(self,symbol)-> List[PositionTrade]:
        
        if symbol:

            df = self.client.get_df(f"""
                SELECT o.*

                FROM  {self.order_table} o

                JOIN (
                    SELECT
                        trade_id,
                        MAX(id) AS max_id

                    FROM  {self.order_table}

                    WHERE status = 'Filled'
                    AND symbol = %s
                    AND event_type = 'STATUS'

                    GROUP BY trade_id
                ) t

                ON o.id = t.max_id

                ORDER BY o.symbol ASC, o.id DESC

                LIMIT 10
            """, (symbol,))

        else:

            # TODAY
            df = self.client.get_df(f"""
                SELECT o.*

                FROM  {self.order_table} o

                JOIN (
                    SELECT
                        trade_id,
                        MAX(id) AS max_id

                    FROM  {self.order_table}

                    WHERE status = 'Filled'
                    AND event_type = 'STATUS'
                    AND timestamp >= CURDATE()

                    GROUP BY trade_id
                ) t

                ON o.id = t.max_id

                ORDER BY o.symbol ASC, o.id DESC
            """)
                
        trades = self.rebuild_trades(df)
        
        #PositionTrade

        return trades
    
    def getLastTrade(self,symbol)-> PositionTrade:
        
        df = self.client.get_df(f"""
                select * from  {self.order_table} 
                WHERE SYMBOL = '{symbol}' AND status = 'Filled' AND event_type = 'STATUS'
                order by id desc 
                LIMIT 10
                """)
        
        trades = self.rebuild_trades(df)
        
        #PositionTrade
        if len(trades)>0:
            return trades[-1]
        else:
            return None

    #########

    async def smart_buy_limit(self,symbol,totalQuantity,ticker):
        pass

    async def smart_sell_limit(self,symbol,totalQuantity,ticker):
        pass
    
    def sell_all(self,symbol):
        self._sell(symbol,100)

    def sell(self,symbol,perc):
        pass
        
         
    #####

    async def onTicker(self,symbol,lastPrice):
        pass

    async def batch(self):
        while True:
            await asyncio.sleep(1)
            

    ib=None
    #ws :WSManager = None
    task_orders = []

    tick_cache = {}
    

    def __init__(self,config,client):
        self.config=config
        self.client=client
        self.lastError="" 
        self.sym_mode = config["live_service"]["mode"] =="sym"
        
        self.exec_to_order = {}
        self.order_commissions = {}
        self._last_call_time = {}  # {symbol: timestamp}
        # Assegna gli event handlers
        self.doSmartAbort=False
        self.strategyManager=None
        self.lastTradeMap = {}

    async def bootstrap(self,ib):
        pass



##############


    def sell_limit(self,symbol,totalQuantity,lmtPrice):
        self._order_limit(symbol,"SELL",totalQuantity,lmtPrice)

    def buy_limit(self,symbol,totalQuantity,lmtPrice):
        self._order_limit(symbol,"BUY",totalQuantity,lmtPrice)

 
    async def smart_buy_limit(self,symbol,totalQuantity,ticker):
        return await self._smart_limit(symbol, "BUY",totalQuantity, ticker)
       
    async def smart_sell_limit(self,symbol,totalQuantity,ticker):
        return  await self._smart_limit(symbol, "SELL",totalQuantity, ticker)
     
    async def smart_buy_market(self,symbol,totalQuantity,ticker):
        return await self._smart_market(symbol, "BUY",totalQuantity, ticker)
  
    async def smart_sell_market(self,symbol,totalQuantity,ticker):
        return await self._smart_market(symbol, "SELL",totalQuantity, ticker)

    async def _smart_market(self,symbol,op, totalQuantity,ticker):
        if self.sym_mode:
            await self._smart_limit_sym(symbol,op,totalQuantity,ticker)
        else:
            await self._smart_limit_real(symbol,op,totalQuantity,ticker,"MARKET")

    async def _smart_limit(self,symbol,op, totalQuantity,ticker):
        if self.sym_mode:
            await self._smart_limit_sym(symbol,op,totalQuantity,ticker)
        else:
            await self._smart_limit_real(symbol,op,totalQuantity,ticker,"LIMIT")

    async def _smart_limit_sym(self,symbol,op, totalQuantity,ticker):
        logger.info(f"SMART SYM {op} LIMIT ORDER {symbol} q:{totalQuantity}")
      
        if True:#self.ws:
            #data["type"] = "ORDER"
            trade_id = 614261832
            
            data = {
                "trade_id": trade_id,
                "orderId": 2018,
                "symbol": symbol,
                "exchange": "SMART",
                "action": op,
                "orderType": "LMT",
                "totalQuantity": totalQuantity,
                "lmtPrice": ticker["last"],
                "status": "Filled",
                "filled": 100.0,
                "remaining": 0.0,
                "avgFillPrice": ticker["last"],
                "lastFillPrice": ticker["last"],
                "log": [
                    {
                        "time": "2026-01-23T14:59:56.373293+00:00",
                        "status": "PendingSubmit",
                        "message": "",
                        "errorCode": 0
                    },
                    {
                        "time": "2026-01-23T14:59:56.551410+00:00",
                        "status": "PreSubmitted",
                        "message": "Fill 100.0@4.59",
                        "errorCode": 0
                    },
                    {
                        "time": "2026-01-23T14:59:56.552414+00:00",
                        "status": "Filled",
                        "message": "",
                        "errorCode": 0
                    }
                ]
            }
            logger.info(f"ticker {ticker}")
            logger.info(f"ticdataker {data}")
            ser = json.dumps(data)


            await self.client.send_order_event("ORDER",
                { "trade_id": trade_id, "symbol":symbol,
                    "status" :"Filled",
                    "event_type": "STATUS",  
                    "timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") ,
                     "data" : data 
             }  )
            
            '''
            await self.ws.broadcast(
                {"type": "ORDER", "trade_id": trade_id, "symbol":symbol,
                 "status" :"Filled","event_type": "STATUS",   "data" : data ,"timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") }
            )
            '''
            if op == "BUY":
                await Balance.sym_change(symbol,totalQuantity, ticker["last"] )
            else:
                await Balance.sym_change(symbol,-totalQuantity, ticker["last"] )

        return None


    #########

    async def batch(self):
        while True:
            await asyncio.sleep(1)
    '''
    async def send_order_event(self,type, data):
       
        try:
            #self.client.send_event("order", )
            logger.info(f"SEND t: {type} data: {data}")

            data["type"] = type
            await self.ws.broadcast(data)
            #logger.info(f"SEND DONE")
        except:
            logger.error("SEND ERROR", exc_info=True)
    '''
