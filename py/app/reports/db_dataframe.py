import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from renderpage import RenderPage
#from config import TIMEFRAME_UPDATE_SECONDS,TIMEFRAME_LEN_CANDLES
from utils import AsyncScheduler
#from mulo_client import MuloClient

# si autoaggiorna ogni tot

class DBDataframe_SymbolTimeFrame:
    def __init__(self,symbol,timeframe):
        self.symbol=symbol
        self.timeframe = timeframe
        self.lastTime = datetime.now()

    def tick(self):
        pass
        #if (datetime.now() - self.lastTime  > timedelta(seconds= self.fetcher.TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
        #    #logger.info(f"Update {self.symbol} {self.timeframe}")
        #    self.lastTime = datetime.now()

######################################

class DBDataframe_Symbol:
    def __init__(self,symbol):
        self.symbol=symbol
        self.map = {}
     
    def tick(self):
       for x,v in self.map.items():
            v.tick()

    def df(self, timeframe) -> DBDataframe_SymbolTimeFrame:
        if not timeframe in map :
            map[timeframe] = DBDataframe_SymbolTimeFrame(self.symbol,timeframe)
        return map[timeframe].df

######################################

class DBDataframe_TimeFrame:
    def __init__(self,config,client ,timeframe):
        #self.symbols=fetcher.live_symbols()
        self.timeframe = timeframe
        self.client=client
        self.lastTime = datetime.now()
        self.last_timestamp=None
        self.df=None
        self.last_index_by_symbol={}
        
        self.TIMEFRAME_UPDATE_SECONDS =config["live_service"]["TIMEFRAME_UPDATE_SECONDS"]  
        self.TIMEFRAME_LEN_CANDLES =config["live_service"]["TIMEFRAME_LEN_CANDLES"]  

        self.client.on_symbols_update += self.on_update_symbols
        self.client.on_full_candle_receive += self.mulo_on_candle_receive

        self.on_symbol_added = MyEvent()
        self.on_row_added = MyEvent()
        self.on_df_last_added = MyEvent()
       #self.update_symbols()
        #self.update()

    async def bootstrap(self):
        # load symbols
        
        self.symbols=self.client.live_symbols()
        logger.info(f"DB boot symbols {self.symbols} {self.timeframe}")

        if True:#not self.timeframe in ["1m","5m"]:
            # non LIVE
            df_h = await self.client.history_data( self.symbols , self.timeframe , limit= 999999 )
            df_h = df_h.drop(columns=["ds_updated_at", "updated_at","source","exchange"], errors="ignore")
            df_h["datetime"] = pd.to_datetime(df_h["timestamp"], unit="ms", utc=True)
            df_h["date"] = pd.to_datetime(df_h["timestamp"], unit="ms", utc=True).dt.date
            df_h = df_h.sort_values("timestamp")
            self.df = df_h
            self.df.fillna(0, inplace=True)
            for symbol in  self.symbols:
                symbol_rows = self.df.index[self.df["symbol"].eq(symbol)]
                if len(symbol_rows)>0:
                    self.last_index_by_symbol[symbol] = symbol_rows[-1]

            logger.info(f"START INDEX {self.last_index_by_symbol}")
            #logger.info(f"\n {self.df}")
            self.last_timestamp=datetime.now()

        #await self.update()

    async def tick(self):
        if (datetime.now() - self.lastTime  > timedelta(seconds= self.TIMEFRAME_UPDATE_SECONDS[self.timeframe] )):
            #logger.info(f"Update  {self.timeframe}")
            #await self.update()
            self.lastTime = datetime.now()

    def set_indicators(self,df):
        pass
        #df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )

    def get_last_rows(self) -> pd.DataFrame:
        idxs = list(self.last_index_by_symbol.values())
        return self.df.loc[idxs]

    async def _on_candle_receive(self, ticker):
        symbol = ticker["s"]
        ts = int(ticker["ts"])

        row_data = {
                "symbol": ticker["s"],
                "timestamp": ts,
                "open": ticker["o"],
                "high": ticker["h"],
                "low": ticker["l"],
                "close": ticker["c"],
                "base_volume":  ticker.get("v", 0) or 0,
                "quote_volume": (ticker.get("c", 0) or 0) * (ticker.get("v", 0) or 0),
                "day_volume":  ticker.get("day_v", 0) or 0,
                "datetime": pd.to_datetime(ts, unit="ms", utc=True)
            }
        
        if ticker['tf'] == "1m" and symbol=="MRNO":
            logger.info(f"receive {ticker['tf']} {self.last_index_by_symbol} < {row_data}")

        if symbol not in self.last_index_by_symbol:
            # 
            logger.info(f"SYMBOL BOOT {symbol}")

            df_h = await self.client.history_data([symbol] , self.timeframe , limit= 999999 )
            df_h = df_h.drop(columns=["ds_updated_at", "updated_at","source","exchange"], errors="ignore")
            df_h.fillna(0, inplace=True)
            df_h["datetime"] = pd.to_datetime(df_h["timestamp"], unit="ms", utc=True)
            df_h["date"] = pd.to_datetime(df_h["timestamp"], unit="ms", utc=True).dt.date
            df_h = df_h.sort_values("timestamp")
            

            #adfd
            if not self.last_timestamp:
                self.df = df_h
                logger.info(f"boot first {symbol}")
                self.last_timestamp=datetime.now()
            else:
                logger.info(f"boot new {symbol}")
                #start_len = len(self.df)
                self.df = pd.concat([self.df, df_h], ignore_index=True)

            symbol_rows = self.df.index[self.df["symbol"].eq(symbol)]
            self.last_index_by_symbol[symbol] = symbol_rows[-1]

            await self.on_symbol_added(symbol)
            #df.loc[len(df)] = row_data
            #self.last_index_by_symbol[symbol] = self.df.index[-1]

            #logger.info(f"SYMBOL BOOT \n{self.df }")

            return
        
        last_idx = self.last_index_by_symbol[symbol]
        last_ts = int(self.df.at[last_idx, "timestamp"])

        # ---- CASO NORMALE ----
        if ts > last_ts:
            logger.info(f"========== APPEND {self.timeframe} ==========")
            new_row = self.df.loc[last_idx].copy()
            new_row.update(row_data)

            new_idx = self.df.index.max() + 1
            self.df.loc[new_idx] = new_row
            self.last_index_by_symbol[symbol] = new_idx

            await self.on_row_added(row_data)
            await self.on_df_last_added(self.timeframe,self.get_last_rows())
            return

        # ---- UPDATE CANDELA CORRENTE ----
        if ts == last_ts:
            #logger.info("update")
            for k in ["open","high", "low", "close", "base_volume", "quote_volume","day_volume","datetime"]:
                self.df.at[last_idx, k] = row_data[k]
            return

        # ---- CASO IMPORTANTE: OUT OF ORDER ----
        if ts < last_ts:
            mask = self.df["symbol"].eq(symbol)

            #logger.info("rollback")
            # 1) tieni solo le righe di quel symbol <= ts
            keep_mask = ~mask | (self.df["timestamp"] <= ts)
            self.df.drop(self.df.index[~keep_mask], inplace=True)

            # 2) trova la nuova ultima riga del symbol
            symbol_rows = self.df.index[self.df["symbol"].eq(symbol)]
            new_last_idx = symbol_rows[-1]
            self.last_index_by_symbol[symbol] = new_last_idx

            # 3) ora fai update/append normalmente
            if self.df.at[new_last_idx, "timestamp"] == ts:
                for k in ["open","high", "low", "close", "base_volume","quote_volume", "day_volume","datetime"]:
                    self.df.at[new_last_idx, k] = row_data[k]
            else:
                new_row = self.df.loc[new_last_idx].copy()
                new_row.update(row_data)
                new_idx = self.df.index.max() + 1
                self.df.loc[new_idx] = new_row
                self.last_index_by_symbol[symbol] = new_idx
                await self.on_row_added(row_data)
                await self.on_df_last_added(self.timeframe,self.get_last_rows())

    async def mulo_on_candle_receive(self, ticker):
        try:
            #logger.info(f"DB on_candle_receive {ticker} {self.timeframe}")
            if ticker["tf"] == self.timeframe:
               
                #if self.timeframe =="1m":#and ticker["s"] == 'XTKG':
                if True:
                    await self._on_candle_receive(ticker)

                    #logger.info(f"last XTKG\n{self.df[self.df['symbol'] == 'XTKG'].tail()}")
                    '''
                    logger.info(
                        "last 5 per symbol\n%s",
                        self.df.groupby("symbol", group_keys=False).tail(5)
                    )
                    '''
                            
        except:
            logger.error("ERROR", exc_info=True)

    async def on_update_symbols(self, symbols):
        logger.info(f"DB reset symbols {symbols} {self.timeframe}")
        self.symbols=symbols
        #await self.update()

    async def update_bo(self):
     
        #logger.info(f"---- DF UPDATE ------- {self.timeframe}")

        if not self.last_timestamp:
            self.df = await self.client.history_data(self.symbols , self.timeframe , limit= 999999 )
            self.df = self.df.drop(columns=["ds_updated_at", "updated_at","quote_volume"], errors="ignore")

            self.df["datetime"] = pd.to_datetime(self.df["timestamp"], unit="ms", utc=True)
            self.df["date"] = pd.to_datetime(self.df["timestamp"], unit="ms", utc=True).dt.date

            self.last_index_by_symbol = (
                self.df.reset_index()
                .groupby("symbol")["index"]
                .max()
                .to_dict()
            )
                        
            #logger.debug(f"GETTING HISTORY {self.symbols} {self.df }")
            #print(self.df)
            #self.df = self.df.set_index("timestamp", drop=True)

            self.last_timestamp = self.df['timestamp'].max()
            #logger.info(f"FIRST {self.timeframe} last_timestamp {self.last_timestamp}")
            #self.df['datetime_local'] = (pd.to_datetime(self.df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )
            
            
        else:            
            #logger.info(f"UPDATE {self.timeframe} last_timestamp {self.last_timestamp}")
            new_df = await self.client.history_data(self.symbols , self.timeframe ,since = self.last_timestamp- timeframe_to_milliseconds(self.timeframe)*2, limit= 9999)
             
            #logger.info( f"NEW \n{new_df.head()}")
            
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
            self.df = self.df.tail(self.TIMEFRAME_LEN_CANDLES[self.timeframe] * len(self.symbols)).reset_index(drop=True)

            self.set_indicators(self.df)

            self.last_timestamp = self.df['timestamp'].max()

        #self.df["date"] = pd.to_datetime(self.df["timestamp"], unit="ms", utc=True).dt.date
            #print( "NEW ",self.df.tail())
        #logger.info( f"DB \n{self.df}" )

    def dataframe(self,symbol="") -> pd.DataFrame:
        #logger.info(f"{self.tim} {self.last_timestamp} {self.df}")

        if not self.last_timestamp:
            return None
        if symbol=="":
            return self.df
        else:
            cp =  self.df.copy()
            return cp[cp["symbol"]== symbol]
            
    def dump(self,symbol=""):
        return f"{self.dataframe(symbol)}"
    
