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
from balance import Balance
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
       # logger.info(f"{OrderManager.ib.trades()}")
        for t in OrderManager.ib.trades():
            if symbol and t.contract.symbol != symbol:
                continue
            if onlyActive and not t.orderStatus.status in ("PreSubmitted", "Submitted"):
                continue
            
        return filtered_trades
    
class OrderManager:

    ib=None
    ws :WSManager = None
    task_orders = []

    tick_cache = {}
    

    def __init__(self,config,ib):
        OrderManager.ib=ib
        OrderManager.lastError=""    
        # Assegna gli event handlers

        def onError( reqId, errorCode, errorString, contract):
            logger.error(f"errorCode {errorCode} {errorString} {contract}")

            OrderManager.lastError = {"reqId" : reqId, "errorCode": errorCode, "errorString": errorString} 
            if errorCode == 110:
                pass
            if errorCode == 162:
                return  # ignorato
           

        if ib:
            OrderManager.ib.cancelOrderEvent += OrderManager.onCancelOrder
            OrderManager.ib.openOrderEvent += OrderManager.onOpenOrder
            OrderManager.ib.orderStatusEvent += OrderManager.onOrderStatus
            OrderManager.ib.newOrderEvent += OrderManager.onNewOrder
            OrderManager.ib.newOrderEvent += OrderManager.onNewOrder
            OrderManager.ib.errorEvent += onError

    async def bootstrap():
        pass 

    #####################


    async def addOrder(trade:Trade,type):
        logger.debug(f"ORDER: {type} {trade}")
        if trade.order.permId == 0:
            return
        
        data =  trade_to_dict(trade)

        ser = json.dumps(data)
        cur.execute('''INSERT INTO ib_orders (trade_id, symbol, status, event_type, data)
                    VALUES (?, ?, ?, ?, ?)''',
                (trade.order.permId, trade.contract.symbol, trade.orderStatus.status,type,ser))
        
        if OrderManager.ws:
            #data["type"] = "ORDER"
            ser = json.dumps(data)
            await OrderManager.ws.broadcast(
                {"type": "ORDER", "trade_id": trade.order.permId, "symbol":trade.contract.symbol,
                 "status" :trade.orderStatus.status,"event_type":type,   "data" : data ,"timestamp" :datetime.now().strftime("%Y-%m-%d %H:%M:%S") }
            )

    async def onNewOrder(trade:Trade):
       await OrderManager.addOrder(trade, "NEW")

    async def onOrderModify(trade:Trade):
      await OrderManager.addOrder(trade, "MODIFY")

    async def onCancelOrder(trade:Trade):
       await OrderManager.addOrder(trade, "CANCEL")

    async def onOpenOrder(trade:Trade):
       await OrderManager.addOrder(trade, "OPEN")

    async def onOrderStatus(trade:Trade):
       await OrderManager.addOrder(trade, "STATUS")

    ###########

    def format_price(contract,price)-> float:
        def round_to_tick(price, tick):
            return round(round(price / tick) * tick, 10)

        def decimals_from_tick(tick):
            return max(0, -int(math.floor(math.log10(tick))))
        
        def format_price(price, min_tick):
            decimals = decimals_from_tick(min_tick)
            return f"{price:.{decimals}f}"

        #cd = OrderManager.ib.reqContractDetails(contract)[0]

        #if contract.symbol in OrderManager.tick_cache:
        tick = OrderManager.tick_cache[contract.symbol ]
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

    def order_limit(symbol,totalQuantity,lmtPrice)-> Trade:
        '''
        '''

        
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        formatted_price = OrderManager.format_price(contract,lmtPrice)

        logger.info(f"LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}->{formatted_price}")

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action='BUY',
            totalQuantity=totalQuantity,
            lmtPrice=formatted_price,
            tif='DAY' ,
            outsideRth=True
        )
        #entry.orderId = ib.client.getReqId()
        #entry.transmit = True
        #entry.whatIf = True
        trade = OrderManager.ib.placeOrder(contract, entry)

        return trade

    def order_limit_stop(symbol,totalQuantity,lmtPrice,stopPrice):
        '''
        Stop attivo solo se entry viene eseguito
        Se entry non fill → stop non entra mai
        '''
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action='BUY',
            totalQuantity=totalQuantity,
            lmtPrice=lmtPrice
        )
        entry.orderId = OrderManager.ib.client.getReqId()
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
        OrderManager.ib.placeOrder(contract, entry)
        OrderManager.ib.placeOrder(contract, stop)

    def order_bracket(symbol,quantity,limitPrice,takeProfitPrice,stopLossPrice):
        '''
    ENTRY + TAKE PROFIT + STOP LOSS)
        '''
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        bracket = OrderManager.ib.bracketOrder(
            action='BUY',
            quantity=quantity,
            limitPrice=limitPrice,     # ENTRY
            takeProfitPrice=takeProfitPrice,
            stopLossPrice=stopLossPrice
        )
        for o in bracket:
            OrderManager.ib.placeOrder(contract, o)
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

    def send_order(symbol,order_handler):
        timeout = 2          # secondi
        interval = 0.1          # ciclo ogni secondo
        start_time = time.time()

        trade:Trade = order_handler()
        ### risolve i decimali 
        while time.time() - start_time < timeout:
            if trade.orderStatus.status =="PendingSubmit":
                if OrderManager.lastError!= None:
                        if OrderManager.lastError["errorCode"] == 110:
                            tick_size= OrderManager.tick_cache[symbol ] 
                            tick_size = min(0.1, tick_size *10)
                            OrderManager.tick_cache[symbol ] = tick_size
                            #logger.info(f"Redo  tick_size:{tick_size}")
                            trade:Trade = order_handler()
                OrderManager.ib.sleep(interval)
            else:
                return trade
        return None

    def smart_buy_limit(symbol,totalQuantity,ticker:Ticker):
        return OrderManager._smart_limit(symbol, "BUY",totalQuantity, ticker)
       
    def smart_sell_limit(symbol,totalQuantity,ticker:Ticker):
        return  OrderManager._smart_limit(symbol, "SELL",totalQuantity, ticker)
     

    def _smart_limit(symbol,op, totalQuantity,ticker:Ticker):
        '''
        return error if != None
        '''
        logger.debug(f"SMART {op} LIMIT ORDER {symbol} q:{totalQuantity}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)  
        
        timeout = 10          # secondi
        interval = 2          # ciclo ogni secondo
        start_time = time.time()
        
        trade=None
        submittedCount=0
        if contract.symbol in OrderManager.tick_cache:
            tick_size = OrderManager.tick_cache[contract.symbol ]
        else:
            cd = OrderManager.ib.reqContractDetails(contract)[0]
            tick_size =cd.minTick
            OrderManager.tick_cache[contract.symbol ] = tick_size
            if not tick_size or tick_size <= 0:
                raise ValueError("minTick non valido")
            
        while time.time() - start_time < timeout:
                        
            if trade:
                logger.info(f"Redo  status {trade.orderStatus.status} ")

                if OrderManager.lastError!= None:
                    if OrderManager.lastError["errorCode"] ==  202:# Order Canceled 
                        pass
                    else:
                        logger.error(f"{OrderManager.lastError}")
                        return OrderManager.lastError

                if trade.orderStatus.status == "PendingSubmit":
                    if not OrderManager.wait_order(trade):
                        logger.warning("Order not added !!! ")
                elif trade.orderStatus.status == "PreSubmitted":
                    permId = trade.orderStatus.permId
                    logger.info(f"Force remove {permId}")
                    OrderManager.lastError = None
                    OrderManager.ib.cancelOrder(trade.order)
                        
                    trade=None
                elif trade.orderStatus.status == "Submitted":
                    #aspetto
                    submittedCount=submittedCount+1
                    if submittedCount == 3:
                        permId = trade.orderStatus.permId
                        logger.info(f"Force remove {permId}")
                        OrderManager.lastError = None
                        #OrderManager.cancel_order(permId)
                        OrderManager.ib.cancelOrder(trade.order)
                        trade=None

                if trade and trade.orderStatus.status == "Filled":
                    logger.info("BUY DONE")
                    return None

            if not trade:
                    
                    def do_order():
                        tick_size = OrderManager.tick_cache[contract.symbol ] 

                        if (op =="BUY"):
                            formatted_price = OrderManager.format_price(contract,ticker.last+ tick_size)
                        else:
                            formatted_price = OrderManager.format_price(contract,ticker.last-tick_size)
                        #formatted_price = round(ticker.last / tick_size) * tick_size

                        logger.info(f">> LimitOrder : {symbol} {op} {totalQuantity} at {ticker.last} -> {formatted_price} (tick_size:{tick_size}) ")

                        # 🔹 ORDINE
                        entry = LimitOrder(
                            action=op,
                            totalQuantity=totalQuantity,
                            lmtPrice=formatted_price,
                            tif='DAY' ,
                            outsideRth=True
                        )
                        OrderManager.lastError = None
                        return OrderManager.ib.placeOrder(contract, entry)

                    trade:Trade = OrderManager.send_order(contract.symbol,do_order)
                    submittedCount=0

                    ###trade:Trade = 
                    #if not OrderManager.wait_order(trade):
                    #    logger.error("Order not added !!! ")

            OrderManager.ib.sleep(interval)

        if trade:
            logger.info("Final cancel")
            OrderManager.ib.cancelOrder(trade.order)

        return  {"reqId" : 0, "errorCode": -1, "errorString": "TIMEOUT"} 


    def sell_limit(symbol,totalQuantity,lmtPrice):
        '''
        '''

        logger.debug(f"SELL LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        formatted_price = OrderManager.format_price(contract,lmtPrice)

        # 🔹 ORDINE DI VENDITA
        entry = LimitOrder(
            action='SELL',
            totalQuantity=totalQuantity,
            lmtPrice=formatted_price,
            tif='GTC' ,
            outsideRth=True
        )
        OrderManager.ib.placeOrder(contract, entry)

    def sell_all(symbol):
        '''
        Vende tutte le azioni possedute per il simbolo specificato.
        '''                                  
        logger.debug(f"SELL ALL {symbol}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        # Trova la posizione corrente
        positions = OrderManager.ib.positions()
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
            OrderManager.ib.placeOrder(contract, entry)
            logger.info(f"Placed sell order for {position_qty} shares of {symbol}")
        else:
            logger.warning(f"No position found for {symbol} to sell")

    def buy_at_level(symbol, quantity, level_price):
        '''
        Compra quando il prezzo raggiunge il livello specificato (ordine stop).
        '''
        logger.debug(f"BUY AT LEVEL {symbol} q:{quantity} level:{level_price}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        # Ordine stop di acquisto al livello di prezzo
        entry = StopOrder(
            action='BUY',
            totalQuantity=quantity,
            stopPrice=level_price,
            tif='GTC',
            outsideRth=True
        )
        OrderManager.ib.placeOrder(contract, entry)
        logger.info(f"Placed stop buy order for {quantity} shares of {symbol} at {level_price}")

    def cancel_order(permId):
        '''
        Cancella un ordine pendente dato il suo permId.
        '''
        logger.info(f"CANCEL ORDER permId: {permId} {get_trades( )}")
        for trade in get_trades( onlyActive=True):
            if trade.order.permId == permId:
                OrderManager.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with permId {permId}")
                return True
        logger.warning(f"No order found with permId {permId}")
        return False
    
    
    def cancel_orderBySymbol(symbol):
        '''
        Cancella un ordine pendente dato il suo symbol.
        '''
        logger.debug(f"CANCEL ORDER symbol: {symbol}")
        for trade in get_trades(symbol =symbol, onlyActive=True ):
            if trade.contract.symbol == symbol:
                logger.info(f"trade {trade}")
                OrderManager.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with symbol {symbol}")
              
     
    #####

    async def onTicker(symbol,lastPrice):
        pass

    #########

    async def batch():
        while True:
            await asyncio.sleep(1)

#####################################


async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)


    ib = IB()
    ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)
    
    OrderManager(config,ib)

    balance = Balance(config,ib)
    await Balance.bootstrap()

    # 🔴 avvio task asincrona
    #task = asyncio.create_task(checkNewTrades())
    ticker = Ticker
    ticker.last = 2.802334
    
    #et = OrderManager.smart_buy_limit("IVF",100,ticker)

    ret = OrderManager.smart_sell_limit("IVF",100,ticker)
    if ret:
        logger.error(f">> {ret}")
    #OrderManager.smart_sell_limit()
    #OrderManager.order_limit("AAPL", 10,180)
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

  