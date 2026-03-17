from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        self.eta= self.params["eta"]
        self.min_gain= self.params["min_gain"]

        self.buyMap = {}
        pass

    '''
    def extra_dataframes(self)->List[str]:
        return ['1d']
    '''

    def buy(self,symbol,price, quantity,time,label=""):
        if not symbol in self.buyMap :
             self.buyMap[symbol] = {}

        if not self.buyMap[symbol]:
            super().buy(symbol,label)
            self.buyMap[symbol] = {"price": price, "quantity": quantity,"time": time}

    def buyGain(self,symbol,close):
        if symbol in self.buyMap and self.buyMap[symbol]:   
            buy_price = self.buyMap[symbol]["price"]
            return 100.0 * (close- buy_price) / buy_price
        else:
            return 0

    def sell(self,symbol,price, quantity,time,label=""):

        if symbol in self.buyMap and self.buyMap[symbol]:
            buy_data =  self.buyMap[symbol]
            #logger.info(f"SELL .. {buy_data}")
            logger.info(f"SELL {symbol} time{time} gain {self.buyGain(symbol, price)}" )
            self.buyMap[symbol] = {}
            self.add_marker(symbol, "SPOT", label, "#FF0000", "square")

            
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
    async def send_property(self,symbol:str, timeframe ,  value ):
        if not self.backtestMode and not self.bootstrapMode:
            #logger.info("send")
            await self.client.send_strategy_prop("TRADE", symbol,timeframe,value)
        else:
            #logger.info(f"send1 {self.backtestMode} {self.bootstrapMode}")
            pass
            #self.add_marker(symbol,"SPOT",name,"#060806","square",position ="atPriceTop")
    
  
        


    async def on_all_candle(self, dataframe: pd.DataFrame,global_index) :
        
        return
    
        last = dataframe.loc[global_index]
        last_date = last["datetime"]
        #ny_time = last_date.astimezone(ZoneInfo("America/New_York"))
        #it_time = last_date.astimezone(ZoneInfo("Europe/Rome"))

        symbol = last["symbol"]
      
        df_now = dataframe[dataframe["timestamp"] <= last["timestamp"]]

        ny_time , is_inside = self.is_in_time(last_date,get_hour_ms(9,30),get_hour_ms(10,00))

        if is_inside:
            logger.info(f" ny_time {ny_time}")
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

    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
      
      
        if local_index<5:
            return

        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

        day_volume = last["day_volume"]
        if day_volume== 0:
             day_volume = last["day_volume_history"]

        #if not self.backtestMode and not self.bootstrapMode:
             #logger.info(f">> {symbol} {local_index} m:{minutes} \n{dataframe.tail(5)}" )  
        is_inside=False
        use_day=True
        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(9,00),get_hour_ms(10,00),use_day):
            
            if self.market.is_in_time(last["datetime"],
                get_hour_ms(9,30),get_hour_ms(10,00),use_day):
                is_inside=True
                if not self.has_meta(symbol,"open_gap"):
                    last_close = MetaInfo.get(symbol,"last_close")
                    if last_close:
                        self.set_meta(symbol,{"open_gap": 100.0* (last["close"] - last_close) / last["close"] })

                        #pre_gain = MetaInfo.get(symbol,"pre_gain")
                        logger.info(f"{symbol} t:{last['datetime']} {self.get_meta(symbol,'open_gap')} close:{last['close']} last_close:{last_close}")

                ###### 15 perc ######

                if self.market.is_in_time(last["datetime"],
                        get_hour_ms(9,45),get_hour_ms(10,00),use_day):

                    if not self.has_meta(symbol,"open_15m_perc"):
                        first = dataframe.iloc[local_index-15]
                    
                        low = min(first["low"] , prev["low"])
                        high = max(first["high"] , prev["high"])
                                
                        l_h_perc = 100.0* (high-low) / low
                        perc =  100.0 * (prev["close"]- first["open"]) / first["open"]

                        logger.info(f"{symbol} OPEN 15M perc:{perc} l_h_perc:{l_h_perc}")

                        self.set_meta(symbol, 
                                {"open_15m_high" : high,
                                "open_15m_low": low,
                                "open_15m_perc" : perc, 
                                "open_15m_perc_lh":l_h_perc} )
                #######
                # LOGIC #
                if self.has_meta(symbol,"open_15m_perc"):
                    open_15m_perc =  self.get_meta(symbol,"open_15m_perc")
                    open_15m_perc_lh =  self.get_meta(symbol,"open_15m_perc_lh")
                    if open_15m_perc_lh > 5 and day_volume > 500000:
                        #logger.info(f"{symbol} PROCESS perc:{open_15m_perc} l_h_perc:{open_15m_perc_lh}")
                        
                        #await self.send_event(symbol, "15M", f"15M",f"15M",color="#04FFFF", ring="news")

                        h = self.get_meta(symbol,"open_15m_high")
                        if last["close"] > h:
                            logger.info(f"{symbol} BREAK 15 UP ")
                            #break
                            self.buy(symbol,last["close"], 100,last["datetime"] ,"15^")
                            await self.send_event(symbol, "BUY", f"BUY",f"BUY",color="#04FFFF", ring="news")

                            #await self.send_event(symbol, "15 ^", f"15 break up",f"15 break up",color="#A01010", ring="news")
            else:
                self.set_meta(symbol,{})

        #low =  last["low"]
        #high =  last["high"]
        #day_volume = last["day_volume"] # va solo per LIVE
        day_volume_gain=0
        if prev["day_volume"]!=0:
            day_volume_gain = 100.0 * (day_volume -  prev["day_volume"] ) /  prev["day_volume"]
        elif prev["day_volume_history"]!=0:
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

        if not is_inside:
            if abs(self.buyGain(symbol,close))>10:
                self.sell(symbol,close,100,last["datetime"],"SELL")


        ######### TRADE
        '''
        if day_volume_gain>10 and day_volume > 100000:
            if (SMA_20 > SMA_200 and prev["SMA_20"]
                and close > SMA_20 and diff_perc < 5  ):
                    self.buy(symbol,close, 100,last["datetime"] ,"VOL")
        '''
        ##### VOL BREAK
        if day_volume_gain>10 and day_volume > 100000:
             await self.send_event(symbol, "VOL", f"VOL 10",f"VOL 10%",color="#10A02F", ring="news")

        #SMA CROSS
        if day_volume > 1_000_000:
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

        await self.send_property(symbol,self.timeframe , 
                                 {"trend_len": trend if  not pd.isna(trend) else 0,
                                "trend_perc" :diff_perc if  not pd.isna(diff_perc) else 0,
                                 "trend_perc_all" :diff_all if  not pd.isna(diff_all) else 0} )



            
  
  