import logging

if __name__ =="__main__":
    import sys
    import os
    from logging.handlers import RotatingFileHandler
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    LOG_DIR = "logs"
    LOG_FILE = os.path.join(LOG_DIR, "back.log")
    os.remove(LOG_FILE)

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger()
    logger.handlers.clear()
    
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5_000_000,
            backupCount=0,
            encoding="utf-8"
        )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


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
    dt_from : int
    dt_to: int
    strategy : List[ Dict]

    def __init__(self, data: Dict[str, Any]):
        self.badgetUSD: int = data.get("badgetUSD", 0)
        self.symbols: List[str] = data.get("symbols", [])
        self.dt_from: int = data.get("dt_from", 0)
        self.dt_to: int = data.get("dt_to", 0)
        self.strategy: List[Dict] = data.get("strategy", [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "badgetUSD": self.badgetUSD,
            "symbols": self.symbols,
            "dt_from": self.dt_from,
            "dt_to": self.dt_to,
            "strategy": self.strategy,
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
        #for symbol in inData.symbols:
        #    self.main_df.back_manager.client.history_data()
       
        since = 1000*int(datetime.strptime(str(inData.dt_from), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Rome")).timestamp())
     
        to = 1000*int(datetime.strptime(str(inData.dt_to), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Rome")).timestamp())

        self.all_df = self.main_df.back_manager.client.back_data(inData.symbols,self.timeframe,since, to)

        self.all_df["local_time"] = pd.to_datetime(self.all_df["timestamp"], unit="ms") \
                        .dt.tz_localize("UTC") \
                        .dt.tz_convert("Europe/Rome") \
                        .dt.tz_localize(None)  # opzionale: rimuove info timezone
        
        #self.all_df["timestamp"] = pd.to_datetime(self.all_df["timestamp"], unit="ms", utc=True)
        #self.all_df["i_timestamp"] = self.all_df["timestamp"]

        self.all_df = self.all_df.set_index("timestamp", drop=False).sort_index()
    
        logger.info(f"BACK_DF \n{self.all_df }")

        self.min_time = self.all_df.index.min()
        self.max_time = self.all_df.index.max()

        self.goTo(self.min_time)

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

                await self.on_df_last_added(self.timeframe,new_rows)
                #logger.info(f"NEW \n{ new_rows.tail(5) }")

            #logger.info(f"\n{ self.filtered_df.tail(10) }")

            self.current_time=current_time
    
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

    async def tick(self,time):
        for x in self.map.values():
            await x.tick(time)

###############################

class BacktestManager:
    params : Dict
    
    def __init__(self,client : MuloLiveClient,render_page : RenderPage):
      self.client=client
      self.render_page = render_page
      pass
    
    async def loadStrategy(self,module_name, class_name,strat_def):
        logger.info(f"LOAD STRATEGY module: {module_name} class:{class_name}")
        try:
            module = importlib.import_module(module_name)
        except:
            logger.error("MODULE NOT FOUND", exc_info=True)

        instance = getattr(module, class_name)
        strategy = instance(self)

        strategy.load(strat_def)

        await strategy.bootstrap()

    async def start(self, inData:BacktestIn,strat_def):
        self.db = Back_DatabaseManager(self,inData)
        for s in inData.strategy:
            await self.loadStrategy(s["module"], s["class"],strat_def)

        self.db.begin()
        time = self.db.start_ts
        time_delta =  self.db.min_tf

        #for i in range(0,10):
        while(time < self.db.end_ts):
            time= time + time_delta
            await self.db.tick(time)
        pass


###############################

if __name__ =="__main__":

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    logger.info("init")
    #init_company_db()

    async def main():
        render_page = RenderPage(None,None)
        propManager = PropertyManager()
        client = MuloLiveClient(DB_FILE,config,propManager)

        manager = BacktestManager(client,render_page)

        data = {
            "badgetUSD": 100,
            "symbols": ["ATOM","CRSR"],
            "dt_from": "2026-02-13 16:00:00",
            "dt_to": "2026-02-13 18:00:00",
            "strategy": [{"module": "strategies.back_strategy", "class": "BackStrategy"}]
        }

        backtest = BacktestIn(data)

        strat_def ={
                "timeframe" : "1m",
				"params" :
				{
					"eta" : 5,
					"min_gain" : 2
				}
        }
        strat_def = convert_json(strat_def)

        await manager.start(backtest,strat_def)

        pass

    asyncio.run(main())