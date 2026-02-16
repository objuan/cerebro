from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import Strategy
from company_loaders import *

from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


class OrderStrategy(Strategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.max_symbols= self.params["max_symbols"]

    def populate_indicators(self) :
       self.addIndicator(self.timeframe,GAIN("gain_1","close",timeperiod=candles_from_seconds(60,self.timeframe)))
       self.addIndicator(self.timeframe,GAIN("gain_5","close",timeperiod=candles_from_seconds(60*5,self.timeframe)))
       self.addIndicator(self.timeframe,GAIN("gain_1h","close",timeperiod=candles_from_seconds(60*60,self.timeframe)))

    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :
        pass
        #  logger.debug(f"on_symbol_candle  {symbol} \n {dataframe.tail(10)}" )

    async def on_all_candle(self, dataframe: pd.DataFrame, metadata: dict) :
        #logger.info(f"\n{dataframe[dataframe['symbol'] == 'CDT'].tail(20)}")
       # logger.info(f"\n{dataframe.tail(20)}")
        
        df = dataframe.dropna(inplace=False)
        df = df.sort_values(["symbol", "timestamp"])

        def sample_last_stride(group, n, stride, column_name):
            # prende gli indici dal fondo con passo stride
            idx = group.index[::-stride][:n]
            out = group.loc[idx, ["symbol", "timestamp", column_name]].copy()
            return out.sort_values("timestamp")
        
        def df_to_metric_dict(df, value_col):
            out = {}

            for sym, g in df.groupby("symbol"):
                points = [
                    {"timestamp": int(ts), "value": float(val)}
                    for ts, val in g.sort_values("timestamp")[["timestamp", value_col]].itertuples(index=False)
                ]

                out[sym] =  points

            return out   
        
        #############

        gain1_df = (
            df.groupby("symbol", group_keys=False)
            .apply(lambda g: sample_last_stride(g, n=10, stride=candles_from_seconds(60,self.timeframe), column_name="gain_1"))
            .reset_index(drop=True)
        )

        gain5_df = (
            df.groupby("symbol", group_keys=False)
            .apply(lambda g: sample_last_stride(g, n=10, stride=candles_from_seconds(60*5,self.timeframe), column_name="gain_5"))
            .reset_index(drop=True)
        )

        gain1h_df = (
            df.groupby("symbol", group_keys=False)
            .apply(lambda g: sample_last_stride(g, n=10, stride=candles_from_seconds(60*60,self.timeframe), column_name="gain_1h"))
            .reset_index(drop=True)
        )

      
        gain1_dict  = df_to_metric_dict(gain1_df,  "gain_1")
        gain5_dict  = df_to_metric_dict(gain5_df,  "gain_5")
        gain1h_dict = df_to_metric_dict(gain1h_df, "gain_1h")

        out = {
            "gain_1" :gain1_dict
        }
        
        #logger.info(f"on_all_candle \n{out}")

        await self.client.send_ticker_rank({"gain_1": gain1_dict,"gain_5": gain5_dict,"gain_1h": gain1h_dict})

        '''
        last_rows = (
            dataframe
            .sort_index()
            .groupby("symbol")
            .tail( self.eta)
        )

        dataframe = last_rows.dropna(inplace=True)
        
        #logger.info(f"last_rows \n{last_rows}")

        df = last_rows.sort_values(["timestamp", "symbol"])

        # Rank per gain_1 e gain_5 dentro ogni timestamp
        df["rank_gain_1"] = (
            df.groupby("timestamp")["gain_1"]
            .rank(method="min", ascending=False)
            .astype(int)#.tail(self.max_symbols)
        )

        df["rank_gain_5"] = (
            df.groupby("timestamp")["gain_5"]
            .rank(method="min", ascending=False)
            .astype(int)#.tail(self.max_symbols)
        )

        #rank_tf = df[["timestamp", "symbol", "gain_1", "gain_5","rank_gain_1", "rank_gain_5"]].copy()
        '''

        '''
        rank_tf = rank_tf.rename(columns={
            "rank_gain_1": "gain_1",
            "rank_gain_5": "gain_5"
        })
        '''

        #logger.info(f"rank_tf \n{df}")

        ################

        '''
        out = {
            "gain_1": defaultdict(list),
            "gain_5": defaultdict(list),
            "gain_1h": defaultdict(list),
            "rank_gain_1": defaultdict(list),
            "rank_gain_5": defaultdict(list),
        }

        for ts, sym, g1, g5, h1, r1, r5 in df[["timestamp", "symbol", "gain_1", "gain_5","gain_1h","rank_gain_1", "rank_gain_5"]].itertuples(index=False):
            out["rank_gain_1"][sym].append({"timeframe": ts, "value": int(r1)})
            out["rank_gain_5"][sym].append({"timeframe": ts, "value": int(r5)})
            out["gain_1"][sym].append({"timeframe": ts, "value": float(g1)})
            out["gain_5"][sym].append({"timeframe": ts, "value": float(g5)})
            out["gain_1h"][sym].append({"timeframe": ts, "value": float(h1)})

        # opzionale: converti defaultdict in dict normale
        out = {k: dict(v) for k, v in out.items()}

        #await self.client.send_ticker_rank("GAIN 1m",rank_tf.to_dict(orient="records"))
        await self.client.send_ticker_rank("GAIN 1m",out)

        #logger.info(f"on_all_candle \n{out}")
        '''
   