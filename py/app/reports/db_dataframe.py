import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from renderpage import RenderPage
from config import TIMEFRAME_UPDATE_SECONDS,TIMEFRAME_LEN_CANDLES


# si autoaggiorna ogni tot

class DBDataframe_SymbolTimeFrame:
    def __init__(self,fetcher,symbol,timeframe):
        self.symbol=symbol
        self.fetcher=fetcher
        self.timeframe = timeframe
        self.lastTime = datetime.now()

    def tick(self):
        if (datetime.now() - self.lastTime  > timedelta(seconds= TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
            logger.info(f"Update {self.symbol} {self.timeframe}")
            self.lastTime = datetime.now()

######################################

class DBDataframe_Symbol:
    def __init__(self,fetcher,symbol):
        self.symbol=symbol
        self.fetcher=fetcher
        self.map = {}
     
    def tick(self):
       for x,v in self.map.items():
            v.tick()

    def df(self, timeframe) -> DBDataframe_SymbolTimeFrame:
        if not timeframe in map :
            map[timeframe] = DBDataframe_SymbolTimeFrame(self.fetcher,self.symbol,timeframe)
        return map[timeframe].df

######################################

class DBDataframe_TimeFrame:
    def __init__(self,fetcher,timeframe):
        self.pairs=fetcher.live_symbols()
        self.fetcher=fetcher
        self.timeframe = timeframe
        self.lastTime = datetime.now()
        self.last_timestamp=None
        self.update()

    def tick(self):
        if (datetime.now() - self.lastTime  > timedelta(seconds= TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
            logger.info(f"Update  {self.timeframe}")
            self.update()
            self.lastTime = datetime.now()

    def set_indicators(self,df):
        pass
        #df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )

    def update(self):
        if not self.last_timestamp:
            self.df = self.fetcher.history_data(self.pairs , self.timeframe , limit= 999999 )
            #print(self.df)
            #self.df = self.df.set_index("timestamp", drop=True)

            self.last_timestamp = self.df['timestamp'].max()
            logger.info(f"FIRST {self.timeframe} last_timestamp {self.last_timestamp}")
            #self.df['datetime_local'] = (pd.to_datetime(self.df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )
            
            
        else:            
            #logger.info(f"UPDATE {self.timeframe} last_timestamp {self.last_timestamp}")
            new_df = self.fetcher.history_data(self.pairs , self.timeframe ,since = self.last_timestamp, limit= 9999)
             
            #print( "NEW ",new_df)
            
            self.df = pd.concat([self.df, new_df], ignore_index=True)

            # 🔥 OVERWRITE: tieni l’ultimo record per stessa chiave
            
            '''
            self.df  = (
                    self.df .sort_values("timestamp")
                    .drop_duplicates(
                        subset=["exchange", "pair", "timeframe", "timestamp"],
                        keep="last"
                    )
                )
            '''
            
            
            self.df  = self.df.drop_duplicates(
                        subset=["exchange", "pair", "timeframe", "timestamp"],
                        keep="last"
                    )
            
            #self.df .sort_values("timestamp")

            # tieni solo gli ultimi N arrivi
            self.df = self.df.tail(TIMEFRAME_LEN_CANDLES[self.timeframe] * len(self.pairs)).reset_index(drop=True)

            self.set_indicators(self.df)

            self.last_timestamp = self.df['timestamp'].max()

            #print( "NEW ",self.df.tail())
        #print( "DB ",self.df )

    def dataframe(self,pair="") -> pd.DataFrame:
        if pair=="":
            return self.df
        else:
            cp =  self.df.copy()
            return cp[cp["pair"]== pair]
    
###########

class DBDataframe:
    def __init__(self, fetcher):
        self.pairs=fetcher.live_symbols()
        self.fetcher=fetcher
        self.map = {}
     
    def tick(self):
       #print(self.db)
       for x,v in self.map.items():
            v.tick()

    def dataframe(self,timeframe,pair="")-> pd.DataFrame:
        if not timeframe in self.map :
            self.map[timeframe] = DBDataframe_TimeFrame(self.fetcher,timeframe)
        
        return self.map[timeframe].dataframe(pair)
        
