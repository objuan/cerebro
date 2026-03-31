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



class OrderBook:

    def __init__(self, position):

        self.orders = []
        self.trades = []
        self.position = position
        self.currentOrder={}

    def end(self, onClose=None):
        list = [x for x in self.currentOrder.keys()]
        for symbol in list:
            order = self.currentOrder[symbol]
            trade = self.close(symbol, self.position.cur_price[symbol])
            if onClose:
                onClose(trade)

    def lastOrder(self):
        return self.orders[-1] if self.orders else None
    
    def hasCurrentTrade(self,symbol):
        return symbol in self.currentOrder

    def has_any_trade(self):
        return bool(self.currentOrder)

    def get_first_trade(self):
        return next(iter(self.currentOrder.values()), None)
    
    def long(self, symbol, price, quantity, label):

        if self.position.open_long(symbol, float(price), float(quantity)):

            order = Order(symbol, "long",float(price), float(quantity), label)
            self.orders.append(order)
            self.currentOrder[symbol] = order
            return order

    def short(self, symbol, price, quantity, label):

        if self.position.open_short(symbol, float(price), float(quantity)):

            order = Order(symbol, "short",float(price), float(quantity), label)
            self.orders.append(order)
            return order

    def close(self, symbol, price) -> Trade:

        if symbol not in self.position.positions:
            return

        qty = self.position.positions[symbol]
        entry = self.position.entry_price[symbol]

        side = "long" if qty > 0 else "short"

        trade = Trade(symbol, entry, float(price), abs(qty), side)

        self.trades.append(trade)

        self.position.close(symbol, float(price))

        del self.currentOrder[symbol]

        return trade

    def gain(self, symbol, actual_price):

        if symbol not in self.position.positions:
            return None
       
        qty = self.position.positions[symbol]
        entry = self.position.entry_price[symbol]

        gain =  100.0 * (actual_price- entry) / entry
        self.position.positions[symbol] = qty
        return gain
    
    def set_current_price(self, symbol, price): 
        if symbol not in self.position.positions:
            return None
        self.position.set_current_price(symbol, price)  

    def report(self):

        total_pnl = sum(t.pnl() for t in self.trades)

        total_gain = sum(t.gain() for t in self.trades)

        wins = [t for t in self.trades if t.pnl() > 0]
        losses = [t for t in self.trades if t.pnl() <= 0]

        win_rate = len(wins) / len(self.trades) if self.trades else 0

        avg_gain = sum(t.pnl() for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl() for t in losses) / len(losses) if losses else 0

        opens=[]
        try:
            profit_factor = (
                sum(t.pnl() for t in wins) /
                abs(sum(t.pnl() for t in losses))
                if losses else 0
            )
        except:
            profit_factor=0


        for symbol in self.currentOrder.keys():
            order = self.currentOrder[symbol]
            d = self.virtual_close(symbol,order,float(self.position.cur_price[symbol]))
            opens.append(d)

        # -------- REPORT GLOBALE --------
        report = {
            "start_budget": self.position.start_budget,
            "final_equity": self.position.equity(),
            "total_gain": total_gain,
            "total_pnl": total_pnl,
            "trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_gain": avg_gain,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "opens" : opens
        }

        # -------- REPORT PER SYMBOL --------
        trades_by_symbol = defaultdict(list)

        for t in self.trades:
            trades_by_symbol[t.symbol].append(t)

        symbol_report = {}

        for symbol, trades in trades_by_symbol.items():

            wins = [t for t in trades if t.pnl() > 0]
            losses = [t for t in trades if t.pnl() <= 0]

            pnl_total = sum(t.pnl() for t in trades)

            symbol_report[symbol] = {
                "trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) if trades else 0,
                "total_pnl": pnl_total,
                "avg_gain": sum(t.pnl() for t in wins) / len(wins) if wins else 0,
                "avg_loss": sum(t.pnl() for t in losses) / len(losses) if losses else 0,
                "profit_factor": (
                    sum(t.pnl() for t in wins) /
                    max(1,abs(sum(t.pnl() for t in losses)))
                    if losses else 1
                ),
                "trade" : [ x.toDict() for x in trades],
            }
        
      
        report["by_symbol"] = symbol_report

        return report

    def virtual_close(self, symbol, order,price):

        if symbol not in self.position.positions:
            return None

        qty = order.quantity
        entry = order.price
        exit =   price

        if qty > 0:
            pnl = (price - entry) * qty
        else:
            pnl = (entry - price) * abs(qty)

        data = {
            "symbol": symbol,
            "price": price,
           "exit" :exit,
           "entry": entry,
           "qty" : qty,
           "gain" : 100.0 * (exit-entry ) / entry,
           "pnl" : pnl
        }
        return data
        
    


########################

