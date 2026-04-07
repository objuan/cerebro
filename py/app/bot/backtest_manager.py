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
from bot.backtest_db import *

class BacktestManager:
    params : Dict
    
    def __init__(self,config, client : MuloLiveClient,render_page : RenderPage):
        self.client=client
        self.config=config
  
        self.render_page = render_page
        self.strategy_folder = self.config["live_service"]["strategy_folder"]
        self.strategies=[]
        #self.back_strategies=[]
        self.active_strategy=None   
        self.enabled=False
        self.db=None

        if "stategies" in self.config:
            for strat_def in self.config["stategies"]:
                scope = strat_def["scope"]  if "scope" in strat_def else ""
                if scope =="BACK" or scope =="ALL":
                    self.strategies.append(strat_def)

    def setEnabled(self,enabled):
        logger.info(f"BACK MODE {enabled}")
        if self.enabled!= enabled:
            self.enabled=enabled
           
    async def  pre_scan(self):
        logger.info(f"pre_scan {self.inData.to_dict()}")
        await self.db.pre_scan()

    async def loadStrategy(self,module_name, class_name,strat_def):

        logger.info(f"LOAD STRATEGY module: {module_name} class:{class_name}")

        find=False
        if self.active_strategy:
            if self.active_strategy.moduleName == module_name :
                logger.info(f"STRATEGY {module_name} already loaded")
                try:
                    self.active_strategy.dispose()

                    module = importlib.reload(self.active_strategy.module)
                    find=True
                except:
                    logger.error("MODULE NOT FOUND", exc_info=True)

               
        
        if not find:
            try:
                module = importlib.import_module(module_name)
            except:
                logger.error("MODULE NOT FOUND", exc_info=True)

        instance = getattr(module, class_name)
        strategy = instance(self)
        strategy.backtestMode=True
        strategy.load(strat_def)
        strategy.moduleName = module_name
        strategy.module = module
        strategy.name = module_name+"."+class_name
        strategy.code = inspect.getsource(instance)
        strategy.props = self.client.propManager
        self.active_strategy = strategy

        await strategy.initialize()

    def get_strategy_list(self):
        return self.strategies

    def get_profile_data(self,profile_name):
        logger.info(f"GET PROFILE { profile_name}")
        df = self.back_profiles(  )
        sdata = df[df["name"]== profile_name].iloc[0]["data"]
        logger.info(f"SELECT DATA { sdata}")
        data = json.loads(sdata)

        date_obj = datetime.strptime(data["date"], "%Y-%m-%d")
        # inizio giorno
        start_of_day = datetime.combine(date_obj.date(), datetime.min.time())
        # fine giorno
        end_of_day = datetime.combine(date_obj.date(), datetime.max.time())
        unix_min = int(start_of_day.timestamp())*1000
        unix_max = int(end_of_day.timestamp())*1000

        in_data_old= {
            "badgetUSD": 100,
            "symbols": ["ATOM","CRSR"],
            "dt_from": "2026-02-13 16:00:00",
            "dt_to": "2026-02-13 18:00:00",
            "strategy": [{"module": "strategies.back_strategy", "class": "BackStrategy"}]
        }
        in_data = data

        backData =  BacktestIn(in_data)
        backData.symbols = [ x["symbol"] for  x in data["symbols"]]

        backData.dt_from = start_of_day.strftime("%Y-%m-%d %H:%M:%S")
        backData.dt_to =end_of_day.strftime("%Y-%m-%d %H:%M:%S")
        if  data["module"].startswith("strategies."):
            backData.module = data["module"]
        else:
            backData.module = "strategies."+data["module"].strip()
        backData.className = data["class"]
        backData.timeframe = data["tf"]
        backData.params = data["params"]
        return backData


    async def load(self, inData:BacktestIn):
        self.inData=inData
        logger.info(f"LOAD {self.inData.to_dict()}")
        self.db = Back_DatabaseManager(self,inData)
        
        await self.loadStrategy(inData.module, inData.className,
                                {
                                    "timeframe" :  TIMEFRAME_SECONDS[inData.timeframe],
                                    "params": inData.params
                                })

        self.db.begin()


    async def start(self):

        logger.info(f"START ")
        #self.db = Back_DatabaseManager(self,inData)

        await self.active_strategy.start()

        time = self.db.start_ts
        time_delta =  self.db.min_tf

        logger.info(f"BACK START time {ts_to_local_str(self.db.start_ts)}-{ ts_to_local_str(self.db.end_ts)} time_delta {time_delta}")

        #for i in range(0,10):
        '''
        while(time < self.db.end_ts):
            time= time + time_delta
            await self.db.tick(time)
        '''
     
        self.active_strategy.onBackEnd()
        trades= json.dumps([t.toDict() for t in self.active_strategy.book.trades])

        script=self.active_strategy.code

        markers = self.active_strategy.marker_map[self.active_strategy.timeframe] if self.active_strategy.timeframe in self.active_strategy.marker_map else []

        #logger.info(f"markers {markers}")   

        self.client.execute("""
            INSERT INTO back_session (strategy,dt_from,dt_to, in_data, trades,markers,script)
        VALUES (?, ?, ?, ?,?, ?, ?)
        """, (self.active_strategy.name, self.inData.dt_from, self.inData.dt_to,
               json.dumps(self.inData.to_dict()), 
               json.dumps(trades),
               json.dumps(markers.to_dict(orient="records")), 
               script))

        # save back 

        logger.info(f"BACK END")

    def reset(self):
        pass

    ##############

    def setCurrentTime(self,current):
        logger.info(f"setCurrentTime {current}")
        pass

    #########################

    def back_profiles(self):
        
        conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT * from back_profile"""
        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 
    
    def back_data(self,symbols: List[str], timeframe: str, since : int, to: int ):

        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        
        sql_symbols = str(symbols)[1:-1]
        conn = sqlite3.connect(DB_FILE)

        #logger.info(f"SYM BOOT TIME {self.sym_start_time}")

        query = f"""
                    SELECT *
                    FROM ib_ohlc_history
                    WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                    and timestamp>= {since}
                    and timestamp<= {to}
                    ORDER BY timestamp DESC"""

        logger.info(f"query {query}")        
        #print("query",query)

        df = pd.read_sql_query(query, conn)
         
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 

      
    def back_symbols(self, since : int, to: int ):
        
        conn = sqlite3.connect(DB_FILE)

        query = f"""
                   SELECT 
    symbol,
    MIN(timestamp) AS min_timestamp,
    MAX(timestamp) AS max_timestamp
