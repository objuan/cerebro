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
        self.back_strategies=[]
        self.enabled=False
        self.db=None

        if "stategies" in self.config:
            for strat_def in self.config["stategies"]:
                if strat_def["scope"] =="BACK" if "scope" in strat_def else False:
                    self.strategies.append(strat_def)

    def setEnabled(self,enabled):
        logger.info(f"BACK MODE {enabled}")
        self.enabled=enabled

    async def loadStrategy(self,module_name, class_name,strat_def):
        logger.info(f"LOAD STRATEGY module: {module_name} class:{class_name}")
        try:
            module = importlib.import_module(module_name)
        except:
            logger.error("MODULE NOT FOUND", exc_info=True)

        instance = getattr(module, class_name)
        strategy = instance(self)
        strategy.backtestMode=True
        strategy.load(strat_def)
        self.back_strategies.append(strategy)
        await strategy.bootstrap()

    def get_strategy_list(self):
        return self.strategies

    async def load(self, inData:BacktestIn):
        self.inData=inData
        self.db = Back_DatabaseManager(self,inData)

    async def start(self, strat_def):
        #self.db = Back_DatabaseManager(self,inData)
        logger.info(f"BACK START")
        self.back_strategies=[]
        for s in self.inData.strategy:
            await self.loadStrategy(s["module"], s["class"],strat_def)

        self.db.begin()
        time = self.db.start_ts
        time_delta =  self.db.min_tf

        #for i in range(0,10):
        while(time < self.db.end_ts):
            time= time + time_delta
            await self.db.tick(time)
        
        for s in self.back_strategies:
            s.onBackEnd()
        logger.info(f"BACK END")

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

        #logger.info(f"query {query}")        
        #print("query",query)

        df = pd.read_sql_query(query, conn)
         
        df = df.iloc[::-1].reset_index(drop=True)
        conn.close()    
        return df 

      
    def back_symbols(self,timeframe:str, since : int, to: int ):
        
        conn = sqlite3.connect(DB_FILE)

        query = f"""
                   SELECT 
    symbol,
    MIN(timestamp) AS min_timestamp,
    MAX(timestamp) AS max_timestamp
FROM ib_ohlc_history
WHERE timeframe = '{timeframe}'
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

        data = {
            "badgetUSD": 100,
            "symbols": ["BIAF"],
            "symbols1": [
                    "SAFX",
                    "DEVS",
                    "EDHL",
                    "EEIQ",
                    "TURB",
                    "GV",
                    "VEEE",
                    "SVCO",
                    "BTCT",
                    "CODX",
                    ],
            "dt_from": "2026-03-13 08:00:00", # UTC format
            "dt_to": "2026-03-13 16:59:00",
            "strategy": [{"module": "strategies.back_strategy", "class": "BackStrategy"}]
        }

        backtest = BacktestIn(data)

        ### solo una volta
        #await manager.download_data(backtest)

        strat_def ={
                "timeframe" : "1m",
				"params" :
				{
					"eta" : 5,
					"min_gain" : 2
				}
        }
        strat_def = convert_json(strat_def)

        await manager.load(backtest)

        await manager.start(strat_def)

        pass

    asyncio.run(main())