class TradeStrategy(SmartStrategy):

    async def on_start(self):
        
        self.book = OrderBook( self.position )

        self.volume_min_filter= self.params["volume_min_filter"]
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
     
        sma_20= self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
        sma_200 = self.addIndicator(self.timeframe,SMA("sma_200","close",timeperiod=200))
        self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))

        self.add_plot(sma_20, "sma_20","#a70000", "main", style="SparseDotted", lineWidth=2)
        self.add_plot(sma_200, "sma_200","#034cd3", "main", style="SparseDotted", lineWidth=2)

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
        prev = dataframe.iloc[local_index-1]
        sma_20 = last["sma_20"]   
        sma_200 = last["sma_200"]   
        volume = last["day_volume_history"]    

        if local_index<60:
            return
        self.book.set_current_price(symbol, last["close"])    
        
        ##### FIRST ENTER ######
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

            if volume > self.volume_min_filter:#and int(last["timestamp"]) >= self.get_meta(symbol,"first_enter") :
                
                if not self.has_meta(symbol,"volume"):
                    self.set_meta(symbol,{"volume":"OK"})
                    self.add_marker(symbol,"SPOT","VOL","#0A0038","small_square",position ="atPriceTop")
                    if not self.bootstrapMode:
                            await self.send_event(symbol, "VOL", f"VOL > {self.volume_min_filter}", f"VOL > {self.volume_min_filter}",color="#BB0B46", ring="news")


                #logger.info(f"TRADE {symbol} {dataframe.iloc[local_index]['timestamp']}  valid {self.has_meta(symbol,'valid')}  buy_time {self.get_meta(symbol,'buy_time')}")    

                if  not self.has_meta(symbol,"valid") and not self.book.hasCurrentTrade(symbol):
                    #self.set_meta(symbol, {"valid": True }) 

                    trend_up =  sma_200 > dataframe.iloc[local_index-60:local_index]["sma_200"].max()

                    gain = last["gain"]
                    # incrocio sma 20 200 rialzista 
                    if  gain < self.gain_perc/2 and last["close"] > sma_20 and sma_20 > sma_200 and prev["sma_20"] < prev["sma_200"] and trend_up  :
                        self.set_meta(symbol, {"valid": True }) 
                        buy_price = dataframe.iloc[local_index]["close"]
                        dt = dataframe.iloc[local_index]["datetime"]

                        await self.buy(symbol, last["datetime"], buy_price,self.get_quantity(buy_price), f"BUY"  )

                
                if self.book.hasCurrentTrade(symbol) and self.has_meta(symbol,"valid"):
                    
                        
                        gain = self.book.gain(symbol, last["close"]) 
                        dt = last["datetime"]

                        #self.book.set_current_price(symbol, last["close"])           
                        #logger.info(f"gain {symbol} {dt} gain {gain}")

                        if gain < -self.gain_perc:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"SL"  )
                        elif gain > self.gain_perc:
                            trade = await self.sell(symbol, dt, last["close"], -1, f"TP"  )


                        '''
                        logger.info(f"TIME  {symbol}  {dt}  ") 

                        if not self.market.is_in_time(last["datetime"],
                             get_hour_ms(0,0),get_hour_ms(self.trade_last_hh,0),use_day):
                                
                                trade = self.book.close(symbol, last["close"])
                                logger.info(f"SELL TIME  {symbol}  {dt}   gain {gain} pnl : {trade.pnl()}")   

                                self.add_marker(symbol,"BUY","TM","#000000","arrowDown")
                        '''

        #pattern LOGIC

        if not self.has_meta(symbol,"valid"):

            if volume > self.volume_min_filter:
                for n  in [5,4,3]:  
                    valid,min_low,max_high,gain_perc =  self.check_pattern(dataframe,local_index,n,5)
                    if valid:
                        logger.info(f"PATTERN {symbol} {last['datetime']} pattern {n} candles")
                        self.add_marker(symbol,"SPOT",f"M_{n} {gain_perc:.0f}%","#060806","small_square",position ="atPriceTop")

                        patt = { "idx": local_index, "type": n, "candle": last,"min_low":min_low,"max_high":max_high ,"gain":gain_perc   }
                        self.set_meta(symbol, {"pattern":patt } ) 

                        if not self.bootstrapMode:
                            await self.send_event(symbol, "PAT", f"PAT {n}", f"PAT {n}",color="#BB750B", ring="news")

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

        if not self.bootstrapMode and not self.backtestMode:
            logger.info(f"REPORT {self.book.report()}")
            

    ##########################
    def check_pattern(self,dataframe, local_index, N,min_gain):
        if local_index < N - 1:
            return (False,0,0,0)

        window = dataframe.iloc[local_index - N  : local_index+1 ]

        # Separo ultime e precedenti
        prev_candles = window.iloc[:-1]
        last = window.iloc[-1]

        # 1. Controllo che le prime N-1 siano rosse
        if not (prev_candles['close'] < prev_candles['open']).all():
            return (False,0,0,0)

        # 2. Ultima verde
        if not (last['close'] > last['open']):
            return (False,0,0,0)

        # 3. Altezza ultima candela
        last_height = abs(last['close'] - last['open'])

        # 4. Range min/max delle N candele
        max_high = prev_candles['high'].max()
        min_low = prev_candles['low'].min()
        total_range = max_high - min_low
        gain_perc = 100.0 * (total_range / min_low)

        # Evita divisioni strane
        if total_range == 0:
            return (False,0,0,0)

        # 5. Condizione finale
        return (gain_perc > min_gain and last_height >= (total_range / 3)  
            and last_height < total_range  
            and last['close'] < max_high,
            min_low,
            max_high,gain_perc)