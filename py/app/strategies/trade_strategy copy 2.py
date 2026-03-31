from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *
    
########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):

        self.volume_min_filter= 1000000 #self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
      
        capital = self.props.get("trade.day_balance_USD")
        trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass

    async def buy(self,symbol,datetime,price, quantity,label=""):
        if self.book.hasCurrentTrade(symbol):
            return

        logger.info(f"BUY {symbol} {datetime} {quantity} at {price} [{label}]")
        self.add_marker(symbol,"BUY",label,"#000000FF","arrowUp",position="atPriceBottom")

        #if not self.buyMap[symbol]:
        self.book.long(symbol, price, quantity,label)

        #super().buy(symbol,label)
        if not self.bootstrapMode:
            await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#21FF04", ring="news")


    async def sell(self,symbol,datetime, price, quantity,label=""):

        if self.book.hasCurrentTrade(symbol):
            logger.info(f"SELL  {symbol} {datetime}")

            trade = self.book.close(symbol,price)

            self.add_marker(symbol, "SPOT", label, "#000000", "arrowDown",position="atPriceBottom")

            if not self.bootstrapMode:
                await self.send_event(symbol, "SELL", f"SELL",f"SELL",color="#FF0404", ring="news")
            return trade
        else:   
            return None

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        day_volume_ticker = self.addIndicator(self.timeframe,COPY("day_volume_ticker","day_volume"))
     
        self.addIndicator(self.timeframe,SMA("sma_9","close",timeperiod=9))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

        self.add_plot(day_volume_history, "day_volume_history","#d3035a", "sub1", style="Solid", lineWidth=1)
        self.add_plot(day_volume_ticker, "day_volume_ticker","#0318d3", "sub1", style="Solid", lineWidth=1)

    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        
        #if not self.backtestMode and self.bootstrapMode:
        #    return

        use_day=True
        last = dataframe.iloc[local_index]

        if not self.has_meta(symbol,"first_enter"): 
           
            if use_day:
                date = datetime.now().date()    
            else:
                date = last["datetime"].date()    

            d_df = self.client.get_df(f"""SELECT * FROM ib_day_watch  
                        WHERE date = '{date}' AND symbol = '{symbol}' """)  
            
            #first_enter = d_df.iloc[0]["ds_timestamp"]
            if not d_df.empty:  
                utc_dt = datetime.strptime(d_df.iloc[0]["ds_timestamp"], '%Y-%m-%d %H:%M:%S')
                utc_dt = utc_dt.replace(tzinfo=pytz.utc)
                first_enter = int(utc_dt.timestamp()  ) * 1000  
            else:
                first_enter=-1

            self.set_meta(symbol, {"first_enter": first_enter }) 

            #logger.info(f"FIRST ENTER {symbol} {date} {first_enter}")   

            self.add_marker(symbol,"SPOT","X","#060806","square",position ="atPriceTop",timestamp=first_enter)

        
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(0,00),get_hour_ms(self.trade_last_hh,00),use_day):
        
            #########
            
            volume = last["day_volume_history"]    
            
            if volume > self.volume_min_filter:

                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

                if  not self.has_meta(symbol,"valid") and not self.book.hasCurrentTrade(symbol):
                    self.set_meta(symbol, {"valid": True }) 

                    gain = last["gain"]
                    if gain < self.gain_perc/2:
                        
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        #logger.info(f"BUY {symbol} {dt} q:{self.get_quantity(buy_price)} at: {buy_price}")
                        await self.buy(symbol, last["datetime"], buy_price,self.get_quantity(buy_price), f"BUY"  )

                        #logger.info(f"BUY {symbol} {dt} q:{self.get_quantity(buy_price)} at: {buy_price}")
                        #self.book.long(symbol, buy_price, self.get_quantity(buy_price), f"BUY")    
                        #self.add_marker(symbol,"BUY","BUY","#000000","arrowUp")
                  
                
                if self.book.hasCurrentTrade(symbol):
                    
                        
                        gain = self.book.gain(symbol, last["close"]) 
                        dt = last["datetime"]

                        self.book.set_current_price(symbol, last["close"])           
                        #logger.info(f"gain {symbol} {dt} gain {gain}")

                        if gain < -self.gain_perc:
                            #trade = self.book.close(symbol, last["close"])
                            
                            trade = await self.sell(symbol, dt, last["close"], -1, f"SL"  )
                            #logger.info(f"SELL SL  {symbol}  {dt}  gain {gain} pnl : {trade.pnl()}")  
                            #self.add_marker(symbol,"BUY","SL","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  
                        
                        elif gain > self.gain_perc:
                            #trade = self.book.close(symbol, last["close"])
                            trade = await self.sell(symbol, dt, last["close"], -1, f"TP"  )

                            #logger.info(f"SELL TP  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   
                            

                            #self.add_marker(symbol,"BUY","TP","#000000","arrowDown")
                            #self.del_meta(symbol,"valid")  

                        '''
                        logger.info(f"TIME  {symbol}  {dt}  ") 

                        if not self.market.is_in_time(last["datetime"],
                             get_hour_ms(0,0),get_hour_ms(self.trade_last_hh,0),use_day):
                                
                                trade = self.book.close(symbol, last["close"])
                                logger.info(f"SELL TIME  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   

                                self.add_marker(symbol,"BUY","TM","#000000","arrowDown")
                        '''


        if not self.bootstrapMode and not self.backtestMode:
            logger.info(f"REPORT {self.book.report()}")