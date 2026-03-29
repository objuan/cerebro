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
        
        self.book.end()

        logger.info(f"REPORT {self.book.report()}")
        pass


#################

class BackStrategy(_BackStrategy):

    async def on_start(self):
        self.hh_filter= self.params["hh_filter"]
        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False

        pass

    def populate_indicators(self) :
        pass
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        #self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

    async def on_begin(self, dataframe: pd.DataFrame) :
        return
        #logger.info(f"on_begin {len(dataframe)}")
        valid_symbols = dataframe["symbol"].unique()

        logger.info(f"valid_symbols {len(valid_symbols)} {valid_symbols}    ")

        gaitTot=0
        for symbol in  valid_symbols:
            
            df = dataframe[dataframe["symbol"]== symbol]

            date = df.iloc[0]["datetime"].date()    

            #logger.info(f"... {symbol} {date}")   

            d_df = self.client.get_df(f"""SELECT * FROM ib_day_watch  
                        WHERE date = '{date}' AND symbol = '{symbol}' """)  
            
            #first_enter = d_df.iloc[0]["ds_timestamp"]

            utc_dt = datetime.strptime(d_df.iloc[0]["ds_timestamp"], '%Y-%m-%d %H:%M:%S')
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            first_enter = int(utc_dt.timestamp()  ) * 1000  

            #logger.info(f"... {symbol} {utc_dt} {first_enter}")   

            #for hh in [9]:
            if True:
                
                
                #logger.info(f"df {symbol} #{len(dataframe)} \n{df}")

                '''
                candle = df[
                        (df['datetime'].dt.hour == hh) & 
                        (df['datetime'].dt.minute == 00)
                    ].copy()
                '''
                candle = df[df['timestamp'] >= first_enter].head(1)

                if candle.empty:
                    continue

                open_price = candle.iloc[0]["close"]    
                volume = df[df['timestamp'] <= first_enter]["base_volume"].sum()    

                if volume > 500_000:

                    window = df[df['timestamp'] >= first_enter]

                    high = window["high"].max() 
                    low = window["low"].min()   

                    #logger.info(f"candle {symbol} {utc_dt} #{len(candle)} o:{open_price} v:{volume}")
                    #logger.info(f"df {symbol} #{len(df)} \n{df}")

                
                    close_price = df.iloc[-1]["close"]

                    #gain_pre = 100.0 * (candle.iloc[0]["close"]- df.iloc[0]["open"]) /  df.iloc[0]["open"]

                    #gain_last = 100.0 * (df.iloc[-1]["close"]- df.iloc[0]["open"]) /  df.iloc[0]["open"]
                    #gain = gain_last-gain_pre

                    gain = 100.0 * (close_price- open_price) / open_price

                    gain_min = 100.0 * (low- open_price) / open_price

                    gain_max = 100.0 * (high- open_price) / open_price

                    gaitTot+=gain
                    logger.info(f"GAIN {symbol} {utc_dt} p:{open_price} c:{close_price} gain:{gain} min:{gain_min} max:{gain_max}") 
                    #gaitTot+= gain

                #logger.info(f"{hh} {symbol}  pre:{gain_pre} last:{gain_last} => GAIN {gain}")
            #df['start_gain'] = df['first_open'] > df['prev_close']
        logger.info(f"GAIN TOT gain:{gaitTot}") 
        pass

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        if not self.backtestMode and self.bootstrapMode:
            return

        use_day=False

        if not self.has_meta(symbol,"trade_date"):
            date = dataframe.iloc[0]["datetime"].date()  

            d_df = self.client.get_df(f"""SELECT * FROM ib_day_watch  
                            WHERE date = '{date}' AND symbol = '{symbol}' """)  
           
            utc_dt = datetime.strptime(d_df.iloc[0]["ds_timestamp"], '%Y-%m-%d %H:%M:%S')
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
            #local_tz = pytz.timezone( tz_str='Europe/Rome' )
            
            first_enter = int(utc_dt.timestamp()  ) * 1000  

            self.set_meta(symbol, {"trade_date": utc_dt,"first_enter": first_enter  })   
            
            '''
            start_of_day = datetime.combine(utc_dt.date(), datetime.min.time())
            first_day= int(start_of_day.timestamp()  ) * 1000  

            volume = dataframe[
                (dataframe['timestamp'] >= first_day) & 
                (dataframe['timestamp'] <= first_enter)
            ]["base_volume"].sum()

            candle = dataframe[dataframe['timestamp'] >= first_enter].head(1)
            if not candle.empty:
                if  self.market.is_in_time(candle.iloc[0]["datetime"],
                    get_hour_ms(7,00),get_hour_ms(9,00),use_day):
            
                    if volume > self.volume_min_filter:      

                        logger.info(f"FIRST ENTER {symbol} {start_of_day} - {utc_dt}  volume:{volume}")

                        self.set_meta(symbol, {"valid": True ,"buy_time": int(candle.iloc[0]["timestamp"] )}) 
            '''     

        #########
        last = dataframe.iloc[local_index]
        volume = last["day_volume_history"]    
    
        if volume > self.volume_min_filter:

            #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

            if  not self.has_meta(symbol,"valid") and not self.book.hasCurrentTrade(symbol):
                        
                        self.set_meta(symbol, {"valid": True }) 

                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        logger.info(f"BUY {symbol} {dt} {buy_price}")
                        self.book.long(symbol, buy_price, 100, f"BUY")    

            
            if self.book.hasCurrentTrade(symbol):
                
                    
                    gain = self.book.gain(symbol, dataframe.iloc[local_index]["close"]) 
                    dt = dataframe.iloc[local_index]["datetime"]

                    self.book.set_current_price(symbol, last["close"])           
                    #logger.info(f"gain {symbol} {dt} gain {gain}")

                    if gain < -10:
                        self.book.close(symbol, dataframe.iloc[local_index]["close"])
                        logger.info(f"SELL SL  {symbol}  {dt}  gain {gain}")  
                        #self.del_meta(symbol,"valid")  
                    
                    if gain > 10:
                        self.book.close(symbol, dataframe.iloc[local_index]["close"])
                        logger.info(f"SELL TP  {symbol}  {dt}   gain {gain}")   

                        #self.del_meta(symbol,"valid")  

       
        
