import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import VWAP
from company_loaders import *
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *

class ReportManager:

    def __init__(self, config,job  ,db : DBDataframe):
        self.job=job
        self.config=config
        self.db=db
        self.gain_time_min = 60
        self.history_days  = 50
        self.render_page=None
        self.invalidate=False
        job.on_symbols_update += self.on_symbols_update
        

    async def bootstrap(self):
        symbols = await self.job.send_cmd("symbols")
        
        await self.on_symbols_update(symbols, symbols,[])

        self.scheduler = AsyncScheduler()

        shapshot_time = self.config["reports"]["shapshot_time"]
        logger.info(f"shapshot_time {shapshot_time}")
        
        self.scheduler.schedule_every(shapshot_time,self.take_snapshot, key= "10m")

        self.df_report =None
        self.shapshot_history =  deque(maxlen=100)
        # events
        self.on_snapshot_10m = MyEvent()
        ##
        self.invalidate=True
        self.db.db_dataframe("1m").on_row_added+= self.on_db_1m_added

        self.first_open=[]

        self.ind_vwap = VWAP("vwap")

        await self.tick()
        #self.fill()

    def getLastDF(self):
        return self.shapshot_history[-1]

    async def on_symbols_update(self, symbols,to_add,to_remove):
        logger.debug(f"Report reset symbols {symbols}")
        self.symbols=symbols
        self.live_df = self.job.live_symbols()
        logger.debug(f"live_df \n{self.live_df}")
        self.first_open=[]

    def format_time(self,time):
        return f"{self.gain_time_min} m"

    async def take_snapshot(self,key:str):
        #logger.info(f"take_snapshot {key} {len(self.shapshot_history)} ")

        #diff = self.make_diff(self.df_report,self.shapshot_history[-1] )
        
        #logger.info(f"take_snapshot diff \n{self.df_report}")

        self.shapshot_history.append(self.df_report)
        if len(self.shapshot_history)>=2:
            #logger.info(f"send  {self.on_snapshot_10m._handlers }")
            await self.on_snapshot_10m(self.shapshot_history[-2],self.shapshot_history[-1])

    def py_value(self,v):
        if hasattr(v, "item"):
            v = v.item()
        return round(v, 6) if isinstance(v, float) else v

    async def send_current(self):
            # prima volta mando tutto 
            #self.df_report = self.df_report.reset_index()  
            
            full_dict = {
                symbol: {
                    col: self.py_value(self.df_report.loc[symbol, col])
                    for col in ["rank","rank_delta","gain","last", "day_volume","avg_base_volume_1d","float","rel_vol_24","rel_vol_5m",
                                "gap","avg_base_volume_1d","avg_base_volume_5m","volume_5m"]
                }
                for symbol in self.df_report.index
            }

            #logger.info(f"full_dict \n{full_dict}")
            await self.render_page.send({
                    "type" : "report",
                    "data": full_dict
            })
            

        
    def make_diff(self, current: pd.DataFrame, old: pd.DataFrame):

        cols = [
            "rank","rank_delta","gain","last","day_volume",
            "avg_base_volume_1d","float","rel_vol_24",
            "rel_vol_5m","gap","avg_base_volume_5m","volume_5m"
        ]

        # 🔹 rimuove eventuali duplicati di index (fondamentale)
        current = current[~current.index.duplicated(keep="last")]
        old = old[~old.index.duplicated(keep="last")]

        # allinea indici
        all_symbols = current.index.union(old.index)

        current_aligned = current.reindex(all_symbols)
        old_aligned = old.reindex(all_symbols)

        change_mask = old_aligned[cols].ne(current_aligned[cols])

        changed_dict = {}

        for symbol in all_symbols:

            if symbol not in change_mask.index:
                continue

            row_mask = change_mask.loc[symbol]

            # Se per qualche motivo è DataFrame, prendiamo ultima riga
            if isinstance(row_mask, pd.DataFrame):
                row_mask = row_mask.iloc[-1]

            if row_mask.any():

                changed_cols = {}

                for col in cols:

                    mask_value = row_mask[col]

                    if bool(mask_value) and pd.notna(current_aligned.at[symbol, col]):
                        changed_cols[col] = self.py_value(
                            current_aligned.at[symbol, col]
                        )

                if changed_cols:
                    changed_dict[symbol] = changed_cols

        return changed_dict

    async def on_db_1m_added(self,row):
        self.invalidate=True

    async def tick(self):
        
        if not self.invalidate:
            return
        self.invalidate=False
        try:
            
            logger.debug("TICK")

            await self.scheduler.tick()

            isLiveZone = self.job.market.isLiveZone()

            # situazione attuale

            #  symbol  last_close  last   volume  ask  bid  gain  ts   datetime
            df_tickers = self.job.getTickersDF()
            #logger.info(f"Tickers \n{df_tickers}")
        

            df_5m = self.db.dataframe("5m")
            #logger.info(df_5m)
            df_5m = df_5m.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

            mean_base_volume_5m = (
                            df_5m
                            .sort_values("timestamp")
                            .groupby("symbol")
                            .tail(self.history_days)
                            .groupby("symbol")["base_volume"]
                            .mean()
                            .reset_index(name="avg_base_volume_5m")
                        )

            #print(df_5m)
            #logger.info(f"mean_base_volume_5m \n{mean_base_volume_5m }")

            #logger.info(f"mean_base_volume_5m \n{df_5m[df_5m['symbol']=='ERNA'].tail(100) }")
            #########

            #           
            df_1d = self.db.dataframe("1d")
            #df_df_1d5m = df_1d.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
            #logger.info(f"df_1d \n{df_1d}")


            mean_base_volume_1d = (
                df_1d
                .sort_values("timestamp")
                .groupby("symbol")
                .tail(self.history_days)
                .groupby("symbol")["base_volume"]
                .mean()
                .reset_index(name="avg_base_volume_1d")
            )

            #logger.info(f"mean_base_volume_1d \n{mean_base_volume_1d.to_string(index=False)}")

            ####

            df_1m = self.db.dataframe("1m")[["timestamp","symbol","close","open","low","high","base_volume","date"]]
            
            #self.ind_vwap.apply(df_1m)

            #df_1m["date"] = pd.to_datetime(df_1m["timestamp"], unit="ms", utc=True).dt.date
            #df_1d["date"] = pd.to_datetime(df_1d["timestamp"], unit="ms", utc=True).dt.date
            #logger.info(f"df_1m \n{df_1m.to_string(index=False)}")
         
            df = df_tickers.copy().rename(columns={"ts": "timestamp"})

            #logger.info(f"df \n{df.to_string(index=False)}")
            
            #self.ind_vwap.apply(df)
            
            df = df[["symbol","last_close","last","gain","ask","bid","day_volume"]]#self.get_last(df_1m)#.drop(columns=["quote_volume"])

            #logger.info(f"df1 \n{df_1m.to_string(index=False)}")


            ######## LAST CLOSE, FIRST OPEN #########

            
            
            #last_close = self.close_by_symbols(df_1m) 
            #logger.info(f"CLOSE \n{last_close.to_string(index=False)}")
            #df = df.merge(  last_close[["symbol","last_close"]], on="symbol",    how="left")
            
            if isLiveZone:
                if len ( self.first_open) == 0:
                    self.first_open = self.open_by_symbols(df_1m) 

                    logger.debug(f"OPEN \n{self.first_open.to_string(index=False)}")
         
                df = df.merge(  self.first_open[["symbol","first_open"]], on="symbol",    how="left")
            
            #logger.info(f"df \n{df.to_string(index=False)}")

            ## GAIN 
            #df["gain"] =  ((df['close'] - df['last_close'] ) / df['last_close'])  * 100
             #df["gain"] =  ((df['last'] - df['last_close'] ) / df['last_close'])  * 100

            ## GAP
            if isLiveZone:
                df["gap"] =  ((df['first_open'] - df['last_close'] ) /df['last_close'])  * 100
            else:
                df["gap"] =  df["gain"] 
            #logger.info(f"result {df}")

            #logger.info(f"df \n{df.to_string(index=False)}")
   
            #logger.info(f"result \n{df}")

            #volume delle ultime 24 ore con il volume medio giornaliero storico.

            df = df.merge(  mean_base_volume_1d, on="symbol",    how="left")
            df = df.merge(  mean_base_volume_5m, on="symbol",    how="left")

            #df['base_volume_5m'] = df_1m.tail(5)['base_volume'].sum()
  
            df_5m_last = (
                df_5m[["symbol", "base_volume"]]
                .groupby("symbol")
                .nth(-1)
                .reset_index()
                .rename(columns={"base_volume": "volume_5m"})
            ) 

            df = df.merge(  df_5m_last[["symbol","volume_5m"]], on="symbol",    how="left")
                             
            #logger.info(f"volume_5m \n{df_5m_last }")
            #logger.info(f"df['avg_base_volume_5m'] \n{df['avg_base_volume_5m'] }")

            df['rel_vol_24'] = (df['day_volume'] / df['avg_base_volume_1d'])  * 100
            df['rel_vol_5m'] = ((df['volume_5m'] / df['avg_base_volume_5m']) ) * 100

            #logger.info(f" df['rel_vol_5m'] \n{ df['rel_vol_5m'] }")

            #float

            df = df.merge(  self.job.df_fundamentals[["symbol","float"]], on="symbol",    how="left")
            
            #logger.info(f"df \n{df.to_string(index=False)}")
            #logger.info(f"df_1m \n{df_1m.to_string(index=False)}")
            #logger.info(f"result \n{df.to_string(index=False)}")

            ######### FINAL ###########

            df = df.fillna(0)
            df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
            df_new_report = df.sort_values(by="gain", ascending=False)
            df_new_report["rank"] = range(1, len(df_new_report) + 1)
            
            df_new_report = df_new_report.set_index("symbol")

            #logger.info(f"result \n{df_new_report}")

            ##################
            
            if len(self.shapshot_history) >0:
                last_snapshot = self.shapshot_history[-1]

                df_new_report = df_new_report.join(
                    last_snapshot[["rank"]].rename(columns={"rank": "rank_old"}),
                    how="left"
                )
            
                # Se un symbol è nuovo, usa il rank corrente come rank_old
                df_new_report["rank_old"].fillna(df_new_report["rank"], inplace=True)
                df_new_report["rank_delta"] = df_new_report["rank"] - df_new_report["rank_old"] 
                #######

                changed_dict = self.make_diff(df_new_report,self.df_report)

                if len(changed_dict)>0:
                    #logger.info(f"changed_dict \n{changed_dict}")

                    await self.render_page.send({
                        "type" : "report",
                        "data": changed_dict
                    })
            else:
                df_new_report["rank_old"] =  df_new_report["rank"] 
                df_new_report["rank_delta"] = df_new_report["rank"] - df_new_report["rank_old"] 

            #logger.info(f"result \n{df_new_report.tail(10)}")

            self.df_report  = df_new_report
        
            if len(self.shapshot_history) ==0:
                self.shapshot_history.append(self.df_report )
              
            # TODO  REPORT CONTINUAZIONE ,GAIN 2 week

        except:
            logger.error("REPORT ERROR" , exc_info=True)

    ##################

    def add_last_close(self,df)-> pd.DataFrame:
        close = self.close_by_symbols(df) 
        logger.debug(f"CLOSE {close}")
        df = df.merge(  close, on="symbol",    how="left")

    def open_by_symbols(self,df_1m)-> pd.DataFrame:
            '''
            use df_1m
            '''
            #last_date = datetime.fromtimestamp(df_1m.iloc[-1]["timestamp"]/1000)
 
            #prev_close = prev_day_before_24(last_date)
            #_prev_close = datetime_to_unix_ms(prev_close)

            #logger.info(f"First date {last_date} close {prev_close} ")

            win = self.get_day_window(df_1m)

            open_by_symbol = (
                win#[df_1m["timestamp"] > _prev_close]     # 1️⃣ filtro
                #.sort_values("timestamp")          # 2️⃣ ordina
                .groupby("symbol", as_index=False)
                .head(1)                            # 3️⃣ ultima riga per symbol
            )
            #logger.info(f"open_by_symbol {open_by_symbol}")
            open_by_symbol.rename(columns={"open": "first_open"}, inplace=True)
            return open_by_symbol[["symbol","timestamp", "first_open"]]

    def close_by_symbols(self,df_1m)-> pd.DataFrame:
            
            '''
            use df_1d
            '''
            last_date = df_1m["date"].max()
            #if (last_date == datetime().date()):
                 
            
            if str(last_date) == str(datetime.now().date()):
                 # prendo la data di ieri
                 logger.debug("take yesterday")
                 last_date = datetime.now().date() - timedelta(days=1)

            logger.debug(f"Last date {last_date} now { datetime.now().date()} ")
            
            last_date = datetime(last_date.year, last_date.month, last_date.day, 23,59,59)
           
            #last_date = datetime.fromtimestamp(df_1m.iloc[-1]["timestamp"]/1000)
            #test
           
            #prev_close = prev_day_before_24(last_date)
            _prev_close = datetime_to_unix_ms(last_date)

            logger.debug(f"Last date {last_date} close {_prev_close} ")

            close_by_symbol = (
                df_1m[df_1m["timestamp"] < _prev_close]     # 1️⃣ filtro
                #.sort_values("timestamp")          # 2️⃣ ordina
                .groupby("symbol", as_index=False)
                .tail(1)                            # 3️⃣ ultima riga per symbol
            )
            close_by_symbol.rename(columns={"close": "last_close"}, inplace=True)
            return close_by_symbol[["symbol","timestamp","last_close"]]
            
    
    def get_window(self,df,minutes, timeframe)-> pd.DataFrame:
         
        n = numero_candele(minutes,timeframe)
        logger.debug(f"win  {minutes}-> #{n}")
        return (df.tail(n))
    
    
    def get_day_window(self,df)-> pd.DataFrame:
         
        ##df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.date

        last_day = df.groupby("symbol")["date"].max()

        df_last = df[df.apply(
            lambda r: r["date"] == last_day[r["symbol"]],
            axis=1
        )]
        return df_last.drop(columns=["date"])

    def serialize(self):

        return {
            "type":"report",
            "report_type":"top_gain",
            "title" : "Top Gainer",
            "columns" : self.columnsData
        }
  