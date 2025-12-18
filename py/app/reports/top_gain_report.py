import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage



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

    def onStart(self)-> bool:
        self.columns= [f"Change From {self.format_time(self.gain_time_min)}(%)","Pair/News","Rank","Price","Volume","Rel Vol (DaylyRate)", "Rel Vol (5 min %)","Gap"]
        live_df = self.job.live_symbols_df()
        return len(live_df)>0
    
    def onTick(self):
        
        try:
            # situazione attuale
            live_df = self.job.live_symbols_df()
            logger.info(live_df)

            #dt = datetime.now() - timedelta(minutes=self.gain_time_min)

            df = self.db.dataframe("1m")[["timestamp","pair","close","quote_volume","base_volume"]].copy()

            df_1d = self.db.dataframe("1d")

            #self.df = pd.DataFrame(columns=self.columns)

            #self.df[self.columns[0]] = 1
            #df = live_df[["pair","timestamp","close", "base_volume" , "quote_volume"]].copy()

            #print("history_shapshot",history_shapshot)
            df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )
            df = df.sort_values(["pair", "timestamp"]).reset_index(drop=True)

            df["gain"] =  ((df['close'] - df['close'].shift(60) ) / df['close'].shift(60))  * 100

            # 24 ore
            
            base_vol_24h = (
                df
                .groupby("pair", group_keys=False)
                .apply(
                    lambda g: (
                        g
                        .set_index("timestamp")["base_volume"]
                        .rolling(4)
                        .sum()
                        .values
                    )
                )
            )
            df["base_volume_24h"] = base_vol_24h.explode().astype(float).values
            mean_quote_volume = (
                df_1d
                .sort_values("timestamp")
                .groupby("pair")
                .tail(self.history_days)
                .groupby("pair")["quote_volume"]
                .mean()
                .reset_index(name="avg_quote_volume")
            )
            #ogger.info(mean_quote_volume)

            df = df.merge(  mean_quote_volume, on="pair",    how="left")

            '''
            df['Rel Vol (DaylyRate)'] = (
                df['quote_volume_24h'] /
                df.groupby('pair')['quote_volume_24h']
                .transform(lambda x: x.rolling(self.history_days*1440, min_periods=1).mean())
            )
            '''
            df = df.sort_values(["pair", "timestamp"]).reset_index(drop=True)

            #df = df.merge(  mean_quote_volume, on="pair",    how="left")
            
            
            #df["Vol50 media"]  = df['pair'].map(mean_quote_volume)

            logger.info(df[df["pair"] == 'BTC/USDC'])
            '''
            df['Rel Vol (DaylyRate)'] = (
                df['quote_volume_24h'] /
                df.groupby('pair')['quote_volume_24h']
                .transform(lambda x: x.rolling(self.history_days*1440, min_periods=1).mean())
            )
            '''

            '''
            vol_5m = (
                df.groupby('pair')['quote_volume']
                .rolling(5).sum()
                .reset_index(level=0, drop=True)
            )

            avg_vol_5m = (
                vol_5m.groupby(df['pair'])
                    .rolling(20)
                    .mean()
                    .reset_index(level=0, drop=True)
            )
            
            '''

            #df['Rel Vol (5 min %)'] = (vol_5m / avg_vol_5m) * 100

            #print( live_df)
            #print( "df", df)
        except:
            logger.error("REPORT ERROR" , exc_info=True)

    def serialize(self):

        return {
            "type":"report",
            "report_type":"top_gain",
            "title" : "Top Gainer",
            "columns" : self.columns
        }
  