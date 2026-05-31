import logging
import gzip
import itertools
import copy

if __name__ =="__main__":
    import sys
    import os
    from logging.handlers import RotatingFileHandler

    sys.argv.append("BINANCE")
    
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

from collections import defaultdict
from typing import Dict
import pandas as pd

from zoneinfo import ZoneInfo
from typing import List, Dict, Any
from datetime import datetime, timedelta
from bot.indicators import Indicator
from company_loaders import *
from collections import deque
from mulo_live_client import MuloLiveClient
from config import DB_FILE,CONFIG_FILE,TF_SEC_TO_DESC,BACK_CONFIG_FILE
from props_manager import PropertyManager
import importlib
from order_book import Trade

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
        self.orderManager=None
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
        #logger.info(f"BACK MODE {enabled}")
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
        
        data = json.loads(sdata)

        in_data = data
        backData =  BacktestIn(in_data)
    
        #logger.info(f"SELECT DATA { data}")

        date_obj = datetime.strptime(data["date"], "%Y-%m-%d")
        back_days = data["backDays"]

        logger.info(f"back_days { back_days}")

        # inizio giorno
        
        end_of_day = date_obj.replace(hour=23, minute=0, second=0, microsecond=0)
        
        df = self.back_symbols(data["date"],back_days)#[ x["symbol"] for  x in data["symbols"]]
        backData.symbols = df["symbol"].tolist()

        start_of_day = end_of_day - timedelta(days=back_days)
        start_of_day = start_of_day.replace(hour=2, minute=0, second=0, microsecond=0)
        
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

    async def select(self, inData:BacktestIn):
        self.inData=inData
        logger.info(f"SELECT {self.inData.to_dict()}")

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


    async def start(self, saveResults) -> List[Trade]:

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
     
        await self.active_strategy.onBackEnd()
        trades= json.dumps([t.toDict() for t in self.active_strategy._book.trades])

        script=self.active_strategy.code

        #logger.info(f"marker_map {self.active_strategy.marker_map}")   

        markers = self.active_strategy.marker_map[self.active_strategy.timeframe] if self.active_strategy.timeframe in self.active_strategy.marker_map else None

        inds = self.active_strategy.dump_indicators()

        #logger.info(f"inData {self.inData}")   
        #logger.info(f"trades {trades}")   
        #logger.info(f"markers {markers}")   
        #logger.info(f"inds {len(inds)}")   
        
        if saveResults:
            inds = gzip.compress(
                 json.dumps(inds).encode("utf-8")
            )

            #logger.info(f"saveResults {self.inData.to_dict()} trades {trades} markers {markers} inds len {len(inds)}")
            
            self.client.execute("""
                INSERT INTO back_session (strategy,dt_from,dt_to, in_data, trades,markers,indicators,script,ds_timestamp)
            VALUES (%s, %s, %s, %s,%s, %s, %s,%s,%s)
            """, (self.active_strategy.name, self.inData.dt_from, self.inData.dt_to,
                json.dumps(self.inData.to_dict()), 
                json.dumps(trades),
                json.dumps(markers.to_dict(orient="records")) if markers is not None else None   , 
                inds , 
                script, datetime.now(tz=ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M:%S"))
            )

        # save back 

        logger.info(f"BACK END")

        return self.active_strategy._book.trades

    def reset(self):
        pass

    ##############

    def setCurrentTime(self,current):
        logger.info(f"setCurrentTime {current}")
        pass

    #########################

    def back_profiles(self):
        
        #conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT * from back_profile"""
        df = self.client.get_df(query)
        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()    
        return df 
    
    def back_data(self,symbols: List[str], timeframe: str, since : int, to: int ):

        if len(symbols) == 0:
            logger.error("symbol empty !!!")
            return None

        
        sql_symbols = str(symbols)[1:-1]
        #conn = sqlite3.connect(DB_FILE)

        #logger.info(f"SYM BOOT TIME {self.sym_start_time}")
        if timeframe not in "1m":
            df = self.client.history_data(symbols,timeframe,since=since,to=to)
        else:
            query = f"""
                        SELECT *
                        FROM ib_ohlc_history
                        WHERE symbol in ({sql_symbols}) AND timeframe='{timeframe}'
                        and timestamp>= {since}
                        and timestamp<= {to}
                        ORDER BY timestamp DESC"""

            #logger.info(f"query {query}")        
            #print("query",query)

            df = self.client.get_df(query)
            
            df = df.iloc[::-1].reset_index(drop=True)
       # conn.close()    
        return df 

    
    def back_ai_symbols(self, date):
        
        query = f"""SELECT DISTINCT SYMBOL 
                FROM ai_trainingset 
                WHERE 
                DATE = '{date}'
                AND live = '1' 
                AND volume >= 1000000 
                AND gain > 20"""
      
                    
        #print("query",query)

        df = self.client.get_df(query)
        df = df.iloc[::-1].reset_index(drop=True) 
        return df 
    
    def last_symbols(self,from_date):
        unix_min = int(from_date.timestamp())*1000
        unix_max = int(datetime.now().timestamp())*1000

        query = f"""
                    SELECT distinct symbol
                    FROM ib_ohlc_history
                    WHERE timeframe = '1m'
                    AND timestamp >= {unix_min}
                    AND timestamp <= {unix_max}
                    """
        df = self.client.get_df(query)
        df = df.iloc[::-1].reset_index(drop=True)
          
        return df 

    def back_symbols_from_to(self, from_date, to_date):
    
        if BINANCE_MODE:

                date_obj = datetime.strptime(from_date, "%Y-%m-%d")
                start_of_day = datetime.combine(date_obj.date(), datetime.min.time())
                # fine giorno
                date_obj = datetime.strptime(to_date, "%Y-%m-%d")
                end_of_day = datetime.combine(date_obj.date(), datetime.max.time())
                unix_min = int(start_of_day.timestamp())*1000
                unix_max = int(end_of_day.timestamp())*1000

                logger.info(f"{unix_min} {unix_max}")
                
                #dt = datetime.strptime(date, "%Y-%m-%d")
                #since = int(dt.replace(hour=0, minute=0, second=0).timestamp())
                #to = int(dt.replace(hour=23, minute=59, second=59).timestamp())

                query = f"""
                    SELECT 
                    symbol,
                    MIN(timestamp) AS min_timestamp,
                    MAX(timestamp) AS max_timestamp
                    FROM ib_ohlc_history
                    WHERE timeframe = '1m'
                    AND timestamp >= {unix_min}
                    AND timestamp <= {unix_max}
                    GROUP BY symbol;"""
        df = self.client.get_df(query)
        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()    
        return df 
                
    def back_symbols(self, date, back_days):
    
        if BINANCE_MODE:

                date_obj = datetime.strptime(date, "%Y-%m-%d")
                # inizio giorno
                end_of_day = datetime.combine(date_obj.date(), datetime.min.time())

                # fine giorno
                start_of_day = date_obj - timedelta(days=back_days)
                start_of_day = datetime.combine(start_of_day.date(), datetime.max.time())

                unix_min = int(start_of_day.timestamp())*1000
                unix_max = int(end_of_day.timestamp())*1000

                logger.info(f"symbols at {start_of_day} {end_of_day}")
                
                #dt = datetime.strptime(date, "%Y-%m-%d")
                #since = int(dt.replace(hour=0, minute=0, second=0).timestamp())
                #to = int(dt.replace(hour=23, minute=59, second=59).timestamp())

                '''
                query = f"""
                    SELECT 
                    symbol,
                    MIN(timestamp) AS min_timestamp,
                    MAX(timestamp) AS max_timestamp
                    FROM ib_ohlc_history
                    WHERE timeframe = '1m'
                    AND timestamp >= {unix_min}
                    AND timestamp <= {unix_max}
                    GROUP BY symbol;"""
                '''
                query = f"""SELECT distinct symbol FROM ib_ohlc_history
                            WHERE timeframe = '1m'
                            AND timestamp >= {unix_min}
                            AND timestamp <= {unix_max}"""

            #query = f"""SELECT distinct symbol FROM ib_day_watch
            #                WHERE date = '{date}' order by symbol"""
        else:
            query = f"""SELECT distinct symbol FROM ib_day_watch
                            WHERE date = '{date}' order by symbol"""
            '''
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
            '''
                    
        #print("query",query)

        df = self.client.get_df(query)
        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()    
        return df 
    

    
    def save_profile(self,name,data):
        #conn = sqlite3.connect(DB_FILE)
        #cursor = conn.cursor()

        query = """
        INSERT INTO back_profile (
            name,
            data
        )
        VALUES (
            %s,
            %s
        )

        ON DUPLICATE KEY UPDATE

            data = VALUES(data)
        """

        self.client.execute(query, (name, json.dumps(data)))
       #conn.commit()
        #conn.close()

    async def download_data(self, data:BacktestIn):
        for timeframe in ["1m","5m","1d"]:
            for symbol in data.symbols:
                logger.info(f"GET DATA {symbol} {timeframe}")
                await self.client.send_cmd("/chart/align_data", {"mode":"","symbol" : symbol,"timeframe": timeframe  })

    async def get_history_by_date(self,strategy,date):
       # conn = sqlite3.connect(DB_FILE)
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_of_day = datetime.combine(date_obj.date(), datetime.min.time())
        end_of_day = datetime.combine(date_obj.date(), datetime.max.time())
     

        query = f"""  SELECT id,strategy,dt_from,dt_to, in_data,trades,to_char(ds_timestamp) as ds_timestamp from back_session where strategy='{strategy}' and dt_to >= '{start_of_day}' and dt_to <= '{end_of_day}' order by ds_timestamp desc limit 5"""
        df = self.client.get_df(query)
        
        #logger.info(f"get_history {query} {df}")

        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()    
        return df

    async def get_history(self,strategy,dt_from,dt_to):
       # conn = sqlite3.connect(DB_FILE)
        query = f"""  SELECT id,strategy,dt_from,dt_to, in_data,trades,to_char(ds_timestamp) as ds_timestamp from back_session where strategy='{strategy}' and dt_from >= '{dt_from}' and dt_to <= '{dt_to}' order by ds_timestamp desc limit 5"""
        df = self.client.get_df(query)
        #logger.info(f"get_history {query} {df}")

        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()    
        return df

    def get_history_strategy(self,history_id):
        arr={}
       
        #conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT script from back_session where id={history_id} """
        df = self.client.get_df(query)
        # decomprime la colonna indicators

        df = df.iloc[::-1].reset_index(drop=True)
       # conn.close()  

        return df["script"].iloc[0]

    def get_symbol_history(self,history_id,symbol,timeframe):
        arr={}
       
       # conn = sqlite3.connect(DB_FILE)
        query = f""" SELECT strategy,indicators,trades,in_data,markers from back_session where id={history_id} """
        df = self.client.get_df(query)

        data = json.loads(df["in_data"].iloc[0])
        
        if data["timeframe"] != timeframe:
            return {"strategy": df["strategy"].iloc[0],
                "markers": [], "trades": [],"inds":[]    }

        # decomprime la colonna indicators
        df["indicators"] = df["indicators"].apply(
            lambda x: json.loads(
                gzip.decompress(x).decode("utf-8")
            ) if x is not None else None
        )
        #print(df["indicators"].iloc[0])
        df = df.iloc[::-1].reset_index(drop=True)
        #conn.close()   

        trades = json.loads(df["trades"].iloc[0])

        try:
            markers = json.loads(df["markers"].iloc[0])
            #logger.info(f"trades {symbol} {markers}")
            markers = [x for x in markers if x["symbol"] == symbol]
        except:
            markers = []

        #inds = json.loads(df["indicators"].iloc[0])
        inds = df["indicators"].iloc[0]

        for ind in inds:
            ind["data"] = [x for x in ind["data"] if x["symbol"] == symbol]
        
        '''
        for _trade in _trades:
            trades = json.loads(_trade)
            for trade in trades:
                if trade["symbol"]==symbol: 
                    arr.append(trade)   
                    #logger.info(f"{trade}")
        '''
        return {"strategy": df["strategy"].iloc[0],
                "markers": markers, "trades": trades,"inds":inds    }

    def get_history_indicators(self,symbol,timeframe,id):
        h = self.get_symbol_history(id,symbol ,timeframe )
  
        return [ {"strategy": h["strategy"], "markers": h["markers"],"list": h["inds"]}]


###############################


async def generate_hyper_configs(base_config, callFun):

    base_params = base_config["params"]
    hyper = base_config["hyper"] if "hyper" in base_config  else None

    if hyper:
        # nomi parametri hyper
        keys = hyper.keys()

        # tutte le combinazioni
        values_product = itertools.product(*(hyper[k] for k in keys))

        for values in values_product:

            # copia params originali
            params = copy.deepcopy(base_params)

            # sostituisce valori hyper
            for key, value in zip(keys, values):
                params[key] = value

            # chiama funzione
            await callFun(params)
    else:
        await callFun(base_params)


if __name__ =="__main__":

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    logger.info("init")
    #init_company_db()

    async def main(class_name, start_date,end_date,save_results):
        render_page = RenderPage(None,None)
        propManager = PropertyManager(None)
        client = MuloLiveClient(DB_FILE,config,propManager)

        manager = BacktestManager(config,client,render_page)

        df = client.get_df(f"""SELECT distinct date FROM ib_day_watch""")
    
        all_results= []

        
        with open(BACK_CONFIG_FILE, "r", encoding="utf-8") as f:
            back_config = json.load(f)

        entry = next(
            (item for item in back_config["list"] if item["class"] == class_name),
            None
        )

        if not entry:
            logger.error(f"class {class_name} not found")
            exit(-1)

        # File di log test
        log_filename = f"app\\bot\\back_test\\{class_name}_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.txt"

        # Apertura file
        test_log_file = open(log_filename, "w", encoding="utf-8")

        def log_info(message):
            """
            Scrive sia nel logger standard che nel file di test.
            """

            # Logger standard
            logger.info(message)

            # Scrittura su file
            test_log_file.write(message + "\n")
            test_log_file.flush()


        log_info(f"START TEST {class_name} {start_date} {end_date}")
      
        params = entry["params"]
      
        async def test_work(params):
                            
            results= []
            summary={}
            tot_gain=0.0

            ret = {"params" : params, "results": results,"summary": summary}
            all_results.append(ret)

            log_info(f"START WORK {params}")

            df = manager.back_symbols_from_to(start_date,end_date)
                               
            s_list = df["symbol"].tolist()
                 
            if len(s_list)>0:
                                
                log_info(f"STAT PROCESS {s_list}")

                data = {
                                        "badgetUSD": 1000,
                                        "symbols": s_list,
                                        "dt_from" :f"{start_date} 00:00:00", #f"{date_1} 2:00:00", # UTC format
                                        "dt_to": f"{end_date} 23:59:00",
                                        "module" : entry["module"],
                                        "class": class_name,
                                        "pre_scan": {
                                            "enabled": False,
                                            "min_day_volume": 0
                                        },
                                        "params" :params,
                                        "timeframe" : entry["timeframe"]

                                    
                                    }
                                    

                backtest = BacktestIn(data)

                                 
                await manager.load(backtest)

                daily_trades = defaultdict(list)

                trades = await manager.start( saveResults=save_results)

                # Raggruppa trades per giorno
                for t in trades:

                                        day = datetime.fromtimestamp(
                                            t.exit_datetime/1000
                                        ).date()

                                        daily_trades[day].append(t)

                                        #logger.info(f"t {t.symbol}")
                                    


                tot_gain=0.0
                all_w=0
                all_l=0
                tot_pnl=0.0 
                all_slots = 0

                for day, day_trades in sorted(daily_trades.items()):

                                        gain = 0
                                        pnl = 0
                                        w = 0
                                        l = 0

                                        slots=0

                                        for t in day_trades:

                                            all_slots = max(all_slots ,t.current_slots )
                                            slots = max(slots ,t.current_slots )

                                            g = t.gain()

                                            gain += g
                                            pnl += t.pnl()

                                            if g > 0:
                                                w += 1
                                            else:
                                                l += 1

                                        results.append({
                                            "date": str(day),
                                            "gain": gain,
                                            "pnl": pnl,
                                            "win": w,
                                            "loss": l,
                                            "slots": slots,
                                            "trades": day_trades,
                                            "num_trades": len(day_trades),
                                            "winrate": (
                                                w / len(day_trades) * 100
                                                if len(day_trades) > 0 else 0
                                            )
                                        })
                                        
                                        tot_gain+= gain
                                        tot_pnl+= pnl
                                        all_w += w
                                        all_l += l

            summary["gain"] = tot_gain
            summary["pnl"] = tot_pnl
            summary["win"] = all_w
            summary["loss"] = all_l
            summary["slots"] = all_slots
            summary["num_trades"] = len(results)
            

        await generate_hyper_configs(entry, test_work)

      
        ##############
        log_info(f"==================================")    
        for ret in all_results:
                        results = ret["results"]
                        summary = ret["summary"]
                        params = ret["params"]

                        log_info(f"=================")    
                        log_info(f"{params}")  
                        for r in results:   
                            #logger.info(f"{r}")  
                            log_info(f"{r['date']} TRADES {len(r['trades'])} pnl:{r['pnl']} win/loss {r['win']}/{r['loss']}  \t\t\tgain:{r['gain']} slots: {r['slots'] }")   

                        log_info(f"=====")    
                        log_info(f"TOT GAIN {summary['gain']}  pnl:{summary['pnl']} win {summary['win']} / {summary['loss']} #{summary['num_trades']} slots:{summary['slots']}")      
        log_info(f"==================================")  
        script=manager.active_strategy.code

        test_log_file.write(script + "\n")
        test_log_file.flush()

    asyncio.run(main("BackStrategyIB_1H","2026-05-28","2026-05-30",False))