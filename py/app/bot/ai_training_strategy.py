from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategies.strategy_utils import StrategyUtils
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from company_loaders import *
from collections import deque
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
#from strategy.order_strategy import *



#################

class AiTrainingStrategy(SmartStrategy):

    async def on_start(self):
        self.chain_up_max=4
        self.min_open_gain= 10
        self.volume_min_filter = 500_000
        
        self.find_map = {}

    async def onBackEnd(self):
        
        count=0
        for symbol,data in self.find_map.items():
            for entry in data:

                diff = entry["high"] - entry["low"]
                chain_gain =  (diff) / entry["low"] * 100  
                
                volume = entry["volume"]
                live = entry["live"]
                date = datetime.fromtimestamp(entry["start"]/1000 ).strftime('%Y-%m-%d')
                start = datetime.fromtimestamp(entry["start"]/1000 ).strftime('%Y-%m-%d %H:%M:%S')
                end = datetime.fromtimestamp(entry["end"]/1000 ).strftime('%Y-%m-%d %H:%M:%S')

                logger.info(f"{symbol} {start} {end} {chain_gain}")

                if count == 0:
                    self.client.execute(f"DELETE FROM ai_trainingset where date = '{date}'")
                    count+=1

                self.client.execute("""
                    INSERT INTO ai_trainingset (symbol,live, gain,volume, date,start,end, in_data)
                    VALUES (?,?, ?, ?, ?,?,?,?)
                    """, (symbol,live, chain_gain, volume,date, start,end,json.dumps(entry)))

   

    def populate_indicators(self) :
       
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        sma_20 = self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        chain_up = self.addIndicator(self.timeframe,CHAIN("chain_up",True))

 
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=False

        if (local_index < 2):   
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        close = last["close"]
       
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        #if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
        #    return
     
        chain_up = int(last["chain_up"]) if pd.notna(last["chain_up"]) else 0
        volume = last["day_volume_history"]   
        

        if volume < self.volume_min_filter:
            return

        if chain_up>=2 :#and chain_up <= self.chain_up_max:
                #logger.info(f"chain_len {chain_len}")
                chain_start = dataframe.iloc[local_index-chain_up+1]

                diff = last["high"] - chain_start["low"]
                chain_gain =  (diff) / chain_start["low"] * 100  
                datetime =  last["datetime"] 
                live =  last["timestamp"] > self.get_meta(symbol,"first_enter")

                if chain_gain > self.min_open_gain:

                    if not symbol in self.find_map:
                        self.find_map[symbol] = []

                    find_list =  self.find_map[symbol]
                    if len(find_list) == 0:
                        find_list.append({ "live" :'1' if live else '0', "volume" : volume, "start" :int(last['timestamp']) , "end" :  int(last['timestamp']) , "low":  chain_start['low'], "high":  last['high']})
                        logger.info(f"FIND FIRST {datetime} {symbol} gain {chain_gain} %")
                    else:
                        prev = find_list[-1]
                        #logger.info(f".. {prev} {last['timestamp']}")
                        
                        if  last['timestamp']-prev["end"]  == 60*1000:
                            prev["high"]=  last['high']
                            prev["end"]=  int(last['timestamp'])
                            logger.info(f"APPEND {datetime} {symbol} gain {chain_gain} %")

                        else:        
                            find_list.append({ "live" :'1' if live else '0', "volume" : volume, "start" :int(last['timestamp']) , "end" :  int(last['timestamp']) , "low":  chain_start['low'], "high":  last['high']})
                            logger.info(f"FIND FIRST {datetime} {symbol} gain {chain_gain} %")

               