from ib_insync import *
import asyncio
from datetime import datetime, timedelta
import logging
import json
import sqlite3
from config import DB_FILE,CONFIG_FILE
from utils import convert_json
from props_manager import PropertyManager

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


class TradeManager:

    props: PropertyManager
    def __init__(self, props : PropertyManager):
        self.props=props

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

  
    '''
    def RR(self, stop_loss):
       
        #Risk / Reward (RR) 
        #2:1 → rischi 10€ per guadagnarne 20€
        
        return self.props("trade.profit_target") / stop_loss
    '''
    

if __name__ =="__main__":
    p = PropertyManager("config/properties.json")
    t = TradeManager(p)
    print(p.get(""))
    p.save()
    
    #print(t.trade_risk())