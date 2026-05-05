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
from order import OrderManager

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

logging.getLogger("ib_insync").setLevel(logging.WARNING)


'''
util.startLoop()   # 🔑 IMPORTANTISSIMO

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)


ib = IB()
ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)
'''

''' tif
    GTC (Swing,Take Profit / Stop Loss,  Bracket Order )
    resta attivo finché non lo cancelli
    sopravvive a fine giornata
    sopravvive a riavvii TWS / script

    IOC 
    prova a eseguire SUBITO (FAST)
    la parte non eseguita viene cancellata
    accetta fill parziali

    FOK — Fill Or Kill (Grandi) 
    deve essere eseguito TUTTO e SUBITO
    se anche 1 share non è disponibile, viene annullato
    NO fill parziali
'''


def trade_log_to_dict(log: TradeLogEntry) -> dict:
    return {
        "time": log.time.isoformat() if log.time else None,
        "status": log.status,
        "message": log.message,
        "errorCode": log.errorCode,
    }

def trade_to_dict(trade: Trade) -> dict:
        return {
            "trade_id": trade.order.permId,
            "orderId": trade.order.orderId,
            "symbol": trade.contract.symbol,
            "exchange": trade.contract.exchange,
            "action": trade.order.action,
            "orderType": trade.order.orderType,
            "totalQuantity": trade.order.totalQuantity,
            "lmtPrice": getattr(trade.order, "lmtPrice", None),
            "status": trade.orderStatus.status,
            "filled": trade.orderStatus.filled,
            "remaining": trade.orderStatus.remaining,
            "avgFillPrice": trade.orderStatus.avgFillPrice,
            "lastFillPrice": trade.orderStatus.lastFillPrice,
             "log": [trade_log_to_dict(l) for l in trade.log],
        }

def trade_to_json(trade: Trade) -> str:
    return json.dumps({
        "trade_id": trade.order.permId,
        "orderId": trade.order.orderId,
        "symbol": trade.contract.symbol,
        "exchange": trade.contract.exchange,
        "action": trade.order.action,
        "orderType": trade.order.orderType,
        "totalQuantity": trade.order.totalQuantity,
        "lmtPrice": getattr(trade.order, "lmtPrice", None),
        "status": trade.orderStatus.status,
        "filled": trade.orderStatus.filled,
        "remaining": trade.orderStatus.remaining,
        "avgFillPrice": trade.orderStatus.avgFillPrice,
        "lastFillPrice": trade.orderStatus.lastFillPrice,
        "log": [
            {
                "time": l.time.isoformat() if l.time else None,
                "status": l.status,
                "message": l.message,
                "errorCode": l.errorCode,
            }
            for l in trade.log
        ],
    })

    '''
PreSubmitted
Submitted
Filled
Cancelled
Inactive'''
def ib_get_trades(symbol = None,onlyActive = False):
      
        filtered_trades = []
       # logger.info(f"{self.ib.trades()}")
        for t in OrderManager.ib.trades():
            if symbol and t.contract.symbol != symbol:
                continue
            if onlyActive and not t.orderStatus.status in ("PreSubmitted", "Submitted"):
                continue
            
        return filtered_trades
    

###########################################

