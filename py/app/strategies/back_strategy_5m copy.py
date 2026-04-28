from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategies.strategy_utils import StrategyUtils
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
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

'''
1. Indicatori Necessari

    EMA 9 (Fast) & EMA 21 (Slow): Per identificare la direzione del trend immediato.

    VWAP (Volume Weighted Average Price): Fondamentale per capire se il prezzo è "caro" o "economico" rispetto alla giornata.

    Stochastic RSI (14, 14, 3, 3): Per individuare i punti di ingresso precisi in ipervenduto/ipercomprato durante un trend.

    ATR (Average True Range): Per impostare uno stop loss dinamico basato sulla volatilità attuale.

2. Regole di Ingresso (Long)

    Trend: Il prezzo deve essere sopra la EMA 21 e la VWAP.

    Setup: La EMA 9 deve incrociare verso l'alto la EMA 21 (o restare stabilmente sopra).

    Trigger: Aspetta un ritracciamento in cui il prezzo tocca la EMA 9 o 21, mentre lo Stochastic RSI scende sotto il livello 20 (ipervenduto) e poi incrocia verso l'alto.

    Conferma: La candela di ingresso deve chiudere sopra il massimo della candela precedente.

3. Gestione del Rischio (Il segreto della profittabilità)

    Stop Loss: Posizionato sotto l'ultimo minimo locale o a 1,5×ATR dal punto di ingresso.

    Take Profit: Rapporto Rischio/Rendimento di 1:1.5. In un mercato trending come quello di aprile 2026, molti trader chiudono metà posizione a 1:1 e lasciano correre il resto usando un trailing stop sulla EMA 21.
'''
class TRADE_DATE(Indicator):
    def __init__(self, target):
        super().__init__([target])
        self.target=target
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        # 1. Riferimenti agli array numpy per le performance ⚡
        dest = dataframe[self.target].to_numpy()
        source = dataframe["timestamp"].to_numpy()

        # 2. Definiamo il range di calcolo
        # Partiamo da from_local_index per non ricalcolare il passato
        start = max(0, from_local_index)
        
        # 3. Estraiamo e convertiamo solo i nuovi timestamp
        # Se source è in secondi, unit='s'. Se millisecondi, unit='ms'
        new_timestamps = source[symbol_idx[start:]]
        new_dates = pd.to_datetime(new_timestamps, unit='ms').strftime('%Y%m%d').astype(int)

        #logger.info(f"{new_dates}")
        # 4. Assegnazione incrementale
        for i, i_idx in enumerate(range(start, len(symbol_idx))):
            idx = symbol_idx[i_idx]
            dest[idx] = new_dates[i]

             
class VWAP(Indicator):
    def __init__(self, target_col, price_col: str, volume_col: str):
        super().__init__([target_col])
        self.price_col = price_col
        self.volume_col = volume_col
        self.target_col = target_col
        self.cum_pv = {}    # Somma cumulativa di (Prezzo * Volume)
        self.cum_vol = {}   # Somma cumulativa del Volume
        # Non serve più self.first perché usiamo la colonna 'date'

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        # Estraiamo i dati necessari come array numpy per la velocità ⚡
        dates = dataframe["date"].to_numpy()
        prices = dataframe[self.price_col].to_numpy()
        volumes = dataframe[self.volume_col].to_numpy()
        dest = dataframe[self.target_col].to_numpy()
            
        start = max(0, from_local_index)

        # Inizializziamo gli accumulatori per il simbolo se non esistono
        if symbol not in self.cum_pv:
            self.cum_pv[symbol] = 0.0
            self.cum_vol[symbol] = 0.0

        for i_idx in range(start, len(symbol_idx)):
            idx = symbol_idx[i_idx]
            
            # 1. Identifichiamo il cambio di giorno 🌅
            # Se è la prima riga assoluta o se la data corrente è diversa dalla precedente
            is_new_day = False
            if i_idx == 0:
                is_new_day = True
            else:
                prev_idx = symbol_idx[i_idx - 1]
                if dates[idx] != dates[prev_idx]:
                    is_new_day = True

            # 2. Logica di Reset o Accumulo
            if is_new_day:
                self.cum_pv[symbol] = prices[idx] * volumes[idx]
                self.cum_vol[symbol] = volumes[idx]
            else:
                self.cum_pv[symbol] += prices[idx] * volumes[idx]
                self.cum_vol[symbol] += volumes[idx]

            # 3. Calcolo finale del valore VWAP
            if self.cum_vol[symbol] > 0:
                dest[idx] = self.cum_pv[symbol] / self.cum_vol[symbol]
            else:
                dest[idx] = prices[idx]

