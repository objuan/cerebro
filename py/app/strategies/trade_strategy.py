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
   
 
        atr = self.addIndicator("1d",ATR_SMA("atr",14))

        sma_20= self.addIndicator(self.timeframe,SMA_INT("SMA_20","close",20))

        sma_20_gain= self.addIndicator(self.timeframe,GAIN("SMA_20_G","SMA_20",1))
        #sma_200= self.addIndicator(self.timeframe,SMA("SMA_200","close",200))

        #i = self.addIndicator(self.timeframe,VWAP_OPEN("vwap",1))
        #i1 = self.addIndicator(self.timeframe,VWAP_PERC("vwap_perc"))

        #self.addIndicator(self.timeframe, VWAP_DIFF("diff"))
       
        '''
        self.add_plot(i, "vwap","#15ff00", "main", source="vwap",style="SparseDotted", lineWidth=2)
        self.add_plot(i, "vwap_up","#15ff00", "main", source="vwap_up",style="SparseDotted", lineWidth=2)
        self.add_plot(i, "vwap_down","#15ff00", "main", source="vwap_down",style="SparseDotted", lineWidth=2)

        self.add_plot(i1, "vwap_perc","#034cd3", "sub1", source="vwap_perc",style="Solid", lineWidth=2)

        self.add_legend(i1, "vwap_perc_var","var","#ffffff" )
        
        '''

        self.add_plot(sma_20, "SMA_20","#034cd3", "main", source="SMA_20",style="SparseDotted", lineWidth=2)

        self.add_plot(sma_20_gain, "SMA_20_G","#034cd3", "sub1", source="SMA_20_G",style="Solid", lineWidth=2)


    ######################################

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        if self.bootstrapMode:
            return
            
        if not symbol in self.metaInfo:
            
            last_close, ts_last_close=  await self.client.last_close(symbol)
            self.metaInfo[symbol] = {"last_close": last_close,"ts_last_close" : ts_last_close}

            #logger.info(f"DO {symbol} {  self.metaInfo[symbol] }")

        #logger.info(f"DO {symbol} {global_index} \n{dataframe.tail(5)}" )

        if not "last_open" in self.metaInfo[symbol]:
            if self.client.market.isLiveZone():
                last_open, ts_last_open=  await self.client.last_open(symbol)
                self.metaInfo[symbol]["last_open"]=  last_open
                self.metaInfo[symbol]["ts_last_open"] = ts_last_open

                mask = (
                        (dataframe["timestamp"] >= self.metaInfo[symbol]["ts_last_close"]) &
                        (dataframe["timestamp"] <= self.metaInfo[symbol]["ts_last_open"])
                    )
                self.metaInfo[symbol]["low"] = dataframe.loc[mask, "low"].min()
                self.metaInfo[symbol]["high"] = dataframe.loc[mask, "high"].max()

                self.metaInfo[symbol]["pre_gain"]= 100 * (last_open -  self.metaInfo[symbol]["last_close"]) /  self.metaInfo[symbol]["last_close"]
                self.metaInfo[symbol]["pre_gain_LH"]= float(100 * ( self.metaInfo[symbol]["high"] -  self.metaInfo[symbol]["low"]) /  self.metaInfo[symbol]["low"])
                logger.info(f"OPEN {symbol} {  self.metaInfo[symbol] }")
               
            else:
                mask = dataframe["timestamp"] >= self.metaInfo[symbol]["ts_last_close"]
                self.metaInfo[symbol]["low"] = dataframe.loc[mask, "low"].min()
                self.metaInfo[symbol]["high"] = dataframe.loc[mask, "high"].max()

                logger.info(f"PRE {symbol} {  self.metaInfo[symbol] }")

        #if not self.bootstrapMode:
        #    logger.info(f"DO {symbol} {global_index} \n{dataframe.tail(5)}" )

        #df_symbols = dataframe[dataframe["symbol"]== symbol ]
        low =  dataframe.loc[global_index]["low"]
        SMA_20 =  dataframe.loc[global_index]["SMA_20"]
        SMA_20_G =  dataframe.loc[global_index]["SMA_20_G"]
        if symbol =="BTAI":
             logger.info(f">> {symbol} {global_index} {low} {SMA_20_G} {SMA_20}" )

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

            self.spot(symbol, f"0.5,{diff:.1f}", color, "SMA_20")

        ############ OPEN TRADE

        

        

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
