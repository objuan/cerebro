from typing import Dict
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from company_loaders import *
from collections import deque
import talib.abstract as ta

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
#from reports.report_manager import ReportManager


class Indicator:
    
    def __init__(self,target_cols):
        self.target_cols=target_cols
        pass

    def get_render_data(self, dataframe,target_col) -> pd.DataFrame:
        if not target_col in self.target_cols:
            raise "col not found : " + target_col
        return (
            dataframe[["symbol", "timestamp", target_col]]
            .dropna(subset=[target_col])
            .rename(columns={
                target_col: "value",
                "timestamp": "time"
            })
        )


    def compute(self, dataframe, group, start_pos):
        pass

    def apply(self, dataframe: pd.DataFrame, from_global_index=0):

        for symbol, group in dataframe.groupby("symbol"):

            group = group.sort_values("timestamp")

            if from_global_index == -1:
                start_pos = 0
            else:
                mask = group.index >= from_global_index
                if not mask.any():
                    continue
                start_pos = group.index.get_indexer(group[mask].index)[0]

            self.compute(dataframe, group, start_pos)

 
 
class VWAP_OPEN(Indicator):
    def __init__(self, target_col, variance_mult, price_name="close"):
        super().__init__([target_col,target_col+"_up",target_col+"_down"])
        self.target_col = target_col
        self.price_name = price_name
        self.variance_mult=variance_mult

    def compute(self, dataframe, group, start_pos):

        group = group.sort_values("timestamp")
        ts = pd.to_datetime(group["timestamp"], unit="ms")

        # sessione regular US (15:30 Italia)
        session = (ts - pd.Timedelta(hours=14, minutes=30)).dt.date
        #session = ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.date

        # prezzo tipico
        price = (group["high"] + group["low"] + group[self.price_name]) / 3

        # volume reale candela
        volume = group["base_volume"]

        # cumulativi per sessione
        cum_vol = volume.groupby(session).cumsum()

        cum_pv = (price * volume).groupby(session).cumsum()
        #
        cum_p2v  = (price * price * volume).groupby(session).cumsum()

        # VWAP
        vwap  = (cum_pv / cum_vol).replace([np.inf, -np.inf], np.nan)

        variance = (cum_p2v / cum_vol) - (vwap * vwap)
        variance = variance.clip(lower=0)
        std = np.sqrt(variance)

        upper = vwap + self.variance_mult * std
        lower = vwap - self.variance_mult * std

        #variance = (cum_pv_2v / cum_vol- vwap_full*vwap_full).replace([np.inf, -np.inf], np.nan)

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap.values
            dataframe.loc[group.index, self.target_col+"_up"] = upper.values
            dataframe.loc[group.index, self.target_col+"_down"] = lower.values

        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap.iloc[start_pos:].values
            dataframe.loc[group.index[start_pos:], self.target_col+"_up"] = \
                upper.iloc[start_pos:].values
            dataframe.loc[group.index[start_pos:], self.target_col+"_down"] = \
                lower.iloc[start_pos:].values


class VWAP_DIFF(Indicator):
  
  def __init__(self,target_col):
        self.target_col=target_col
    
  def compute(self, dataframe, group, start_pos):
        
        close = group["close"]
        vwap = group["vwap"]

        diff_perc = ((close - vwap) / vwap) * 100
        
        dataframe.loc[group.index, self.target_col] = diff_perc

        #logger.info(f"VWAP_DIFF AFTER \n{group.tail(30)}")
        
class SMA(Indicator):
   
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod

    def compute(self, dataframe, group, start_pos):
        
        warmup = max(0, start_pos - self.window + 1)

        sub = group.iloc[warmup:].copy()

        sma = sub[self.source_col].rolling(window=self.window).mean()

        # Scrivi solo le righe nuove
        dataframe.loc[sub.index[start_pos - warmup:], self.target_col] = \
            sma.iloc[start_pos - warmup:].values
        
        #logger.info(f"group\n {group}")

class EMA(Indicator):
   
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod

    def compute(self, dataframe, group, start_pos):
        
        #logger.info(f"compute {start_pos} \n{group}")
        
        alpha = 2 / (self.window + 1)
        close = group[self.source_col]

        if start_pos == 0:
            ema = close.ewm(span=self.window, adjust=False).mean()
            dataframe.loc[group.index, self.target_col] = ema.values
            return

        # Recupera EMA precedente
        prev_index = group.index[start_pos - 1]
        prev_ema = dataframe.loc[prev_index, self.target_col]

        ema_values = []

        for i in range(start_pos, len(group)):
            price = close.iloc[i]
            prev_ema = alpha * price + (1 - alpha) * prev_ema
            ema_values.append(prev_ema)

        dataframe.loc[group.index[start_pos:],self.target_col] = ema_values

