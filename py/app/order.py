from ib_insync import *
import asyncio
from datetime import datetime, timedelta
import logging
import json
import sqlite3
from config import DB_FILE,CONFIG_FILE
from utils import convert_json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

'''
util.startLoop()   # 🔑 IMPORTANTISSIMO

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
config = convert_json(config)


ib = IB()
ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)
'''

def onNewOrder(trade):
    print(f"NEW ORDER: {trade}")
    # Salva nel database
    cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (trade.order.permId, trade.contract.symbol, trade.order.action, trade.order.totalQuantity, 
                getattr(trade.order, 'lmtPrice', None), trade.orderStatus.status, 
                trade.orderStatus.filled, trade.orderStatus.remaining, 'newOrder'))

def onOrderModify(trade):
    print(f"ORDER MODIFY: {trade}")
    # Aggiorna nel database
    cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (trade.order.permId, trade.contract.symbol, trade.order.action, trade.order.totalQuantity, 
                getattr(trade.order, 'lmtPrice', None), trade.orderStatus.status, 
                trade.orderStatus.filled, trade.orderStatus.remaining, 'orderModify'))

def onCancelOrder(trade):
    print(f"ORDER CANCEL: {trade}")
    # Aggiorna status nel database
    cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (trade.order.permId, trade.contract.symbol, trade.order.action, trade.order.totalQuantity, 
                getattr(trade.order, 'lmtPrice', None), trade.orderStatus.status, 
                trade.orderStatus.filled, trade.orderStatus.remaining, 'cancelOrder'))

def onOpenOrder(trade):
    print(f"OPEN ORDER: {trade}")
    # Aggiorna nel database
    cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (trade.order.permId, trade.contract.symbol, trade.order.action, trade.order.totalQuantity, 
                getattr(trade.order, 'lmtPrice', None), trade.orderStatus.status, 
                trade.orderStatus.filled, trade.orderStatus.remaining, 'openOrder'))

def onOrderStatus(trade):
    print(f"ORDER STATUS: {trade}")
    # Aggiorna status, filled, remaining nel database
    cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
               (trade.order.permId, trade.contract.symbol, trade.order.action, trade.order.totalQuantity, 
                getattr(trade.order, 'lmtPrice', None), trade.orderStatus.status, 
                trade.orderStatus.filled, trade.orderStatus.remaining, 'orderStatus'))


class OrderManager:

    ib=None
    def __init__(self,ib):
        OrderManager.ib=ib
    # Assegna gli event handlers
    #ib.newOrderEvent += onNewOrder
    #ib.orderModifyEvent += onOrderModify
        OrderManager.ib.cancelOrderEvent += onCancelOrder
        OrderManager.ib.openOrderEvent += onOpenOrder
        OrderManager.ib.orderStatusEvent += onOrderStatus

##############



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

    def order_limit(symbol,totalQuantity,lmtPrice):
        '''
        '''

        logger.debug(f"LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        # 🔹 ORDINE PADRE (ENTRY)
        entry = LimitOrder(
            action='BUY',
            totalQuantity=totalQuantity,
            lmtPrice=lmtPrice,
            tif='GTC' ,
            outsideRth=True
        )
        #entry.orderId = ib.client.getReqId()
        #entry.transmit = True
        #entry.whatIf = True
        OrderManager.ib.placeOrder(contract, entry)

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

def onStatus(trade):
        print("STATUS",
            trade.orderStatus.status,
            trade.orderStatus.filled,
            trade.orderStatus.remaining
        )

def onFilled(trade, fill):
    print(
        f"FILL | {trade.contract.symbol} | "
        f"{fill.execution.price} x {fill.execution.shares}"
    )

def onNewTrade(trade):
    print(
        f"NEW TRADE | {trade.contract.symbol} | "
        f"{trade.order.action} {trade.order.totalQuantity}"
    )

    def onStatus(trade):
        s = trade.orderStatus
        print(
            f"{trade.contract.symbol} | "
            f"{s.status} | filled={s.filled} remaining={s.remaining}"
        )

    trade.statusEvent += onStatus
    trade.filledEvent += onFilled

#ib.tradesEvent += onNewTrade

    for trade in ib.trades():
        trade.statusEvent += onStatus
        trade.filledEvent += onFilled

# 🔴 Hook su nuovi trade (workaround)
async def checkNewTrades():


    order_limit("NVDA", 100,180)

    known = set()
    while True:
        # Filtra i trades per quelli di oggi
        today = datetime.now().date()
        todays_trades = [t for t in ib.trades() if t.log and t.log[0].time.date() == today]
        
        for t in todays_trades:
            
        
            if False and id(t) not in known:
                known.add(id(t))
                logger.info(f"TRADE {t}")

                #filledQuantity
                # Salva l'ordine nel database (inserisci se non esiste, aggiorna se esiste)
                cur.execute('''INSERT INTO ib_orders (trade_id, symbol, action, quantity, price, status, filled, remaining, event_action)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (t.order.permId, t.contract.symbol, t.order.action, t.order.totalQuantity, 
                            getattr(t.order, 'lmtPrice', None), t.orderStatus.status, 
                            t.orderStatus.filled, t.orderStatus.remaining, 'newTrade'))

                t.statusEvent += onStatus
                t.filledEvent += onFilled
        #ib.sleep(0.2)   # 🔑 NON blocca il loop
        await asyncio.sleep(0.2)

async def main():

    util.startLoop()   # 🔑 IMPORTANTISSIMO

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)


    ib = IB()
    ib.connect('127.0.0.1', config["database"]["live"]["ib_port"], clientId=1)

    OrderManager(ib)

    # 🔴 avvio task asincrona
    #task = asyncio.create_task(checkNewTrades())

    OrderManager.order_limit("AAPL", 10,180)

    ib.run()
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
    
    asyncio.run(main())