FROM ib_ohlc_history
WHERE timeframe = '1m'
  AND timestamp >= {since}
  AND timestamp <= {to}
GROUP BY symbol;
"""
                    
        #print("query",query)

        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 
    

    
    def save_profile(self,name,data):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        query = """
            INSERT INTO back_profile (name, data)
            VALUES (?, ?)
            ON CONFLICT(name)
            DO UPDATE SET data = excluded.data
        """

        cursor.execute(query, (name, json.dumps(data)))
        conn.commit()
        conn.close()

    async def download_data(self, data:BacktestIn):
        for timeframe in ["1m","5m","1d"]:
            for symbol in data.symbols:
                logger.info(f"GET DATA {symbol} {timeframe}")
                await self.client.send_cmd("/chart/align_data", {"mode":"","symbol" : symbol,"timeframe": timeframe  })

    async def get_history(self,strategy,dt_from,dt_to):
        conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT * from back_session where strategy='{strategy}' and dt_from >= '{dt_from}' and dt_to <= '{dt_to}' order by ds_timestamp desc limit 10"""
        df = pd.read_sql_query(query, conn)
        #logger.info(f"get_history {query} {df}")

        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df

    def get_symbol_history(self,history_id,symbol):
        arr={}
       
        conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT * from back_session where id={history_id} """
        df = pd.read_sql_query(query, conn)
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()   

        trades = json.loads(df["trades"].iloc[0])
        markers = json.loads(df["markers"].iloc[0])


        logger.info(f"trades {symbol} {markers}")

        markers = [x for x in markers if x["symbol"] == symbol]
        '''
        for _trade in _trades:
            trades = json.loads(_trade)
            for trade in trades:
                if trade["symbol"]==symbol: 
                    arr.append(trade)   
                    #logger.info(f"{trade}")
        '''
        return {"strategy": df["strategy"].iloc[0],
                "markers": markers, "trades": trades    }

    def get_history_indicators(self,symbol,id):
        h = self.get_symbol_history(id,symbol  )
  
        return [ {"strategy": h["strategy"], "markers": h["markers"]}]


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

        manager = BacktestManager(config,client,render_page)

        df = client.get_df(f"""SELECT distinct date FROM ib_day_watch""")
   
       # for _, row_dict in df.iterrows():
        for date in ["2026-03-30"]: 
         
            #date = row_dict["date"] 

            logger.info(f"=========  PROCESS  {date} ====================")

            df = client.get_df(f"""SELECT distinct symbol FROM ib_day_watch
                        WHERE date = '{date}' """)
            list = df["symbol"].tolist()
            list = list[:80]

            ##list = ["IMNN"]
            
            logger.info(f"STAT PROCESS {list}")
            data = {
                "badgetUSD": 10000,
                "symbols": list,
                "dt_from": f"{date} 0:00:00", # UTC format
                "dt_to": f"{date} 23:59:00",
                "module" : "strategies.back_strategy",
                "class": "BackStrategy",
                "pre_scan": {
                    "enabled": False,
                    "min_day_volume": 5_000_000
                },
                "params" : {
                    "gain_perc" : 10,
                    "volume_min_filter" :1_000_000,
                    "trade_last_hh" : 14
                    },
                "timeframe" : "1m"

            # "strategy": [{"module": "strategies.back_strategy", "class": "BackStrategy"}]
            }
            #"strategy": [{"module": "strategies.back_strategy", "class": "BackStrategy"}]

            backtest = BacktestIn(data)

            ### solo una volta
            #await manager.download_data(backtest)

            await manager.load(backtest)

            await manager.start()

            manager.reset()

        pass

    asyncio.run(main())