################################################################

class DBDataframe:
    def __init__(self,config,client):
        #self.symbols=fetcher.live_symbols()
        self.client=client
        self.config=config
        self.map = {}
        #self.scheduler = Scheduler()

        #self.scheduler.schedule_every( self.config["scanner"]["update_time"], self.update_scanner)
    
    
    async def task_update_scanner(self):
        if self.config["live_service"]["enabled"]:
            logger.info(f"update_scanner {self}! {time.ctime()}")

            #await self.fetcher.scanner()
           
    async def bootstrap(self):
        logger.info(f"DB BOOTSTRAP")
        try:
            # WAIT FOR JOB READY
            #while not self.fetcher.ready:
            #    asyncio.sleep(0.5)
            #    yield

            logger.info(f"DB BOOTSTRAP READY")

            
            self.scheduler = AsyncScheduler()
            #self.scheduler.schedule_every( self.config["scanner"]["update_time"], self.task_update_scanner)

            '''
            if self.config["scanner"]["enabled"]:
                await self.update_scanner()
            else:
                await self.fetcher.on_update_symbols()
            '''
            
            #leggo dal db l'esistente
            await self.db_dataframe("10s").bootstrap()
            await self.db_dataframe("1m").bootstrap()
            await self.db_dataframe("5m").bootstrap()
            await self.db_dataframe("1d").bootstrap()
        except:
            logger.error("BOOT ERROR" , exc_info=True)

    async def tick(self):
       
        await self.scheduler.tick()

        for x,v in self.map.items():
            await v.tick()

        #print(self.db_dataframe("1m").dump("VTYX"))

    def db_dataframe(self,timeframe)-> DBDataframe_TimeFrame:
        if not timeframe in self.map :
            self.map[timeframe] = DBDataframe_TimeFrame(self.config,self.client,timeframe)
        
        return self.map[timeframe]

    def dataframe(self,timeframe,symbol="")-> pd.DataFrame:
        return self.db_dataframe(timeframe).dataframe(symbol)
        
