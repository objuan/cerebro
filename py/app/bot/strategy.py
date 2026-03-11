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
from concurrent.futures import ThreadPoolExecutor

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


class Strategy:
    params : Dict
    timeframe: str
    db : DBDataframe

    def Boot():
        Strategy.executor = ThreadPoolExecutor(max_workers=8)
    
    def submit_df_event(strategy, tf, new_df):
        loop = asyncio.get_running_loop()

        loop.run_in_executor(
            Strategy.executor,
            strategy._run_async_task,
            tf,
            new_df
        )
    
    #########
    #     
    def __init__(self,manager):
        self.manager=manager
        self.render_page=manager.render_page
        self.client = manager.client
        self.indicators={}
        self.db_df_map={}
        self.db = None
        self.df_map={}
        self.trade_index_global=None
        self.trade_dataframe = None
        self.scope = ""
        self.backtestMode=False
        self.bootstrapMode=False
        self.sem = asyncio.Semaphore(20)
    
    def load(self,strat_def):
        #strat.handler = find_method_local(EventManager,code)
        self.params= strat_def["params"]
        self.scope =  strat_def["scope"] if "scope" in strat_def else ""
        self.timeframe =  SECONDS_TO_TIMEFRAME[strat_def["timeframe"]]

    def get_fundamentals(self,symbol)->pd.DataFrame:
        return self.client.get_fundamentals(symbol)
   
    def addIndicator(self,tf:str, ind:Indicator):
        if not  tf in self.indicators:
            self.indicators[tf] = []
        self.indicators[tf].append(ind)
        ind.client = self.client
        return ind

    def _fill_symbol_indicators(self,symbol, timeframe, from_local_index:int):
        #logger.info(f"_fill_indicators {symbol} {timeframe} {from_local_index} ")

        for tf, inds in self.indicators.items():  
            if tf == timeframe:
                #logger.info(f"_fill_indicators {from_local_index}")
                g_df = self.df(tf)
                _df = self.df(timeframe,symbol)
                   
                for ind in inds:
                    try:
                       # logger.info(f"_fill_indicators {from_local_index}")
                        ind.apply(symbol, g_df, _df,from_local_index)
                        '''
                        if allMode:
                            ind.apply(self.df(tf))    
                        else:

                            ind.apply(df)
                        '''
                    except:
                        logger.error("error",exc_info=True)

    def _fill_indicators(self,timeframe, from_global_index:int):
        for tf, inds in self.indicators.items():
            if tf == timeframe:
                for ind in inds:
                    try:
                        #logger.info(f"_fill_indicators {from_global_index}")
                        ind.applyAll(self.df(tf),from_global_index)
                        '''
                        if allMode:
                            ind.apply(self.df(tf))    
                        else:

                            ind.apply(df)
                        '''
                    except:
                        logger.error("error",exc_info=True)

    def live_indicators(self,symbol,timeframe,from_ts,to_ts):
        return None

    async def on_start(self):
        pass

    def dispose(self):
        logger.info(f"Dispose {self}")

        for tf, db_df in self.db_df_map.items():
            db_df.on_df_last_added-= self.on_df_last_added

        pass

    async def bootstrap(self, backtestMode):
        
        self.backtestMode=backtestMode
        self.bootstrapMode=True
        logger.info(f"bootstrap {self.__class__} tf:{self.timeframe } backtestMode:{backtestMode}")

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
            db_df.on_df_last_added+= self.on_df_last_added

        for tf,df in self.df_map.items():
            #df_ = df.loc[df["symbol"] == "HCTI"]
            logger.debug(f"END {tf}\n{df.tail(10)}")

        # trade
        for symbol, group in self.df_map[self.timeframe].groupby("symbol"):
            #logger.info(f"{symbol} {group.index.tolist()}")
            self.trade_dataframe = group

            idx=0
            for global_idx in group.index:
                try:
                    self.trade_index_global= global_idx
                    await self.trade_symbol_at(symbol, group,idx,{})
                    idx=idx+1
                except:
                    logger.error(f"trade_symbol_at  {symbol} index {global_idx}" , exc_info=True)

        self.bootstrapMode=False
        logger.info(f"bootstrap {self.__class__} tf:{self.timeframe } DONE")   

    ########

    async def on_symbols_update(self, df_tf : DBDataframe_TimeFrame, to_add,to_remove):
        #logger.info(f"=== {self.__class__} >> on_symbols_update {df_tf.timeframe} add {to_add} del {to_remove}")
        async with self.sem:
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
    # DEVE ESSERE MULTITHREAD
    async def _on_df_last_added(self, tf, new_df):
        Strategy.submit_df_event(self,tf,new_df)

    async def _bounded_call(self, tf, new_df):
        async with self.sem:
            await self._on_df_last_added(tf, new_df)
            
    def _run_async_task(self, tf, new_df):
        asyncio.run(self._bounded_call(tf, new_df))

 
    async def on_df_last_added(self, tf, new_symbol, new_row):


        logger.info(f"=== {self.__class__} >> on_df_last_added {tf} {new_symbol}")
 
        async with self.sem:
            df_tf = self.df_map[tf]

            ##aggiungo in fondo
            new_global_idx = df_tf.index.max() + 1
            df_tf.loc[new_global_idx] = new_row
           
            #rows_to_add = []

            '''
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
            '''
            #logger.info(f"rows_to_add \n{rows_to_add}")

            #if rows_to_add:
            
                #add_df = pd.DataFrame(rows_to_add).copy()

                #logger.info(f"TO ADD \n {add_df.tail(4)}")

                #from_global_index = df_tf.index.max()

                #ADD NEW
                #df_tf = pd.concat([df_tf, add_df], ignore_index=True)
                #self.df_map[tf] = df_tf

                #self._fill_indicators(allMode=False,df=add_df)
                #TODO BETTER
                #self._fill_indicators(tf,allMode=True)
                
                #last_rows = df_tf.tail(len(rows_to_add))
            
            # logger.info(f"ADD FINAL\n{last_rows}")
                #self._fill_indicators()

            self._fill_symbol_indicators( new_symbol, tf,-1)

                # candele solo per l'evento principale
            if self.timeframe == tf:
                    symbols = [new_symbol]

                    #logger.debug(f"symbols  {symbols}")
    
                    await self.on_all_candle( self.df_map[self.timeframe],{})

                    for symbol, group in self.df_map[self.timeframe].groupby("symbol"):
                        self.trade_dataframe = group
                        if symbol in symbols:
                            await self.on_symbol_candle(symbol, group,{})
                            self.trade_index_global= group.index.max()
                            await self.trade_symbol_at(symbol, group,len(group)-1,{})


    def _populate_dataframes(self):
        self.db_df_map[self.timeframe] = self.manager.db.db_dataframe(self.timeframe)
        for tf in self.extra_dataframes():
            self.db_df_map[tf] = self.manager.db.db_dataframe(tf)
        
    def has_meta(self,symbol,field, timeframe=None):
        return self.manager.db.db_dataframe(timeframe if timeframe else self.timeframe).has_meta(symbol,field)
    
    def get_meta(self,symbol,field,timeframe=None, defualtValue=None):
        return  self.manager.db.db_dataframe(timeframe if timeframe else self.timeframe).get_meta(symbol,field,defualtValue)

    def set_meta(self,symbol,meta:dict,timeframe=None):
        self.manager.db.db_dataframe(timeframe if timeframe else self.timeframe).set_meta(symbol,meta)

    def get_all_meta(self,symbol,timeframe=None):
        return self.manager.db.db_dataframe(timeframe if timeframe else self.timeframe).get_all_meta(symbol)
        
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

    async def trade_symbol_at(self,  symbol:str, dataframe: pd.DataFrame,global_index : int, metadata: dict):
        '''
        call at every main timeframe  symbol  candle,dataframe is filtered
        '''
        pass

    #################
    
    def on_plot_lines_changed(self, symbol, tf):
         pass
    
    #######################

    async def send_event(self,symbol:str, name:str, small_desc:str,  full_desc:str,color):
        if not self.backtestMode and not self.bootstrapMode:
            await self.client.send_event("strategy",symbol,name,small_desc,full_desc,{"color":color})
        else:
            self.add_marker(symbol,"SPOT",name,"#060806","square",position ="atPriceTop")

    def __str__(self):
        return f"{self.__class__} params:{self.params}"


    #######