class GAIN(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def compute(self, dataframe, group, start_pos):

        close = group[self.source_col]

        if start_pos == 0:
            gain = (close - close.shift(self.timeperiod)) / close.shift(self.timeperiod) * 100
            dataframe.loc[group.index, self.target_col] = gain.values
            return

        warmup = max(0, start_pos - self.timeperiod)

        sub = group.iloc[warmup:].copy()

        gain = (sub[self.source_col] - sub[self.source_col].shift(self.timeperiod)) / \
            sub[self.source_col].shift(self.timeperiod) * 100

        dataframe.loc[sub.index[start_pos - warmup:], self.target_col] = \
            gain.iloc[start_pos - warmup:].values       
        

class VWAP(Indicator):
    def __init__(self,target_col, price_name="close"):
        super().__init__([target_col])
        self.target_col=target_col
        self.price_name=price_name

    def compute(self, dataframe, group, start_pos):

        group = group.sort_values("timestamp")
        ts = pd.to_datetime(group["timestamp"], unit="ms")

        price = (group["high"] + group["low"] + group[self.price_name]) / 3
        day = ts.dt.date
        
        day_volume = group["day_volume"]  # cumulativo

        # volume reale della barra (differenza giornaliera)
        volume_bar = day_volume.groupby(day).diff()

        # prima barra del giorno → diff() = NaN → deve essere uguale a day_volume
        volume_bar = volume_bar.fillna(day_volume)

        # cumulativo prezzo * volume_bar
        cum_pv = (price * volume_bar).groupby(day).cumsum()

        vwap_full = cum_pv / day_volume
        vwap_full = vwap_full.replace([np.inf, -np.inf], np.nan)#.fillna(0)

        #logger.info(f"vwap_full {vwap_full}")

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap_full.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap_full.iloc[start_pos:].values
            
        '''
        volume = group["base_volume"]

      

        # cumulativi completi
        cum_pv = (price * volume).groupby(day).cumsum()
        cum_vol = volume.groupby(day).cumsum()

        vwap_full = cum_pv / cum_vol

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap_full.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap_full.iloc[start_pos:].values
        '''
        

'''
        
class GAIN(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        
       # logger.info(f"GAIN \n{dataframe.tail(30)}")

        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        dataframe[self.target_col] = (
            dataframe
                .groupby("symbol")[self.source_col]
                .transform(
                    lambda s: ((s - s.shift(self.timeperiod)) / s.shift(self.timeperiod)) * 100
                )
        )
       # logger.info(f"GAIN AFTER \n{dataframe.tail(30)}")
'''

class AVG(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
     
        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        
        dataframe[self.target_col] = (
                dataframe
                .groupby("symbol")[self.source_col]
                .transform(lambda s: s.rolling(self.timeperiod, min_periods=self.timeperiod).mean())
        )
      

class FLOAT(Indicator):
    def __init__(self,target_col):
        super().__init__([target_col])
        self.target_col=target_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
     
        symbols = dataframe["symbol"].unique().tolist()
        #logger.info(f"FLOAT \n{symbols}")

        for symbol in symbols:
            if not symbol in self.cache:
                 #logger.info(f"get_fundamentals {self.client.get_fundamentals_dict(symbol)}")
                 self.cache[symbol] = self.client.get_fundamentals_dict(symbol)["float"]

        dataframe[self.target_col] = dataframe["symbol"].map(self.cache)


class SORT_POS(Indicator):
    def __init__(self,target_col, source_col):
        super().__init__([target_col])
        self.target_col=target_col
        self.source_col=source_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
       # 1️⃣ ultima riga per symbol (preserva indice)
        last_rows = (
            dataframe
            .sort_index()
            .groupby("symbol")
            .tail(1)
        )
        # 2️⃣ ordina per source_col e crea rank (1 = migliore)
        last_rows = last_rows.sort_values(self.source_col, ascending=False)
        last_rows[self.target_col] = range(1, len(last_rows) + 1)

        # 3️⃣ mappa symbol -> rank
        rank_map = last_rows.set_index("symbol")[self.target_col].to_dict()

        # 4️⃣ assegna a TUTTE le righe
        dataframe[self.target_col] = dataframe["symbol"].map(rank_map)

        #logger.info(f"rank_map \n{rank_map}")
        #logger.info(f"SORT_POS \n{dataframe}")