class IB_OrderManager(OrderManager):
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
        OrderManager.ib = ib
        self.ib=ib

        logger.info(f"ib {ib}")
    
        async def onError( reqId, errorCode, errorString, contract):
            logger.error(f"errorCode {errorCode} {errorString} {contract}")

            
            self.lastError = {"reqId" : reqId, "errorCode": errorCode, "errorString": errorString} 

            #if  self.client..ws:
           
                #data["type"] = "ORDER"
            #ser = json.dumps( self.lastError)

            if errorCode in [2104, 2105, 2106,2107,2108]:
                await self.client.send_message_event(self.lastError )
            else:
                await self.client.send_error_event(self.lastError )

            '''     
                await self.ws.broadcast(
                    {"type": "ERROR", "data":ser }
                )
                '''

            if errorCode == 110:
                pass
            if errorCode == 162:
                return  # ignorato
           
        if ib:
            self.ib.cancelOrderEvent += self.onCancelOrder
            self.ib.openOrderEvent += self.onOpenOrder
            self.ib.orderStatusEvent += self.onOrderStatus
            self.ib.newOrderEvent += self.onNewOrder
            self.ib.newOrderEvent += self.onNewOrder
            self.ib.errorEvent += onError
            #self.ib.execDetailsEvent  += self.onExec
            self.ib.commissionReportEvent += self.onCommission
        pass 

    #############
    
    async def addOrder(self,trade:Trade,type):
        logger.debug(f"ORDER: {type} {trade}")
        if trade.order.permId == 0:
            return
        data =  trade_to_dict(trade)
        self._addOrder(data,type)

    async def onNewOrder(self,trade:Trade):
       await self.addOrder(trade, "NEW")

    async def onOrderModify(self,trade:Trade):
      await self.addOrder(trade, "MODIFY")

    async def onCancelOrder(self,trade:Trade):
       await self.addOrder(trade, "CANCEL")

    async def onOpenOrder(self,trade:Trade):
       await self.addOrder(trade, "OPEN")

    async def onOrderStatus(self,trade:Trade):
       await self.addOrder(trade, "STATUS")


    #############

    '''
    def onExec(self,trade, fill):
        
        logger.info(f"onExec {trade} {fill}")
        self.exec_to_order[fill.execution.execId] = trade.order.orderId
    '''

    async def onCommission(self,trade:Trade,fill:Fill,commissionReport:CommissionReport):
        logger.info(f"onCommission {trade} \ncommissionReport:{commissionReport}")

        orderId = trade.order.orderId
        permId = trade.orderStatus.permId
        comm = commissionReport.commission
        pnl = commissionReport.realizedPNL

        logger.info(f"orderId {orderId} Commission:{comm} pnl:{pnl} permId:{permId}")

        df = self.client.get_df(f""" select * from ib_order_commissions  WHERE trade_id = '{permId}'  """)
        if len(df)>0:
            logger.info(f"UPDATE \n{df}")
            pnl = pnl + df.iloc[0]["pnl"]
            comm = comm + df.iloc[0]["commission"]
            cur.execute('''UPDATE ib_order_commissions set pnl= ? ,  commission = ?
                    WHERE trade_id = ? ''',
                (pnl,comm ,permId))
        else:
            cur.execute('''INSERT INTO ib_order_commissions (trade_id, symbol, pnl, commission)
                    VALUES (?, ?, ?, ?)''',
                (permId, trade.contract.symbol,pnl,comm ))
            
        if self.getLastTrade(trade.contract.symbol):
            msg = { "data" :self.getLastTrade(trade.contract.symbol).to_dict()}
            
            await self.client.send_trade_event("POSITION_TRADE",msg)
            await self.strategyManager.on_live_trade_event("POSITION_TRADE",self.getLastTrade(trade.contract.symbol))
     
    ###########

    def format_price(self,contract,price)-> float:
        def round_to_tick(price, tick):
            return round(round(price / tick) * tick, 10)

        def decimals_from_tick(tick):
            return max(0, -int(math.floor(math.log10(tick))))
        
        def format_price(price, min_tick):
            decimals = decimals_from_tick(min_tick)
            return f"{price:.{decimals}f}"

        #cd = self.ib.reqContractDetails(contract)[0]

        #if contract.symbol in self.tick_cache:
        tick = self.tick_cache[contract.symbol ]
       # else:
       #     tick =cd.minTick
        #    if not tick or tick <= 0:
        #        raise ValueError("minTick non valido")
        
        logger.info(f"format_price {price} {tick}")
        # arrotonda al tick
        price = round_to_tick(price, tick)
         # calcola decimali
        price_str = format_price(price, tick)

        return  float(price_str)

