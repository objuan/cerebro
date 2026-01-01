import pandas as pd
import logging
from datetime import datetime, timedelta
from company_loaders import *

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *

class SummaryReport(ReportWidget):

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
        if not self.job.ready:
            return False
        
        logger.info("onStart SummaryReport")
     
        self.columnsData = [
            {"title": f"Change From Close" ,"decimals": 2, "colors":{ "range_min": -2 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   } },
            {"title": "Symbol/News" , "type" :"str" },
            {"title": "Price","decimals": 5 },
        ]

        live_df = self.job.live_symbols()
        
        return len(live_df)>0
    
    async def onTick(self,render_page):
        
        try:

            isLiveZone = self.job.market.isLiveZone()

            df_tickers = self.job.getTickersDF()
            logger.info(f"Tickers \n{df_tickers}")
        
            df_1m = self.db.dataframe("1m")[["timestamp","symbol","close","open","low","high","base_volume"]]
            df_1m["date"] = pd.to_datetime(df_1m["timestamp"], unit="ms", utc=True).dt.date
           
            df = df_tickers.copy()#self.get_last(df_1m)#.drop(columns=["quote_volume"])

           
            last_close = self.close_by_symbols(df_1m) 
             
            logger.info(f"CLOSE \n{last_close.to_string(index=False)}")

            df = df.merge(  last_close[["symbol","last_close"]], on="symbol",    how="left")
           
            df["gain"] =  ((df['last'] - df['last_close'] ) / df['last_close'])  * 100

            await render_page.send({
                   "id" : self.id,
                   "type" : "report",
                   "data": df[["gain","symbol","last"]].to_numpy().tolist()
               })

        except:
            logger.error("REPORT ERROR" , exc_info=True)

    def serialize(self):
        return {
            "type":"report",
            "report_type":"summary",
            "title" : "Summary",
            "columns" : self.columnsData
        }
  