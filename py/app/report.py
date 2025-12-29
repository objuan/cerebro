import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from widget import *
from renderpage import RenderPage
from utils import *

class ReportWidget(Widget):

    def __init__(self,id):
       super().__init__()
       self.id=id
       
   
    def fill(df):
        pass

    async def notify_candles(self, candles,page:RenderPage):
       pass
       

    def render_html():
        pass

    def from_data(self,data):
        pass
        #type = data["sss"]


    def serialize(self):

        return {
            "report_type":"report",
        }
    
    def get_last(self,df):
            '''
            estrae le ultime righe per ogny symbolo
            '''
            last = (
                df    # 1️⃣ filtro
                #.sort_values("timestamp")          # 2️⃣ ordina
                .groupby("symbol", as_index=False)
                .tail(1)                            # 3️⃣ ultima riga per symbol
            )
            return last


    def add_last_close(self,df)-> pd.DataFrame:
        close = self.close_by_symbols(df) 
        logger.info(f"CLOSE {close}")
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

    def close_by_symbols(self,df_1m, df_1d)-> pd.DataFrame:
            
            '''
            use df_1d
            '''
            
            last_date = datetime.fromtimestamp(df_1m.iloc[-1]["timestamp"]/1000)
            #test
           
            
            prev_close = prev_day_before_24(last_date)
            _prev_close = datetime_to_unix_ms(prev_close)

            #logger.info(f"Last date {last_date} close {prev_close} ")

            close_by_symbol = (
                df_1d[df_1d["timestamp"] < _prev_close]     # 1️⃣ filtro
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
