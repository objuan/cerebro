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

class VWAP1(Indicator):
    def __init__(self, target_col, price_name="close"):
        self.target_col = target_col
        self.price_name = price_name

    def compute(self, dataframe, group, start_pos):

        group = group.sort_values("timestamp")
        ts = pd.to_datetime(group["timestamp"], unit="ms")

        # sessione regular US (15:30 Italia)
        session = (ts - pd.Timedelta(hours=14, minutes=30)).dt.date

        # prezzo tipico
        price = (group["high"] + group["low"] + group[self.price_name]) / 3

        # volume reale candela
        volume = group["base_volume"]

        # cumulativi per sessione
        cum_vol = volume.groupby(session).cumsum()
        cum_pv = (price * volume).groupby(session).cumsum()

        # VWAP
        vwap_full = (cum_pv / cum_vol).replace([np.inf, -np.inf], np.nan)

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap_full.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap_full.iloc[start_pos:].values


class VWAP_DIFF(Indicator):
  
  def __init__(self,target_col):
        self.target_col=target_col
    
  def compute(self, dataframe, group, start_pos):
        
        close = group["close"]
        vwap = group["vwap"]

        diff_perc = ((close - vwap) / vwap) * 100
        
        dataframe.loc[group.index, self.target_col] = diff_perc

        #logger.info(f"VWAP_DIFF AFTER \n{group.tail(30)}")


########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        pass

    def populate_indicators(self) :

        i = self.addIndicator(self.timeframe,VWAP1("vwap"))
       #/ i1 = self.addIndicator(self.timeframe,VWAP("vwap1"))

        self.addIndicator(self.timeframe, VWAP_DIFF("diff"))
        #i=self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=self.eta))
        #i = self.addIndicator(self.timeframe,TEST("test",timeperiod=self.eta))
        #i = self.addIndicator(self.timeframe,VWAP("test"))#,"close",timeperiod=self.eta))
        #i = self.addIndicator(self.timeframe,VWAP("VWAP",timeperiod=self.eta))
        self.add_plot(i, "vwap","#ffffff", True)
        #self.add_plot(i1, "vwap1","#0000ff", True)

    async def trade_symbol_at(self, isLive:bool, symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
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

            #logger.info(f"df_symbols   {symbol} \n {df_symbols.tail(2)}" )

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
  