class CHAIN(Indicator):
    def __init__(self, target,upMode):
        super().__init__([target])
        self.target=target
        self.upMode=upMode
        self.map = {}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        # 1. Riferimenti agli array numpy per le performance ⚡
        dest = dataframe[self.target].to_numpy()
        close = dataframe["close"].to_numpy()
        open = dataframe["open"].to_numpy()

        count = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            idx = symbol_idx[i_idx]
            if  (self.upMode and close[idx] > open[idx]) or (not self.upMode and close[idx] < open[idx]) :
                count=count+1
            else:
                count=0
            dest[idx] =count

#########
#   
class STOCH_RSI(Indicator):
    def __init__(self, target, period=14, smooth_k=3, smooth_d=3):
        super().__init__([target])
        self.target = target
        self.n = period
        self.smooth_k = smooth_k
        self.smooth_d = smooth_d
        self.mem = {}

    def compute_fast(self, symbol, dataframe, symbol_idx, from_local_index):
        dest = dataframe[self.target].to_numpy()
        close = dataframe["close"].to_numpy()

        if symbol not in self.mem:
            self.mem[symbol] = {
                "avg_gain": 0.0,
                "avg_loss": 0.0,
                "count": 0,
                "last_close": None,
                "rsi_buffer": [],
                "stoch_buffer": [],
                "k_buffer": []
            }

        m = self.mem[symbol]
        n = self.n

        for i_idx in range(max(0, from_local_index), len(symbol_idx)):
            idx = symbol_idx[i_idx]

            # --- INIT ---
            if m["last_close"] is None:
                m["last_close"] = close[idx]
                dest[idx] = np.nan
                continue

            delta = close[idx] - m["last_close"]
            m["last_close"] = close[idx]

            gain = max(delta, 0)
            loss = max(-delta, 0)

            m["count"] += 1

            # --- RSI (Wilder / RMA) ---
            if m["count"] < n:
                m["avg_gain"] += gain
                m["avg_loss"] += loss
                dest[idx] = np.nan
                continue

            elif m["count"] == n:
                m["avg_gain"] = (m["avg_gain"] + gain) / n
                m["avg_loss"] = (m["avg_loss"] + loss) / n

            else:
                m["avg_gain"] = (m["avg_gain"] * (n - 1) + gain) / n
                m["avg_loss"] = (m["avg_loss"] * (n - 1) + loss) / n

            # RSI
            if m["avg_loss"] == 0:
                rsi = 100
            else:
                rs = m["avg_gain"] / m["avg_loss"]
                rsi = 100 - (100 / (1 + rs))

            # --- STOCH RSI ---
            m["rsi_buffer"].append(rsi)
            if len(m["rsi_buffer"]) > n:
                m["rsi_buffer"].pop(0)

            if len(m["rsi_buffer"]) < n:
                dest[idx] = np.nan
                continue

            low = min(m["rsi_buffer"])
            high = max(m["rsi_buffer"])

            if high - low == 0:
                stoch = 0.0   # TradingView
            else:
                stoch = (rsi - low) / (high - low)

            stoch *= 100

            # --- %K ---
            m["stoch_buffer"].append(stoch)
            if len(m["stoch_buffer"]) > self.smooth_k:
                m["stoch_buffer"].pop(0)

            if len(m["stoch_buffer"]) < self.smooth_k:
                dest[idx] = np.nan
                continue

            k = sum(m["stoch_buffer"]) / self.smooth_k

            # --- %D ---
            m["k_buffer"].append(k)
            if len(m["k_buffer"]) > self.smooth_d:
                m["k_buffer"].pop(0)

            if len(m["k_buffer"]) < self.smooth_d:
                dest[idx] = np.nan
                continue

            d = sum(m["k_buffer"]) / self.smooth_d

            # OUTPUT TradingView = %K (default)
            dest[idx] = k

#################

