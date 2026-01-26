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
import traceback
from order import OrderManager
from trade_manager import TradeOrder
from balance import Balance

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

conn = sqlite3.connect(DB_FILE, isolation_level=None)
cur = conn.cursor()

logging.getLogger("ib_insync").setLevel(logging.WARNING)


class OrderTaskManager:

    ib=None
    ws :WSManager = None
    task_orders = []

    def __init__(self,config,orderManager):
        OrderTaskManager.orderManager=orderManager
        # Assegna gli event handlers

    async def bootstrap():
        logger.info("ORDER BOOT")

   
        cur.execute("""UPDATE task_orders set status='BOOT_CANC' 
            WHERE id IN (
                SELECT MAX(o.id)
                FROM task_orders o
                GROUP BY task_id
            )
            AND status in ('READY','STEP') """)
        

        df = pd.read_sql_query("""SELECT *
            FROM task_orders
            WHERE id IN (
                SELECT MAX(id)
                FROM task_orders
                GROUP BY task_id
            )
            AND status =='READY' 
            """, conn)
        OrderTaskManager.task_orders=[]
        for row in df.to_dict("records"):
            data = OrderTaskManager.get_task_order(row)
            logger.info(f"ORDER ADD {data}")

            OrderTaskManager.task_orders.append(data)

        logger.info(f"ORDER BOOT DONE {OrderTaskManager.task_orders}")   

  
    async  def on_update_trade(trade_order : TradeOrder):
        #logger.info(f"on_update_trade {trade_order} {OrderTaskManager.task_orders}")

        if any(order["symbol"] == trade_order.symbol  for order in OrderTaskManager.task_orders):
            existing_order = next(
                (order for order in OrderTaskManager.task_orders if order["symbol"]  == trade_order.symbol ),
                None
            )
            logger.info(f"on_update_trade {trade_order}  existing_order {existing_order}")

            actions = existing_order["data"]
            step = existing_order["step"]
            
            rules = [x for x in actions if x["step"] == step]
            if step ==1:
                rules[0]["price"] = trade_order.price
                await OrderTaskManager.send_task_order(existing_order)
            if step ==2 and len(rules) == 2:
                rules[0]["price"] = trade_order.take_profit
                rules[1]["price"] = trade_order.stop_loss
                await OrderTaskManager.send_task_order(existing_order)

           
    ##############

    async def send_task_order(order):
         if OrderTaskManager.ws:
            #data["type"] = "ORDER"
            await OrderTaskManager.ws.broadcast(
                {"type": "TASK_ORDER", "data" : order}
            )

    ############

 
    async def on_task_order_trigger(order,order_step,ticker ):
        try:
    
            logger.info(f'TRIGGER {order_step} last:{ticker["last"]} ')

            if order_step["side"] =="BUY":
                    #real_price = lastPrice+  lastPrice* 0.001

                    #trade = OrderManager.order_limit(order["symbol"], order_step["quantity"],real_price)
                    ret = await OrderTaskManager.orderManager.smart_buy_limit(order["symbol"], order_step["quantity"],ticker)#real_price)
                    if ret:
                        #error
                        order_step["error"] = ret
                        order["error"] = ret
                        logger.error(f">> {ret}")
                    else:
                        order_step["state"] = "filled"
                        order_step["trigger_price"] = ticker["last"]
       

            if order_step["side"] =="SELL":
                    #real_price = lastPrice-  lastPrice* 0.001
               
                    pos = Balance.get_position(order["symbol"])
                    if pos.position == None or pos.position ==0:
                         logger.warning("Position empty !!! ")
                         order["error"] = "Position empty "
                    elif pos.position<=0:
                        logger.warning("Position zero ")
                        order["error"] = "Position zero "
                    else:
                        logger.info(f"SELL ALL {order['symbol']} {pos.position } at {ticker['last']} ")

                        ret = await OrderTaskManager.orderManager.smart_sell_limit(order["symbol"], order_step["quantity"],ticker)
                        if ret:
                            #error
                            order_step["error"] = ret
                            order["error"] = ret
                            logger.error(f">> {ret}")
                        else:
                            order_step["trigger_price"] = ticker["last"]
                            order_step["state"] = "filled"
            
        except:
            try:
                logger.error("ERROR",exc_info=True)
                err = traceback.format_exc()
                order_step["error"] = err
                order["error"] = err
                #cur.execute('''INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                #                VALUES (?,?, ?, ?, ?, ?)''',
                #            ( order["task_id"],order["symbol"],"ERROR", json.dumps(order["data"]),time.time(),-1))
                #conn.commit()
                await OrderTaskManager.push_state(order,"ERROR")
                OrderTaskManager.task_orders.remove(order)
            except:
                order["error"] = "generic error"
                logger.fatal("ERROR",exc_info=True)
                #cur.execute('''INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                #                VALUES (?,?, ?, ?, ?, ?)''',
                #            ( order["task_id"],order["symbol"],"FATAL ERROR", json.dumps(order["data"]),time.time(),-1))
                #conn.commit()
                await OrderTaskManager.push_state(order,"FATAL ERROR")

                OrderTaskManager.task_orders.remove(order)
                

    def do_task_order_abort(order):
        order["cmd"] = "ABORT"
        
    async def push_state(order,status):
        cur.execute('''INSERT INTO task_orders (task_id, symbol, status,step,  data, timestamp,trade_id)
                                        VALUES (?,?, ?, ?, ?, ?,?)''',
                                    ( order["task_id"],order["symbol"],status,order["step"], json.dumps(order["data"]),time.time(),-1))
        conn.commit()

        logger.info(f">>> {order}")
        await OrderTaskManager.send_task_order(order)


    ##############################

    def get_task_order(row):
            data = {
                "id": row["id"],
                "task_id": row["task_id"],
                "trade_id": row["trade_id"],
                "status": row["status"],
                "step": row["step"],
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "data": json.loads(row["data"])
            }
            return data
    
    ################################

    async def bracket(symbol,timeframe):
        df = pd.read_sql_query(f"""
            SELECT  symbol, timeframe,  data
            FROM trade_marker
            WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
        """, conn)
        if (len(df) == 0):
            raise HTTPException(
                status_code=400,
                detail=f"Trade marker not found: {symbol}  {timeframe}"
        )

        data = json.loads(df.iloc[0]["data"])
        logger.info(f"ADD bracket {data}")

        price = data["price"]
        quantity = data["quantity"]
        stop_loss = data["stop_loss"]
        take_profit = data["take_profit"]

        logger.info(f"ADD bracket p:{price} q:{quantity} sl:{stop_loss} tp:{take_profit}")

        actions = [
            {
                "step" : 1,
                "side" : "BUY",
                "op" : "last >",
                "price" : price,
                "quantity" : quantity,
                "desc" : "MARKER"
            },
            {
                "step" : 2,
                "side" : "SELL",
                "op" : "last >",
                "price" : take_profit,
                "quantity" : quantity,
                "desc" : "TP"
            },
            {
                "step" : 2,
                "side" : "SELL",
                "op" : "last <",
                "price" : stop_loss,
                "quantity" : quantity,
                "desc" : "SL"
            }
        ]

        task = await OrderTaskManager.create_task(symbol, actions)
        #await OrderTaskManager.add_at_level(symbol,"last price >",quantity,price,action)
    
    async def add_at_level(symbol,triggerAt,totalQuantity,lmtPrice,action):
        pass

    async def create_task(symbol, actions):

        unix_time = time.time()
        task_id =1
        df = pd.read_sql_query("SELECT MAX(task_id) as task_id FROM task_orders", conn)
        if not pd.isna( df["task_id"].max()):
            task_id = int(df.iloc[0][0])+1

        cur.execute('''INSERT INTO task_orders (task_id, symbol, status,step,  data, timestamp,trade_id)
                    VALUES (?,?, ?, ?, ?, ?,?)''',
                (task_id,symbol,"READY", 1, json.dumps(actions),unix_time,-1))
        
        conn.commit()

        df = pd.read_sql_query("SELECT * FROM task_orders WHERE id = "+str(cur.lastrowid), conn)
        order=None
        for row in df.to_dict("records"):
            order = OrderTaskManager.get_task_order(row)

        OrderTaskManager.task_orders.append(order)
        await OrderTaskManager.send_task_order(order)
        #logger.info(f"TASK << {order}")
        return order
    
    async def cancel_orderBySymbol(symbol):
        logger.info(f"{OrderTaskManager.task_orders}")
        for order in OrderTaskManager.task_orders.copy():
            if order["symbol"] == symbol:
                    
                OrderTaskManager.do_task_order_abort(order)

