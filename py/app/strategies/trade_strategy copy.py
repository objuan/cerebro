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
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]

        self.position = Position(10000)
        self.book = OrderBook( self.position )

        self.tradeInfo = {}
        pass

    async def onBackEnd(self):

        logger.info(f"REPORT {self.book.report()}")
        pass


    '''
    def extra_dataframes(self)->List[str]:
        return ['1d']
    '''

    async def buy(self,symbol,price, quantity,time,label=""):
        if self.book.hasCurrentTrade(symbol):
            return

        logger.info(f"BUY {symbol} {label}")
        self.add_marker(symbol,"BUY",label,"#005307FF","arrowUp",position="atPriceBottom")

        #if not self.buyMap[symbol]:
        self.book.long(symbol, price, quantity,label)

        #super().buy(symbol,label)
        if not self.bootstrapMode:
            await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#04FFFF", ring="news")

        
        #self.buyMap[symbol] = {"price": price, "quantity": quantity,"time": time}

    def sell(self,symbol,datetime, price, quantity,time,label=""):

        if self.book.hasCurrentTrade(symbol):
            logger.info(f"SELL .. {symbol} {datetime}")
            self.book.close(symbol,price)
            self.add_marker(symbol, "SPOT", label, "#FF0000", "arrowDown",position="atPriceBottom")

        '''
        #if symbol in self.buyMap and self.buyMap[symbol]:
            buy_data =  self.buyMap[symbol]
            #logger.info(f"SELL .. {buy_data}")
            logger.info(f"SELL {symbol} time{time} gain {self.buyGain(symbol, price)}" )
            self.buyMap[symbol] = {}
            self.add_marker(symbol, "SPOT", label, "#FF0000", "square")
        '''

    def buyGain(self,symbol,close):
        if self.book.hasCurrentTrade(symbol):
            return self.book.gain(symbol,close)
        else:
            return 0
        '''
        if symbol in self.buyMap and self.buyMap[symbol]:   
            buy_price = self.buyMap[symbol]["price"]
            return 100.0 * (close- buy_price) / buy_price
        else:
            return 0
        '''
    def setSL(self,symbol, price):
        self.set_meta(symbol,{"SL": price})

    def setTP(self,symbol, price):
        self.set_meta(symbol,{"TP": price})

    def populate_indicators(self) :
     
        sma_20= self.addIndicator(self.timeframe,SMA("SMA_20","close",20))
        sma_200= self.addIndicator(self.timeframe,SMA("SMA_200","close",200))
        
        
        diff = self.addIndicator(self.timeframe, DIFF_PERC("DIFF","SMA_200","SMA_20" ))
        gain= self.addIndicator(self.timeframe,GAIN("GAIN","close",1))

        max= self.addIndicator(self.timeframe,MAX("MAX","close",60))

        trend = self.addIndicator(self.timeframe, TREND_LIMIT("TREND","DIFF" ))


        max_perc= self.addIndicator(self.timeframe,MAX_ALL("DIFF_ALL","DIFF"))

        #day_perc= self.addIndicator(self.timeframe,GAIN("DGAIN","day_volume",1))

        day_volume_ticker = self.addIndicator(self.timeframe,COPY("day_volume_ticker","day_volume"))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))

        #self.add_legend(sma_9_gain,"SMA_9_G", "sma9 G", "#034cd3")
        #self.add_legend(sma_20_gain,"SMA_20_G", "sma20 G", "#034cd3")
        
        
        self.add_plot(sma_20, "SMA_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_200, "SMA_200","#034cd3", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(max, "MAX","#926B00FF", "main", source="MAX",style="Solid", lineWidth=1)

        #self.add_plot(day, "day","#d30303", "sub1", style="Solid", lineWidth=1)
        self.add_plot(day_volume_ticker, "day_volume_ticker","#0318d3", "sub1", style="Solid", lineWidth=1)
        self.add_plot(day_volume_history, "day_volume_history","#d3035a", "sub1", style="Solid", lineWidth=1)


    ######################################

    async def send_trade_order(self,symbol:str,type:str,side:str, quantity:str, price, tp, sl,  desc:str):
        if self.backtestMode: return

        await self.client.send_strategy_trade("strategy-trade",symbol,self.timeframe,
                 {"type":type,"price_op":side,"quantity": quantity
                  ,"price": price,"take_profit": tp,"stop_loss":sl,"desc": desc})
       
    async def send_trade_bracket(self, symbol:str,datetime,side:str, quantity:str, price, tp, sl,  desc:str):
        if self.backtestMode: return

        logger.info(f"BUY  {symbol} {datetime} s:{side} p:{price} tp:{tp} sl:{sl}")
        await self.send_trade_order(symbol,"bracket",side,quantity,price,tp, sl, desc )
        
    async def on_all_candle(self, dataframe: pd.DataFrame,global_index) :
        
        return
        #last = dataframe.loc[global_index]
     
        #logger.info(f"last {last}")
     
        last = dataframe.loc[global_index]
        last_date = last["datetime"]
        last_ts = int(last["timestamp"])
        #ny_time = last_date.astimezone(ZoneInfo("America/New_York"))
        #it_time = last_date.astimezone(ZoneInfo("Europe/Rome"))

        #symbol = last["symbol"]
      
  
        if self.market.is_in_time(last["datetime"],
            get_hour_ms(8,0),get_hour_ms(12,0),True):

            logger.info(f" ny_time {last_date} {last_ts} idx:{global_index} ")

            df_now = dataframe[
                (dataframe["timestamp"] == last_ts) &
                (dataframe["day_volume_history"] > 100_000) &
                (dataframe["GAIN"] > 0)
            ]
            gain_snap = df_now.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
            
            #logger.info(f"gain_snap \n{gain_snap}")

            if len(gain_snap)>0 and not self.book.has_any_trade():
                first = gain_snap.iloc[0]

                logger.info(f"BUY  {last_date} \n{gain_snap}")

                symbol = first["symbol"]
                
                RR = 3
                mx_loss_perc = 0.25  # 25%

                max_loss = last["close"] * mx_loss_perc

                sl = last["close"] - max_loss
                tp = last["close"] + max_loss * RR
                
                self.setSL(symbol,sl)
                self.setTP(symbol,tp)


                logger.info(f"TP  {tp} sl:{sl}")
                
                self.book.long(symbol, last["close"], 100,"G")



            if self.book.has_any_trade():

                    trade = self.book.get_first_trade()

                    
                    df_last = dataframe[
                            (dataframe["timestamp"] == last_ts) &
                            (dataframe["symbol"] == trade.symbol) 
                        ]
                            
                    if len(df_last)>0:
                        last = df_last.tail(1).iloc[0]

                        symbol = trade.symbol
                        
                        close = last["close"]

                        gain = self.buyGain(trade.symbol,close)

                        logger.info(f"LAST TRADE {trade.symbol} {last['datetime']} tp:{self.get_meta(symbol,'TP')} c:{last['close']} gain:{gain} ")
                
                        if close > self.get_meta(symbol,"TP"):
                            #logger.info(f"TP {self.get_meta(symbol,'TP')}")
                            #self.sell(symbol,last["datetime"],close,100,last["datetime"],"TP")
                            logger.info(f"SELL .. {symbol} {last_date}")
                            self.book.close(symbol,last['close'])
                        elif close < self.get_meta(symbol,"SL"):
                            #logger.info(f"SL {self.get_meta(symbol,'SL')}")
                            #self.sell(symbol,last["datetime"],close,100,last["datetime"],"SL")
                            logger.info(f"SELL .. {symbol} {last_date}")
                            self.book.close(symbol,last['close'])
        return
        
        '''
            # apertura
            if (ny_time.hour == 9 and ny_time.minute == 30):
                self.open = df_now.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
                self.open["pos"] = range(1, len(self.open) + 1)
                self.open["last_close"] = 0
                for idx, row in self.open.iterrows():
                    last_close, ts_last_close=  await self.client.last_close(symbol)
                    self.open.at[idx, "last_close"] = last_close

            #self.open["last_open"] = MetaInfo.get_meta()

            if (ny_time.hour == 9 and ny_time.minute == 45):
                self.open_15 = df_now.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
                self.open_15["pos"] = range(1, len(self.open_15) + 1)

            if (ny_time.hour == 10 and ny_time.minute == 00):
                self.open_30 = df_now.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
                self.open_30["pos"] = range(1, len(self.open_30) + 1)

                # report

                # gain 15 
                df15 = self.open[["symbol","close","pos"]].merge(
                    self.open_15[["symbol","close","pos"]],
                    on="symbol",
                    suffixes=("_open","_15")
                )

                df15["gain_15m"] = (df15["close_15"] - df15["close_open"]) / df15["close_open"] * 100

                #gain 30

                df30 = self.open[["symbol","close","pos"]].merge(
                    self.open_30[["symbol","close","pos"]],
                    on="symbol",
                    suffixes=("_open","_30")
                )

                df30["gain_30m"] = (df30["close_30"] - df30["close_open"]) / df30["close_open"] * 100

                logger.info(f"open \n{self.open}")
                logger.info(f"df15 \n{df15}")
                logger.info(f"df30 \n{df30}")
                #d = dataframe.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
                #d = d.head(5)



        if not self.backtestMode and not self.bootstrapMode:
            d = dataframe.groupby("symbol").tail(1).sort_values("GAIN", ascending=False)
            #logger.info(f">>  \n{d}" )  

           # logger.info(f"live  {symbol} it:{it_time} ny:{ny_time}")

            #logger.info(f">>  \n{dataframe.tail(5)}" )  
        '''
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
      
     

        #if not self.bootstrapMode:
        #    logger.info(f"REPORT {self.book.report()}")

      
        if local_index<5:
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        if not self.bootstrap:
            logger.info(f">> {type(last['datetime'])} trade_symbol_at \n{dataframe.tail(5)}" )  

        #day_volume = last["day_volume"]
        #if day_volume== 0:
        day_volume = last["day_volume_history"]

        #logger.info(f">> day_volume {day_volume}" )  

        day_volume_gain=0
        #if prev["day_volume"]!=0:
        #    day_volume_gain = 100.0 * (day_volume -  prev["day_volume"] ) /  prev["day_volume"]
        if prev["day_volume_history"]!=0:
            day_volume_gain = 100.0 * (day_volume -  prev["day_volume_history"] ) /  prev["day_volume_history"]

        close =  last["close"]
        prev_close =  prev["close"]
        SMA_200 =  last["SMA_200"]
        SMA_20 =  last["SMA_20"]
        MAX =  prev["MAX"] 
        diff_all =  prev["DIFF_ALL"] 
        diff_perc =  last["DIFF"] 
        trend =  last["TREND"]
        trend_prev =  prev["TREND"]

        close_sma_gain = 100.0 * ((close - SMA_20 ) /  SMA_20)
  
        break_max = close > MAX and prev_close <= MAX

        ###

        ## US TIME
        trade_last_hh = 11

        #if not self.backtestMode and not self.bootstrapMode:
             #logger.info(f">> {symbol} {local_index} m:{minutes} \n{dataframe.tail(5)}" )  
        is_inside=False
        #use_day=datetime.now().hour  >= 14
        #UTF
        if self.backtestMode:
            use_day=False
        else:
            use_day = True#last["datetime"].hour >= 13
        ##
        #logger.info(f'{last["datetime"].hour}')

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

                    if not self.has_meta(symbol,"open_15m_perc"):
                        window = dataframe.iloc[local_index-15:local_index]
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
                        logger.info(f"{symbol} t:{last['datetime']}  OPEN 15M O:{first['open']}  C:{last['close']} perc:{perc} l_h_perc:{l_h_perc} local_index:{local_index} last_idx: { last.name}")

                        self.set_meta(symbol, 
                                {"open_15m_high" : high,
                                "open_15m_low": low,
                                "open_15m_perc" : perc, 
                                "open_15m_perc_lh":l_h_perc,
                                "open_15m_close_idx": local_index,
                                } )
                        
                    if True:
                        if self.get_meta(symbol,"open_15m_perc_lh") > 5 and day_volume > 500_000:
                            if not self.book.hasCurrentTrade(symbol) :
                                RR = 3
                                mx_loss_perc = 0.25

                                max_loss =(self.get_meta(symbol,"open_15m_high") - self.get_meta(symbol,"open_15m_low")) * mx_loss_perc
                                
                                open_15m_perc_lh =  self.get_meta(symbol,"open_15m_perc_lh")
                                open_15m_close_idx =  self.get_meta(symbol,"open_15m_close_idx")
                                
                                window = dataframe.iloc[open_15m_close_idx:local_index-1]
                                int_high = window["high"].max()

                                candle_perc = 100.0 * (last["high"] -  last["low"] ) /  last["low"]
                                mid = (last["high"] -  last["low"] ) /2 +  last["low"] 
                                if candle_perc > open_15m_perc_lh * mx_loss_perc and last["close"] > last["open"] and last["close"]  > mid:
                                    self.add_marker(symbol,"W","W","#060806","small_square",position ="atPriceTop")
                                    
                                    if symbol =="ORBS":
                                        logger.info(f' t:{last["datetime"]} int_high: {int_high} close: {last["close"]} {open_15m_close_idx} {local_index-1}')

                                    if last["close"]> int_high:
                                        self.add_marker(symbol,"M","M","#000000","small_square",position ="atPriceBottom")

                                        sl = last['close'] - max_loss
                                        tp = last['close'] + max_loss * RR

                                        self.add_marker(symbol, "TP", "TP", "#0026FF","TP",value=tp)
                                        self.add_marker(symbol, "SL", "SL", "#0026FF","SL",value=sl)

                                        self.setSL(symbol,sl)
                                        self.setTP(symbol,tp)
                                        
                                        await self.send_trade_bracket(symbol,last["datetime"],"BUY", 100, last['close'], tp, sl, "test")

                                        await self.buy(symbol,last["close"], 100,last["datetime"] ,f"15^")
                                    

                        
                #######
                # LOGIC   #
                if self.has_meta(symbol,"open_15m_perc"):
                    open_15m_perc =  self.get_meta(symbol,"open_15m_perc")
                    open_15m_perc_lh =  self.get_meta(symbol,"open_15m_perc_lh")

                    #logger.info(f'ok {symbol} {last['datetime']} v:{day_volume} {open_15m_perc_lh}')

                    if open_15m_perc_lh > 5 and day_volume > 500000:
                        #logger.info(f"{symbol} PROCESS perc:{open_15m_perc} l_h_perc:{open_15m_perc_lh}")
                        
                        #await self.send_event(symbol, "15M", f"15M",f"15M",color="#04FFFF", ring="news")


                        ######### LOGIC 1 ########
                      
                        ######### LOGIC 2 ########
                        if False:
                            h = self.get_meta(symbol,"open_15m_high")
                            if last["close"] > h and break_max:
                                #logger.info(f"{symbol} BREAK 15 UP ")
                                #break
                                #RISK
                            
                                if not self.book.hasCurrentTrade(symbol):
                                    RR = 3
                                    mx_loss_perc = 0.25
                                    max_loss =(self.get_meta(symbol,"open_15m_high") - self.get_meta(symbol,"open_15m_low")) * mx_loss_perc
                                    sl = last['close'] - max_loss
                                    tp = last['close'] + max_loss * RR

                                    self.add_marker(symbol, "TP", "TP", "#0026FF","TP",value=tp)
                                    self.add_marker(symbol, "SL", "SL", "#0026FF","SL",value=sl)

                                    self.setSL(symbol,sl)
                                    self.setTP(symbol,tp)
                                    
                                    #logger.info(f"close {last['close']}")
                                    #logger.info(f"sl {sl}")
                                    #logger.info(f"tp {tp}")

                                    await self.send_trade_bracket(symbol,"BUY", 100, last['close'], tp, sl, "test")

                                    await self.buy(symbol,last["close"], 100,last["datetime"] ,f"15^")
                                
                            #await self.send_event(symbol, "15 ^", f"15 break up",f"15 break up",color="#A01010", ring="news")
            else:
                # sell existing
                if self.has_meta(symbol,"open_15m_perc"):
                    if self.book.hasCurrentTrade(symbol):
                         self.sell(symbol,close,100,last["datetime"],"OUT")
                         
                self.set_meta(symbol,{})

        #low =  last["low"]
        #high =  last["high"]
        #day_volume = last["day_volume"] # va solo per LIVE


        #if not is_inside:
        if self.book.hasCurrentTrade(symbol):
            if close > self.get_meta(symbol,"TP"):
                #logger.info(f"TP {self.get_meta(symbol,'TP')}")
                self.sell(symbol,last["datetime"],close,100,last["datetime"],"TP")
            elif close < self.get_meta(symbol,"SL"):
                #logger.info(f"SL {self.get_meta(symbol,'SL')}")
                self.sell(symbol,last["datetime"],close,100,last["datetime"],"SL")
        #if abs(self.buyGain(symbol,close))>2:
        #        self.sell(symbol,close,100,last["datetime"],"SELL")


        ######### TRADE
        '''
        if day_volume_gain>10 and day_volume > 100000:
            if (SMA_20 > SMA_200 and prev["SMA_20"]
                and close > SMA_20 and diff_perc < 5  ):
                    self.buy(symbol,close, 100,last["datetime"] ,"VOL")
        '''
        ##### VOL BREAK
        if day_volume_gain>10 and day_volume > 300000:
             await self.send_event(symbol, "VOL", f"VOL 10",f"VOL 10%",color="#10A02F", ring="")

        #SMA CROSS
        if day_volume > 500_000:
            '''
            if (SMA_20 > SMA_200 and prev["SMA_20"] <= prev["SMA_200"]
                and   SMA_200 > prev["SMA_200"]):
                await self.send_event(symbol, "SMA", f"SMA CR",f"SMA over ",color="#0AD8F3", ring="news")
            '''
            if (break_max ):
                if close < SMA_200:
                    await self.send_event(symbol, "MAX", f"max cross <",f"max over ",color="#31F30A", ring="alert1")
                else:
                    await self.send_event(symbol, "MAX", f"max cross >",f"max over ",color="#F3A90A", ring="chime")

        await self.set_property(symbol,self.timeframe , 
                                 {"trend_len": trend if  not pd.isna(trend) else 0,
                                "trend_perc" :diff_perc if  not pd.isna(diff_perc) else 0,
                                 "trend_perc_all" :diff_all if  not pd.isna(diff_all) else 0} )

        if not self.bootstrapMode and not self.backtestMode:
            logger.info(f"REPORT {self.book.report()}")



            
  
  