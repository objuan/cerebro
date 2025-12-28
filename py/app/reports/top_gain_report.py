import pandas as pd
import logging
from datetime import datetime, timedelta

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

    def onStart(self,render_page)-> bool:
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
            {"title": f"Change From {self.format_time(self.gain_time_min)}(%)" ,"decimals": 2, "colors":{ "range_min": -2 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   } },
            {"title": "Symbol/News" , "type" :"str" },
            {"title": "Price","decimals": 5 },
            {"title": "Volume" },
            {"title": "Rel Vol (DaylyRate)","decimals": 2 },
            {"title": "Rel Vol (5 min %)","decimals": 2},
            {"title": "Gap", "decimals": 1, "colors":{ "range_min": -2 , "range_max":10 ,  "color_min": "#7B9AFD" , "color_max":"#3800B9"   } }

        ]

        live_df = self.job.live_symbols_df()
        return len(live_df)>0
    
    async def onTick(self,render_page):
        
        try:
            # situazione attuale
            live_df = self.job.live_symbols_df()
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

            df = self.get_last(df_1m)#.drop(columns=["quote_volume"])

            logger.info(f"df_1m {df_1m}")
        
            #self.add_last_close(df_1m)
            ######## LAST CLOSE, FIRST OPEN #########

            first_open = self.open_by_symbols(df_1m) 
            #logger.info(f"OPEN {first_open}")
            last_close = self.close_by_symbols(df_1m,df_1d) 
            #logger.info(f"CLOSE {last_close}")

            df = df.merge(  last_close[["symbol","last_close"]], on="symbol",    how="left")
            df = df.merge(  first_open[["symbol","first_open"]], on="symbol",    how="left")
            
            ## GAIN 
            df["gain"] =  ((df['close'] - df['last_close'] ) / df['last_close'])  * 100

            ## GAP
            df["gap"] =  ((df['first_open'] - df['last_close'] ) /df['last_close'])  * 100
            logger.info(f"result {df}")

            #volume 24
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

            # volume oggi

            win_oggi = self.get_day_window(df_1m)
            logger.info(f"day {win_oggi}")
        
            vol_day = (
                win_oggi
                .groupby("symbol", group_keys=False,as_index=False)
                .sum()
                .rename(columns={"base_volume": "volume_day"})
            )
            df = df.merge(  vol_day[["symbol","volume_day"]], on="symbol",    how="left")

            logger.info(f"result {df}")

            #volume delle ultime 24 ore con il volume medio giornaliero storico.
            df = df.merge(  mean_base_volume_1d, on="symbol",    how="left")
            df = df.merge(  mean_base_volume_5m, on="symbol",    how="left")

            df['rel_vol_24'] = (df['volume_24h'] / df['avg_base_volume_1d'])  * 100
            df['rel_vol_5m'] = ((df['base_volume'] / df['avg_base_volume_5m']) ) * 100

            logger.info(f"result {df}")

            await render_page.send({
                   "id" : self.id,
                   "type" : "report",
                   "data": df[["gain","symbol","close", "volume_24h","rel_vol_24","rel_vol_5m","gap"]].to_numpy().tolist()
               })
            
            return   
            #self.df = pd.DataFrame(columns=self.columns)

            #self.df[self.columns[0]] = 1
            #df = live_df[["pair","timestamp","close", "base_volume" , "quote_volume"]].copy()

            #print("history_shapshot",history_shapshot)
            #df['datetime_local'] = (pd.to_datetime(df['timestamp'], unit='ms', utc=True) .dt.tz_convert('Europe/Rome') )
            df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

            df["gain"] =  ((df['close'] - df['close'].shift(60) ) / df['close'].shift(60))  * 100

            #la differenza tra l’OPEN corrente e il CLOSE precedente.
            #Esiste solo all’apertura
            #Indica news / eventi overnight
            df["gap"] =  ((df['open'] - df['close'].shift(1) ) /df['close'].shift(1))  * 100


            # 24 ore
            
            base_vol_24h = (
                df
                .groupby("symbol", group_keys=False)
                .apply(
                    lambda g: (
                        g
                        .set_index("timestamp")["base_volume"]
                        .rolling(60*24)
                        .sum()
                        .values
                    )
                )
            )
            '''
            quote_vol_24h = (
                df
                .groupby("symbol", group_keys=False)
                .apply(
                    lambda g: (
                        g
                        .set_index("timestamp")["quote_volume"]
                        .rolling(60*24)
                        .sum()
                        .values
                    )
                )
            )
            '''
            df["base_volume_24h"] = base_vol_24h.explode().astype(float).values
            #df["quote_volume_24h"] = quote_vol_24h.explode().astype(float).values

            #ogger.info(mean_quote_volume)

            df = df.merge(  mean_base_volume_1d, on="symbol",    how="left")
            df = df.merge(  mean_base_volume_5m, on="symbol",    how="left")

            #  df_5m["base_volume_history"]

            #volume delle ultime 24 ore con il volume medio giornaliero storico.
            df['rel_vol_24'] = (df['base_volume_24h'] / df['avg_base_volume_1d']) 

               
            #quanto il volume dell’ultima candela 5m è sopra/sotto la media delle candele 5m.
            #df['Rel Vol (5 min %)'] = (df['base_volume_5m'] / df['avg_base_volume_5m'])
            df['rel_vol_5m'] = ((df['base_volume'] / df['avg_base_volume_5m']) ) * 100
            
            

            df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

            #df = df.merge(  mean_quote_volume, on="symbol",    how="left")
            
            
            #df["Vol50 media"]  = df['symbol'].map(mean_quote_volume)

            #logger.info(df[df["symbol"] == 'BTC/USDC'])

            #logger.info(df[df["symbol"] == 'ETH/USDC'])

            '''
            df['Rel Vol (DaylyRate)'] = (
                df['quote_volume_24h'] /
                df.groupby('symbol')['quote_volume_24h']
                .transform(lambda x: x.rolling(self.history_days*1440, min_periods=1).mean())
            )
            '''

            '''
            vol_5m = (
                df.groupby('symbol')['quote_volume']
                .rolling(5).sum()
                .reset_index(level=0, drop=True)
            )

            avg_vol_5m = (
                vol_5m.groupby(df['symbol'])
                    .rolling(20)
                    .mean()
                    .reset_index(level=0, drop=True)
            )
            
            '''

            #df['Rel Vol (5 min %)'] = (vol_5m / avg_vol_5m) * 100

            #print( live_df)
            #print( "df", df)

            ###################

            latest_rows = df.loc[df.groupby("symbol")["timestamp"].idxmax()]
            latest_rows.sort_values(by = "gain", ascending=True).reset_index(drop=True)
            latest_rows = latest_rows.fillna(0)

            logger.info(latest_rows)
                        
            #df.tail(10)
            await render_page.send({
                   "id" : self.id,
                   "type" : "report",
                   "data": latest_rows[["gain","symbol","close", "base_volume_24h","rel_vol_24","rel_vol_5m","gap"]].to_numpy().tolist()
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
  