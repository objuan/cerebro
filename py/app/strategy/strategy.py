from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategy.indicators import Indicator
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


class Strategy:
    name:str
    schedule_time:int
    params : Dict
    timeframe: str
    
    def __init__(self,manager):
        self.manager=manager
        self.render_page=manager.render_page
        self.indicators={}
        
    def load(self,strat_def):
        self.name= strat_def["name"]
        self.schedule_time= strat_def["schedule_time"]
        #strat.handler = find_method_local(EventManager,code)
        self.params= strat_def["params"]
        self.timeframe =  SECONDS_TO_TIMEFRAME[strat_def["timeframe"]]

    def addIndicator(self,tf:str, ind:Indicator):
        if not  tf in self.indicators:
            self.indicators[tf] = []
        self.indicators[tf].append(ind)

    def _fill_indicators(self,allMode,df=None):
        for tf, inds in self.indicators.items():
            for ind in inds:
                if allMode:
                    ind.apply(self.df[tf])    
                else:
                    ind.apply(df)
        
    async def on_start(self):
        pass

    async def bootstrap(self):

        logger.info(f"bootstrap {self.name} tf:{self.timeframe }")

        await self.on_start()

        self.df_map={}
        self._populate_dataframes()

        self.df= {}
        for tf, db_df in self.df_map.items():
            #copia
            self.df[tf] = db_df.dataframe().copy()
            #
            self.populate_indicators( self.df[tf] , {} )

        self._fill_indicators(allMode=True)

        self.df_map[self.timeframe].on_df_last_added+= self._on_df_last_added

        logger.info(f"END \n{self.df}")

    async def _on_df_last_added(self, tf, new_df):
        logger.info(f"_on_df_last_added {tf} {new_df}")

        df_tf = self.df[tf]
        rows_to_add = []

        for _, row in new_df.iterrows():
            symbol = row["symbol"]
            ts = int(row["timestamp"])

            symbol_rows = df_tf[df_tf["symbol"] == symbol]

            if symbol_rows.empty:
                rows_to_add.append(row)
            else:
                last_ts = int(symbol_rows.iloc[-1]["timestamp"])
                if ts > last_ts:
                    rows_to_add.append(row)

        if rows_to_add:
            add_df = pd.DataFrame(rows_to_add)
            logger.info(f"TO ADD {add_df}")
            df_tf = pd.concat([df_tf, add_df], ignore_index=True)
            self.df[tf] = df_tf
            #self._fill_indicators(allMode=False,df=add_df)
            #TODO BETTER
            self._fill_indicators(allMode=True)
            
            last_rows = df_tf.tail(len(rows_to_add))

            #self._fill_indicators()
            for symbol, group in df_tf.groupby("symbol"):
               await self.on_symbol_candle(symbol, group,{})

    def _populate_dataframes(self):
        self.df_map[self.timeframe] = self.manager.db.db_dataframe(self.timeframe)
        pass

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        pass
    
    async def on_symbol_candle(self, symbol:str, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        pass

    async def send_event(self,symbol:str, name:str, desc:str , data):
        await self.render_page.send(
            {
                "type" : "strategy",
                "symbol": symbol,
                "name" : name,
                "desc" : desc,
                "ts" :  int(time.time() * 1000),
                "data" : data
            }
        )

    def __str__(self):
        return f"{self.__class__} {self.name} t:{self.schedule_time} params:{self.params}"

#############

