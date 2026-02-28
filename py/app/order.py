from typing import List
from fastapi import HTTPException
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
from balance import Balance, PositionTrade
import traceback
from decimal import Decimal, ROUND_DOWN

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
def get_trades(symbol = None,onlyActive = False):
      
        filtered_trades = []
       # logger.info(f"{self.ib.trades()}")
        for t in OrderManager.ib.trades():
            if symbol and t.contract.symbol != symbol:
                continue
            if onlyActive and not t.orderStatus.status in ("PreSubmitted", "Submitted"):
                continue
            
        return filtered_trades
    
##########################

class OrderManager:

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

        # Assegna gli event handlers

    async def bootstrap(self,ib):
        OrderManager.ib = ib
    
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

    def rebuild_trades(self, df) -> List[PositionTrade]:
        trades = []

        # group per symbol
        for symbol, g in df.groupby("symbol"):
            current = None

            # scorri dall'ultima riga alla prima
            for row in g.iloc[::-1].itertuples(index=False):
                side = row.side
                data = json.loads(row.data)

                logger.info(f"rebuild_trades row {data}")

                price = data["avgFillPrice"]
                size = data["totalQuantity"]
                trade_id = data["trade_id"]

                time = data["log"][-1]["time"]
                dt = datetime.fromisoformat(time)
                unix_time = dt.timestamp()

                pnl=0
                comm=0
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
        
    #####################


    async def addOrder(self,trade:Trade,type):
        logger.debug(f"ORDER: {type} {trade}")
        if trade.order.permId == 0:
            return
        
        data =  trade_to_dict(trade)
        action = data["action"]
        ser = json.dumps(data)
        cur.execute('''INSERT INTO ib_orders (trade_id, symbol, side,status, event_type, data)
                    VALUES (?, ?, ?, ?, ?,?)''',
                (trade.order.permId, trade.contract.symbol,action, trade.orderStatus.status,type,ser))
        
        #if self.ws:
            #data["type"] = "ORDER"
        ser = json.dumps(data)
        await self.client.send_order_event("ORDER",
                 { "trade_id": trade.order.permId, 
                    "symbol":trade.contract.symbol,
                    "status" :trade.orderStatus.status,
                    "event_type":type,  
                    "timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") ,
                    "data" : data 
                   }
                 )
        '''
            await self.ws.broadcast(
                {"type": "ORDER", "trade_id": trade.order.permId, "symbol":trade.contract.symbol,
                 "status" :trade.orderStatus.status,"event_type":type,   "data" : data ,"timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") }
            )
            '''

            #if action =="BUY":
            #    msg = {"type": "<", "data" : {} }
            #    await self.ws.broadcast(msg)

        if action =="BUY" and trade.orderStatus.status =="Filled" and type=="STATUS":
                msg = { "data" :self.getLastTrade(trade.contract.symbol).to_dict()}
                #await self.ws.broadcast(msg)

                await self.client.send_trade_event("POSITION_TRADE",msg)
            
        if action =="SELL" and trade.orderStatus.status =="Filled" and type=="STATUS":
                msg = { "data" :self.getLastTrade(trade.contract.symbol).to_dict()}
                #await self.ws.broadcast(msg)

                await self.client.send_trade_event("POSITION_TRADE",msg)

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

    def order_limit(self,symbol,totalQuantity,lmtPrice)-> Trade:
        '''
        '''

        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        formatted_price = self.format_price(contract,lmtPrice)

        logger.info(f"LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}->{formatted_price}")

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action='BUY',
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

    async def smart_buy_limit(self,symbol,totalQuantity,ticker):
        return await self._smart_limit(symbol, "BUY",totalQuantity, ticker)
       
    async def smart_sell_limit(self,symbol,totalQuantity,ticker):
        return  await self._smart_limit(symbol, "SELL",totalQuantity, ticker)
     

    async def _smart_limit(self,symbol,op, totalQuantity,ticker):
        if self.sym_mode:
            await self._smart_limit_sym(symbol,op,totalQuantity,ticker)
        else:
            await self._smart_limit_real(symbol,op,totalQuantity,ticker)

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

    async def _smart_limit_real(self,symbol,op, totalQuantity,ticker):
        '''
        return error if != None
        '''
        logger.info(f"SMART {op} LIMIT ORDER {symbol} q:{totalQuantity}")
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)  
        
        timeout = 120          # secondi
        if op =="BUY":
            timeout = 20 

        interval = 2          # ciclo ogni secondo
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
        while time.time() - start_time < timeout:
                        
            if trade:
                logger.info(f"Redo  status {trade.orderStatus.status} ")

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

                        logger.info(f">> LimitOrder : {symbol} ({attempt}) {op} {totalQuantity} at {ticker['last']} -> {formatted_price} (tick_size:{tick_size}) ")

                        # 🔹 ORDINE
                        if True:
                            # MARKET
                            entry = LimitOrder(
                                action=op,
                                totalQuantity=totalQuantity,
                                lmtPrice=formatted_price,
                                tif='DAY' ,
                                #tif='IOC' , #o tutto o niente
                                outsideRth=True
                            )
                        else:
                            # PRE / AFTER
                            entry = LimitOrder(
                                action=op,
                                totalQuantity=totalQuantity,
                                lmtPrice=formatted_price,
                                tif='DAY' ,
                                #tif='FOK' , #o tutto o niente
                                outsideRth=True
                            )


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

        return  {"reqId" : 0, "errorCode": -1, "errorString": "TIMEOUT"} 


    def sell_limit(self,symbol,totalQuantity,lmtPrice):
        '''
        '''

        logger.debug(f"SELL LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}")
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        formatted_price = self.format_price(contract,lmtPrice)

        # 🔹 ORDINE DI VENDITA
        entry = LimitOrder(
            action='SELL',
            totalQuantity=totalQuantity,
            lmtPrice=formatted_price,
            tif='GTC' ,
            outsideRth=True
        )
        self.ib.placeOrder(contract, entry)

    def sell_all(self,symbol):
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

    def cancel_order(self,permId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        logger.info(f"CANCEL ORDER permId: {permId} {get_trades( )}")
        for trade in get_trades( onlyActive=True):
            if trade.order.permId == permId:
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with permId {permId}")
                return True
        logger.warning(f"No order found with permId {permId}")
        return False
    
    
    def cancel_orderBySymbol(self,symbol):
        '''
        Cancella un ordine pendente dato il suo symbol.
        '''
        logger.debug(f"CANCEL ORDER symbol: {symbol}")
        for trade in get_trades(symbol =symbol, onlyActive=True ):
            if trade.contract.symbol == symbol:
                logger.info(f"trade {trade}")
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with symbol {symbol}")
              
     
    #####

    async def onTicker(self,symbol,lastPrice):
        pass

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


async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)


    ib = IB()
    ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)
    
    o = OrderManager(config,ib)

    balance = Balance(config,ib)
    await Balance.bootstrap()

    # 🔴 avvio task asincrona
    #task = asyncio.create_task(checkNewTrades())
    ticker = Ticker
    ticker["last"] = 2.802334
    
    #et = self.smart_buy_limit("IVF",100,ticker)

    ret = o.smart_sell_limit("IVF",100,ticker)
    if ret:
        logger.error(f">> {ret}")
    #self.smart_sell_limit()
    #self.order_limit("AAPL", 10,180)
    #logger.info("1")

    #ib.run()
    await ib.sleep(float("inf"))

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

  