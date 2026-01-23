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
        self.history = deque(maxlen=100)
        self.last_changed= False
        
    def push(self,ticker):
        if len(self.history) > 0:
            if ticker["ts"] > self.history [-1]["ts"]:
                self.history.append(ticker.copy())
                self.last_changed = True
        else:
            self.history.append(ticker.copy())
        
        #logger.info(f"{self.symbol} #{ len(self.history)} last:{ self.history[-1]}")

    def popLast(self):
        if self.last_changed:
            self.last_changed=False
            return self.history[-1]
        else:
            return None
        
    def take_prev(self,back_seconds):
        num = int(back_seconds / 10)
        if len(self.history)> num:
            return self.history[-num]
        else:
            return None

class EventManager:

    def __init__(self, config,report:ReportManager):
        self.report=report
        self.job = report.job
        self.db = report.db

        self.FLOAT_TIME_SECS = config["events"]["FLOAT_TIME_SECS"]
        self.GAIN_5_MIN = config["events"]["GAIN_5_MIN"]

        self.LF_MAX_FLOAT =  config["events"]["LF_MAX_FLOAT"]  # Esempio: Max 5 milioni di azioni (molto basso)
        self.LF_MIN_GAIN =  config["events"]["LF_MIN_GAIN"]        # Gain minimo del 10% per trigger
        self.LF_IN_REL_VOL =  config["events"]["LF_IN_REL_VOL"]      # Almeno il doppio della media
                    
        self.MF_MIN_FLOAT =  config["events"]["MF_MIN_FLOAT"]
        self.MF_MAX_FLOAT =  config["events"]["MF_MAX_FLOAT"]
        self.MF_MAX_PRICE =  config["events"]["MF_MAX_PRICE"]        # Prezzo ancora "sotto il 20%"
        self.MF_MIN_REL_VOL =  config["events"]["MF_MIN_REL_VOL"]      # Volume molto alto (High Rel Vol)

        # 3. Former Momo Stock
        # Titoli che hanno volumi altissimi rispetto alla loro media storica
        # e mostrano un cambio di rank positivo (rank_delta)
        self.MOMO_MIN_REL_VOL_24 = config["events"]["MOMO_MIN_REL_VOL_24"] # Molto volume nelle ultime 24h
        self.MOMO_MIN_GAIN = config["events"]["MOMO_MIN_GAIN"]

        #logger.info(f"gain_5_min_thresold {self.gain_5_min_thresold}")
        
      
    async def bootstrap(self):
        symbols = await self.job.send_cmd("symbols")
        await self.on_update_symbols(symbols )

        #shapshot_time = self.report.config["reports"]["shapshot_time"]
        #logger.info(f"shapshot_time {shapshot_time}")

        #self.scheduler = AsyncScheduler()
        #self.scheduler.schedule_every(shapshot_time,self.take_snapshot, key= "10m")
        #self.df_report =None
        #self.shapshot_history =  deque(maxlen=100)

        #self.report.on_snapshot_10m+= self.on_snapshot_10m

        self.ticker_history_map = {} 
        self.job.on_ticker_receive += self._on_ticker_receive    
        
    async def _on_ticker_receive(self,ticker):
        #logger.info(f" _on_ticker_receive {ticker}")

        if not ticker["symbol"] in self.ticker_history_map:
            self.ticker_history_map[ticker["symbol"]] =  TickerHistory(ticker["symbol"])
        self.ticker_history_map[ticker["symbol"]].push(ticker)
    
    async def on_update_symbols(self, symbols):
        pass
 
    async def on_snapshot_10m(self,old_df,new_df):
        try:
            pass
        except:
            logger.error("ERROR", exc_info=True)

    async def send_current(self,render_page):
            
        df:pd.DataFrame = self.job.get_df("select data from events order by ds_timestamp desc limit 50")
        #dict = df.to_dict(orient="records")
        #logger.info(f"send_current {df}")
        
        arr = []
        for _, row_dict in df.iterrows():
            d = json.loads(row_dict['data'])
            arr.append(d)
            #logger.debug(f"{row_dict['data']}")
            
        arr.reverse()

        #logger.info(f"send_current {arr}")
       
        await self.render_page.send({
                    "type" : "events",
                    "data": arr
            })

    async def send_event(self, symbol, name, df):
            
            #logger.info(f"SEND EVENT {name} \n{df}")
            '''
            full_dict = {
                symbol: {
                    col: self.py_value(df.loc[symbol, col])
                    for col in ["rank","gain","last", "volume","avg_base_volume_1d","float","rel_vol_24","rel_vol_5m","gap","ts"]
                }
                for symbol in df.index
            }
            '''
            rows_list = [
            {
                # Inseriamo il symbol come prima colonna
                "symbol": symbol,
                "name": name,
                # Espandiamo le altre colonne
                **{
                    col: self.py_value(df.loc[symbol, col])
                    for col in ["rank","gain","last", "volume","avg_base_volume_1d","float","rel_vol_24","rel_vol_5m","gap","ts"]
                }
            }
            for symbol in df.index
            ]
            
            #logger.info(f"SEND EVENT {rows_list[0]}")

            query = "INSERT INTO events ( symbol, name, data) values (?,?,?)"
            self.job.execute(query, (symbol, name, json.dumps(rows_list[0]) ))

            #logger.info(f"full_dict \n{full_dict}")
            await self.render_page.send({
                    "type" : "event",
                    "data": rows_list[0]
            })

    async def tick(self,render_page):
        
        try:
            
            
            for symbol,ticker_history in self.ticker_history_map.items():
                last = ticker_history.popLast()
                if not last:
                    continue

                current_last = last["last"]
                # 5min events

                try:
                    df = self.report.getLastDF().loc[[symbol]]
                except:
                    continue

                prev_5m = ticker_history.take_prev(self.FLOAT_TIME_SECS)

                if prev_5m:
                    previous_last = prev_5m["last"]

                    ##### GAIN 5% in 5 min check
                    gain = ((current_last - previous_last) / previous_last) * 100

                    logger.info(f"CHECK 5m {gain} ")

                    if gain > self.GAIN_5_MIN:
                        await self.send_event(symbol,"Up 5% in 5Min", df)
                
                #
                prev_float= ticker_history.take_prev(20)

                if prev_float:
                    #########
                    #Low Float Volatility
                
                     # Parametri Filtro Hunter
                 

                    current_float = df['float'].iloc[0]
                    rel_vol_5m = df['rel_vol_5m'].iloc[0]
                    rel_vol_24 = df['rel_vol_24'].iloc[0]
                    rank_delta =  df['rank_delta'].iloc[0]# row.get('rank_delta', 0)
                    
                  
                    previous_last = prev_float["last"]
                    gain = ((current_last - previous_last) / previous_last) * 100

                    #logger.info(f"CHECK FLOAT g:{gain} 5:{rel_vol_5m} 24:{rel_vol_24} rd:{rank_delta}")

                    # --- STRATEGIA A: LOW FLOAT HUNTER ---
                        
                    # 3. Hunter Trigger: Prezzo + Volume + Float
                    #LF_MAX_FLOAT ??
                    if gain >= self.LF_MIN_GAIN and rel_vol_5m >= self.LF_IN_REL_VOL:
                            await self.send_event(symbol,"Low Float Volatility", df)
                            #alert_volatility_hunter(symbol, row, gain)

                    # --- STRATEGIA B: MEDIUM FLOAT - HIGH REL VOL ---
                    if self.MF_MIN_FLOAT <= current_float <= self.MF_MAX_FLOAT:
                            # Condizione: High Rel Vol E Price under 20
                            if rel_vol_5m >= self.MF_MIN_REL_VOL and current_last < self.MF_MAX_PRICE:
                                 await self.send_event(symbol,"Medium Float-High Rel Vol E Price under 20$", df)
            
                    #--- STRATEGIA 3: FORMER MOMO STOCK ---
                    # Cerchiamo titoli con forte volume relativo giornaliero e segnale di risveglio (rank_delta > 0)
                    if rel_vol_24 > self.MOMO_MIN_REL_VOL_24 and rank_delta >= 0:
                            if gain >= self.MOMO_MIN_GAIN:
                                await self.send_event(symbol,"FORMER MOMO REBORN", df)

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