from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import Strategy# SmartStrategy

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

class VWAP_PERC(Indicator):
  
  def __init__(self,target_col):
        super().__init__([target_col])
        self.target_col=target_col
    
  def compute(self, dataframe, group, start_pos):
        
        close = group["close"]
        vwap = group["vwap"]
        vwap_up = group["vwap_up"]
        vwap_down = group["vwap_down"]

        band_h = vwap_up-vwap_down
        close_perc = 100* (close - vwap_down) / band_h

        dataframe.loc[group.index, self.target_col] = close_perc

        gain = close_perc - close_perc.shift(1)

        dataframe.loc[group.index, self.target_col + "_gain"] = gain

        variance = ((band_h) / vwap_down) * 100

        dataframe.loc[group.index, self.target_col + "_var"] = variance

########################

#from strategy.order_strategy import *
class SmartStrategy(Strategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []
        self.legend = []
        self.marker_map= {}

    def marker(self,timeframe:str, symbol:str = None)-> pd.DataFrame:
        if timeframe in self.marker_map:
            if not symbol:
                return self.marker_map[timeframe]
            else:
                return self.marker_map[timeframe][self.marker_map[timeframe]["symbol"] == symbol]
        else:
            return  pd.DataFrame()
         
    def buy(self,  symbol, label):
        logger.info(f"BUY {symbol} {label}")
        self.add_marker(symbol,"BUY",label,"#00FF00","arrowUp")

    #shapes : arrowUp, arrowDown, circle
    def add_marker(self, symbol,type, label,color,shape, position ="aboveBar", _timeframe=None):
        timeframe = self.timeframe if _timeframe==None else _timeframe
        
        #logger.info(f"self.trade_index {self.trade_index}")
        candle =  self.trade_dataframe.loc[self.trade_index]
        
        timestamp =  candle["timestamp"]
        value = candle["close"]

        #logger.info(f"marker idx {self.trade_index} {type} {symbol} ts: {timestamp} val: {value}")

        if not timeframe in self.marker_map:
            self.marker_map[timeframe] = pd.DataFrame(
                    columns=["symbol","timeframe","type", "timestamp", "value", "desc","color","shape","position"]
                )

        self.marker_map[timeframe].loc[len(self.marker_map[timeframe])] = [
                symbol,               # symbol
                timeframe,                # type
                type,               # symbol
                timestamp,       # timestamp
                value,              # value
                label,           # desc
                color,
                shape,
                position
            ]

       # self.marker_map["symbol"].append({"type":"buy", "symbol" : symbol, "ts": int(timestamp), "value": price, "desc": label})
     
    def live_markers(self,symbol,timeframe,since):
        if not timeframe:
            timeframe = self.timeframe
        if since:
            df = self.marker(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
        else:
            df = self.marker(timeframe,symbol)
        if df.empty:
            return []
        else:
            #logger.info(f"live_markers since:{since}\n{df}")
            return df.to_dict(orient="records")
       
    def live_legend(self,symbol,timeframe,since):
        if not timeframe:
            timeframe = self.timeframe

        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        arr = []
        for leg in self.legend:
            d = leg.copy()
            del d["ind"]
            d["value"] =   df.iloc[-1] [d["source"]]
            arr.append(d)
         #logger.info(f"live_markers since:{since}\n{df}")
        return arr
        
    def live_indicators(self,symbol,timeframe,since):
     
        if not timeframe:
            timeframe = self.timeframe

        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)

        df = df.replace([np.inf, -np.inf], np.nan)
        df.dropna()
    
        if df.empty:
            return{"strategy": __name__ 
                   ,"legends" : []
                   ,"markers": self.live_markers(symbol,timeframe,since)}
        
        #logger.info(f"out \n{df}")
        o = {"strategy": __name__ ,
             "markers": self.live_markers(symbol,timeframe,since), 
             "legends": self.live_legend(symbol,timeframe,since), 
             "list" : []}

        #logger.info(f"process1 {self.plots}")
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
        self.plots.append({"ind": ind ,"name" : name ,"source" : source, "color" : color, "panel" : panel,"style":style,"lineWidth": lineWidth})
        pass
    
    def add_legend(self, ind:Indicator, source:str,label:str, color:str):
        self.legend.append( {"ind": ind ,"source" : source ,"label" : label, "color" : color})
        pass

########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :

        i = self.addIndicator(self.timeframe,VWAP_OPEN("vwap",1))
        i1 = self.addIndicator(self.timeframe,VWAP_PERC("vwap_perc"))

        #self.addIndicator(self.timeframe, VWAP_DIFF("diff"))
       
        self.add_plot(i, "vwap","#15ff00", "main", source="vwap",style="SparseDotted", lineWidth=2)
        self.add_plot(i, "vwap_up","#15ff00", "main", source="vwap_up",style="SparseDotted", lineWidth=2)
        self.add_plot(i, "vwap_down","#15ff00", "main", source="vwap_down",style="SparseDotted", lineWidth=2)

        self.add_plot(i1, "vwap_perc","#034cd3", "sub1", source="vwap_perc",style="Solid", lineWidth=2)

        self.add_legend(i1, "vwap_perc_var","var","#ffffff" )
    ######################################

    async def trade_symbol_at(self, isLive:bool, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        if not isLive:
            return
        try:
            df_symbols = dataframe[dataframe["symbol"]== symbol ]

            close =  df_symbols.iloc[-2]["close"]
            #vwap =  df_symbols.iloc[-2]["vwap"]
            #vwap_up =  df_symbols.iloc[-1]["vwap_up"]
            #vwap_down =  df_symbols.iloc[-1]["vwap_down"]
            close_perc =  df_symbols.iloc[-1]["vwap_perc"]
            close_perc_prev =  df_symbols.iloc[-2]["vwap_perc"]

            day_volume=  df_symbols.iloc[-1]["day_volume"]

            vwap_perc_gain =  df_symbols.iloc[-1]["vwap_perc_gain"]
            vwap_perc_gain_prev =  df_symbols.iloc[-2]["vwap_perc_gain"]

            if day_volume > 500000:
     
                logger.info(f"df_symbols   {symbol} \n {df_symbols.tail(1)}" )

                #band_h =  vwap_up-vwap_down
                #close_perc = 100* (close - vwap_down) / band_h

                logger.info(f"symbol close_perc {close_perc}")

                if (close_perc > 90):
                    await self.send_event(symbol, "VWAP UP", f"VWAP UP {close_perc:.1f}%",f"vwap over {close_perc:.1f}% ",color="#A7FF1A")
                
                if (close_perc < 10):
                    await self.send_event(symbol, "VWAP LOW", f"VWAP LOW {close_perc:.1f}%",f"vwap lower {close_perc:.1f}% ",color="#F37C0C")
                
                ## sotto
                if (close_perc_prev <=5 and close_perc>5
                    and vwap_perc_gain<0  and vwap_perc_gain_prev >0):
                      await self.send_event(symbol, "VWAP LOW-B", f"vwap low bounce {close_perc:.1f}%",f"vwap over {close_perc:.1f}% ",color="#B8A437")
                
                #f (close_perc > 50):
                #    self.buy(symbol,f"{close_perc:.1f}%")
            #dataframe.loc[global_index]["diff_perc"] = diff_perc

        except:
            logger.error(f"trade_symbol_at   {symbol} index {global_index} \n {dataframe.tail(1)}", exc_info=True )
            #exit(0)

    ######################################

    async def trade_symbol_at_old(self, isLive:bool, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        if not isLive:
            return
            #logger.info(f"trade_symbol_at   {symbol} \n {dataframe.tail(1)}" )
        try:
            df_symbols = dataframe[dataframe["symbol"]== symbol ]
            #close = dataframe.loc[global_index]["close"]
            #vwap = dataframe.loc[global_index]["vwap"]
            #diff_perc = ((close - vwap) / vwap) * 100

            diff_perc_prec =  df_symbols.iloc[-2]["diff"]
            diff_perc =  df_symbols.iloc[-1]["diff"]

            logger.info(f"df_symbols   {symbol} \n {df_symbols.tail(2)}" )

            #dataframe.loc[global_index]["diff_perc"] = diff_perc

            if isLive and diff_perc>1:
                await self.send_event(symbol, "vwap",
                     f"""<span :style="my_ramp_perc({diff_perc},'#FF0000')"> vwap {diff_perc:.1f}%</span>""",
                     f"vwap {diff_perc:.1f}%",color="#E4D61A")

                if isLive and diff_perc_prec* diff_perc<0:
                    await self.send_event(symbol, "vwap sign", f"vwap sign {diff_perc:.1f}%",f"vwap {diff_perc_prec:.1f}%->{diff_perc:.1f}% ",color="#B90AFF")

            pass
            #if (gain > 0):
            #    self.buy(symbol,f"BUY")
                #logger.info(f"trade_symbol_at   {symbol} index {global_index} {gain} " )
        except:
            logger.error(f"trade_symbol_at   {symbol} index {global_index} \n {dataframe.tail(1)}", exc_info=True )
            #exit(0)

    
    '''
    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
        
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(1)}" )

        
        gain = dataframe.iloc[-1]["gain"]

        if (gain > -1):
            #logger.info(f"FIND {gain} > {self.min_gain}")
            self.buy(symbol,f"buy1 gain {gain}")
    '''        
  