class BackStrategy5m(SmartStrategy):

    async def on_start(self):

        self.volume_min_filter= self.params["volume_min_filter"]
        self.inPeriod=False
        self.gain_perc = self.params["gain_perc"]   
        self.trade_last_hh= self.params["trade_last_hh"]
        self.min_open_gain= self.params["min_open_gain"]
        self.trade_first_hh= 5#self.params["trade_first_hh"]
      
        capital = self.props.get("trade.trade_balance_USD")
        #trade_risk = self.props.get("trade.trade_risk")
        self.loss_by_trade = 100#capital * trade_risk
        logger.info(f"LOSS BY TRADE {self.loss_by_trade}")   
        pass

    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)

    def populate_indicators(self) :
        #self.addIndicator(self.timeframe,GAIN("GAIN","close",timeperiod=1))


        date = self.addIndicator(self.timeframe,TRADE_DATE("date"))
        day_volume_history = self.addIndicator(self.timeframe,DAY_VOLUME("day_volume_history"))
        ema21 = self.addIndicator(self.timeframe,EMA("ema21","close",timeperiod=21))
        ema9 = self.addIndicator(self.timeframe,SMA("ema9","close",timeperiod=9))
        vwap = self.addIndicator(self.timeframe,VWAP("vwap_history","close","base_volume"))
        rsi = self.addIndicator(self.timeframe,STOCH_RSI("rsi"))
        chain = self.addIndicator(self.timeframe,CHAIN("chain",True))
      
        
        #gain = self.addIndicator(self.timeframe,GAIN("gain","close",timeperiod=2))
        #self.addIndicator(self.timeframe,SMA("sma_20","close",timeperiod=20))
      
        self.add_plot(ema21, "ema21","#a70000", "main", style="SparseDotted", lineWidth=1)
        self.add_plot(ema9 , "ema9 ","#4800a7", "main", style="SparseDotted", lineWidth=1)

        self.add_plot(vwap , "vwap_history ","#00a732", "main", style="SparseDotted", lineWidth=1)
       
        #self.add_plot(day_volume_history, "day_volume_history","#0318d3", "sub1", style="Solid", lineWidth=1)

        self.add_plot(chain, "chain","#0318d3", "sub1", style="Solid", lineWidth=1)

        #self.add_plot(bad, "bad","#0318d3", "sub1", style="Solid", lineWidth=1)


    def get_quantity(self,price):
        #sl_price = price - price / 100 * self.gain_perc
        return int(self.loss_by_trade  / price )
    
    first = False
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        #if not BackStrategy5m.first:
        #    BackStrategy5m.first=True
        #    logger.info(f"TRADE_SYMBOL_AT \n{symbol} {local_index}  {dataframe}")  

        if (local_index < 2):   
            return
        
        #if symbol =="SKYQ":
        #    logger.info(f"TRADE_SYMBOL_AT \n{symbol} {dataframe.iloc[local_index]}")  


        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-1]

       # max_day = last["max_day"]
        close = last["close"]
        ema21 = last["ema21"]
        ema9 = last["ema9"]
        volume = last["day_volume_history"]    
      #  bad = last["bad"]
         
       # max_day_gain = (last["max_day"] - prev["max_day"] ) / prev["max_day"] * 100  

        ###### FIRST ENTER ########
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        else:
            if not self.has_meta(symbol,"first_enter_marker"):
                await self.add_marker(symbol,"SPOT","X","First","#F6F7F8","square",position ="atPriceTop",timestamp=self.get_meta(symbol,"first_enter"),value=close)
                self.set_meta(symbol, {"first_enter_marker": True })

         # ##### OPEN CLOSE INFOS #######
        #if not self.has_meta(symbol,"compute_open"):
        #        await self.compute_open(symbol,dataframe,local_index, open_count=3, use_day=use_day)


        if  self.market.is_in_time(last["datetime"],
            get_hour_ms(self.trade_first_hh,0),get_hour_ms(self.trade_last_hh,00),use_day):
        
            if not self.has_meta(symbol,"enter_time"):
                self.set_meta(symbol, {"enter_time": last["timestamp"] })   
                await self.add_marker(symbol,"SPOT","E","Enter Time","#F6F7F86F","square",position ="atPriceTop")

            #########
            
            #if not self.backtestMode and self.bootstrapMode:
            #    return
            #open_volume = self.get_meta(symbol,"open_volume",0) 
            
            if volume > self.volume_min_filter :#and last["timestamp"]-self.get_meta(symbol,"first_enter")> 60*60*1000: # filtro primo minuto
                
                if not self.hasCurrentTrade(symbol):
                    if ema9 > ema21:
                        await self.buy(symbol, int(dataframe.iloc[local_index]["timestamp"]), close,100,  f"BUY"  )
                    