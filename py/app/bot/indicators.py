from typing import Dict
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
from reports.report_manager import ReportManager


class Indicator:
    
    def get_render_data(self,dataframe):
        return None
        
class SMA(Indicator):

    client : None

    def __init__(self,target_col, source_col:str, timeperiod:int):
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
        logger.info(f"SMA \n{dataframe}")
        if (last_idx == -1):
            dataframe[self.target_col] = ta.SMA(dataframe[ self.source_col], timeperiod=self.timeperiod)        
        else:
            if len(dataframe) >= self.timeperiod:
                sma = dataframe[self.source_col].iloc[-self.timeperiod:].mean()
                dataframe.at[last_idx, self.target_col] = sma
            else:
                dataframe.at[last_idx, self.target_col] = 0
        
class GAIN(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
        
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


class AVG(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
        #logger.info(f"GAIN \n{dataframe}")
     
        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        
        dataframe[self.target_col] = (
                dataframe
                .groupby("symbol")[self.source_col]
                .transform(lambda s: s.rolling(self.timeperiod, min_periods=self.timeperiod).mean())
        )
        
class WVAP(Indicator):
    def __init__(self,target_col, timeperiod:int):
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
        
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

class FLOAT(Indicator):
    def __init__(self,target_col):
        self.target_col=target_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
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
        self.target_col=target_col
        self.source_col=source_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, last_idx=-1):
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
