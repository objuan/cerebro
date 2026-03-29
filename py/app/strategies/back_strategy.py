from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
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

########################


class _BackStrategy(SmartStrategy):
    
    
    def __init__(self, manager):
        super().__init__(manager)
        self.plots = []
        self.legend = []
        self.marker_map= {}

        self.position = Position(10000)
        self.book = OrderBook( self.position )

    def buy(self,  symbol, price, label):
        logger.info(f"BUY {symbol} {label}")
        self.book.long(symbol, price, 100,label)

        
    def sell(self,symbol,price,label):
        logger.info(f"SELL {symbol} {label}")
        #self.book.short(symbol, price, 100,label)
        self.book.close(symbol,price)
        pass

    def onBackEnd(self):

        logger.info(f"REPORT {self.book.report()}")
        pass


#################

class BackStrategy(_BackStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]
        self.inPeriod=False

        pass

    def populate_indicators(self) :
        
        self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        #self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

    async def on_begin(self, dataframe: pd.DataFrame) :

        #logger.info(f"on_begin {len(dataframe)}")
        valid_symbols = dataframe["symbol"].unique()

        for symbol in  valid_symbols:
            df = dataframe[dataframe["symbol"]== symbol]
            #logger.info(f"df {symbol} #{len(dataframe)} \n{df}")

            candle_1330 = df[
                    (df['datetime'].dt.hour == 13) & 
                    (df['datetime'].dt.minute == 00)
                ].copy()


            gain_pre = 100.0 * (candle_1330.iloc[0]["close"]- df.iloc[0]["open"]) /  df.iloc[0]["open"]
            gain_last = 100.0 * (df.iloc[-1]["close"]- df.iloc[0]["open"]) /  df.iloc[0]["open"]

            logger.info(f"candle_1330  {symbol}  pre:{gain_pre} last:{gain_last}")
            #df['start_gain'] = df['first_open'] > df['prev_close']
        pass


    async def on_all_candle(self, dataframe: pd.DataFrame,global_index) :
        return
    
        for idx,last in  dataframe.loc[[global_index]].iterrows():
            #logger.info(f"last \n{last}")
            
            last_date = last["datetime"]
            last_ts = int(last["timestamp"])
            #logger.info(f" ny_time {last_date} {last_ts} idx:{global_index} ")

            if self.market.is_in_time(last["datetime"],
                get_hour_ms(9,0),get_hour_ms(11,0),False):
                    self.inPeriod=True
                    #logger.info(f" ny_time {last_date} {last_ts} idx:{global_index} ")

                    df_now = dataframe[
                        (dataframe["timestamp"] == last_ts) &
                        (dataframe["day_volume_history"] > 200_000)
                    ]

                    df_gain = df_now[
                        (df_now["GAIN"] > 0) & (df_now["GAIN"] < 2)
                    ]

                    gain_snap = df_gain.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
                    
                    #logger.info(f"gain_snap \n{gain_snap}")

                    if len(gain_snap)>0 and not self.book.has_any_trade():
                        first = gain_snap.iloc[0]

                        gain = first["GAIN"]

                        symbol = first["symbol"]
                            
                        logger.info(f"BUY  {last_date} {symbol} c:{first['close']}")

                        self.book.long(symbol, first["close"], 100,"G")
                        self.TP = gain


                    ########

                    if self.book.has_any_trade():
                        trade = self.book.get_first_trade()

                        if trade.symbol == last["symbol"]:

                            df_last = dataframe[
                                    (dataframe["timestamp"] == last_ts) &
                                    (dataframe["symbol"] == trade.symbol) 
                                ]
                            
                            if len(df_last)>0:
                                last = df_last.tail(1).iloc[0]

                                symbol = trade.symbol
                                
                                close = last["close"]

                                filtered = df_now[df_now["symbol"] == symbol]
                                #logger.info(f"ff\n{filtered}")

                                if not filtered.empty:
                                    gain_actual = filtered.iloc[0]["GAIN"]
                                else:
                                    gain_actual = 0  # oppure 0 o quello che ti serve

                                gain_buy = self.book.gain(symbol,close)

                                logger.info(f"LAST TRADE {trade.symbol} {last['datetime']} l:{close} gain_buy:{gain_buy} gain_actual:{gain_actual}")

                                if gain_buy < -self.TP:
                                    logger.info(f"SELL SL {last_date} {symbol} g:{gain_buy}")

                                    self.book.close(symbol,last['close'])

                                elif gain_buy > self.TP*3 :#and gain_actual<=0:
                                    
                                    logger.info(f"SELL TP {last_date} {symbol} g:{gain_buy}")

                                    self.book.close(symbol,last['close'])

            else:
            
                if self.inPeriod:
         
                    self.inPeriod=False
                    if self.book.has_any_trade():
                        trade = self.book.get_first_trade()
                        symbol = trade.symbol
                       
                        df_last = dataframe[
                                (dataframe["timestamp"] == last_ts) &
                                (dataframe["symbol"] == trade.symbol) 
                            ]
                        if len(df_last)>0:
                            last = df_last.tail(1).iloc[0]
                            gain = self.book.gain(symbol,last['close'])
                            logger.info(f"SELL LAST  {last_date} {symbol} g:{gain}")

                            self.book.close(symbol,last['close'])
                    
                
    async  def on_symbol_candle(self,symbol:str, dataframe: pd.DataFrame, metadata: dict) :

        return
        #logger.info(f"on_symbol_candles   {symbol} \n {dataframe.tail(2)}" )

    
        time = dataframe.iloc[-1]["timestamp"]
        close = dataframe.iloc[-1]["close"]
        sma_9 = dataframe.iloc[-1]["sma_9"]
        sma_20 = dataframe.iloc[-1]["sma_20"]

        #logger.info(f"{symbol} {sma_9} {sma_20}")

        if (sma_9 > sma_20 and not self.book.hasCurrentTrade(symbol)):
            self.buy(symbol, close, "BUY")

        if (sma_9 < sma_20 and self.book.hasCurrentTrade(symbol)):
            self.sell(symbol, close, "SELL")

        #gain = dataframe.iloc[-1]["gain"]
        #if gain > 1:
        #    logger.info(f"{symbol} gain {gain} {ts_to_local_str(time)} {sma_9} {sma_20}")

  