##############

         
    async def onTicker(ticker):
        try:
            symbol = ticker["symbol"]
            #logger.info(f"onTicker {symbol},{ticker}")
            for order in OrderTaskManager.task_orders:
                #logger.info(f"order {order}")
                if order["symbol"] == symbol and not  "error" in order:
                    actions = order["data"]
                    step = order["step"]
                    
                    if "cmd" in order:
                        if order["cmd"] == "ABORT":

                            '''
                            for step in actions:
                                if "real_trade_id" in step:
                                    # cè un ordine attivo
                                    logger.info(f"ABORT ORDER {step}")

                                    pos = Balance.get_position(symbol)
                                    if pos.position == None or pos.position ==0:
                                        logger.warning("Position empty !!! ")
                                    else:
                                        logger.info(f"!!!! SELL ALL {symbol} {pos.position } at {lastPrice} ")
                                    #OrderManager.cancel_order(step["real_trade_id"])

                                    sell_price = lastPrice
                                    OrderManager.sell_limit(symbol, pos.position,sell_price )
                                    pass
                            '''
                            # close it 
                            order["status"] = "USER_CANC"
                            await OrderTaskManager.push_state(order,"USER_CANC")
                            OrderTaskManager.task_orders.remove(order)
                           
                    else:       
                            #logger.info(f"TEST {step} {actions}" )

                            rules = [x for x in actions if x["step"] == step]

                            logger.info(f"VALID {rules}" )

                            for rule in rules:
                                op = rule["op"]
                                triggered = False
                                if op == "last >" :
                                    lmtPrice = float(rule["price"])
                                    #logger.info(f"CHECK {lastPrice} > {lmtPrice}" )
                                    triggered =  (ticker["last"]>lmtPrice )
                                if op == "last <" :
                                    lmtPrice = float(rule["price"])
                                    #logger.info(f"CHECK {lastPrice} > {lmtPrice}" )
                                    triggered =  (ticker["last"]<lmtPrice )

                                if triggered:
                                        
                                        logger.info(f"VALID {rules}" )

                                        await OrderTaskManager.on_task_order_trigger(order,rule,ticker)
                                        if "error" in order:
                                            await OrderTaskManager.push_state(order,"ERROR")
                                            OrderTaskManager.task_orders.remove(order)
                                            continue
                                        else:
                                            order["step"] = order["step"]+1
                                            await OrderTaskManager.push_state(order,"STEP")

          
                                        max_step = 0
                                        for a in actions:
                                            max_step= max(max_step, a["step"])
                                            
                                        logger.info(f'CHECK END {order["step"]}/{max_step}')

                                        if  order["step"]  > max_step:

                                            logger.info(f'END {order}')

                                            await OrderTaskManager.push_state(order,"DONE")

                                            # check end
                                            #cur.execute("""INSERT INTO task_orders (task_id, symbol, status,  data, timestamp,trade_id)
                                            #VALUES (?,?, ?, ?, ?, ?)""",
                                            #    (order["task_id"],order["symbol"],"DONE", json.dumps(order["data"]),time.time(),-1))
                                
                                            #conn.commit()
                                            logger.info(f'ORDER CLOSED {order}')

                                            if "trade" in order:
                                                del order["trade"]

                                            OrderTaskManager.task_orders.remove(order)
                                            

                            
        except:
            logger.error("ERROR",exc_info=True)

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
    ticker ["last"] = 2.802334
    
    #et = OrderManager.smart_buy_limit("IVF",100,ticker)

    #ret = OrderManager.smart_sell_limit("IVF",100,ticker)
    #if ret:
    #   logger.error(f">> {ret}")
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