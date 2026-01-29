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
    pass

class SMA(Indicator):
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
        #logger.info(f"GAIN \n{dataframe}")
     
        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        dataframe[self.target_col] = (
            dataframe
                .groupby("symbol")[self.source_col]
                .transform(
                    lambda s: ((s - s.shift(self.timeperiod)) / s.shift(self.timeperiod)) * 100
                )
        )
