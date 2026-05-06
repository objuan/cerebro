import sys


if __name__ =="__main__":
    sys.argv.append("BINANCE")

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

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

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


    

    async def _addOrder(self,data,type):
        #data =  trade_to_dict(trade)
        action = data["action"]
        ser = json.dumps(data)

        # 🔍 Controllo duplicato
        cur.execute('''SELECT 1 FROM ib_orders 
                    WHERE trade_id=? AND symbol=? AND side=? 
                    AND status=? AND event_type=? AND data=? 
                    LIMIT 1''',
                    (data["trade_id"],
                    data["symbol"],
                    action,
                    data["status"],
                    type,
                    ser))

        exists = cur.fetchone()
        if exists:
            logger.info("Duplicate order detected → skipping insert & event")
            return  # 🚫 STOP: niente insert e niente send

        cur.execute('''INSERT INTO ib_orders (trade_id, symbol, side,status, event_type, data)
                    VALUES (?, ?, ?, ?, ?,?)''',
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
                select * from ib_orders 
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
                    FROM ib_orders o
                    JOIN (
                        SELECT trade_id, MAX(id) AS max_id
                        FROM ib_orders
                        WHERE status = 'Filled'
                        AND SYMBOL = '{symbol}' 
                        AND event_type = 'STATUS'
                        GROUP BY trade_id
                    ) t
                    ON o.id = t.max_id
                    ORDER BY o.symbol ASC, o.id DESC
                    LIMIT 10;
                    """)
        else:
            #DAY
            df = self.client.get_df(f"""
                   SELECT o.*
                    FROM ib_orders o
                    JOIN (
                        SELECT trade_id, MAX(id) AS max_id
                        FROM ib_orders
                        WHERE status = 'Filled'
                        AND event_type = 'STATUS'
                        AND timestamp >= datetime('now', 'start of day')
                        GROUP BY trade_id
                    ) t
                    ON o.id = t.max_id
                    ORDER BY o.symbol ASC, o.id DESC;
                    """)
        
        trades = self.rebuild_trades(df)
        
        #PositionTrade

        return trades
    
    def getLastTrade(self,symbol)-> PositionTrade:
        
        df = self.client.get_df(f"""
                select * from ib_orders 
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
#####################################

class Binance_OrderManager(OrderManager):

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

        self.coin_info = {}

     
    async def bootstrap(self,ib):
        OrderManager.ib = ib     
        mode = self.config["markets"]["BINANCE"]["MODE"]
        logger.info(f"BINANCE MODE: {mode}")
        API_KEY = self.config["markets"]["BINANCE"][mode]["API_KEY"]
        API_SECRET = self.config["markets"]["BINANCE"][mode]["API_SECRET"]

        self.binance_client = await AsyncClient.create(API_KEY, API_SECRET,  testnet=mode=="PAPER")

        asyncio.create_task(self.user_stream_loop())
        

    async def get_last_orders(self,symbol, limit):
        orders = await self.binance_client.get_all_orders(
            symbol=symbol,
            limit=limit
        )
        list = []
        for order in orders:
             #logger.info(order)
            state = Binance_OrderManager.status_map[order["status"]]
            if state =="Filled":
                #logger.info(order)
                avg_price = float(order['cummulativeQuoteQty']) / float(order['executedQty'])

                trade =  {
                        "trade_id": order["orderId"],
                        "orderId": order["orderId"],
                        "time": order["time"],
                        "symbol": order["symbol"],
                        "exchange":"BINANCE",
                        "action": order["side"],
                        "orderType": order["type"],
                        "totalQuantity": order["origQty"],
                        "lmtPrice": getattr(order, "price", None),
                        "status": state,
                        "filled": state=="Filled",
                        "remaining": 0,
                        "avgFillPrice": avg_price,
                        "lastFillPrice": avg_price
           
                    }
                list.append(trade)
                #logger.info(trade)
        return list
        
    status_map = {
        "CANCELED" : "Cancelled",
        "NEW" : "Submitted",
        "FILLED" :"Filled",
        "PARTIALLY_FILLED" :"Partial Filled"
    }

    def compute_commissions_usdc(self,symbol, fee_asset, fee,price):
            base = symbol[:-4]       # 
            quote = symbol[-4:]      # 

            if fee_asset == quote:
                    fee_usdt = fee
            elif fee_asset == base:
                fee_usdt = fee * price
            else:
                # es. BNB → serve prezzo live
                fee_usdt = 0#fee * prices.get(fee_asset + "USDT", 0)
            return fee_usdt

    async def smart_limit(self,symbol,op, totalQuantity,ticker):
        #if self.sym_mode:
        #    await self._smart_limit_sym(symbol,op,totalQuantity,ticker)
        #else:
            await self._smart_limit_real(symbol,op,totalQuantity,ticker,"LIMIT")

    '''
    order_type = ["LIMIT","MARKET"]
    '''
    async def _smart_limit_real(self,symbol,op, totalQuantity,ticker,order_type):

        tick_size="2"
        stepSize=0.1
        if not symbol in self.coin_info:
            self.coin_info[symbol] =  await self.binance_client.get_symbol_info(symbol)
                
        for f in self.coin_info[symbol]["filters"]:
            if f["filterType"] == "PRICE_FILTER":
                tick_size = f["tickSize"]
             
                #logger.info(f"tick_size {f['tickSize']}-> {tick_size}")  

            if f["filterType"] == "LOT_SIZE":
                #LOT_SIZE {'filterType': 'LOT_SIZE', 'minQty': '0.10000000', 'maxQty': '92141578.00000000', 'stepSize': '0.10000000'}
                #logger.info(f"LOT_SIZE {f}")     
                stepSize =  Decimal(f["stepSize"])              

        old= totalQuantity
        totalQuantity = format_qty(totalQuantity,stepSize)

        logger.info(f"QUantity {old} -> {totalQuantity}  ({stepSize})")

        self.doSmartAbort=False
        now = time.time()
        last_time = self._last_call_time.get(symbol)
        if last_time is not None and (now - last_time) < 60:
            logger.warning(f"Chiamata bloccata per {symbol}: già eseguita meno di 1 minuto fa")
            return None

        '''
        return error if != None
        '''
        logger.info(f"SMART {op} LIMIT ORDER {symbol} q:{totalQuantity} type{order_type}")

        timeout = 120          # secondi
        interval = 4          # ciclo ogni secondo

        if op =="BUY":
            timeout = 30
            interval = 6

        start_time = time.time()
        
        trade=None
        submittedCount=0
        attempt = 0      
        while time.time() - start_time < timeout and not self.doSmartAbort:
                        
            if trade:

                trade = await self.binance_client.get_order(
                    symbol=trade["symbol"],
                    orderId=trade["orderId"]
                )

                state = Binance_OrderManager.status_map[trade['status']]
                logger.info(f"Redo  status {symbol} {state} ")

                if self.lastError!= None:
                    if self.lastError["errorCode"] ==  202:# Order Canceled 
                        pass
                    else:
                        logger.error(f"{self.lastError}")
                        return self.lastError

                if state== "Partial Filled":
                    pass

                elif state== "Cancelled":
                    logger.warning("Order Cancelled !!! ")
                    return None
                
                elif state== "Submitted":
                    #aspetto
                    submittedCount=submittedCount+1
                    if submittedCount == 3:
                        
                        #logger.info(f"filled {trade["filled"]}")
                        #if trade.orderStatus.filled==0:
                            permId = trade["orderId"]
                            logger.info(f"Force remove {permId}")
                            self.lastError = None
                            #self.cancel_order(permId)
                            #self.ib.cancelOrder(trade.order)
                            await self.cancel_order(permId)
                            trade=None
                        

                if trade and state == "Filled":
                    logger.info("BUY DONE")
                    return None

            if not trade:
                    
                    if ticker:
                        price_ticker = Decimal(ticker["last"])
                    else:
                        _ticker = await self.binance_client.get_symbol_ticker(symbol=symbol)
                        price_ticker = Decimal(_ticker["price"] )


                    if (op =="BUY"):
                        price = price_ticker+ Decimal(tick_size)*attempt
                        logger.info(f'Change price {price_ticker} s:{tick_size} ({attempt}) -> {price}')
                        formatted_price =   format_price(price, tick_size)
                            
                    else:
                        price = price_ticker- Decimal(tick_size)*attempt
                        formatted_price =   format_price(price, tick_size)   
                            
                    logger.info(f">> {order_type} : {symbol} ({attempt}) {op} {totalQuantity} at {price_ticker} -> {formatted_price} (tick_size:{tick_size}) ")

                        # 🔹 ORDINE
                    self.lastError = None
                    trade =  await self.create_order(symbol, op, order_type, totalQuantity, formatted_price)

                    if not trade:
                         logger.info("Error Exit")
                         return
                    
                    attempt=attempt+1
                    
                    submittedCount=0

                    ###trade:Trade = 
                    #if not self.wait_order(trade):
                    #    logger.error("Order not added !!! ")

            await asyncio.sleep(interval)

        if trade:
            logger.info("Final cancel")
            self.lastError = None
            #self.ib.cancelOrder(trade.order)
            await self.cancel_order(trade["orderId"])
            await asyncio.sleep(2)
      

        self.doSmartAbort=False
        self.lastTradeMap[symbol]= None
        return  {"reqId" : 0, "errorCode": -1, "errorString": "TIMEOUT"} 


    async def create_order(self,symbol,side,type,quantity, price=0, adjustPrice=False):
        try:
            logger.info(f"CREATE ORDER {symbol} {side} {type} {quantity} at {price}")
            if type =="MARKET":
                order = await self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity
                )
            else:
                if adjustPrice:
                    if not symbol in self.coin_info:
                        self.coin_info[symbol] =  await self.binance_client.get_symbol_info(symbol)
                    
                    for f in self.coin_info[symbol]["filters"]:
                            #logger.info(f"{f}")

                            if f["filterType"] == "PRICE_FILTER":
                                tick_size = float(f["tickSize"])
                                old = price
                                price =  math.floor(price / tick_size) * tick_size     
                                logger.info(f"tickSize:{tick_size} price {old} => {price}")        

                order = await self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    type="LIMIT",
                    quantity=quantity,
                    price = price,
                    timeInForce="GTC"
                )

            logger.info(order)

            '''
            if type =="MARKET":
                fee_usdt=0
                lastFillPrice=0
                avgFillPrice=0
                if len(order["fills"])>0:
                    fill = order["fills"][0]
                    fill["fee"]  = self.compute_commissions_usdc(order["symbol"],fill["commissionAsset"],float(fill["commission"]),float(fill["price"]))
                    fill["status"] =  Binance_OrderManager.status_map[order["status"]]
   
                trade =  {
                    "trade_id": order["orderId"],
                    "orderId": order["orderId"],
                    "symbol": order["symbol"],
                    "exchange":"BINANCE",
                    "action": order["side"],
                    "orderType": order["type"],
                    "totalQuantity": order["origQty"],
                    "lmtPrice": getattr(order, "price", None),
                    "status":  Binance_OrderManager.status_map[order["status"]],
                    "filled": Binance_OrderManager.status_map[order["status"]]=="Filled",
                    "remaining": 0,
                    "avgFillPrice": avgFillPrice,
                    "lastFillPrice": lastFillPrice,
                    "log": order["fills"],
                }

                await self._addOrder(trade, "NEW")
                '''
            return order
                    
        except BinanceAPIException as e:
            logger.error(e)
            self.lastError = {"symbol" : symbol, "errorCode":  99 , "errorString" :  e.message}
            
            await self.client.send_error_event( self.lastError )
            return None

    async def cancel_order(self,orderId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        ''''''
       
        orders = await self.binance_client.get_open_orders()

        for o in orders:
            if o["orderId"] == orderId:
                #logger.info(o)
                logger.info(f"CANCEL ORDER permId: {orderId} ")

                order = await self.binance_client.cancel_order(
                    symbol=o["symbol"],
                    orderId=orderId) 
                
                #logger.info(f"CANCEL ORDER : {order} ")

        return False
    
    
    async def cancel_orderBySymbol(self,symbol):
        '''
        Cancella un ordine pendente dato il suo symbol.
        '''
        logger.info(f"CANCEL ORDER symbol: {symbol} ")

        orders = await self.binance_client.get_open_orders()

        for o in orders:
            if o["symbol"] == symbol:
                logger.info(o)
     
                order = await self.binance_client.cancel_order(
                    symbol=o["symbol"],
                    orderId=o["orderId"]) 
        return False
              
    async def abort_smart(self,symbol):
        await self.cancel_orderBySymbol(symbol)

        if symbol in self.lastTradeMap:
            trade = self.lastTradeMap[symbol]
            del self.lastTradeMap[symbol]
            logger.info(f"abort_smart {symbol} { trade.symbol if trade else '..'}")
            self.doSmartAbort=True
           

    async def user_stream_loop(self):
   
        while True:
            try:
                bsm = BinanceSocketManager(self.binance_client)
                socket = bsm.user_socket()

                async with socket as stream:
                    while True:
                        #logger.info("WATCH")
                        msg = await stream.recv()
                        #if msg["e"] == "outboundAccountPosition":
                        logger.info(f">> {msg}")

                        if msg["e"] == "executionReport" :#and msg["x"] == "TRADE":
                            trade_id = msg["i"]
                            orderId =  msg["t"]
                            ts = msg["T"]
                            symbol = msg["s"]

                            side =  msg["S"]
                            type =  msg["o"]

                            qty_tot = float(msg["q"])    
                            price_limit = float(msg["p"])  # prezzo limit

                            qty_exe = float(msg["l"])    # quantità eseguita
                            
                            price = float(msg["L"])  # prezzo fill
                            
                            state = Binance_OrderManager.status_map[msg["X"]] # FILLED, NEW,"PARTIALLY_FILLED"

                            fee_asset = msg["N"]
                            fee = float(msg["n"]) #0.001 ZEN di commissione

                            fee_usdt = self.compute_commissions_usdc(symbol,fee_asset,fee,price)

                            cur.execute('''SELECT data FROM ib_orders 
                                    WHERE trade_id=? AND symbol=? AND side=? 
                                    LIMIT 1''',
                                    (trade_id,
                                    symbol,
                                    side
                                    ))

                            exists = cur.fetchone()

                            log=[]
                            if exists:
                                 log = json.loads(exists[0])["log"]  # 👈 parse JSON → dict
                                 #logger.info(log)

                            ts = int(ts / 1000)  # 👈 Binance usa millisecondi

                            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                            formatted = dt.isoformat()
                            
                            if not any(entry["status"] == state for entry in log):
                                log.append({'time': formatted, 'status' : state, 'fee':fee_usdt,'message': '' ,'errorCode': 0 })

                            trade =  {
                                        "trade_id": trade_id,
                                        "orderId": trade_id,
                                        "symbol": symbol,
                                        "exchange":"BINANCE",
                                        "action": side,
                                        "orderType": type,
                                        "totalQuantity": qty_tot,
                                        "lmtPrice": price_limit,
                                        "status":  state,
                                        "filled": state=="Filled",
                                        "remaining": qty_tot-qty_exe,
                                        "avgFillPrice": price,
                                        "lastFillPrice": price,
                                        "log":log
                                    }

                            await self._addOrder(trade, "STATUS")
                        
                          # 📌 EVENTO PRINCIPALE
                        if msg["e"] == "outboundAccountPosition":

                            for b in msg["B"]:
                                asset = b["a"]
                                free = float(b["f"])
                                locked = float(b["l"])

                                # stato precedente
                                #prev = balances_state.get(asset, {"free": 0, "locked": 0})
                            

                                msg = {"type": "UPDATE_PORTFOLIO", "symbol" :asset , "position" : free+locked, "marketPrice": 0, "marketValue" : 0}
                                await Balance.update(asset,msg)

                                if Balance.ws:
                                    ser = json.dumps(msg)
                                    await Balance.ws.broadcast(msg)

                                # 🔥 aggiorna solo se cambia qualcosa
                                '''
                                if free != prev["free"] or locked != prev["locked"]:
                                    balances_state[asset] = {
                                        "free": free,
                                        "locked": locked
                                    }

                                    total = free + locked

                                    await Balance.update(asset, {
                                        "symbol": asset,
                                        "position": total,
                                        "avgCost": 0
                                    })

                                    print(f"UPDATE {asset}: {total}")
                                '''

                        # 📌 EVENTO secondario (depositi, fee, ecc.)
                        '''
                        elif msg["e"] == "balanceUpdate":
                            asset = msg["a"]
                            delta = float(msg["d"])

                            prev = balances_state.get(asset, {"free": 0, "locked": 0})

                            new_free = prev["free"] + delta

                            balances_state[asset] = {
                                "free": new_free,
                                "locked": prev["locked"]
                            }

                            total = new_free + prev["locked"]

                            await Balance.update(asset, {
                                "symbol": asset,
                                "position": total,
                                "avgCost": 0
                            })

                            print(f"DELTA {asset}: {delta}")
                        '''

            except Exception as e:
                logger.error(f"WS error: {e}",exc_info=True)
                await asyncio.sleep(1)

#####################################

async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    client =  MuloLiveClient(DB_FILE,config,None)
    if BINANCE_MODE:
        ib =None
    else:
        ib = IB()
        port=config["general"]["ib_port_live"] if live_mode else config["general"]["ib_port_paper"]   

        ib.connect('127.0.0.1', port, clientId=1)

    live_mode = config["general"]["live_mode"] == "true"
   
    if BINANCE_MODE:
        o = Binance_OrderManager(config,client)
    else:
        o = IB_OrderManager(config,client)

    balance = Balance(config,ib,None)
 

    await Balance.bootstrap()


    await o.bootstrap(ib)

    await asyncio.sleep(1)

   # logger.info(f"ZEN : {Balance.get_position('ZEN').position} USDC:{Balance.get_position('USDC').position}")

    #orderId = await o.create_order("ZENUSDC","BUY","LIMIT", 1.5  ,7.1 )["orderId"] #0.02774 

    #await o.create_order("ZENUSDC","BUY","MARKET", 1  )

              
    #o = await o.smart_buy_limit("ZENUSDC",100, None)
    o = await o.smart_buy_market("LUNCUSDC",100, None)

    '''
    symbol = "ZENUSDC"
    pos = Balance.get_position("ZEN")
    if (pos and pos.position>0):
            logger.info(f"SELL ALL {symbol} {pos.position} ")
            ret = await o.smart_sell_limit(symbol,pos.position, None)
    '''

    #o = await o.smart_sell_limit("ZENUSDC", 2.5, None)

    #logger.info(f"ZEN : {Balance.get_position('ZEN').position} USDC:{Balance.get_position('USDC').position}")


    # 🔴 avvio task asincrona
    #task = asyncio.create_task(checkNewTrades())
    '''
    ticker = Ticker
    ticker["last"] = 2.802334
    
    #et = self.smart_buy_limit("IVF",100,ticker)

    ret = o.smart_sell_limit("IVF",100,ticker)
    if ret:
        logger.error(f">> {ret}")
     '''
    
    #self.smart_sell_limit()
    #self.order_limit("AAPL", 10,180)
    #logger.info("1")

    #ib.run()
    #await ib.sleep(float("inf"))
    while True:
        #await o.create_order("ZENUSDC","BUY","MARKET", 1  )
        #await o.cancel_order(orderId)
        await asyncio.sleep(5)

    logger.info("DONE")
    '''
    await asyncio.wait(
                    [task],
                    return_when=asyncio.FIRST_COMPLETED
                )
    '''
    
if __name__ =="__main__":

    #############
    # Rotazione: max 5 MB, tieni 5 backup
  
    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    #main()
    asyncio.run(main())

  