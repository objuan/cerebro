import pandas as pd
import logging
from datetime import datetime, timedelta
from company_loaders import *
from collections import deque

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

# il tick è di 10 secondi 
class TickerHistory:
    def __init__(self,symbol):
        self.symbol= symbol
        self.history =  deque(maxlen=100)
 
    def push(self,ticker):
        if len(self.history) > 0:
            if ticker["ts"] > self.history [-1]["ts"]:
                self.history.append(ticker.copy())
        else:
            self.history.append(ticker.copy())
        
        #logger.info(f"{self.symbol} #{ len(self.history)} last:{ self.history[-1]}")

    def last(self):
        return self.history[-1]
        
    def take_prev(self,back_seconds):
        num = int(back_seconds / 10)
        if len(self.history)> num:
            return self.history[-num]
        else:
            return None

class EventManager:

    def __init__(self, report:ReportManager):
        self.report=report
        self.job = report.job
        self.db = report.db

        self.gain_thresold = 0.1
      
    async def bootstrap(self):
        symbols = await self.job.send_cmd("symbols")
        await self.on_update_symbols(symbols )

        #shapshot_time = self.report.config["reports"]["shapshot_time"]
        #logger.info(f"shapshot_time {shapshot_time}")

        self.scheduler = AsyncScheduler()
        #self.scheduler.schedule_every(shapshot_time,self.take_snapshot, key= "10m")
        #self.df_report =None
        #self.shapshot_history =  deque(maxlen=100)

        self.report.on_snapshot_10m+= self.on_snapshot_10m

        self.ticker_history = {} 
            
        self.job.on_ticker_receive += self._on_ticker_receive    
        

    async def _on_ticker_receive(self,ticker):
        #logger.info(f" _on_ticker_receive {ticker}")

        if not ticker["symbol"] in self.ticker_history:
            self.ticker_history[ticker["symbol"]] =  TickerHistory(ticker["symbol"])
        self.ticker_history[ticker["symbol"]].push(ticker)
    
    async def on_update_symbols(self, symbols):
        pass
        #logger.info(f"Report reset symbols {symbols}")
        #self.symbols=symbols
        #self.live_df = self.job.live_symbols()
        #logger.debug(f"live_df \n{self.live_df}")
 
    async def on_snapshot_10m(self,old_df,new_df):
        try:
            pass
            #logger.info(f"on_snapshot_10m \n{old_df} \n{new_df}")

            #await self.scan_for_up(old_df,new_df,0.1)
            #await  self.scan_for_volatility(old_df,new_df)
        except:
            logger.error("ERROR", exc_info=True)


    async def scan_for_up(self,old_df,new_df, gain_thresold):
        
        for symbol, row in new_df.iterrows():
            current_last = row['last']
            
            # Controlliamo se abbiamo un prezzo precedente per questo simbolo
            if symbol in old_df.index:
                previous_last = old_df.at[symbol, 'last']

                # Calcolo del Gain Percentuale
                # Formula: ((Nuovo - Vecchio) / Vecchio) * 100
                gain = ((current_last - previous_last) / previous_last) * 100

                logger.info(f"{previous_last} -> {current_last} g:{gain}")

                # Se il gain è maggiore di 10 (10%)
                if gain > gain_thresold:
                    await self.send_event("Up 5% in 5Min", new_df)
            

    async def scan_for_volatility(self,old_df,new_df):
        global market_cache
        
        # Parametri Filtro Hunter
        MAX_FLOAT = 5_000_000  # Esempio: Max 5 milioni di azioni (molto basso)
        MIN_GAIN = 10.0        # Gain minimo del 10% per trigger
        MIN_REL_VOL = 2.0      # Almeno il doppio della media
        
        for symbol, row in new_df.iterrows():

            current_last = row['last']
            current_float = row['float']
            rel_vol_5m = row['rel_vol_5m']
            
            # 1. Filtro Preliminare: Il titolo è un "Low Float"?
            if current_float <= MAX_FLOAT:
                
                # 2. Controllo se abbiamo dati precedenti per calcolare la volatilità
                if symbol in old_df.index:
                    previous_last = old_df.at[symbol, 'last']

                    gain = ((current_last - previous_last) / previous_last) * 100
                    
                    # 3. Hunter Trigger: Prezzo + Volume + Float
                    if gain >= MIN_GAIN and rel_vol_5m >= MIN_REL_VOL:
                         await self.send_event("Low Float Volatility", new_df)
                        #alert_volatility_hunter(symbol, row, gain)
                

    async def send_event(self, name, df):
            
            #logger.info(f"SEND EVENT {name} \n{df}")
            full_dict = {
                symbol: {
                    col: self.py_value(df.loc[symbol, col])
                    for col in ["rank","gain","last", "day_v","avg_base_volume_1d","float","rel_vol_24","rel_vol_5m","gap"]
                }
                for symbol in df.index
            }

            #logger.info(f"full_dict \n{full_dict}")
            await self.render_page.send({
                    "type" : "event",
                    "name" : name,
                    "data": full_dict
            })

    async def tick(self,render_page):
        
        try:
            
            
            for symbol,ticker_history in self.ticker_history.items():
                last = ticker_history.last()
                current_last = last["last"]
                # 5min events

                prev_5m = ticker_history.take_prev(20)

                if prev_5m:
                    previous_last = prev_5m["last"]
                    gain = ((current_last - previous_last) / previous_last) * 100

                    logger.info(f"CHECK 5m {gain} ")

                    if gain > self.gain_thresold:
                        await self.send_event("Up 5% in 5Min", self.report.getLastDF().loc[[symbol]])
            '''
            df_10 = self.db.dataframe("10s")
            self.shapshot_history.append(df_10.copy())

            logger.info(f"#{len(self.shapshot_history)}")
            '''

        except:
            logger.error("REPORT ERROR" , exc_info=True)

            
    
    def py_value(self,v):
        if hasattr(v, "item"):
            v = v.item()
        return round(v, 6) if isinstance(v, float) else v