from ib_insync import *
import asyncio
from datetime import datetime, timedelta
import logging
import json
import pandas as pd
from dataclasses import dataclass
from config import DB_FILE,CONFIG_FILE
from utils import convert_json
from props_manager import PropertyManager
#from mulo_client import MuloClient

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def calc_percent( from_price, to_price):
        return ((to_price-from_price) / from_price) * 100
    
#@dataclass
class TradeOrder:
    symbol: str
    timeframe: str
    type: str
    # chart setup
    price: float
    stop_loss: float
    take_profit: float
    # ui setup
    quantity : float
    
    # computed
    total_price_usd : float
    loss_usd : float
    profit_usd : float

    def __init__(self, data: dict):
            
            self.symbol=data["symbol"]
            self.timeframe=data["timeframe"]
            self.type=data["type"]
            self.price=float(data["price"])
            self.stop_loss=float(data["stop_loss"])
            self.take_profit=float(data["take_profit"])
            self.quantity=float(data["quantity"])
    
            
        
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "type": self.type,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "quantity": self.quantity,

            "total_price_usd" : self.total_price_usd,
            "loss_usd" : self.loss_usd,
            "profit_usd" : self.profit_usd
        }
    
    def __str__(self) -> str:
        return str(self.to_dict())
        
    def __repr__(self) -> str:
       return str(self.to_dict())

#####################################################

class TradeManager:
    props: PropertyManager

    def __init__(self, config,client, props : PropertyManager):
        self.props=props
        self.client=client

        props.add_computed("trade.risk_per_trade", self.risk_per_trade)
        props.add_computed("trade.max_day_loss", self.max_day_loss)

    def risk_per_trade(self):
            capital = self.props.get("balance.USD")
            trade_risk = self.props.get("trade.trade_risk")
            return capital * trade_risk

    def max_day_loss(self):
            capital = self.props.get("balance.USD")
            day_risk = self.props.get("trade.day_risk")
            return capital * day_risk

    async def on_property_changed(self,prop_name,value,renderPage):
         logger.info(f"trade prop change {prop_name}")

         if prop_name == "trade.risk_per_trade":
            df  = self.client.get_df("SELECT * FROM trade_marker")
            logger.info(f"df {df}")
            for row in df.to_dict(orient="records"):
                 dict = json.loads(row['data'])
                 logger.info(f"row {dict}")
                 path = "trade.tradeData."+row["symbol"]
                 order = TradeOrder(dict)
                 self.fill_computed(order)
                 await renderPage.send({"type":"props", "path": path, "value":order.to_dict() })
            pass
    
    def fill_computed(self, order: TradeOrder):
         order.total_price_usd  = order.quantity * order.price
         order.loss_usd  = order.quantity * order.stop_loss-order.total_price_usd
         order.profit_usd  =order.quantity * order.take_profit- order.total_price_usd

    async  def update_order(self,symbol, timeframe,data)-> TradeOrder:
        self.client.execute("DELETE FROM trade_marker WHERE symbol=?",
            (symbol,))
        
        order =TradeOrder(data)
        self.fill_computed(order)
        self.client.execute("""
                INSERT INTO trade_marker (symbol, timeframe,  data)
                VALUES (?, ?, ?)
            """, (
                symbol,
                timeframe,
                json.dumps(order.to_dict())
            ))
        return order

    async  def add_order(self,symbol, timeframe,data)-> TradeOrder:
        self.client.execute("DELETE FROM trade_marker WHERE symbol=? ",
            (symbol,))
        
        order =None
        if data["type"] =="bracket":
             order = await self.add_order_bracket(symbol, timeframe,data["price"])
        if order:     
            self.client.execute("""
                INSERT INTO trade_marker (symbol, timeframe,  data)
                VALUES (?, ?, ?)
            """, (
                symbol,
                timeframe,
                json.dumps(order.to_dict())
            ))
        return order
    
    async def  add_order_bracket(self,symbol, timeframe,price)-> TradeOrder:
        last_candles_count = 10
        
        df_last_data = await self.client.ohlc_data(symbol,timeframe)
        df_last_data["datetime"] = (
            pd.to_datetime(df_last_data["t"], unit="ms", utc=True)
            .dt.tz_convert(None)   # converte in timezone locale
        )
        logger.info(f"df_last_data {df_last_data.tail(10)}")

        max_h = df_last_data.tail(last_candles_count)["h"].max()
        min_l = df_last_data.tail(last_candles_count)["l"].min()
        stop_loss=min_l
     
        #loss_percent = calc_percent(price,stop_loss )
        #tp_percent = loss_percent * self.props.get("trade.rr")
        #take_profit= price + price * tp_percent

        take_profit = price + ( price -stop_loss ) * self.props.get("trade.rr")


        logger.info(f"min {min_l} max {max_h}")

        order = TradeOrder({
             "symbol" : symbol,
             "timeframe" : timeframe,
             "type" : "bracket",
             "price" : price,
             "stop_loss" : stop_loss,
             "take_profit" : take_profit,
             "quantity" : 100
        })
        self.fill_computed(order)
        return order

    
    '''
    def RR(self, stop_loss):
       
        #Risk / Reward (RR) 
        #2:1 → rischi 10€ per guadagnarne 20€
        
        return self.props("trade.profit_target") / stop_loss
    '''
    

if __name__ =="__main__":

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            #print(config)
    except FileNotFoundError:
        logger.error("Config File non trovato")
    except json.JSONDecodeError as e:
        logger.error("JSON non valido:", e)

    client = MuloClient(DB_FILE,config)
    client.sym_mode=False
    p = PropertyManager("config/properties.json")
    t = TradeManager(config, client,p)
    print(p.get(""))
    #p.save()
    
    async def test():
        order = await t.add_order("NVDA","10s", {"price" : 180 ,"type" : "bracket"})
        print(order.to_dict())     

    asyncio.run(test())
   
    
    #print(t.trade_risk())