##############

   
    def buy_breakout_no_slippage(self, symbol, quantity, price):
        '''
        BUY a breakout SENZA accettare prezzi sopra
        - Trigger a 110
        - Compra solo a 110 o meno
        '''

        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        order = Order(
            action='BUY',
            orderType='STP LMT',
            totalQuantity=quantity,
            auxPrice=price,   # trigger
            lmtPrice=price    # NO prezzi sopra
        )

        self.ib.placeOrder(contract, order)
        
    def _order_limit(self,symbol,action,totalQuantity,lmtPrice)-> Trade:
        '''
        '''

        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        formatted_price = self.format_price(contract,lmtPrice)

        logger.info(f"LIMIT ORDER {symbol} {action} q:{totalQuantity} p:{lmtPrice}->{formatted_price}")

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action=action,
            totalQuantity=totalQuantity,
            lmtPrice=formatted_price,
            tif='DAY' ,
            #tif='FOK', #tutto o niente, + difficile
            outsideRth=True
        )
        #entry.orderId = ib.client.getReqId()
        #entry.transmit = True
        #entry.whatIf = True
        trade = self.ib.placeOrder(contract, entry)

        return trade



    def order_limit_stop(self,symbol,totalQuantity,lmtPrice,stopPrice):
        '''
        Stop attivo solo se entry viene eseguito
        Se entry non fill → stop non entra mai
        '''
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action='BUY',
            totalQuantity=totalQuantity,
            lmtPrice=lmtPrice
        )
        entry.orderId = self.ib.client.getReqId()
        entry.transmit = False

        # 🔹 STOP LOSS
        stop = StopOrder(
            action='SELL',
            totalQuantity=totalQuantity,
            stopPrice=stopPrice,
            parentId=entry.orderId
        )
        stop.transmit = True   # ultimo ordine = invio

        # 🔹 INVIO
        self.ib.placeOrder(contract, entry)
        self.ib.placeOrder(contract, stop)

    def order_bracket(self,symbol,quantity,limitPrice,takeProfitPrice,stopLossPrice):
        '''
    ENTRY + TAKE PROFIT + STOP LOSS)
        '''
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        bracket = self.ib.bracketOrder(
            action='BUY',
            quantity=quantity,
            limitPrice=limitPrice,     # ENTRY
            takeProfitPrice=takeProfitPrice,
            stopLossPrice=stopLossPrice
        )
        for o in bracket:
            self.ib.placeOrder(contract, o)
        '''
        # Attendi aggiornamenti
        ib.sleep(1)

        # Stato ordine
        print(trade.orderStatus.status)


        def onStatus(trade):
            print(
                trade.orderStatus.status,
                trade.orderStatus.filled,
                trade.orderStatus.remaining
            )

        trade.filledEvent += lambda t: print("FILLED")
        trade.statusEvent += onStatus
        '''

    async def send_order(self,symbol,order_handler,attempt):
        timeout = 2          # secondi
        interval = 0.1          # ciclo ogni secondo
        start_time = time.time()

        trade:Trade = order_handler(attempt)
        ### risolve i decimali 
        while time.time() - start_time < timeout:
            if trade.orderStatus.status =="PendingSubmit":
                if self.lastError!= None:
                        if self.lastError["errorCode"] == 110:
                            tick_size= self.tick_cache[symbol ] 
                            tick_size = min(0.1, tick_size *10)
                            self.tick_cache[symbol ] = tick_size
                            #logger.info(f"Redo  tick_size:{tick_size}")
                            trade:Trade = order_handler(attempt)
                await asyncio.sleep(interval)
            else:
                return trade
        return None

    def format_price(self,contract,price)-> float:
        def round_to_tick(price, tick):
            return round(round(price / tick) * tick, 10)

        def decimals_from_tick(tick):
            return max(0, -int(math.floor(math.log10(tick))))
        
        def format_price(price, min_tick):
            decimals = decimals_from_tick(min_tick)
            return f"{price:.{decimals}f}"

        #cd = self.ib.reqContractDetails(contract)[0]

        #if contract.symbol in self.tick_cache:
        tick = self.tick_cache[contract.symbol ]
       # else:
       #     tick =cd.minTick
        #    if not tick or tick <= 0:
        #        raise ValueError("minTick non valido")
        
        logger.info(f"format_price {price} {tick}")
        # arrotonda al tick
        price = round_to_tick(price, tick)
         # calcola decimali
        price_str = format_price(price, tick)

        return  float(price_str)

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

    async def abort_smart(self,symbol):
        if symbol in self.lastTradeMap:
            trade = self.lastTradeMap[symbol]
            del self.lastTradeMap[symbol]
            logger.info(f"abort_smart {symbol} { trade.symbol if trade else '..'}")
            self.doSmartAbort=True
            if trade :#and self.trade==symbol:
                logger.info("FORCE TRADE cancel")
                self.lastError = None
                self.ib.cancelOrder(trade.order)
                await asyncio.sleep(2)
                if self.lastError!= None:
                    if self.lastError["errorCode"] ==  10148:# Order FILLED 
                        logger.info("BUY DONE AFTER CANCEL")
               

    '''
    order_type = ["LIMIT","MARKET"]
    '''
    async def _smart_limit_real(self,symbol,op, totalQuantity,ticker,order_type):

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
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)  
        
        timeout = 120          # secondi
        interval = 4          # ciclo ogni secondo

        if op =="BUY":
            timeout = 30
            interval = 6

        start_time = time.time()
        
        trade=None
        submittedCount=0
        if contract.symbol in self.tick_cache:
            tick_size = self.tick_cache[contract.symbol ]
        else:
            cd = self.ib.reqContractDetails(contract)[0]
            tick_size =cd.minTick
            self.tick_cache[contract.symbol ] = tick_size
            if not tick_size or tick_size <= 0:
                raise ValueError("minTick non valido")
        attempt = 0      
        while time.time() - start_time < timeout and not self.doSmartAbort:
                        
            if trade:
                logger.info(f"Redo  status {symbol} {trade.orderStatus.status} ")

                if self.lastError!= None:
                    if self.lastError["errorCode"] ==  202:# Order Canceled 
                        pass
                    else:
                        logger.error(f"{self.lastError}")
                        return self.lastError

                if trade.orderStatus.status == "Cancelled":
                    logger.warning("Order Cancelled !!! ")
                    return None
                
                elif trade.orderStatus.status == "PendingSubmit":
                    if not self.wait_order(trade):
                        logger.warning("Order not added !!! ")
                elif trade.orderStatus.status == "PreSubmitted":
                    permId = trade.orderStatus.permId
                    logger.info(f"Force remove {permId}")
                    self.lastError = None
                    self.ib.cancelOrder(trade.order)
                        
                    trade=None
                elif trade.orderStatus.status == "Submitted":
                    #aspetto
                    submittedCount=submittedCount+1
                    if submittedCount == 3:
                        logger.info(f"filled {trade.orderStatus.filled}")
                        if trade.orderStatus.filled==0:
                            permId = trade.orderStatus.permId
                            logger.info(f"Force remove {permId}")
                            self.lastError = None
                            #self.cancel_order(permId)
                            self.ib.cancelOrder(trade.order)
                            trade=None

                if trade and trade.orderStatus.status == "Filled":
                    logger.info("BUY DONE")
                    return None

            if not trade:
                    
                    def do_order(attempt):
                        
                        tick_size = self.tick_cache[contract.symbol ] 

                        if (op =="BUY"):
                            price = ticker["last"]+ tick_size*attempt
                           
                            logger.info(f'Change price {ticker["last"]} s:{tick_size} ({attempt}) -> {price}')
                            formatted_price = self.format_price(contract,price)
                        else:
                            price = ticker["last"]- tick_size*attempt

                            formatted_price = self.format_price(contract,price)
                        #formatted_price = round(ticker["last"] / tick_size) * tick_size

                        logger.info(f">> {order_type} : {symbol} ({attempt}) {op} {totalQuantity} at {ticker['last']} -> {formatted_price} (tick_size:{tick_size}) ")

                        # 🔹 ORDINE
                        if order_type=="LIMIT":
                            # MARKET
                            entry = LimitOrder(
                                action=op,
                                totalQuantity=totalQuantity,
                                lmtPrice=formatted_price,
                                tif='DAY' ,
                                #tif='IOC' , #o tutto o niente
                                outsideRth=True
                            )
                        elif order_type=="MARKET":
                            entry = MarketOrder(
                            action=op,              # "BUY" o "SELL"
                                totalQuantity=totalQuantity,
                                tif='DAY',              # oppure 'IOC'
                                outsideRth=True
                            )
                    
                            
                        '''
                            # PRE / AFTER
                            entry = LimitOrder(
                                action=op,
                                totalQuantity=totalQuantity,
                                lmtPrice=formatted_price,
                                tif='DAY' ,
                                #tif='FOK' , #o tutto o niente
                                outsideRth=True
                            )
                        '''

                        ''' per vedere commissioni
                        order.whatIf = True

                        trade = ib.placeOrder(contract, order)
                        ib.sleep(1)

                        print("Commission:", trade.orderState.commission)
                        print("Min:", trade.orderState.minCommission)
                        print("Max:", trade.orderState.maxCommission)
                        print("Margin:", trade.orderState.initMarginChange)
                                                '''
                        self.lastError = None
                        return self.ib.placeOrder(contract, entry)

                    
                    trade:Trade = await self.send_order(contract.symbol,do_order,attempt)
                    if trade:
                        trade.symbol = contract.symbol
                        self.lastTradeMap[symbol]= trade
                    
                    attempt=attempt+1
                    
                    submittedCount=0

                    ###trade:Trade = 
                    #if not self.wait_order(trade):
                    #    logger.error("Order not added !!! ")

            self.ib.sleep(interval)

        if trade:
            logger.info("Final cancel")
            self.lastError = None
            self.ib.cancelOrder(trade.order)
            await asyncio.sleep(2)
            if self.lastError!= None:
                if self.lastError["errorCode"] ==  10148:# Order FILLED 
                    logger.info("BUY DONE AFTER CANCEL")
                    return None

        self.doSmartAbort=False
        self.lastTradeMap[symbol]= None
        return  {"reqId" : 0, "errorCode": -1, "errorString": "TIMEOUT"} 


    def sell(self,symbol,perc):
        '''
        Vende tutte le azioni possedute per il simbolo specificato.
        '''                                  
        logger.debug(f"SELL ALL {symbol}")
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        # Trova la posizione corrente
        positions = self.ib.positions()
        position_qty = 0
        for pos in positions:
            if pos.contract.symbol == symbol:
                position_qty = pos.position
                break

        if position_qty > 0:
            if perc<100:
                position_qty = position_qty * (float(perc)/100)
            # Vendi tutto a mercato
            entry = MarketOrder(
                action='SELL',
                totalQuantity=position_qty
            )
            self.ib.placeOrder(contract, entry)
            logger.info(f"Placed sell order for {position_qty} shares of {symbol}")
        else:
            logger.warning(f"No position found for {symbol} to sell")


    def buy_at_level(self,symbol, quantity, level_price):
        '''
        Compra quando il prezzo raggiunge il livello specificato (ordine stop).
        '''
        logger.debug(f"BUY AT LEVEL {symbol} q:{quantity} level:{level_price}")
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        # Ordine stop di acquisto al livello di prezzo
        entry = StopOrder(
            action='BUY',
            totalQuantity=quantity,
            stopPrice=level_price,
            tif='GTC',
            outsideRth=True
        )
        self.ib.placeOrder(contract, entry)
        logger.info(f"Placed stop buy order for {quantity} shares of {symbol} at {level_price}")

    async def cancel_order(self,permId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        logger.info(f"CANCEL ORDER permId: {permId} {ib_get_trades( )}")
        for trade in ib_get_trades( onlyActive=True):
            if trade.order.permId == permId:
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with permId {permId}")
                return True
            else:
                logger.warning(f"No order found with permId {permId}")
        return False
    
    
    async def cancel_orderBySymbol(self,symbol):
        '''
        Cancella un ordine pendente dato il suo symbol.
        '''
        logger.debug(f"CANCEL ORDER symbol: {symbol}")
        for trade in ib_get_trades(symbol =symbol, onlyActive=True ):
            if trade.contract.symbol == symbol:
                logger.info(f"trade {trade}")
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with symbol {symbol}")
              

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
        

    status_map = {
        "CANCELED" : "Cancelled",
        "NEW" : "Submitted",
        "FILLED" :"Filled",
        "PARTIALLY_FILLED" :"Partial Filled"
    }

    def compute_commissions_usdc(self,symbol, fee_asset, fee,price):
            base = symbol       # ZEN
            quote = symbol     # USDC
            if fee_asset == quote:
                    fee_usdt = fee
            elif fee_asset == base:
                fee_usdt = fee * price
            else:
                # es. BNB → serve prezzo live
                fee_usdt = 0#fee * prices.get(fee_asset + "USDT", 0)
            return fee_usdt

    async def create_order(self,symbol,side,type,quantity, price=0):
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
                if not symbol in self.coin_info:
                    self.coin_info[symbol] =  await self.binance_client.get_symbol_info(symbol)
                
                for f in self.coin_info[symbol]["filters"]:
                        #logger.info(f"{f}")

                        '''
                        if f["filterType"] == "PERCENT_PRICE_BY_SIDE":
                            logger.info(f"{f}")
                            bidMultiplierUp = float(f["bidMultiplierUp"])
                            bidMultiplierDown = float(f["bidMultiplierDown"])
                            askMultiplierUp = float(f["askMultiplierUp"])
                            askMultiplierDown = float(f["askMultiplierDown"])
                            avgPriceMins = float(f["avgPriceMins"])

                            ticker = await self.binance_client.get_symbol_ticker(symbol=symbol)
                            market_price = float(ticker["price"])

                            if side =="BUY":
                                min = market_price  * bidMultiplierDown
                                max = market_price  * bidMultiplierUp
                            else: 
                                min = market_price  * askMultiplierDown
                                max = market_price  * askMultiplierDown
                                
                            logger.info(f"min max :{min}-{max} ")

                            old = price
                            price = max(min(price, max), min)

                            logger.info(f"min max :{min}-{max} price {old} => {price}")
                        '''
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

            if type =="MARKET":
                fee_usdt=0
                lastFillPrice=0
                avgFillPrice=0
                if len(order["fills"])>0:
                    fill = order["fills"][0]
                    fee_usdt = self.compute_commissions_usdc(order["symbol"],fill["commissionAsset"],float(fill["commission"]),float(fill["price"]))

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
            return order["orderId"]
                    
        except BinanceAPIException as e:
            logger.error(e)

            await self.client.send_error_event(e.message )

    async def cancel_order(self,orderId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        ''''''
        logger.info(f"CANCEL ORDER permId: {orderId} ")

        orders = await self.binance_client.get_open_orders()

        for o in orders:
            if o["orderId"] == orderId:
                logger.info(o)
     
                order = await self.binance_client.cancel_order(
                    symbol=o["symbol"],
                    orderId=orderId) 
                
                logger.info(f"CANCEL ORDER : {order} ")

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
              

    async def user_stream_loop(self):
   
        while True:
            try:
                bsm = BinanceSocketManager(self.binance_client)
                socket = bsm.user_socket()

                async with socket as stream:
                    while True:
                        logger.info("WATCH")
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

                            log.append({'time': formatted, 'status' : state, 'message': '' ,'errorCode': 0 })

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

    logger.info(f"ZEN : {Balance.get_position('ZEN').position} USDC:{Balance.get_position('USDC').position}")

    orderId = await o.create_order("ZENUSDC","BUY","LIMIT", 1.5  ,7.1 ) #0.02774 

    #await o.create_order("ZENUSDC","BUY","MARKET", 1  )

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
        await o.cancel_order(orderId)
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

  