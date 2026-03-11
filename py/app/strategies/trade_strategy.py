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



class MAX_LIMIT(Indicator):
  
    def __init__(self,target_col, timeperiod:int, outlier_std=2):
        super().__init__([target_col])
        self.target_col=target_col
        self.window=timeperiod
        self.outlier_std = outlier_std

    def compute(self, symbol, dataframe: pd.DataFrame, group: pd.DataFrame, from_local_index):

        warmup = max(0, from_local_index - self.window + 1)

        #gli indici restano quelli del dataframe originale.
        sub = group.iloc[warmup:]

        m = sub["high"].rolling(window=self.window).max()

        start = from_local_index - warmup

        idx = sub.index[start:]

        logger.info(f"{symbol} idx {idx}" )

        dataframe.loc[idx, self.target_col] = m.iloc[start:].values   

########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        self.metaInfo = {}
        pass

    def extra_dataframes(self)->List[str]:
        return ['1d']

    def populate_indicators(self) :
     

        #gain= self.addIndicator(self.timeframe,GAIN("GAIN","close",1))

        '''
        sma_200= self.addIndicator(self.timeframe,SMA_INT("SMA_200","close",200))
      
      
        sma_200_gain= self.addIndicator(self.timeframe,GAIN("SMA_200_G","SMA_200",1))

        sma_20= self.addIndicator(self.timeframe,SMA_INT("SMA_20","close",20))
        sma_20_gain= self.addIndicator(self.timeframe,GAIN("SMA_20_G","SMA_20",1))

        sma_9= self.addIndicator(self.timeframe,SMA_INT("SMA_9","close",9))
        sma_9_gain= self.addIndicator(self.timeframe,GAIN("SMA_9_G","SMA_9",1))

        max= self.addIndicator(self.timeframe,MAX_LIMIT("MAX",60))
        '''
        max= self.addIndicator(self.timeframe,MAX_LIMIT("MAX",60))
        

        #self.add_legend(sma_9_gain,"SMA_9_G", "sma9 G", "#034cd3")
        #self.add_legend(sma_20_gain,"SMA_20_G", "sma20 G", "#034cd3")
        
        #self.add_plot(sma_200, "SMA_200","#034cd3", "main", source="SMA_200",style="SparseDotted", lineWidth=2)
        #self.add_plot(sma_20, "SMA_20","#03d31f", "main", source="SMA_20",style="SparseDotted", lineWidth=2)
        #self.add_plot(sma_9, "SMA_9","#d30303", "main", source="SMA_9",style="SparseDotted", lineWidth=2)

       # self.add_plot(sma_20_gain, "SMA_20_G","#034cd3", "sub1", source="SMA_20_G",style="Solid", lineWidth=2)
      
        #self.add_plot(sma_200_gain, "SMAG_200","#034cd3", "sub1", source="SMA_200_G",style="SparseDotted", lineWidth=2)
        self.add_plot(max, "MAX","#FFE600FF", "main", source="MAX",style="Solid", lineWidth=1)
    


    ######################################

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
       
        logger.info(f">> {symbol} {local_index} \n{dataframe.tail(2)}" )  
        return
    
        #if self.bootstrapMode:
        #    return
        #if symbol =="SKYE":
        #     logger.info(f">> {symbol} {local_index} \n{dataframe.tail(10)}" )

        
        #if not self.bootstrapMode:
        #    logger.info(f"DO {symbol} {global_index} \n{dataframe.tail(5)}" )
        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]
        #if symbol =="SKYE":
        #     logger.info(f">> {symbol} l:{last['datetime']} p:{prev['datetime']}" )

        #df_symbols = dataframe[dataframe["symbol"]== symbol ]
        low =  last["low"]
        high =  last["high"]
        close =  last["close"]

        SMA_200 =  last["SMA_200"]
        SMA_200_G = last["SMA_200_G"]
        SMA_20 =  last["SMA_20"]
        SMA_20_PREV =  prev["SMA_20"]
        SMA_9 =  last["SMA_9"]
        SMA_20_G = last["SMA_20_G"]
        SMA_9_G =  last["SMA_9_G"]
        GAIN =  last["GAIN"]
        
        return
        diff = abs(low - SMA_20)
        #if (abs(SMA_20_G)> 0.5  and diff < 0.1):

        if abs(SMA_20_G)>0.5:
            RED = (255, 0, 0)
            GREEN = (49, 211, 17)

            max_abs = 1
            t = ( diff/max_abs)
            t = max(0, min(1, 1-t))

            color_rgb = lerp_color(RED, GREEN, t)
            color = rgb_to_hex(color_rgb)

            self.spot(symbol, f"", color, "SMA_20")

        m = min (SMA_200,SMA_20_PREV ) 
        M = max (SMA_200,SMA_20_PREV ) 

        delta = 100 * (M - m) / m
        if  abs(delta) <5 and abs(SMA_200_G) < 0.1:
            self.spot(symbol, f"={delta:.1f}", "#2B272952", "SMA_200")

            if  GAIN > 5 and close > SMA_20:
                await self.send_event(symbol, "PLANE_UP",f"PLANE_UP {GAIN}",f"PLANE_UP {GAIN}","#FF0000" )

        #p_9 = 100 * (SMA_9 - SMA_200) / SMA_200
        #p_20 = 100 * (SMA_20 - SMA_200) / SMA_200

        #if  abs(p_20) < 2:
        #     self.spot(symbol, f"^", "#FF0000", "close")
        ############ OPEN TRADE
        #logger.info(f"{SMA_20_G} {SMA_9_G} {GAIN}")
        
        '''
        if abs(SMA_20_G)<0.5 and abs(SMA_9_G)<0.5 and abs(SMA_200_G)<0.5 and GAIN > 5 and close > SMA_9:
            # tutto piatto, ho un balzo
            await self.send_event(symbol, "PLANE_UP",f"PLANE_UP {GAIN}",f"PLANE_UP {GAIN}","#FF0000" )

            self.spot(symbol, f"^", "#FF0000", "close")
        '''

        

    async def trade_symbol_at1(self, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):

        try:
            atr = self.df("1d",symbol).iloc[-1]["atr"]
            #logger.info(f"atr {symbol}  {atr}" )

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
     
               # logger.info(f"df_symbols   {symbol} \n {df_symbols.tail(1)}" )

                #band_h =  vwap_up-vwap_down
                #close_perc = 100* (close - vwap_down) / band_h

               # logger.info(f"symbol close_perc {close_perc}")

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
