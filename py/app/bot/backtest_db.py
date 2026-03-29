import logging

from typing import Dict
import pandas as pd

from zoneinfo import ZoneInfo
from typing import List, Dict, Any
from datetime import datetime, timedelta
from bot.indicators import Indicator
from company_loaders import *
from collections import deque
from mulo_live_client import MuloLiveClient
from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC
from props_manager import PropertyManager
import importlib

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

class BacktestIn:
    badgetUSD : int
    symbols: List[str]
    dt_from : str
    dt_to: str
    module: str
    className: str
    params: str
    timeframe: str
    pre_scan: Any

    #strategy : List[ Dict]

    def __init__(self, data: Dict[str, Any]):
        self.badgetUSD = data.get("badgetUSD", 0)
        self.symbols = data.get("symbols", [])
        self.dt_from = data.get("dt_from", 0)
        self.dt_to = data.get("dt_to", 0)
        self.module = data.get("module", "")
        self.className = data.get("class", "")
        self.params = data.get("params", {})
        self.timeframe = data.get("timeframe", "1m")
        self.pre_scan =  data.get("pre_scan",{})
        #self.strategy: List[Dict] = data.get("strategy", [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "badgetUSD": self.badgetUSD,
            "symbols": self.symbols,
            "dt_from": self.dt_from,
            "dt_to": self.dt_to,
            "module": self.module,
            "class": self.className,
            "params": self.params,
            "timeframe": self.timeframe,
            "pre_scan": self.pre_scan,
        }

###############################

