from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
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
from strategies.strategy_utils import *


########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        
        self.last_timestamp=0
        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.trade_last_mm= self.params["trade_last_mm"]
      
        capital = self.props.get("trade.day_balance_USD")
        trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass


    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        day_volume_ticker = self.addIndicator(self.timeframe,COPY("day_volume_ticker","day_volume"))
     
        sma_20= self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        sma_200 = self.addIndicator(self.timeframe,SMA("sma_200","close",timeperiod=200))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

        max= self.addIndicator(self.timeframe,MAX("MAX","close",60))

        self.add_plot(sma_20, "sma_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_200, "sma_200","#034cd3", "main", style="SparseDotted", lineWidth=2)

        self.add_plot(day_volume_history, "day_volume_history","#d3035a", "sub1", style="Solid", lineWidth=1)
        self.add_plot(day_volume_ticker, "day_volume_ticker","#0318d3", "sub1", style="Solid", lineWidth=1)

        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
                            
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        
        if self.bootstrapMode:
            if not self.has_meta("__trade","init"):
                self.set_meta("__trade", {"init": True})   
                history =  self.orderManager.getTradeHistory(None)
                for trade in history:
                    if not trade.isClosed():
                        self.set_meta( trade.symbol, {"last_trade":trade})   
                        logger.info(f"BOOTSTRAP LAST TRADE {trade.symbol} {trade.isClosed()} {trade.to_dict()}")     
            return
        

        #if not self.backtestMode and self.bootstrapMode:
        #    return

        use_day=True
        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]
        sma_20 = last["sma_20"]   
        sma_200 = last["sma_200"]   
        volume = last["day_volume_history"]    
        MAX =  prev["MAX"] 

        if local_index<60:
            return
        
        self.set_current_price(symbol, last["close"])    
        
        ##### FIRST ENTER ######

        if not self.has_meta(symbol,"first_enter"): 
            await self.compute_first_enter(symbol, dataframe,local_index, use_day )
      
        # OPEN CLOSE INFOS
        if volume > self.volume_min_filter:
            
            if not self.has_meta(symbol,"compute_open"):
                await self.compute_open(symbol,dataframe,local_index, open_count=15, use_day=use_day)

            if self.has_meta(symbol,"compute_open"):
                if not self.has_meta(symbol,"up_done" ):

                    h = self.get_meta(symbol,"open_high",999999 )
                    if last["close"] > h:
                            self.set_meta(symbol,{"up_done": False} )
                            await self.add_marker(symbol,"SPOT","UP","UP","#004726","small_square",position ="atPriceTop")
                            #if not self.bootstrapMode:    
                            #    await self.send_event(symbol, "UP", f"UP", f"UP",color="#0B89BB", ring="news")

            #await self.set_property(symbol,self.timeframe , 
            #                     {"open_h":  self.get_meta(symbol,"open_high",999999 )}
            #                   )


        #######################
        if volume > self.volume_min_filter:

            if  self.market.is_in_time(last["datetime"],
                get_hour_ms(0,00),get_hour_ms(self.trade_last_hh,self.trade_last_mm),use_day):
        
                ######### FIRST OPEN PERIOD ########

                #and int(last["timestamp"]) >= self.get_meta(symbol,"first_enter") :
                
                if not self.has_meta(symbol,"volume"):
                    self.set_meta(symbol,{"volume":"OK"})

                    await self.add_marker(symbol,"SPOT","VOL",f"VOL > {self.volume_min_filter}","#BB0B46",position ="atPriceTop")
                    #if not self.bootstrapMode:
                    #        await self.send_event(symbol, "VOL", f"VOL > {self.volume_min_filter}", f"VOL > {self.volume_min_filter}",color="#BB0B46", ring="news")


                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

                if  not self.has_meta(symbol,"valid") and not self.hasCurrentTrade(symbol):
                    #self.set_meta(symbol, {"valid": True }) 

                    trend_up =  sma_200 > dataframe.iloc[local_index-60:local_index]["sma_200"].max()

                    gain = last["gain"]
                    # incrocio sma 20 200 rialzista 
                    if  gain < self.gain_perc/2 and last["close"] > sma_20 and sma_20 > sma_200 and prev["sma_20"] < prev["sma_200"] and trend_up  :
                        self.set_meta(symbol, {"valid": True }) 
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        await self.buy(symbol, last["datetime"], buy_price,self.get_quantity(buy_price), f"BUY"  )

                
                if self.hasCurrentTrade(symbol) and self.has_meta(symbol,"valid"):
                    
                        
                        gain,ts = self.buyGain(symbol, last["close"]) 
                        dt = last["datetime"]
                        time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000

                        #self.set_current_price(symbol, last["close"])           
                        #logger.info(f"gain {symbol} {dt} gain {gain}")

                        if gain < -self.gain_perc:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"SL"  )
                        elif gain > self.gain_perc:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"TP"  )

                        '''
                        logger.info(f"TIME  {symbol}  {dt}  ") 

                        if not self.market.is_in_time(last["datetime"],
                             get_hour_ms(0,0),get_hour_ms(self.trade_last_hh,0),use_day):
                                
                                trade = self.close(symbol, last["close"])
                                logger.info(f"SELL TIME  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   

                                self.add_marker(symbol,"BUY","TM","#000000","arrowDown")
                        '''

        # VOLUME DIFF
        #if volume > self.volume_min_filter:
        vol_diff = volume - prev["day_volume_history"]
        await self.set_property(symbol,"1m",{"volume_diff":vol_diff})

        # strenght
        '''
        back = 5
        strength = 100.0 * (last["close"] - dataframe.iloc[local_index-back]["close"]) /  dataframe.iloc[local_index-5]["close"]
        v=0
        for i  in [0,1,2,3,4]:
            v += dataframe.iloc[local_index-i]["day_volume_history"] * dataframe.iloc[local_index-i]["close"]
        v = v / back
        #logger.info(f"{volume} {v} ss {len( [-back,0])}")
        await self.set_property(symbol,"1m",{"strenght":strength * v})
        '''
        
        # MAX LOGIC

        if volume > self.volume_min_filter:
            prev_close = prev["close"]
            break_max = last["close"] >= MAX and prev_close < MAX
        

            if (break_max ):
                if  last["close"] < sma_200:
                    await self.add_marker(symbol, "SPOT", "MAX", f"max cross <",color="#31F30A", ring="alert1")
                else:
                    await self.add_marker(symbol,  "SPOT","MAX", f"max cross >",color="#F3A90A", ring="alert1")

        #pattern LOGIC

        #if not self.has_meta(symbol,"valid"):
        if True:

            if volume > self.volume_min_filter:
                '''
                fvg_ok, fvg_type, gap_low, gap_high, gap_perc = self.check_fvg(
                    dataframe, local_index
                )
                if fvg_ok :
                    msg = f"^_{gap_perc:.1f}" if fvg_type =="bullish" else f"V_{gap_perc:.1f}"
                    await self.add_marker(symbol,"SPOT",msg,f"FVG {fvg_type} {gap_perc:.1f}","#060806","small_square",position ="atPriceTop")
                    #if not self.bootstrapMode:
                    #    await self.send_event(symbol, "FVG", f"FVG {fvg_type} {gap_perc:.1f}", f"FVG",color="#57472E", ring="news")
                '''
                '''
                for n  in [5,4,3]:  
                    valid,min_low,max_high,gain_perc =  StrategyUtils.check_pattern(dataframe,local_index,n,5)
                    if valid:
                        logger.info(f"PATTERN {symbol} {last['datetime']} pattern {n} candles")
                        await self.add_marker(symbol,"SPOT",f"M_{n} {gain_perc:.0f}%",f"PAT {n}","#BB750B","small_square",position ="atPriceTop")

                        patt = { "idx": local_index, "type": n, "candle": last,"min_low":min_low,"max_high":max_high ,"gain":gain_perc   }
                        self.set_meta(symbol, {"pattern":patt } ) 

                        #if not self.bootstrapMode:
                        #    await self.send_event(symbol, "PAT", f"PAT {n}", f"PAT {n}",color="#BB750B", ring="news")

                        break
                
                ######

                if self.has_meta(symbol,"pattern") and not self.book.hasCurrentTrade(symbol) :
                    patt = self.get_meta(symbol,"pattern")
                    buy_limit = patt["max_high"] + patt["max_high"]*0.01
                    if last["close"] > buy_limit and local_index - patt["idx"] < 5:

                        logger.info(f"PATTERN BREAKOUT {symbol} {last['datetime']} pattern {patt['type']} candles")
                    
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        await self.buy(symbol, last["datetime"], buy_price,self.get_quantity(buy_price), f"BUY"  )
                    
                if self.book.hasCurrentTrade(symbol) and self.has_meta(symbol,"pattern") :
                    patt = self.get_meta(symbol,"pattern")
                    gain = self.book.gain(symbol, last["close"]) 
                    dt = last["datetime"]
                    min_low = patt["min_low"]
                    max_high = patt["max_high"]

                    pattern_gain_perc = self.get_meta(symbol,"pattern")["gain"]

                    self.book.set_current_price(symbol, last["close"])           
                    #logger.info(f"gain {symbol} {dt} gain {gain}")

                    if last["close"]< min_low:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"SL"  )
                            self.del_meta(symbol,"pattern")
                    elif last["close"]>max_high + (max_high-min_low)*2:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"TP"  )
                            self.del_meta(symbol,"pattern")
                    elif local_index -  patt["idx"] > 10:
                        # > 10 minuti
                        trade = await self.sell(symbol, dt, last["close"], -1, f"TO"  )
                        self.del_meta(symbol,"pattern")
                '''
        '''
        if not self.bootstrapMode and not self.backtestMode:
            if int(last["timestamp"]) > self.last_timestamp:
                logger.info(f"REPORT {self.book.report()}")
                self.last_timestamp =  last["timestamp"] 
        '''
            

    ##########################

  
    async def compute_open(self,symbol,dataframe,local_index,open_count = 15, use_day=True):
        trade_last_hh = self.trade_last_hh
        last = dataframe.iloc[local_index]
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(9,00),get_hour_ms(trade_last_hh,00),use_day):
            #logger.info(f'{last["datetime"]}')

            if self.market.is_in_time(last["datetime"],
                get_hour_ms(9,30),get_hour_ms(trade_last_hh,00),use_day):
                #logger.info(f'{last["datetime"]}')

                is_inside=True
                if not self.has_meta(symbol,"open_gap"):
                    last_close = MetaInfo.get(symbol,"last_close")
                    if not last_close:
                        last_close, ts_last_close=  await self.client.last_close(symbol,last["datetime"] ) 
                    
                    #logger.info(f'last_close {last_close}')

                    if last_close:
                        self.set_meta(symbol,{"open_gap": 100.0* (last["close"] - last_close) / last["close"] })

                        #pre_gain = MetaInfo.get(symbol,"pre_gain")
                        logger.info(f"{symbol} t:{last['datetime']} {self.get_meta(symbol,'open_gap')} close:{last['close']} last_close:{last_close}")

                ###### 15 perc ######

                if self.market.is_in_time(last["datetime"],
                        get_hour_ms(9,45),get_hour_ms(trade_last_hh,00),use_day):

                    if not self.has_meta(symbol,"open_perc"):
                        window = dataframe.iloc[local_index-open_count:local_index]
                        low = window["low"].min()
                        high = window["high"].max()

                        l_h_perc = 100.0 * (high - low) / low

                        first = window.iloc[0]
                        last = window.iloc[-1]

                        perc = 100.0 * (last["close"] - first["open"]) / first["open"]
                        '''
                        first = dataframe.iloc[local_index-15]
                    
                        low = min(first["low"] , prev["low"])
                        high = max(first["high"] , prev["high"])
                                
                        l_h_perc = 100.0* (high-low) / low
                        perc =  100.0 * (prev["close"]- first["open"]) / first["open"]
                        '''
                        #logger.info(f"OPEN {symbol} t:{last['datetime']}  OPEN 15M O:{first['open']}  C:{last['close']} perc:{perc} l_h_perc:{l_h_perc} local_index:{local_index} last_idx: { last.name}")

                        self.set_meta(symbol, 
                                {
                                    "compute_open" : True,
                                "open_high" : high,
                                "open_low": low,
                                "open_perc" : perc, 
                                "open_perc_min_max":l_h_perc,
                                "open_close_idx": local_index,
                                } )
        return self.has_meta(symbol,"open_high" )
    
    async def compute_first_enter(self,symbol,dataframe,local_index, use_day):
            if not self.has_meta(symbol,"first_enter"): 
                
                first_enter = await StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)

                self.set_meta(symbol, {"first_enter": first_enter }) 

                await self.add_marker(symbol,"SPOT","X","#060806","square",position ="atPriceTop",timestamp=first_enter)
