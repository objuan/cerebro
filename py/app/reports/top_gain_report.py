import pandas as pd
import logging
from datetime import datetime, timedelta
from company_loaders import *

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *

class TopGainReportWidget(ReportWidget):

    def __init__(self,id, job,db : DBDataframe):
        super().__init__(id)
        self.job=job
        self.db=db
        self.gain_time_min = 60
        self.history_days  = 50
        #self.fill()
   
    def format_time(self,time):
        return f"{self.gain_time_min} m"

    async def onStart(self,render_page)-> bool:
        logger.info("onStart")
        self.columns= [f"Change From {self.format_time(self.gain_time_min)}(%)","Symbol/News","Rank","Price","Volume","Rel Vol (DaylyRate)", "Rel Vol (5 min %)","Gap"]
        
        self.columnsData = [
            {"title": f"Change From {self.format_time(self.gain_time_min)}(%)", "data":"gain" },
            {"title": "Symbol/News", "data":"symbol" },
            {"title": "Price", "data":"close" },
            {"title": "Volume", "data":"base_volume" },
            {"title": "Rel Vol (DaylyRate)", "data":"rel_vol_24" },
            {"title": "Rel Vol (5 min %)", "data":"rel_vol_5m" },
            {"title": "Gap", "data":"gap" }

        ]
        self.columnsData = [
            {"title": f"Change From Close" ,"decimals": 2, "colors":{ "range_min": -2 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   } },
            {"title": "Symbol/News" , "type" :"str" },
            {"title": "Price","decimals": 5 },
            {"title": "Volume" },
            {"title": "Float" },
            {"title": "Rel Vol (DaylyRate)","decimals": 2 },
            {"title": "Rel Vol (5 min %)","decimals": 2},
            {"title": "Gap", "decimals": 1, "colors":{ "range_min": -10 , "range_max":10 ,  "color_min": "#FF0101" , "color_max":"#002FFF"   } }

        ]

        live_df = self.job.live_symbols()
        
        logger.debug(f"live_df \n{live_df}")

    
        return len(live_df)>0
    
    async def onTick(self,render_page):
        
        try:
            # situazione attuale
            #live_df = self.job.live_symbols()
            #logger.info(live_df)

            #dt = datetime.now() - timedelta(minutes=self.gain_time_min)

            df_5m = self.db.dataframe("5m")
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
            #########

            #           
            df_1d = self.db.dataframe("1d")
            df_df_1d5m = df_1d.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
            #logger.info(df_1d)

            mean_base_volume_1d = (
                df_1d
                .sort_values("timestamp")
                .groupby("symbol")
                .tail(self.history_days)
                .groupby("symbol")["base_volume"]
                .mean()
                .reset_index(name="avg_base_volume_1d")
            )

            ####

            df_1m = self.db.dataframe("1m")[["timestamp","symbol","close","open","low","high","base_volume"]]
            df_1m["date"] = pd.to_datetime(df_1m["timestamp"], unit="ms", utc=True).dt.date
            df_1d["date"] = pd.to_datetime(df_1d["timestamp"], unit="ms", utc=True).dt.date
            #logger.info(f"df_1m \n{df_1m.to_string(index=False)}")
         
            df = self.get_last(df_1m)#.drop(columns=["quote_volume"])

            logger.info(f"df \n{df.to_string(index=False)}")

            ######## LAST CLOSE, FIRST OPEN #########

            first_open = self.open_by_symbols(df_1m) 

            logger.info(f"OPEN \n{first_open.to_string(index=False)}")
            
            last_close = self.close_by_symbols(df_1m,df_1d) 
             
            logger.info(f"CLOSE \n{last_close.to_string(index=False)}")

            df = df.merge(  last_close[["symbol","last_close"]], on="symbol",    how="left")
            df = df.merge(  first_open[["symbol","first_open"]], on="symbol",    how="left")
            
            ## GAIN 
            #df["gain"] =  ((df['close'] - df['last_close'] ) / df['last_close'])  * 100
            df["gain"] =  ((df['close'] - df['last_close'] ) / df['last_close'])  * 100

            ## GAP
            df["gap"] =  ((df['first_open'] - df['last_close'] ) /df['last_close'])  * 100
            #logger.info(f"result {df}")

            
            #volume 24
            '''
            win_24 = self.get_window(df_1m,60*24,"1m")

            vol_24h = (
                win_24
                .groupby("symbol", group_keys=False,as_index=False)
                .sum()
                .rename(columns={"base_volume": "volume_24h"})
            )
            
            logger.debug(f"win_24 {vol_24h}")

            df = df.merge(  vol_24h[["symbol","volume_24h"]], on="symbol",    how="left")

            logger.info(f"result {df}")
            '''
            # volume oggi

            win_oggi = self.get_day_window(df_1m)
            #logger.info(f"day \n{win_oggi}")
        
            vol_day = (
                win_oggi
                .groupby("symbol", group_keys=False,as_index=False)
                .sum()
                .rename(columns={"base_volume": "volume_day"})
            )
            df = df.merge(  vol_day[["symbol","volume_day"]], on="symbol",    how="left")

            #logger.info(f"result \n{df}")

            #volume delle ultime 24 ore con il volume medio giornaliero storico.

            df = df.merge(  mean_base_volume_1d, on="symbol",    how="left")
            df = df.merge(  mean_base_volume_5m, on="symbol",    how="left")

            df['base_volume_5m'] = df_1m.tail(1)['base_volume'].sum()

            df['rel_vol_24'] = (df['volume_day'] / df['avg_base_volume_1d'])  * 100
            df['rel_vol_5m'] = ((df['base_volume_5m'] / df['avg_base_volume_5m']) ) * 100

            #float

            df = df.merge(  self.job.df_fundamentals[["symbol","float"]], on="symbol",    how="left")
            
            #logger.info(f"df_1m \n{df_1m.to_string(index=False)}")
            #logger.info(f"result \n{df.to_string(index=False)}")

            await render_page.send({
                   "id" : self.id,
                   "type" : "report",
                   "data": df[["gain","symbol","close", "volume_day","float","rel_vol_24","rel_vol_5m","gap"]].to_numpy().tolist()
               })

        except:
            logger.error("REPORT ERROR" , exc_info=True)

    def serialize(self):

        return {
            "type":"report",
            "report_type":"top_gain",
            "title" : "Top Gainer",
            "columns" : self.columnsData
        }
  