class Back_DBDataframe_TimeFrame:

    def __init__(self,main_df, timeframe,inData:BacktestIn ):
        self.main_df=main_df
        self.inData=inData
        self.timeframe = timeframe
        self.map={}
        self.last_index_by_symbol={}
        self.on_row_added = MyEvent()
        self.on_df_last_added = MyEvent()
        self.time_tick = TIMEFRAME_SECONDS[timeframe] * 1000
        self.symbols = inData.symbols

        logger.info(f"INIT SYMBOLS {self.symbols}")
        #for symbol in inData.symbols:
        #    self.main_df.back_manager.client.history_data()
       
        since = 1000*int(datetime.strptime(str(inData.dt_from), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Rome")).timestamp())
     
        to = 1000*int(datetime.strptime(str(inData.dt_to), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Rome")).timestamp())

        self.all_df = self.main_df.back_manager.back_data(inData.symbols,self.timeframe,since, to)


        self.all_df["local_time"] = pd.to_datetime(self.all_df["timestamp"], unit="ms") \
                        .dt.tz_localize("UTC") \
                        .dt.tz_convert("Europe/Rome") \
                        .dt.tz_localize(None)  # opzionale: rimuove info timezone
        
        self.all_df["datetime"] = pd.to_datetime(
                self.all_df["timestamp"].astype("int64"),
                unit="ms",
                utc=True
            )
         # opzionale: rimuove info timezone

        #self.all_df["timestamp"] = pd.to_datetime(self.all_df["timestamp"], unit="ms", utc=True)
        self.all_df["i_timestamp"] = self.all_df["timestamp"]

        self.all_df = self.all_df.set_index("i_timestamp", drop=False).sort_index()
    
        #logger.info(f"BACK_DF \n{self.all_df }")

        self.min_time = self.all_df.index.min()
        self.max_time = self.all_df.index.max()

        self.symbols = self.pre_scan()
        logger.info(f"OUT SYMBOLS {self.symbols}")

        self.filtered_df =  self.all_df
        #self.goTo(self.min_time)

    def goTo(self, begin_time):
        self.current_time = begin_time

        self.filtered_df =  self.all_df [ self.all_df.index<= self.current_time]

        '''
        for symbol in  self.symbols:
            symbol_rows = self.filtered_df[self.filtered_df["symbol"].eq(symbol)]
            print("...",symbol_rows)
            if len(symbol_rows)>0:
                self.last_index_by_symbol[symbol] = symbol_rows[-1]
        '''

        logger.info(f"START FROM {self.timeframe} { begin_time}")
 
    def full_dataframe(self,symbol="") -> pd.DataFrame:
        #logger.info(f"{self.tim} {self.last_timestamp} {self.df}")
        if symbol=="":
            return self.all_df
        else:
            cp =  self.all_df.copy()
            return cp[cp["symbol"]== symbol]
        
    def dataframe(self,symbol="") -> pd.DataFrame:
        #logger.info(f"{self.tim} {self.last_timestamp} {self.df}")
        if symbol=="":
            return self.filtered_df
        else:
            cp =  self.filtered_df.copy()
            return cp[cp["symbol"]== symbol]
        
    async def tick(self,time):
        if time >= self.current_time + self.time_tick:
            previous_time = self.current_time
            current_time = self.current_time + self.time_tick

            #logger.info(f"tick {current_time} {datetime.fromtimestamp(current_time/1000)}")

            new_rows = self.all_df.loc[(self.all_df.index > previous_time) & (self.all_df.index <= current_time)]
            if not new_rows.empty:
                self.filtered_df = pd.concat([self.filtered_df, new_rows])
                for symbol, group in new_rows.groupby("symbol"):

                    #logger.info(f".. {symbol} \n{ group.tail(5) }")
                    
                    await self.on_df_last_added(self.timeframe,symbol, group)
                #logger.info(f"NEW \n{ new_rows.tail(5) }")

            #logger.info(f"\n{ self.filtered_df.tail(10) }")

            self.current_time=current_time
    
    def  pre_scan(self):
        # prendo ultima candela di ognuno , volume > 500_000
        if self.inData.pre_scan.get("enabled",False) == False:
            return self.symbols 
        
        min_day_volume = self.inData.pre_scan.get("min_day_volume",5_000_000)

        valid_symbols = (
            self.all_df.groupby("symbol")["base_volume"]
            .sum()
            .loc[lambda x: x > min_day_volume]
            .index
        )
        
        self.all_df = self.all_df[self.all_df["symbol"].isin(valid_symbols)]

        
        valid_symbols = self.all_df["symbol"].unique()
        self.symbols = valid_symbols

      
        logger.info(f"PRE SCAN {len(self.all_df )} {valid_symbols }")
          
        return self.symbols

########

class Back_DatabaseManager:
    def __init__(self,back_manager,inData:BacktestIn ):
        self.back_manager=back_manager
        self.inData=inData
        self.map={}
           
    def db_dataframe(self,timeframe)-> Back_DBDataframe_TimeFrame:
        if not timeframe in self.map :
            self.map[timeframe] = Back_DBDataframe_TimeFrame(self,timeframe,self.inData) 
        # min max
        return self.map[timeframe]
    
    def full_dataframe(self,timeframe,symbol="")-> pd.DataFrame:
        return self.db_dataframe(timeframe).full_dataframe(symbol)

    def dataframe(self,timeframe,symbol="")-> pd.DataFrame:
        return self.db_dataframe(timeframe).dataframe(symbol)

    def begin(self):
        _min = 999999999999999
        _max =0
        tf = 9999000
        for timeframe,db in self.map.items():
            _min= min(_min,db.min_time)
            _max= max(_max,db.max_time)
            tf = min(tf , TIMEFRAME_SECONDS[timeframe]*1000 )

        logger.info(f"TEST PERIOD : {ts_to_local_str(_min)} {ts_to_local_str(_max)} tf: {tf}")

        self.start_ts = _min
        self.end_ts = _max
        self.min_tf = tf

        for timeframe,db in self.map.items():
            db.goTo(_min)

    async def  pre_scan(self):
        for timeframe,db in self.map.items():
            await db.pre_scan()

    async def tick(self,time):
        for x in self.map.values():
            await x.tick(time)
