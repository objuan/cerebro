import logging
if __name__ =="__main__":
    import sys
    import os
    from logging.handlers import RotatingFileHandler
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    LOG_DIR = "logs"
    LOG_FILE = os.path.join(LOG_DIR, "ai_loader.log")
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
from order_book import Trade
from bot.backtest_manager import BacktestManager


logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from bot.backtest_db import *

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
    
        all_results= []
        tot_gain=0.0

        dates = ["2026-04-01","2026-04-02","2026-04-07","2026-04-08","2026-04-09","2026-04-10","2026-04-13"
                             ,"2026-04-14","2026-04-15","2026-04-16","2026-04-17","2026-04-20"
                             ,"2026-04-22","2026-04-23","2026-04-24"]
        #dates = ["2026-04-21"]

       
        df = client.get_df(f"""SELECT distinct date FROM ib_day_watch""")

        #dates = df['date'].tolist()

        #logger.info(f"==============  START  ====================")    
        params = {
                                
                                    "trade_last_hh" : 15,

         }

  

        for date in dates:

                            logger.info(f"=========  PROCESS  {date} ====================")

                            #df = client.get_df(f"""SELECT distinct symbol FROM ib_day_watch
                            #            WHERE date = '{date}' order by symbol""")
                            df = manager.back_symbols(date)

                            list = df["symbol"].tolist()
                            #list = list[:80]

                            ##list = ["IMNN"]
                            
                            logger.info(f"STAT PROCESS {list}")
                            data = {
                                "badgetUSD": 1000,
                                "symbols": list,
                                "dt_from": f"{date} 2:00:00", # UTC format
                                "dt_to": f"{date} 23:59:00",
                                "module" : "bot.ai_training_strategy",
                                "class": "AiTrainingStrategy",
                                "pre_scan": {
                                    "enabled": False,
                                    "min_day_volume": 0
                                },
                                "params" :params,
                                "timeframe" : "1m"

                            }
                          
                            backtest = BacktestIn(data)

            
                            await manager.load(backtest)

                            trades = await manager.start()

                          
                    


    asyncio.run(main())