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
import pymysql
from order import *
from telegram import send_telegram_message

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


from aiohttp import ClientTimeout
from aiohttp.client_exceptions import (
    ClientConnectorDNSError,
    ClientConnectorError,
    ServerDisconnectedError
)


class BinanceClientManager:

    def __init__(self, api_key, api_secret, testnet=True):

        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        self.binance_client = None

        self.timeout = ClientTimeout(
            total=30,
            connect=10,
            sock_connect=10,
            sock_read=20
        )

        self.lock = asyncio.Lock()

    async def connect(self):

        async with self.lock:

            # evita doppia connessione
            if self.binance_client is not None:
                return

            logger.info("Connessione Binance...")

            self.binance_client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
                requests_params={
                    "timeout": self.timeout
                }
            )

            await self.binance_client.ping()

            logger.info("Binance connesso")

    async def reconnect(self):

        async with self.lock:

            logger.warning("Riconnessione Binance...")

            try:
                if self.binance_client:
                    await self.binance_client.close_connection()

            except Exception:
                logger.exception("Errore chiusura client")

            self.binance_client = None

            await asyncio.sleep(2)

            self.binance_client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
                requests_params={
                    "timeout": self.timeout
                }
            )

            await self.binance_client.ping()

            logger.info("Riconnessione completata")

    async def safe_request(self, method_name, **kwargs):

        max_retries = 3

        for attempt in range(max_retries):

            try:

                if self.binance_client is None:
                    await self.connect()

                method = getattr(self.binance_client, method_name)

                return await method(**kwargs)

            except (
                asyncio.TimeoutError,
                ClientConnectorDNSError,
                ClientConnectorError,
                ServerDisconnectedError
            ) as e:

                logger.warning(
                    f"Errore rete Binance [{method_name}] "
                    f"tentativo {attempt+1}: {e}"
                )

                await self.reconnect()

            except BinanceAPIException as e:

                logger.error(
                    f"Errore API Binance [{method_name}] "
                    f"{e.code} {e.message}"
                )

                raise

            except Exception:

                logger.exception(
                    f"Errore inatteso Binance [{method_name}]"
                )

                await self.reconnect()

        raise ConnectionError(
            f"Falliti tutti i retry Binance [{method_name}]"
        )

    async def close(self):

        if self.binance_client:

            try:
                await self.binance_client.close_connection()

            except Exception:
                logger.exception("Errore chiusura Binance")

###############################

