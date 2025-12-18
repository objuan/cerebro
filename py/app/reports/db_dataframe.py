import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from renderpage import RenderPage

TIMEFRAME_UPDATE_SECONDS = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "30s": 30,
    "1m": 10,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 60*60,
    "2h": 7200,
    "4h": 14400,
    "1d": 60*60*12,
}
TIMEFRAME_LEN_CANDLES = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "30s": 30,
    "1m": 1000,
    "3m": 180,
    "5m": 1000,
    "15m": 900,
    "30m": 1800,
    "1h": 24*7,
    "2h": 7200,
    "4h": 14400,
    "1d": 60,
}


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

    def update(self):
        if not self.last_timestamp:
            self.df = self.fetcher.history_data(self.pairs , self.timeframe , limit= TIMEFRAME_LEN_CANDLES[self.timeframe] )
            self.last_timestamp = self.df['timestamp'].max()
            logger.info(f"FIRST {self.timeframe} last_timestamp {self.last_timestamp}")
            self.df['datetime_local'] = (pd.to_datetime(self.df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )

        else:            
            #logger.info(f"UPDATE {self.timeframe} last_timestamp {self.last_timestamp}")
            new_df = self.fetcher.history_data(self.pairs , self.timeframe ,since = self.last_timestamp, limit= TIMEFRAME_LEN_CANDLES[self.timeframe] )
            #print( "NEW ",new_df)

            self.df = pd.concat([self.df, new_df], ignore_index=True)

            # 🔥 OVERWRITE: tieni l’ultimo record per stessa chiave
            self.df  = (
                    self.df .sort_values("timestamp")
                    .drop_duplicates(
                        subset=["exchange", "pair", "timeframe", "timestamp"],
                        keep="last"
                    )
                )

            # tieni solo gli ultimi N arrivi
            self.df = self.df.tail(TIMEFRAME_LEN_CANDLES[self.timeframe]).reset_index(drop=True)
            self.last_timestamp = self.df['timestamp'].max()
        #print( "DB ",self.df )

    def dataframe(self,pair="") -> pd.DataFrame:
        return self.df
    
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
