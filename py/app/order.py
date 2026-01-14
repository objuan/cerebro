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


class OrderManager:

    ib=None
    ws :WSManager = None
    task_orders = []

    def __init__(self,config,ib):
        OrderManager.ib=ib
        # Assegna gli event handlers

        if ib:
            OrderManager.ib.cancelOrderEvent += OrderManager.onCancelOrder
            OrderManager.ib.openOrderEvent += OrderManager.onOpenOrder
            OrderManager.ib.orderStatusEvent += OrderManager.onOrderStatus
            OrderManager.ib.newOrderEvent += OrderManager.onNewOrder

            OrderManager.ib.updatePortfolioEvent  += OrderManager.onUpdatePortfolio
            OrderManager.ib.positionEvent   += OrderManager.onPositionEvent 
            #OrderManager.ib.accountValueEvent    += OrderManager.onAccountValueEvent  
            OrderManager.ib.accountSummaryEvent     += OrderManager.onAccountSummaryEvent   


    async def bootstrap():
        logger.info("ORDER BOOT")

        cur.execute("""UPDATE task_orders set status='CANC' 
WHERE id IN (
    SELECT MAX(o.id)
    FROM task_orders o
    GROUP BY task_id
)
AND status =='READY' """)

        df = pd.read_sql_query("""SELECT *
FROM task_orders
WHERE id IN (
    SELECT MAX(id)
    FROM task_orders
    GROUP BY task_id
)
AND status =='READY' 
""", conn)
        OrderManager.task_orders=[]
        for row in df.to_dict("records"):
            data = OrderManager.get_task_order(row)
            logger.info(f"ORDER ADD {data}")

            OrderManager.task_orders.append(data)

        logger.info(f"ORDER BOOT DONE {OrderManager.task_orders}")   

    async def onUpdatePortfolio(portfoglio : PortfolioItem):
        #logger.info(f"onUpdatePortfolio: {portfoglio}")

        msg = {"type": "UPDATE_PORTFOLIO", "symbol" : portfoglio.contract.symbol , "position" : portfoglio.position, "marketPrice": portfoglio.marketPrice, "marketValue" : portfoglio.marketValue}
        if OrderManager.ws:
            ser = json.dumps(msg)
            await OrderManager.ws.broadcast(msg)

    async def onPositionEvent(position : Position):
        #logger.info(f"onPositionEvent: {position}")

        msg = {"type": "POSITION", "symbol" : position.contract.symbol , "position" : position.position, "avgCost": position.avgCost}
        if OrderManager.ws:
            ser = json.dumps(msg)
            await OrderManager.ws.broadcast(msg)


    async def onAccountValueEvent(value : AccountValue):
        logger.info(f"onAccountValueEvent: {value}")

    async def onAccountSummaryEvent(value : AccountValue):
        logger.info(f"onAccountSummaryEvent: {value}")

    #####################


    async def addOrder(trade:Trade,type):
        logger.info(f"ORDER: {type} {trade}")
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

        cd = OrderManager.ib.reqContractDetails(contract)[0]
        tick = cd.minTick
        if not tick or tick <= 0:
            raise ValueError("minTick non valido")
        # arrotonda al tick
        price = round_to_tick(price, tick)
         # calcola decimali
        price_str = format_price(price, tick)

        return  float(price_str)
    
    ##############
    # TASK
    ##############

    def on_task_order_trigger(order,lastPrice):
        try:
            logger.info(f'TRIGGER {order["symbol"]},{lastPrice}>{order["data"]["lmtPrice"]}')

            real_price = lastPrice+ + lastPrice* 0.001
 
            trade = OrderManager.order_limit(order["symbol"], order["data"]["totalQuantity"],real_price)
            OrderManager.ib.sleep(0.5)

            order["trade"] = trade
            order["data"]["trigger_price"] = lastPrice

            cur.execute('''INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                        VALUES (?,?, ?, ?, ?, ?)''',
                    (order["task_id"],order["symbol"],"DONE", json.dumps(order["data"]),time.time(),trade.orderStatus.permId))
            
            conn.commit()
            logger.info(f'TRIGGER CLOSED {order}')
            
        except Exception:
            logger.error("ERROR",exc_info=True)
            err = traceback.format_exc()
            order["data"]["error"] = err
            cur.execute('''INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                        VALUES (?,?, ?, ?, ?, ?)''',
                    ( order["task_id"],order["symbol"],"ERROR", json.dumps(order["data"]),time.time(),-1))
            
            conn.commit()

        OrderManager.task_orders.remove(order)

    def get_task_order(row):
            data = {
                "id": row["id"],
                "task_id": row["task_id"],
                "trade_id": row["trade_id"],
                "status": row["status"],
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "data": json.loads(row["data"])
            }
            return data
    
    def task_buy_at_level(symbol,totalQuantity,lmtPrice):

        unix_time = time.time()
        data={
            "type": "buy_at_level",
            "totalQuantity": totalQuantity,
            "lmtPrice" : lmtPrice
        }
        task_id =1
        df = pd.read_sql_query("SELECT MAX(task_id) as task_id FROM task_orders", conn)
        if not pd.isna( df["task_id"].max()):
            task_id = int(df.iloc[0][0])+1

        cur.execute('''INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                    VALUES (?,?, ?, ?, ?, ?)''',
                (task_id,symbol,"READY", json.dumps(data),unix_time,-1))
        
        conn.commit()

        df = pd.read_sql_query("SELECT * FROM task_orders WHERE id = "+str(cur.lastrowid), conn)
        order=None
        for row in df.to_dict("records"):
            order = OrderManager.get_task_order(row)

        OrderManager.task_orders.append(order)
        logger.info(f"TASK << {data}")
        return data
    
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

    def sell(symbol,totalQuantity,lmtPrice):
        '''
        '''

        logger.debug(f"SELL LIMIT ORDER {symbol} q:{totalQuantity} p:{lmtPrice}")
        contract = Stock(symbol, 'SMART', 'USD')
        OrderManager.ib.qualifyContracts(contract)

        # 🔹 ORDINE DI VENDITA
        entry = LimitOrder(
            action='SELL',
            totalQuantity=totalQuantity,
            lmtPrice=lmtPrice,
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
        logger.debug(f"CANCEL ORDER permId: {permId}")
        for trade in OrderManager.ib.trades():
            if trade.order.permId == permId:
                OrderManager.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order with permId {permId}")
                return True
        logger.warning(f"No order found with permId {permId}")
        return False
    
    #####

    def onTicker(symbol,lastPrice):
        try:
            #logger.info(f"onTicker {symbol},{lastPrice}")
            for order in OrderManager.task_orders:
                #logger.info(f"order {order}")
                if order["symbol"] == symbol:
                    order_type = order["data"]["type"]
                    if order_type =="buy_at_level":
                        lmtPrice = float(order["data"]["lmtPrice"])
                        if (lastPrice>lmtPrice ):
                            OrderManager.on_task_order_trigger(order,lastPrice)
        except:
            logger.error("ERROR",exc_info=True)

    #########

    async def batch():
        while True:
            await asyncio.sleep(1)

#####################################


def main():

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
    logger.info("1")

    ib.run()

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
    
    main()
    #asyncio.run(main())