class Binance_OrderManager(OrderManager):

    def __init__(self,config,client):
        super().__init__(config,client) 


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
        self.telegram_order_messages = client.config["general"]["telegram_order_messages"]
        
     
    async def bootstrap(self,ib):
        OrderManager.ib = ib     
        mode = self.config["markets"]["BINANCE"]["MODE"]
        logger.info(f"ORDER BOOT")
        API_KEY = self.config["markets"]["BINANCE"][mode]["API_KEY"]
        API_SECRET = self.config["markets"]["BINANCE"][mode]["API_SECRET"]

        self.order_table = self.config["markets"]["BINANCE"][mode]["order_table"]

        logger.info(f"ORDER TABLE {self.order_table}")  

        self.client.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.order_table} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                trade_id VARCHAR(255),
                symbol VARCHAR(64),
                side VARCHAR(32),
                status VARCHAR(64),
                event_type VARCHAR(64),
                data LONGTEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

            )
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
            """)


        self.client.execute(f"""
            CREATE INDEX IF NOT EXISTS  ib_{self.order_table}
            ON {self.order_table}(trade_id)
            """)
        
        self.client.execute(f"""
            CREATE INDEX IF NOT EXISTS  is_{self.order_table}
            ON {self.order_table}(symbol)
            """)

        self.manager=None
        try:
            #self.binance_client = await AsyncClient.create(API_KEY, API_SECRET,  testnet=mode=="PAPER")
            self.manager = BinanceClientManager(
                api_key=API_KEY,
                api_secret=API_SECRET,
                testnet=mode=="PAPER"
            )
        except:
            logger.error("",exc_info=True)
            exit(-1)

        asyncio.create_task(self.user_stream_loop())
        

    async def get_last_orders(self,symbol, limit):
        if not self.manager:
            return []
        
        orders = await self.manager.safe_request("get_all_orders", symbol=symbol, limit=limit)  
        '''
        orders = await self.binance_client.get_all_orders(
            symbol=symbol,
            limit=limit
        )
        '''
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
            #self.coin_info[symbol] =  await self.binance_client.get_symbol_info(symbol)
            self.coin_info[symbol] = await self.manager.safe_request("get_symbol_info", symbol=symbol)  
                
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

                trade = await self.manager.safe_request("get_order",  
                    symbol=trade["symbol"],
                    orderId=trade["orderId"])  
                '''
                trade = await self.binance_client.get_order(
                    symbol=trade["symbol"],
                    orderId=trade["orderId"]
                )
                '''

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
                        #_ticker = await self.binance_client.get_symbol_ticker(symbol=symbol)
                        _ticker = await self.manager.safe_request("get_symbol_ticker",  symbol=symbol)
                            
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
                         #logger.info("Error Exit")
                         return  {"reqId" : 0, "errorCode": -1, "errorString": "ERROR"} 
                    
                         # return
                    
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
                '''
                order = await self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity
                )
                '''
                order = await self.manager.safe_request("create_order",
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity
                )

            else:
                if adjustPrice:
                    if not symbol in self.coin_info:
                        self.coin_info[symbol] =  await self.manager.safe_request("get_symbol_info", symbol=symbol) 
                        #self.coin_info[symbol] =  await self.binance_client.get_symbol_info(symbol)
                    
                    for f in self.coin_info[symbol]["filters"]:
                            #logger.info(f"{f}")

                            if f["filterType"] == "PRICE_FILTER":
                                tick_size = float(f["tickSize"])
                                old = price
                                price =  math.floor(price / tick_size) * tick_size     
                                logger.info(f"tickSize:{tick_size} price {old} => {price}")        

                order = await self.manager.safe_request("create_order",
                    symbol=symbol,
                    side=side,
                    type="LIMIT",
                    quantity=quantity,
                    price = price,
                    timeInForce="GTC")
                '''
                order = await self.binance_client.create_order(
                    symbol=symbol,
                    side=side,
                    type="LIMIT",
                    quantity=quantity,
                    price = price,
                    timeInForce="GTC"
                )
                '''

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

            if self.telegram_order_messages:
                send_telegram_message(self.lastError)

            return None

    async def cancel_order(self,orderId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        ''''''
       
        ##orders = await self.binance_client.get_open_orders()
        orders = await self.manager.safe_request("get_open_orders")

        for o in orders:
            if o["orderId"] == orderId:
                #logger.info(o)
                logger.info(f"CANCEL ORDER permId: {orderId} ")

                order = await self.manager.safe_request("cancel_order",
                    symbol=o["symbol"],
                    orderId=orderId) 
                
                '''
                order = await self.binance_client.cancel_order(
                    symbol=o["symbol"],
                    orderId=orderId) 
                '''
                
                #logger.info(f"CANCEL ORDER : {order} ")

        return False
    
    
    async def cancel_orderBySymbol(self,symbol):
        '''
        Cancella un ordine pendente dato il suo symbol.
        '''
        logger.info(f"CANCEL ORDER symbol: {symbol} ")

        #orders = await self.binance_client.get_open_orders()
        orders = await self.manager.safe_request("get_open_orders")

        for o in orders:
            if o["symbol"] == symbol:
                logger.info(o)
     
                order = await self.manager.safe_request("cancel_order",
                    symbol=o["symbol"],
                    orderId=o["orderId"]) 
                '''
                order = await self.binance_client.cancel_order(
                    symbol=o["symbol"],
                    orderId=o["orderId"]) 
                '''
        return False
              
    async def abort_smart(self,symbol):
        await self.cancel_orderBySymbol(symbol)

        if symbol in self.lastTradeMap:
            trade = self.lastTradeMap[symbol]
            del self.lastTradeMap[symbol]
            logger.info(f"abort_smart {symbol} { trade.symbol if trade else '..'}")
            self.doSmartAbort=True
           

    async def user_stream_loop(self):
   
        binance_client=None
        while True:
            try:
                binance_client = await AsyncClient.create(
                    api_key=self.manager.api_key,
                    api_secret=self.manager.api_secret,
                    testnet=self.manager.testnet,
                    requests_params={
                        "timeout": self.manager.timeout
                    }
                 )

            #await self.binance_client.ping()

                #if not binance_client:
                #    await asyncio.sleep(1)
                #    continue
                bsm = BinanceSocketManager(binance_client)
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

                            exists = self.client.get_df(f'''SELECT data FROM {self.order_table} 
                                    WHERE trade_id=%s AND symbol=%s AND side=%s
                                    LIMIT 1''',
                                    (trade_id,
                                    symbol,
                                    side        ))

                            log=[]
                            if len(exists)>0:
                                 log = json.loads(exists.iloc[0]["data"])["log"]  # 👈 parse JSON → dict
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

                                position = free+locked

                                # stato precedente
                                #prev = balances_state.get(asset, {"free": 0, "locked": 0})
                            

                                msg = {"type": "UPDATE_PORTFOLIO", "symbol" :asset , "position" : position, "marketPrice": 0, "marketValue" : 0}
                                await Balance.update(asset,msg)

                                logger.info(f"Balance update {asset} free:{free} locked:{locked} total:{position}") 
                                if Balance.ws:
                                    await Balance.ws.broadcast(msg)

                                    if asset =="USDC":  
                                        Balance.cash_usd = position
                                        await Balance.onUSDChanged()
                                        #await Balance.ws.broadcast({"type":"props", "path": "account.cash_usd", "value":Balance.cash_usd } )

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
                logger.error(f"Order WS error: {e}",exc_info=True)
                await asyncio.sleep(1)
                try:
                    binance_client.close_connection()
                    binance_client=None
                except:
                    logger.error(f"Order WS error 2: {e}",exc_info=True)


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

  