from typing import Dict
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta

from order_task import OrderTaskManager
from balance import Balance, PositionTrade
from company_loaders import *
from collections import deque
from utils import SECONDS_TO_TIMEFRAME
logger = logging.getLogger(__name__)
from concurrent.futures import ThreadPoolExecutor

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
from bot.strategy import *

#from strategy.order_strategy import *
class SmartStrategy(Strategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.position = Position(10000)
        self._book = OrderBook( self.position )
        self.propMap = {}
        #self.slot_count=2

    def get_quantity(self,loss_by_trade,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(loss_by_trade  / price )

    '''
    ring: [default, alarm, chime, alert1, new_symbol, news ]
    '''
    async def add_marker(self, symbol,type, label,desc,color,shape="small_square", position ="atPriceTop",
                    _timeframe=None, sourceField = "close", value=None,timestamp=None,ring="news",sendEvent=True):
        timeframe = self.timeframe if _timeframe==None else _timeframe
        
        #logger.info(f"self.trade_index {self.trade_index}")
        candle =  self.trade_dataframe.loc[self.trade_index_global]
        if not timestamp:
            timestamp =  candle["timestamp"]
        if not value:
            value = candle[sourceField]

        #logger.info(f"marker idx {self.trade_index} {type} {symbol} ts: {timestamp} val: {value}")

        if not timeframe in self.marker_map:
            self.marker_map[timeframe] = pd.DataFrame(
                    columns=["symbol","timeframe","type", "timestamp", "price", "desc","color","shape","position"]
                )

        self.marker_map[timeframe].loc[len(self.marker_map[timeframe])] = [
                symbol,               # symbol
                timeframe,                # type
                type,               # symbol
                timestamp,       # timestamp
                value,              # price
                label,           # desc
                "#000000",
                shape,
                position
            ]
        if not self.bootstrapMode and sendEvent:    
            await self.send_event(symbol, label, desc,desc,color=color, ring=ring)

        #logger.info(f"marker_map {self.marker_map}")

       # self.marker_map["symbol"].append({"type":"buy", "symbol" : symbol, "ts": int(timestamp), "value": price, "desc": label})
     

    def live_markers(self,symbol,timeframe,from_ts,to_ts):
        if not timeframe:
            timeframe = self.timeframe
        '''
        if since:
            df = self.marker(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
        else:
            df = self.marker(timeframe,symbol)
        '''
        df = self.get_df_windows( self.marker(timeframe,symbol),from_ts,to_ts)

        if df.empty:
            return []
        else:
            #logger.info(f"live_markers since:{since}\n{df}")
            return df.to_dict(orient="records")
       
    def live_legend(self,symbol,timeframe,from_ts,to_ts):
        if not timeframe:
            timeframe = self.timeframe

        df = self.get_df_windows( self.df(timeframe,symbol),from_ts,to_ts)
        '''
        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        '''

        arr = []
        for leg in self.legend:
            d = leg.copy()
            del d["ind"]
            try:
                v = df.iloc[-1][d["source"]]
                d["value"] = 0 if pd.isna(v) else v
            except:
                d["value"] =0
            arr.append(d)
         #logger.info(f"live_markers since:{since}\n{df}")
        return arr
    
    def get_df_windows(self,source_df,from_ts,to_ts):
        if from_ts or to_ts:
            df = source_df
            if not df.empty:
                if from_ts:
                    df = df[df["timestamp"]>= from_ts]
                else:
                    df = df[df["timestamp"]<= to_ts]
            #logger.info(f"since {since}\n{df}")
        else:
            df = source_df

        df = df.replace([np.inf, -np.inf], np.nan)
        df.dropna()
        return df
        
    def live_indicators(self,symbol,timeframe,from_ts,to_ts):
     
        if not timeframe:
            timeframe = self.timeframe

        '''
        if from_ts or to_ts:
            df = self.df(timeframe,symbol)
            if not df.empty:
                if from_ts:
                    df = df[df["timestamp"]>= from_ts]
                else:
                    df = df[df["timestamp"]<= to_ts]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        '''

        #df = df.replace([np.inf, -np.inf], np.nan)
        #df.dropna()
        df = self.get_df_windows(self.df(timeframe,symbol),from_ts,to_ts)

        
        if df.empty:
            return{"strategy": __name__ 
                   ,"legends" : []
                   ,"markers": self.live_markers(symbol,timeframe,from_ts,to_ts)}
        
        #logger.info(f"out \n{df}")
        o = {"strategy": __name__ ,
             "markers": self.live_markers(symbol,timeframe,from_ts,to_ts), 
             "legends": self.live_legend(symbol,timeframe,from_ts,to_ts), 
             "list" : []}

        #logger.info(f"process1 {self.plots}")

        #logger.info(f"live_indicators {symbol} {timeframe} from_ts:{from_ts} to_ts:{to_ts} {self} \n{df}") 

        for p in  self.plots:
            for col in p["ind"].target_cols:
                if (col ==p["source"] or not p["source"]):
                    #logger.info(f"process {col}")
                    d = p.copy()
                    del d["ind"]
                    d["symbol"] = symbol
                    d["timeframe"] = timeframe
                    df_data = p["ind"].get_render_data(df,col)
                    if symbol:
                            df_data = df_data[["time","value"]]
                    d["data"] = df_data.to_dict(orient="records")
                        
                    o["list"].append(d)

        return o
    
    #######
    # style in ['Solid','Dotted','Dashed','LargeDashed','SparseDotted']
    def add_plot(self,ind : Indicator ,name :str,  color:str,panel: str ='main',source = None, style="Solid",lineWidth=1):
        if not source:
            source = ind.target_cols[0]
        self.plots.append({"ind": ind ,"name" : name ,"source" : source, "color" : color, "panel" : panel,"style":style,"lineWidth": lineWidth})
        pass
    
    def add_legend(self, ind:Indicator, source:str,label:str, color:str):
        self.legend.append( {"ind": ind ,"source" : source ,"label" : label, "color" : color})
        pass

    #########

    def get_all_meta(self,symbol=None):
        if symbol and not symbol in self._meta: return {}
        if symbol:
            return self._meta[symbol]
        else:
            return self._meta
        
    def get_df_meta(self):
        return pd.DataFrame.from_dict(self._meta , orient="index")

    def has_meta(self,symbol,fieldName):
        if not symbol in self._meta: return False
        return fieldName in self._meta[symbol]

    def get_meta(self,symbol,fieldName, default=None):
        if not symbol in self._meta: return default
        return self._meta[symbol].get(fieldName,default)

    def del_meta(self,symbol,fieldName):
        if not symbol in self._meta: return 
        if fieldName in self._meta[symbol]: 
            del self._meta[symbol][fieldName]

    def set_meta(self,symbol,meta: dict):
        if not symbol in self._meta:
            self._meta[symbol] = {}
        for k,v in meta.items():
             self._meta[symbol][k] = v
    #########

    async def set_property(self,symbol ,  value ):
        if self.backtestMode : return

        if not symbol in self.propMap:  
            self.propMap[symbol] = {}    
        self.propMap[symbol].update(value)

        if not self.backtestMode and not self.bootstrapMode:
            #logger.info("send")
            await self.client.send_strategy_prop("TRADE", symbol,self.timeframe,value)
        else:
            #logger.info(f"send1 {self.backtestMode} {self.bootstrapMode}")
            pass
            #self.add_marker(symbol,"SPOT",name,"#060806","square",position ="atPriceTop")

    async def sync_properties(self):   
        logger.info(f"sync_properties {self.propMap}")
        for symbol in self.propMap:
             await self.client.send_strategy_prop("TRADE", symbol,self.timeframe,self.propMap[symbol])

    async def send_trade_order(self,symbol:str,type:str,side:str, quantity:str, price, tp, sl,  desc:str):
        if self.backtestMode: return

        await self.client.send_strategy_trade("strategy-trade",symbol,self.timeframe,
                 {"type":type,"price_op":side,"quantity": quantity
                  ,"price": price,"take_profit": tp,"stop_loss":sl,"desc": desc})
       
    async def send_trade_bracket(self, symbol:str,datetime,side:str, quantity:str, price, tp, sl,  desc:str):
        if self.backtestMode: return

        logger.info(f"BUY  {symbol} {datetime} s:{side} p:{price} tp:{tp} sl:{sl}")
        await self.send_trade_order(symbol,"bracket",side,quantity,price,tp, sl, desc )

    #########

    '''
    def getSlot(self,symbol):
        if self.slot_count<=0:  
            return False
        else:
            return True

    def takeSlot(self,symbol):
        logger.info(f"takeSlot {symbol} slot_count before {self.slot_count}")   
        self.slot_count-=1
        
        
    def freeSlot(self,symbol):
        if self.hasCurrentTrade(symbol):    
            self.slot_count+=1
            self.set_property("","",{"slot_count":self.slot_count })
    ''' 

    async def on_live_trade_event(self,type, trade:PositionTrade):
        if type =="POSITION_TRADE":
            
            #if not trade.isClosed():
            #    self.takeSlot(trade.symbol)
            #    #await self.set_property("","",{"slot_count":self.slot_count })

            self.set_meta( trade.symbol, {"last_trade":trade})   
            #trade = Trade.from_dict(data)
            logger.info(f"TRADE EVENT {trade.to_dict()}  ")

    def tp_enabled(self,symbol):
        return self.props.get(f"strategy.{symbol}.tp",True)
       
    def sl_enabled(self,symbol):
        return self.props.get(f"strategy.{symbol}.sl",True)
    
    def buy_enabled(self,symbol):
        return self.props.get(f"strategy.{symbol}.buy",True)
    
    async def buy(self,symbol,timestamp,price, quantity,label=""):
        if self.hasCurrentTrade(symbol):
            return
        
        #check budget
     
        if not self.buy_enabled(symbol):
            logger.info(f"BUY DISABLED {symbol} ")
            if not self.bootstrapMode:
                 await self.send_event(symbol, "BUY OFF", f"BUY DISABLED",f"BUY DISABLED" ,color="#FF2A04", ring="news")
            return 
 
        logger.info(f"BUY {symbol} {timestamp} {quantity} at {price} [{label}]")
        await self.add_marker(symbol,"BUY","BUY",label,"#3CFF00FF","arrowUp",position="atPriceBottom",ring="chime")

        #if not self.buyMap[symbol]:
        self._book.long(symbol, timestamp, price, quantity,label)

        #super().buy(symbol,label)
        if not self.bootstrapMode and not self.backtestMode:
            usd = Balance.cash_usd

            logger.info(f"BUY {symbol} total_price {price * quantity} cash_usd {usd}")

            if price * quantity > usd:
                logger.info(f"NOT ENOUGH CASH TO BUY {symbol} price {price} quantity {quantity} cash_usd {usd}")
                return    


            await self.orderManager.smart_buy_limit(symbol, quantity,self.client.getTicker(symbol))
            pass
        #    await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#21FF04", ring="news")


    async def sell(self,symbol,timestamp, price, label=""):

        if self.hasCurrentTrade(symbol):
            logger.info(f"SELL  {symbol} {timestamp}")
            
            #self.freeSlot(symbol)   
            #a#wait self.send_property("","",{"slot_count":self.slot_count })

            trade = self._book.close(symbol,timestamp,price)

            await self.add_marker(symbol, "SELL", "SELL",label, "#FF0404", "arrowDown",position="atPriceBottom")

            if not self.bootstrapMode and not self.backtestMode:
                await self.orderManager.abort_smart(symbol)

                await OrderTaskManager.cancel_orderBySymbol(symbol)

                pos = Balance.get_position(symbol)
                if (pos and pos.position>0):
                    logger.info(f"SELL ALL {symbol} {pos.position} ")
                    ret = await self.orderManager.smart_sell_limit(symbol,pos.position, self.client.getTicker(symbol))


            #    await self.send_event(symbol, "SELL", f"SELL",f"SELL",color="#FF0404", ring="news")
            return trade
        else:   
            return None
    
    def hasCurrentTrade(self,symbol):
        if not self.bootstrapMode and not self.backtestMode:
                if self.has_meta(symbol, "last_trade"):
                    last_trade : PositionTrade = self.get_meta(symbol, "last_trade")
                    return last_trade if last_trade.isClosed()==False else None   
                else:
                    return None    
        else:
           return self._book.hasCurrentTrade(symbol)

    def getCurrentTrade(self,symbol):
        if not self.bootstrapMode and not self.backtestMode:
                if self.has_meta(symbol, "last_trade"):
                    last_trade : PositionTrade = self.get_meta(symbol, "last_trade")
                    return last_trade if last_trade.isClosed()==False else None   
                else:
                    return None    
        else:
           return self._book.getCurrentTrade(symbol)
        
    def buyGain(self,symbol,close):
        if not self.bootstrapMode and not self.backtestMode:
                if self.has_meta(symbol, "last_trade"):
                    logger.info(f"BUYGAIN has_meta {symbol} last_trade {self.get_meta(symbol, 'last_trade').to_dict()}")    
                    last_trade : PositionTrade = self.get_meta(symbol, "last_trade")
                    if not last_trade.isClosed():
                        tot = 0.0
                        c=0
                        time=0
                        q= 0.0
                        buy_cost = 0.0
                        for op in last_trade.list:
                            if op.side == "BUY":
                                c=c+1
                                q+= op.size
                                gain = 100.0 * ((close - op.price) /  op.price)
                                buy_cost +=  op.price * op.size
                                tot+= gain
                                time = max(time ,op.time )

                        actual_sell = q *  close
                        return (tot /   c  , int(time * 1000), actual_sell- buy_cost)
                    else:
                        return  (None,None,None)    
                else:
                    return  (None,None,None)    
        else:
            if self._book.hasCurrentTrade(symbol):
                return self._book.gain(symbol,close)
            else:
                return (None,None,None)
                

    def set_current_price(self, symbol, price) :
        self._book.set_current_price(symbol,price)

    '''
    async def buy(self,symbol,datetime,price, quantity,label=""):
        if self.book.hasCurrentTrade(symbol):
            return

        logger.info(f"BUY {symbol} {datetime} {quantity} at {price} [{label}]")
        await self.add_marker(symbol,"BUY","BUY",label,"#3CFF00FF","arrowUp",position="atPriceBottom",ring="chime")

        #if not self.buyMap[symbol]:
        self.book.long(symbol, datetime, price, quantity,label)

        #super().buy(symbol,label)
        #if not self.bootstrapMode:
        #    await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#21FF04", ring="news")


    async def sell(self,symbol,datetime, price, label=""):

        if self.book.hasCurrentTrade(symbol):
            logger.info(f"SELL  {symbol} {datetime}")

            trade = self.book.close(symbol,datetime,price)

            await self.add_marker(symbol, "SELL", "SELL",label, "#FF0404", "arrowDown",position="atPriceBottom")

            #if not self.bootstrapMode:
            #    await self.send_event(symbol, "SELL", f"SELL",f"SELL",color="#FF0404", ring="news")
            return trade
        else:   
            return None

    def buyGain(self,symbol,close):
        if self.book.hasCurrentTrade(symbol):
            return self.book.gain(symbol,close)
        else:
            return 0
        
    '''
    def setSL(self,symbol, price):
        self.set_meta(symbol,{"SL": price})

    def setTP(self,symbol, price):
        self.set_meta(symbol,{"TP": price})