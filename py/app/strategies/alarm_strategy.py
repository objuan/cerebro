from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import Strategy
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

#from strategy.order_strategy import *
def get_key (symbol,tf):
    return symbol+"_"+tf


def point_above_line(p1, p2, p, eps=1e-9):
    #print("point_side", p1, p2, p)
    if p2["x"] == p1["x"]:
        return "on vertical line"

    m = (p2["y"] - p1["y"]) / (p2["x"] - p1["x"])
    y_line = p1["y"] + m * (p["x"] - p1["x"])

    diff = p["y"] - y_line

    if diff > eps:
        return "above"
    elif diff < -eps:
        return "below"
    else:
        return "on line"

    
class Alarm:
    def __init__(self, symbol: str, timeframe: str, source: str, type: str, line_data):
        self.symbol = symbol
        self.timeframe = timeframe
        self.source = source
        self.type = type
        self.line_data=line_data
        self.line_type = line_data["type"]
        self.desc=""
        self._consume ={}

    def consume(self,phase):
        self._consume[phase] = True
    def remove_consume(self,phase):
        if phase in self._consume:
            del self._consume[phase]

    def isConsumed(self,phase):
        return phase in  self._consume

    def eval(self,lastCandle)->bool:

        val = float(lastCandle[self.source])
        ts = int(lastCandle["timestamp"])
      
        if self.line_type =="price-line":
            price = self.line_data["p"]["val"]["y"]
            if (self.type == "above"):
                self.desc=f"{val:.4f} > {price:.4f}"
                return val > price
            elif (self.type == "below"):
                self.desc=f"{val:.4f} < {price:.4f}"
                return val < price
       
        if self.line_type =="line":
            t1 = int(self.line_data["p1"]["time"])
            t2 = int(self.line_data["p2"]["time"])
            p1 = self.line_data["p1"]["val"]["y"]
            p2 = self.line_data["p2"]["val"]["y"]
            if t2 < t1:
                a = p1
                p1 = p2
                p2=a
                a = t1
                t1 = t2
                t2=a
            
            dt1 = datetime.fromtimestamp(t1/1000)
            dt2 = datetime.fromtimestamp(t2/1000)
            #print("LINE",p1,p2,t1,t2, "ts",ts,dt1,dt2)

            ret = point_above_line({"x":t1,"y":p1 },{"x":t2,"y":p2 },{"x":ts,"y":val })
            self.desc=f"{val:.4f} {self.type} line"
            return ret ==self.type
            #print("RET" ,ret)
            #return ret
        if self.line_type =="split-box":
            mid = self.line_data["center_left"]["y"]
            if val > mid and not self.isConsumed(">"):
                self.consume(">")
                self.remove_consume("<")
                self.desc= "Above SPlit"
                return True
            if val < mid and not self.isConsumed("<"):
                self.consume("<")
                self.remove_consume(">")
                self.desc= "Below Split"
                return True

        if self.line_type =="trade-box":
            tp = self.line_data["top_left"]["y"]
            sl = self.line_data["bottom_right"]["y"]
            buy = self.line_data["center_left"]["y"]

            if val > buy and not self.isConsumed("buy"):
                self.consume("buy")
                self.desc= "Above BUY"
                return True
            
            if val > tp and not self.isConsumed("tp"):
                self.consume("tp")
                self.desc= "Above TakeProfit"
                return True
            
            if val < sl and not self.isConsumed("sl"):
                self.consume("sl")
                self.desc= "Below StopLoss"
                return True

            #print("trade box ",buy,tp,sl )
            pass
        #if (self.type == "above"):
        #    return 
        #  print("val",val,"price",price)
        return False

    def toDict(self):
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "source": self.source,
            "type": self.type,
            "line" : self.line_type
        }
    
class AlarmStrategy(Strategy):

   
    async def on_start(self):
        self.alarmMap = {}
        pass

    def on_plot_lines_changed(self, symbol, tf):
        key = get_key(symbol,tf)
        #logger.info(f"on_plot_lines_changed   {symbol} {tf}" )

        if not key in self.alarmMap:
             self.alarmMap[key]= []
        
        self.update_alarms(symbol,tf)
             
    
    def update_alarms(self,symbol,timeframe):
        key = get_key(symbol,timeframe)

        #logger.info(f"update_alarms {symbol,timeframe}")
        self.alarmMap[key] = []
        df = self.client.get_df("""
            SELECT guid, symbol, timeframe, type, data
            FROM chart_lines
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        if len(df)>0:
            #logger.info(f"update_alarms \n{df}")

            for _, row in df.iterrows():
                data = json.loads(row["data"])
                alarms = data.get("alarms", [])
                
                if len(alarms)>0:
                    #logger.info(f"FIND {alarms}")
                    for alarm in alarms:
                        type = alarm["type"]
                        source = alarm["source"]

                        #logger.info(f"ADD s:{source} t:{type} ")
   
                        self.alarmMap[key].append(
                          Alarm(symbol,timeframe, source,type, data)
                        )

          
    def populate_indicators(self) :
        pass

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
        #devo controllare tutti i timeframe
        for timeframe in ["10s","30s","1m","5m","15m","1h"]:
            key = get_key(symbol,timeframe)
            if not key in self.alarmMap:
                self.alarmMap[key]= []
                self.update_alarms(symbol,timeframe)

            if len(self.alarmMap[key])>0:
                last = dataframe.iloc[-1]

                for alarm in self.alarmMap[key]:
                    ret = alarm.eval(last)

                    #logger.info(f"CHECK {alarm.toDict()} ret:{ret} ")

                    if ret:
                        await self.send_event(symbol,
                            name= f"ALARM",
                                    small_desc=f"{timeframe} {alarm.desc}",
                                    full_desc=f"{timeframe} {alarm.desc}",
                                    color = "#C1FFCE")
        #logger.info(f"on_symbol_candles   {symbol} {self.timeframe} \n {dataframe.tail(2)}" )
  


  