#############


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

    def spot(self,  symbol, label,color, sourceField):
        #logger.info(f"SPOT {symbol} {label}")
        self.add_marker(symbol,"SPOT",label,color,"circle", position ="atPriceMiddle" , sourceField=sourceField)

    def buy(self,  symbol, label):
        logger.info(f"BUY {symbol} {label}")
        self.add_marker(symbol,"BUY",label,"#060806","arrowUp")


    #shapes : arrowUp, arrowDown, circle,square
    #atPriceTop,atPriceBottom,atPriceMiddle
    def add_marker(self, symbol,type, label,color,shape, position ="atPriceTop",
                    _timeframe=None, sourceField = "close"):
        timeframe = self.timeframe if _timeframe==None else _timeframe
        
        #logger.info(f"self.trade_index {self.trade_index}")
        candle =  self.trade_dataframe.loc[self.trade_index_global]
        
        timestamp =  candle["timestamp"]
        value = candle[sourceField]

       # logger.info(f"marker idx {self.trade_index} {type} {symbol} ts: {timestamp} val: {value}")

        if not timeframe in self.marker_map:
            self.marker_map[timeframe] = pd.DataFrame(
                    columns=["symbol","timeframe","type", "timestamp", "price", "desc","color","shape","position"]
                )

        self.marker_map[timeframe].loc[len(self.marker_map[timeframe])] = [
                symbol,               # symbol
                timeframe,                # type
                type,               # symbol
                timestamp,       # timestamp
                value,              # price
                label,           # desc
                color,
                shape,
                position
            ]

       # self.marker_map["symbol"].append({"type":"buy", "symbol" : symbol, "ts": int(timestamp), "value": price, "desc": label})
     
    def live_markers(self,symbol,timeframe,from_ts,to_ts):
        if not timeframe:
            timeframe = self.timeframe
        '''
        if since:
            df = self.marker(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
        else:
            df = self.marker(timeframe,symbol)
        '''
        df = self.get_df_windows( self.marker(timeframe,symbol),from_ts,to_ts)

        if df.empty:
            return []
        else:
            #logger.info(f"live_markers since:{since}\n{df}")
            return df.to_dict(orient="records")
       
    def live_legend(self,symbol,timeframe,from_ts,to_ts):
        if not timeframe:
            timeframe = self.timeframe

        df = self.get_df_windows( self.df(timeframe,symbol),from_ts,to_ts)
        '''
        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        '''

        arr = []
        for leg in self.legend:
            d = leg.copy()
            del d["ind"]
            try:
                d["value"] =   df.iloc[-1] [d["source"]]
            except:
                d["value"] =0
            arr.append(d)
         #logger.info(f"live_markers since:{since}\n{df}")
        return arr
    
    def get_df_windows(self,source_df,from_ts,to_ts):
        if from_ts or to_ts:
            df = source_df
            if not df.empty:
                if from_ts:
                    df = df[df["timestamp"]>= from_ts]
                else:
                    df = df[df["timestamp"]<= to_ts]
            #logger.info(f"since {since}\n{df}")
        else:
            df = source_df

        df = df.replace([np.inf, -np.inf], np.nan)
        df.dropna()
        return df
        
    def live_indicators(self,symbol,timeframe,from_ts,to_ts):
     
        if not timeframe:
            timeframe = self.timeframe

        '''
        if from_ts or to_ts:
            df = self.df(timeframe,symbol)
            if not df.empty:
                if from_ts:
                    df = df[df["timestamp"]>= from_ts]
                else:
                    df = df[df["timestamp"]<= to_ts]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        '''

        #df = df.replace([np.inf, -np.inf], np.nan)
        #df.dropna()
        df = self.get_df_windows(self.df(timeframe,symbol),from_ts,to_ts)

        
        if df.empty:
            return{"strategy": __name__ 
                   ,"legends" : []
                   ,"markers": self.live_markers(symbol,timeframe,from_ts,to_ts)}
        
        #logger.info(f"out \n{df}")
        o = {"strategy": __name__ ,
             "markers": self.live_markers(symbol,timeframe,from_ts,to_ts), 
             "legends": self.live_legend(symbol,timeframe,from_ts,to_ts), 
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
