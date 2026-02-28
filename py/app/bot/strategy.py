from typing import Dict
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import Indicator
from company_loaders import *
from collections import deque
from utils import SECONDS_TO_TIMEFRAME
logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


class Strategy:
    params : Dict
    timeframe: str
    
    def __init__(self,manager):
        self.manager=manager
        self.render_page=manager.render_page
        self.client = manager.client
        self.indicators={}
        self.db_df_map={}
        self.df_map={}
        self.trade_index=None
        self.trade_dataframe = None
        
    def load(self,strat_def):
        #strat.handler = find_method_local(EventManager,code)
        self.params= strat_def["params"]
        self.timeframe =  SECONDS_TO_TIMEFRAME[strat_def["timeframe"]]

    def get_fundamentals(self,symbol)->pd.DataFrame:
        return self.client.get_fundamentals(symbol)
   
    def addIndicator(self,tf:str, ind:Indicator):
        if not  tf in self.indicators:
            self.indicators[tf] = []
        self.indicators[tf].append(ind)
        ind.client = self.client
        return ind

    def _fill_indicators(self,timeframe, from_global_index:int):
        for tf, inds in self.indicators.items():
            if tf == timeframe:
                for ind in inds:
                    try:
                        #logger.info(f"_fill_indicators {from_global_index}")
                        ind.apply( self.df(tf),from_global_index)
                        '''
                        if allMode:
                            ind.apply(self.df(tf))    
                        else:

                            ind.apply(df)
                        '''
                    except:
                        logger.error("error",exc_info=True)

    def live_indicators(self,symbol,timeframe,since):
        return None

    async def on_start(self):
        pass

    def dispose(self):
        logger.info(f"Dispose {self}")

        for tf, db_df in self.db_df_map.items():
            db_df.on_df_last_added-= self._on_df_last_added

        pass

    async def bootstrap(self):

        logger.info(f"bootstrap {self.__class__} tf:{self.timeframe }")

        await self.on_start()

        self._populate_dataframes()

        self.df_map= {}
        for tf, db_df in self.db_df_map.items():
            #copia
            self.df_map[tf] = db_df.dataframe().copy()
            #
        self.populate_indicators( )

        for tf, db_df in self.db_df_map.items():
            self._fill_indicators(tf,0)
            db_df.on_df_last_added+= self._on_df_last_added

        for tf,df in self.df_map.items():
            #df_ = df.loc[df["symbol"] == "HCTI"]
            logger.debug(f"END {tf}\n{df.tail(10)}")

        # trade
        for symbol, group in self.df_map[self.timeframe].groupby("symbol"):
            #logger.info(f"{symbol} {group.index.tolist()}")
            self.trade_dataframe = group

            for idx in group.index:
                try:
                    self.trade_index= idx
                    await self.trade_symbol_at(False,symbol, group,idx,{})
                except:
                    logger.error(f"trade_symbol_at  {symbol} index {idx}" , exc_info=True)
                   

    ########

    async def on_symbols_update(self, df_tf : DBDataframe_TimeFrame, to_add,to_remove):
        #logger.info(f"=== {self.__class__} >> on_symbols_update {df_tf.timeframe} add {to_add} del {to_remove}")
        
        for s in to_remove:
            for tf, i_df in self.df_map.items():
                if tf == df_tf.timeframe:
                    logger.info(f"DEL {s} FROM \n{df_tf.dataframe(s).tail(10)}")

                    i_df = i_df[i_df["symbol"] != s]

                    self.df_map[tf] = i_df
                    
                    count = len(i_df[i_df["symbol"] == s])
                    if count != 0:
                        raise Exception(f"Bad db state !!!! {s} #{count}")

                    '''
                    i_df.drop(
                        i_df[i_df["symbol"].isin(to_remove)].index,
                        inplace=True
                    )
                    '''

        for s in to_add:
            for tf, db_df in self.db_df_map.items():
                if tf == df_tf.timeframe:
                    #copia i nuovi simboli
                    #self.df_map[tf] = db_df.dataframe().copy()
                    #CHECK
                    df = self.df_map[tf] 

                    logger.info(f"ADDING {tf} ")#\n{df_tf.dataframe(s).tail(20)}" )

                    count = len(df[df["symbol"] == s])
                    if count != 0:
                        raise Exception(f"Bad db state !!!! {s} #{count}")
                    
                    add_df = df_tf.dataframe(s).copy()
                   #logger.info(f"BOOT ADD {tf} \n{add_df.tail(10)}" )
                    df = pd.concat([df, add_df], ignore_index=True)
                    self.df_map[tf] = df

    ########

    async def _on_df_last_added(self, tf, new_df):
        #logger.info(f"=== {self.__class__} >> on_df_last_added {tf} \n{new_df}")

        df_tf = self.df_map[tf]
        rows_to_add = []

        for _, row in new_df.iterrows():
            symbol = row["symbol"]
            ts = int(row["timestamp"])

            symbol_rows = df_tf[df_tf["symbol"] == symbol]
            #logger.info(f"symbol_rows {symbol} {ts}")
            if symbol_rows.empty:
                rows_to_add.append(row)
            else:
                last_ts = int(symbol_rows.iloc[-1]["timestamp"])

                #logger.info(f"last_ts {last_ts}")
                
                if ts > last_ts:
                    rows_to_add.append(row)

        #logger.info(f"rows_to_add \n{rows_to_add}")

        if rows_to_add:
            add_df = pd.DataFrame(rows_to_add).copy()

            #logger.info(f"TO ADD \n {add_df.tail(4)}")

            from_global_index = df_tf.index.max()

            #ADD NEW
            df_tf = pd.concat([df_tf, add_df], ignore_index=True)
            self.df_map[tf] = df_tf

            #self._fill_indicators(allMode=False,df=add_df)
            #TODO BETTER
            #self._fill_indicators(tf,allMode=True)
            
            last_rows = df_tf.tail(len(rows_to_add))
        
           # logger.info(f"ADD FINAL\n{last_rows}")
            #self._fill_indicators()

            self._fill_indicators(tf, from_global_index)

            # candele solo per l'evento principale
            if self.timeframe == tf:
                symbols = add_df["symbol"].unique().tolist()

                #logger.debug(f"symbols  {symbols}")
 
                await self.on_all_candle( self.df_map[self.timeframe],{})

                for symbol, group in self.df_map[self.timeframe].groupby("symbol"):
                    self.trade_dataframe = group
                    if symbol in symbols:
                        await self.on_symbol_candle(symbol, group,{})
                        self.trade_index= group.index.max()
                        await self.trade_symbol_at(True,symbol, group,group.index.max(),{})

    def _populate_dataframes(self):
        self.db_df_map[self.timeframe] = self.manager.db.db_dataframe(self.timeframe)
        for tf in self.extra_dataframes():
            self.db_df_map[tf] = self.manager.db.db_dataframe(tf)
        
    def df(self,timeframe:str, symbol:str = None)-> pd.DataFrame:
        if timeframe in self.df_map:
            if not symbol:
                return self.df_map[timeframe]
            else:
                return self.df_map[timeframe][self.df_map[timeframe]["symbol"] == symbol]
        else:
            return  pd.DataFrame()
    
    def extra_dataframes(self)->List[str]:
        return []

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        pass
    

    async def on_all_candle(self, dataframe: pd.DataFrame, metadata: dict) :
        '''
        call at every main timeframe candle, dataframe is all
        '''
        pass

    async def on_symbol_candle(self, symbol:str, dataframe: pd.DataFrame, metadata: dict):
        '''
        call at every main timeframe  symbol  candle,dataframe is filtered
        '''
        pass

    async def trade_symbol_at(self,isLive:bool,  symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        '''
        call at every main timeframe  symbol  candle,dataframe is filtered
        '''
        pass

    #################
    def on_plot_lines_changed(self, symbol, tf):
         pass
    

    #######################

    async def send_event(self,symbol:str, name:str, small_desc:str,  full_desc:str,color):
       
        await self.client.send_event("strategy",symbol,name,small_desc,full_desc,{"color":color})


    def __str__(self):
        return f"{self.__class__} params:{self.params}"




    #######
#############

