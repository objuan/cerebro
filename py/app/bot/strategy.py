from typing import Dict
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


#from strategy.order_strategy import *
class SmartStrategy(Strategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []
        self.marker_map= {}

    def marker(self,timeframe:str, symbol:str = None)-> pd.DataFrame:
        if timeframe in self.marker_map:
            if not symbol:
                return self.marker_map[timeframe]
            else:
                return self.marker_map[timeframe][self.marker_map[timeframe]["symbol"] == symbol]
        else:
            return  pd.DataFrame()
         
    def buy(self,  symbol, label):
        self.add_marker(symbol,"BUY",label,"#00FF00","arrowUp")

    #shapes : arrowUp, arrowDown, circle
    def add_marker(self, symbol,type, label,color,shape, position ="aboveBar", _timeframe=None):
        timeframe = self.timeframe if _timeframe==None else _timeframe
        
        #logger.info(f"self.trade_index {self.trade_index}")
        candle =  self.trade_dataframe.loc[self.trade_index]
        
        timestamp =  candle["timestamp"]
        value = candle["close"]

        #logger.info(f"marker idx {self.trade_index} {type} {symbol} ts: {timestamp} val: {value}")

        if not timeframe in self.marker_map:
            self.marker_map[timeframe] = pd.DataFrame(
                    columns=["symbol","timeframe","type", "timestamp", "value", "desc","color","shape","position"]
                )

        self.marker_map[timeframe].loc[len(self.marker_map[timeframe])] = [
                symbol,               # symbol
                timeframe,                # type
                type,               # symbol
                timestamp,       # timestamp
                value,              # value
                label,           # desc
                color,
                shape,
                position
            ]

       # self.marker_map["symbol"].append({"type":"buy", "symbol" : symbol, "ts": int(timestamp), "value": price, "desc": label})
     
    def live_markers(self,symbol,timeframe,since):
        if not timeframe:
            timeframe = self.timeframe
        if since:
            df = self.marker(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
        else:
            df = self.marker(timeframe,symbol)
        if df.empty:
            return []
        else:
            logger.info(f"live_markers since:{since}\n{df}")
            return df.to_dict(orient="records")
       
    def live_indicators(self,symbol,timeframe,since):
     
        if not timeframe:
            timeframe = self.timeframe

        if since:
            df = self.df(timeframe,symbol)
            if not df.empty:
                df = df[df["timestamp"]>= since]
            #logger.info(f"since {since}\n{df}")
        else:
            df = self.df(timeframe,symbol)
        if df.empty:
            return{"strategy": __name__ ,"markers": self.live_markers(symbol,timeframe,since)}
        
        #logger.info(f"out \n{df}")
        o = {"strategy": __name__ ,"markers": self.live_markers(symbol,timeframe,since), "list" : []}

        for p in  self.plots:
           d = p.copy()
           del d["ind"]
           d["symbol"] = symbol
           d["timeframe"] = timeframe
           df_data = p["ind"].get_render_data(df)
           if symbol:
                df_data = df_data[["time","value"]]
           d["data"] = df_data.to_dict(orient="records")
             
           o["list"].append(d)

        return o
    
    #######

    def add_plot(self,ind : Indicator ,name :str,  color:str,isMain: bool =True):
        self.plots.append({"ind": ind ,"name" : name , "color" : color, "main" : isMain})
        pass
    
    #######


#############

