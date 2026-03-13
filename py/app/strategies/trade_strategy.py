from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

class COPY(Indicator):
  
    def __init__(self,target_col, source:str):
        super().__init__([target_col])
        self.source=source
        self.target_col=target_col

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source].to_numpy()

        for i_idx in range(from_local_index,len(symbol_idx) ):
            dest[symbol_idx[i_idx]] = source[symbol_idx[i_idx]]

class GAIN(Indicator):
  
    def __init__(self,target_col, source:str, timeperiod:int):
        super().__init__([target_col])
        self.source=source
        self.target_col=target_col
        self.timeperiod=timeperiod

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source].to_numpy()

        for i_idx in range(from_local_index,len(symbol_idx) ):
            prev = source[symbol_idx[max(0,i_idx -self.timeperiod )]]
            current = source[symbol_idx[i_idx]]
            dest[symbol_idx[i_idx]] = 100.0 * (current-prev ) / prev


class DIFF_PERC(Indicator):
  
    def __init__(self,target_col, source_base:str, source_signal:str):
        super().__init__([target_col])
        self.source_base=source_base
        self.target_col=target_col
        self.source_signal=source_signal

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        warmup = max(0, from_local_index )

        dest = dataframe[self.target_col].to_numpy()
        source_base = dataframe[self.source_base].to_numpy()
        source_signal = dataframe[self.source_signal].to_numpy()

        for idx in [ symbol_idx[i_idx] for i_idx in range(warmup,len(symbol_idx) )]:
            dest[idx] = 100.0 * (source_signal[idx] - source_base[idx]) / source_base[idx]

