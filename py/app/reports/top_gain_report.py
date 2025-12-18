import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage

# si autoaggiorna ogni tot
class SmartDataframe:
    def __init__(self, pairs, updateTime_minutes, handleCompute):
        self.pairs=pairs
        self.updateTime_minutes=updateTime_minutes
        self.handleCompute=handleCompute

    def update(self):
        self.df = self.handleCompute()

class TopGainReportWidget(ReportWidget):

    def __init__(self,id, job,db : DBDataframe):
        self.id=id
        self.job=job
        self.db=db
        self.gain_time_min = 60
        self.history_days  = 50

        #def update_1d(pair):
        #    self.job.history_data( "1m",dt )
    
        #self.df_1d = SmartDataframe(1, update_1d )

        self.fill()
   
    def format_time(self,time):
        return f"{self.gain_time_min} m"

    def fill(self):


        self.columns= [f"Change From {self.format_time(self.gain_time_min)}(%)","Pair/News","Rank","Price","Volume","Rel Vol (DaylyRate)", "Rel Vol (5 min %)","Gap"]

        # situazione attuale
        live_df = self.job.live_symbols_df()

        
        dt = datetime.now() - timedelta(minutes=self.gain_time_min)

        df_1m = self.db.dataframe("1m")

        df_1d = self.db.dataframe("1d")

        '''
        history_shapshot = self.job.history_at_time( "1m",dt )
        history_shapshot['datetime_local'] = (
            pd.to_datetime(history_shapshot['timestamp'], unit='ms', utc=True)
            .dt.tz_convert('Europe/Rome')
        )

        if (len(history_shapshot)== 0):
            logger.error("Could not founs prev shapshot")
            self.df=None
            return 
        '''            
        #self.df = pd.DataFrame(columns=self.columns)

        #self.df[self.columns[0]] = 1
        df = live_df.copy()

        #print("history_shapshot",history_shapshot)
        df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )

        logger.info(f"{df_1d}")
        #df[self.columns[0]] =  ((live_df['close'] - df_1m['close'].shift(60) ) / df_1m['close'].shift(60))  * 100
        #print("df_1d",df_1d)
        #mean_qv = df_1d.groupby('pair')['quote_volume'].mean()
        mean_quote_volume = (
            df_1d.groupby('pair')['quote_volume']
            .mean()
            .reset_index(name='avg_quote_volume')
        )
        print(mean_quote_volume)
        df["Vol50 media"]  = df['pair'].map(mean_quote_volume)

        print(df)
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
        print( "df", df)
        pass

    def serialize(self):

        return {
            "type":"report",
            "report_type":"top_gain",
            "title" : "Top Gainer",
            "columns" : self.columns
        }
  