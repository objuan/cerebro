import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from renderpage import RenderPage
#from config import TIMEFRAME_UPDATE_SECONDS,TIMEFRAME_LEN_CANDLES
from utils import AsyncScheduler

# si autoaggiorna ogni tot

class DBDataframe_SymbolTimeFrame:
    def __init__(self,fetcher,symbol,timeframe):
        self.symbol=symbol
        self.fetcher=fetcher
        self.timeframe = timeframe
        self.lastTime = datetime.now()

    def tick(self):
        if (datetime.now() - self.lastTime  > timedelta(seconds= self.fetcher.TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
            #logger.info(f"Update {self.symbol} {self.timeframe}")
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
        self.symbols=fetcher.live_symbols()
        self.fetcher=fetcher
        self.timeframe = timeframe
        self.lastTime = datetime.now()
        self.last_timestamp=None
        self.df=None
       #self.update_symbols()
        #self.update()

    async def bootstrap(self):
        # load symbols
        await self.on_update_symbols()
        await self.update()

    async def tick(self):
        if (datetime.now() - self.lastTime  > timedelta(seconds= self.fetcher.TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
            #logger.info(f"Update  {self.timeframe}")
            await self.update()
            self.lastTime = datetime.now()

    def set_indicators(self,df):
        pass
        #df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )

    async def on_update_symbols(self):
        self.symbols=self.fetcher.live_symbols()

    async def update(self):
     
        #logger.info(f"---- DF UPDATE ------- {self.timeframe}")

        if not self.last_timestamp:
            self.df = await self.fetcher.history_data(self.symbols , self.timeframe , limit= 999999 )

            #logger.debug(f"GETTING HISTORY {self.symbols} {self.df }")
            #print(self.df)
            #self.df = self.df.set_index("timestamp", drop=True)

            self.last_timestamp = self.df['timestamp'].max()
            logger.info(f"FIRST {self.timeframe} last_timestamp {self.last_timestamp}")
            #self.df['datetime_local'] = (pd.to_datetime(self.df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )
            
            
        else:            
            #logger.info(f"UPDATE {self.timeframe} last_timestamp {self.last_timestamp}")
            new_df = await self.fetcher.history_data(self.symbols , self.timeframe ,since = self.last_timestamp, limit= 9999)
             
            #print( "NEW ",new_df)
            
            self.df = pd.concat([self.df, new_df], ignore_index=True)

            # 🔥 OVERWRITE: tieni l’ultimo record per stessa chiave
            
            '''
            self.df  = (
                    self.df .sort_values("timestamp")
                    .drop_duplicates(
                        subset=["exchange", "symbol", "timeframe", "timestamp"],
                        keep="last"
                    )
                )
            '''
            
            
            self.df  = self.df.drop_duplicates(
                        subset=["exchange", "symbol", "timeframe", "timestamp"],
                        keep="last"
                    )
            
            #self.df .sort_values("timestamp")

            # tieni solo gli ultimi N arrivi
            self.df = self.df.tail(self.fetcher.TIMEFRAME_LEN_CANDLES[self.timeframe] * len(self.symbols)).reset_index(drop=True)

            self.set_indicators(self.df)

            self.last_timestamp = self.df['timestamp'].max()

        self.df["date"] = pd.to_datetime(self.df["timestamp"], unit="ms", utc=True).dt.date
            #print( "NEW ",self.df.tail())
        #logger.info( f"DB {self.df}" )

    def dataframe(self,symbol="") -> pd.DataFrame:
        if not self.last_timestamp:
            return None
        if symbol=="":
            return self.df
        else:
            cp =  self.df.copy()
            return cp[cp["symbol"]== symbol]
    
################################################################

class DBDataframe:
    def __init__(self,config, fetcher):
        #self.symbols=fetcher.live_symbols()
        self.fetcher=fetcher
        self.config=config["database"]
        self.map = {}
        #self.scheduler = Scheduler()

        #self.scheduler.schedule_every( self.config["scanner"]["update_time"], self.update_scanner)
    
    async def update_scanner(self):
        if self.config["scanner"]["enabled"]:
            #logger.info(f"update_scanner {self}! {time.ctime()}")

            await self.fetcher.scanner()
            

    async def bootstrap(self):
        logger.info(f"DB BOOTSTRAP")
        try:
            # WAIT FOR JOB READY
            #while not self.fetcher.ready:
            #    asyncio.sleep(0.5)
            #    yield

            logger.info(f"DB BOOTSTRAP READY")
            self.scheduler = AsyncScheduler()
            self.scheduler.schedule_every( self.config["scanner"]["update_time"], self.update_scanner)

            if self.config["scanner"]["enabled"]:
                await self.update_scanner()
            else:
                await self.fetcher.on_update_symbols()
            
            #leggo dal db l'esistente
            await self.db_dataframe("1m").bootstrap()
            await self.db_dataframe("5m").bootstrap()
            await self.db_dataframe("1d").bootstrap()
        except:
            logger.error("BOOT ERROR" , exc_info=True)

    async def tick(self):
       #print(self.db)
       await self.scheduler.tick()

       for x,v in self.map.items():
            await v.tick()

    def db_dataframe(self,timeframe)-> DBDataframe_TimeFrame:
        if not timeframe in self.map :
            self.map[timeframe] = DBDataframe_TimeFrame(self.fetcher,timeframe)
        
        return self.map[timeframe]

    def dataframe(self,timeframe,symbol="")-> pd.DataFrame:
        return self.db_dataframe(timeframe).dataframe(symbol)
        