class SMA(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        
        #warmup = max(0, from_local_index - self.window + 1)
        
       # if symbol == "KALA":
        #logger.info(f"SMA {symbol} idx #{symbol_idx} from_local_index {from_local_index}")

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

            #logger.info(f"i_idx {range(from_local_index + self.window,len(symbol_idx))}")

        for i_idx in range(from_local_index,len(symbol_idx) ):
                    sum=0.0
                    #logger.info(f"i_idx { range(max(0,i_idx- self.window+1), i_idx+1 )}")
                    r = range(max(0,i_idx- self.window+1), i_idx+1 )
                    for j_idx in r:
                        sum+= source[symbol_idx[j_idx]]
                    sum=sum/ len(r)
                    #logger.info(f"sum {i_idx} {symbol_idx[i_idx]}= {sum}")
                    dest[symbol_idx[i_idx]] =sum

class MAX(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        for i_idx in range(from_local_index,len(symbol_idx) ):
            m=0.0
            for j_idx in range(max(0,i_idx- self.window+1), i_idx+1 ):
                m= max(m,source[symbol_idx[j_idx]])
            dest[symbol_idx[i_idx]] =m

class MAX_ALL(Indicator):
  
    def __init__(self,target_col, source_col:str):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        M = 0
        if from_local_index>0:
            M = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            M= max(M,source[symbol_idx[i_idx]])
            dest[symbol_idx[i_idx]] =M

        ########

class TREND_LIMIT(Indicator):
  
    def __init__(self,target_col, signal:int, outlier_std=2):
        super().__init__([target_col])
        self.target_col=target_col
        self.signal=signal
        self.outlier_std = outlier_std
        self.trend_map={}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.signal].to_numpy()

        count = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            if  source[symbol_idx[i_idx]] >0:
                count=count+1
            else:
                count=0
            dest[symbol_idx[i_idx]] =count

class TOUCH(Indicator):
    def __init__(self,target_col,trend):
        super().__init__([target_col])
        self.target_col=target_col
        self.self.trend=trend

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        trend = dataframe[self.trend].to_numpy()
        
        v_trend_prec = 0 if from_local_index==0 else trend[symbol_idx[i_idx-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            v_trend = trend[symbol_idx[i_idx]]
            if v_trend>0 and v_trend_prec==0:
                 dest[symbol_idx[i_idx]] =1
            else:
                 dest[symbol_idx[i_idx]] =0
            v_trend_prec= v_trend
            

########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        self.metaInfo = {}

        self.buyMap = {}
        pass

    def extra_dataframes(self)->List[str]:
        return ['1d']

    def buy(self,symbol,price, quantity,time,label=""):
        if not symbol in self.buyMap :
             self.buyMap[symbol] = {}

        if not self.buyMap[symbol]:
            super().buy(symbol,label)
            self.buyMap[symbol] = {"price": price, "quantity": quantity,"time": time}

    def buyGain(self,symbol,close):
        if symbol in self.buyMap and self.buyMap[symbol]:   
            buy_price = self.buyMap[symbol]["price"]
            return 100.0 * (close- buy_price) / buy_price
        else:
            return 0

    def sell(self,symbol,price, quantity,time,label=""):

        if symbol in self.buyMap and self.buyMap[symbol]:
            buy_data =  self.buyMap[symbol]
            #logger.info(f"SELL .. {buy_data}")
            logger.info(f"SELL {symbol} time{time} gain {self.buyGain(symbol, price)}" )
            self.buyMap[symbol] = {}
            self.add_marker(symbol, "SPOT", label, "#FF0000", "square")

            

            
    def populate_indicators(self) :
     
        sma_20= self.addIndicator(self.timeframe,SMA("SMA_20","close",20))
        sma_200= self.addIndicator(self.timeframe,SMA("SMA_200","close",200))

        diff = self.addIndicator(self.timeframe, DIFF_PERC("DIFF","SMA_200","SMA_20" ))
        gain= self.addIndicator(self.timeframe,GAIN("GAIN","close",1))

        max= self.addIndicator(self.timeframe,MAX("MAX","close",60))

        trend = self.addIndicator(self.timeframe, TREND_LIMIT("TREND","DIFF" ))


        max_perc= self.addIndicator(self.timeframe,MAX_ALL("DIFF_ALL","DIFF"))

        day_perc= self.addIndicator(self.timeframe,GAIN("DGAIN","day_volume",1))
        #day= self.addIndicator(self.timeframe,COPY("D","day_volume"))


        '''
        gain= self.addIndicator(self.timeframe,GAIN("GAIN","close",1))

        
        sma_200= self.addIndicator(self.timeframe,SMA_INT("SMA_200","close",200))
      
      
        sma_200_gain= self.addIndicator(self.timeframe,GAIN("SMA_200_G","SMA_200",1))

        sma_20= self.addIndicator(self.timeframe,SMA_INT("SMA_20","close",20))
        sma_20_gain= self.addIndicator(self.timeframe,GAIN("SMA_20_G","SMA_20",1))

        sma_9= self.addIndicator(self.timeframe,SMA_INT("SMA_9","close",9))
        sma_9_gain= self.addIndicator(self.timeframe,GAIN("SMA_9_G","SMA_9",1))

        max= self.addIndicator(self.timeframe,MAX_LIMIT("MAX",60))

        diff = self.addIndicator(self.timeframe, DIFF_PERC("DIFF","SMA_200","SMA_20" ))
        trend = self.addIndicator(self.timeframe, TREND_LIMIT("TREND","DIFF" ))
        '''

        #self.add_legend(sma_9_gain,"SMA_9_G", "sma9 G", "#034cd3")
        #self.add_legend(sma_20_gain,"SMA_20_G", "sma20 G", "#034cd3")
        
        
        self.add_plot(sma_20, "SMA_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_200, "SMA_200","#034cd3", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)

        #self.add_plot(day, "day","#d30303", "sub1", style="Solid", lineWidth=1)
        self.add_plot(day_perc, "day_perc","#0318d3", "sub1", style="Solid", lineWidth=1)
        



        '''
        self.add_plot(sma_200, "SMA_200","#034cd3", "main", source="SMA_200",style="SparseDotted", lineWidth=2)
        
        
        
        #self.add_plot(sma_9, "SMA_9","#d30303", "main", source="SMA_9",style="SparseDotted", lineWidth=2)

       
        #self.add_plot(sma_200_gain, "SMAG_200","#034cd3", "sub1", source="SMA_200_G",style="SparseDotted", lineWidth=2)
        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)

        #self.add_plot(diff, "DIFF","#d30303", "sub1", source="DIFF",style="Solid", lineWidth=1)
        self.add_plot(trend, "TREND","#d30303", "sub1", source="TREND",style="Solid", lineWidth=1)
        '''
     
    


    ######################################
    async def send_property(self,symbol:str, timeframe ,  value ):
        if not self.backtestMode and not self.bootstrapMode:
            #logger.info("send")
            await self.client.send_strategy_prop("TRADE", symbol,timeframe,value)
        else:
            #logger.info(f"send1 {self.backtestMode} {self.bootstrapMode}")
            pass
            #self.add_marker(symbol,"SPOT",name,"#060806","square",position ="atPriceTop")

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        #if not self.backtestMode and not self.bootstrapMode:
        #     logger.info(f">> {symbol} {local_index} \n{dataframe.columns}" )  
        #if symbol != "ASNS":
        #    return
        if local_index<5:
            return
            
        #if symbol == "ACXP":
        #    logger.info(f">> {symbol} {local_index} \n{dataframe.tail(2)}" )  
        #if not self.backtestMode and not self.bootstrapMode:
        #    logger.info(f">> {symbol} {local_index} \n{dataframe.tail(2)}" )  

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

   
        #low =  last["low"]
        #high =  last["high"]
        day_volume = last["day_volume"] # va solo per LIVE
        day_volume_gain=0
        if prev["day_volume"]!=0:
            day_volume_gain = 100.0 * (day_volume -  prev["day_volume"] ) /  prev["day_volume"]

        close =  last["close"]
        prev_close =  prev["close"]

      

        SMA_200 =  last["SMA_200"]
        SMA_20 =  last["SMA_20"]

        MAX =  prev["MAX"] 
        diff_all =  prev["DIFF_ALL"] 
        diff_perc =  last["DIFF"] 
        trend =  last["TREND"]
        trend_prev =  prev["TREND"]

        close_sma_gain = 100.0 * ((close - SMA_20 ) /  SMA_20)
  
        break_max = close > MAX and prev_close <= MAX

        if abs(self.buyGain(symbol,close))>10:
            self.sell(symbol,close,100,last["datetime"],"SELL")
        #trend_norm = 1 - np.exp(-trend / 20)
        #slope = (SMA_20 - dataframe.iloc[local_index-5]["SMA_20"]) / SMA_20
        #slope_norm = np.tanh(slope * 20)
        #trend_strength = 100 * diff_perc * trend_norm #* (1 + slope_norm)

        #trend_strength = 100 * perc * trend_norm * (1 + slope_norm)
        '''
        if trend>0:
            if trend_prev == 0:
                self.spot(symbol,"t", "#0A8106","SMA_200")
            trend_power = min(trend,60) / 60
            diff_power = (1 + min(9, max(diff_perc,-1))) / 10

            #self.spot(symbol,"t", "#210681","SMA_200")

            if (close > MAX and prev_close <= MAX ):
                self.buy(symbol,f"CLOSE/{trend_power:.1f}")
            else:
                if (diff_perc< 5):
                   self.buy(symbol,f"{trend_strength:.1f}")
        '''

        if day_volume_gain>10 and day_volume > 100000:
            if (SMA_20 > SMA_200 and prev["SMA_20"]
                and close > SMA_20 and diff_perc < 5  ):
                    self.buy(symbol,close, 100,last["datetime"] ,"VOL")

        #####
        if day_volume_gain>10 and day_volume > 100000:
             await self.send_event(symbol, "VOL", f"VOL 10",f"VOL 10%",color="#10A02F", ring="news")

        #SMA CROSS
        if day_volume > 1_000_000:
            if (SMA_20 > SMA_200 and prev["SMA_20"] <= prev["SMA_200"]
                and   SMA_200 > prev["SMA_200"]):
                await self.send_event(symbol, "SMA", f"SMA CR",f"SMA over ",color="#0A6FF3", ring="news")

            if (break_max ):
                if close < SMA_200:
                    await self.send_event(symbol, "MAX", f"max cross <",f"max over ",color="#31F30A", ring="alert1")
                else:
                    await self.send_event(symbol, "MAX", f"max cross >",f"max over ",color="#F3A90A", ring="chime")

        await self.send_property(symbol,self.timeframe , 
                                 {"trend_len": trend if  not pd.isna(trend) else 0,
                                "trend_perc" :diff_perc if  not pd.isna(diff_perc) else 0,
                                 "trend_perc_all" :diff_all if  not pd.isna(diff_all) else 0} )



            
  
  