from typing import Dict
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
from strategies.strategy_utils import StrategyUtils
from company_loaders import *
from collections import deque
import talib.abstract as ta

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
#from reports.report_manager import ReportManager


class Indicator:
    
    def __init__(self,target_cols):
        self.target_cols=target_cols
        self.init=False
        pass

    def initialize(self,df : pd.DataFrame):
        for col in self.target_cols:
            df[col] = 0.0

    def get_render_data(self, dataframe,target_col) -> pd.DataFrame:
        if not target_col in self.target_cols:
            raise "col not found : " + target_col
        return (
            dataframe[["symbol", "timestamp", target_col]]
            .dropna(subset=[target_col])
            .rename(columns={
                target_col: "value",
                "timestamp": "time"
            })
        )

    def df_view(symbol, df: pd.DataFrame, column:str)-> pd.DataFrame:
      
        mask = df["symbol"].to_numpy() == symbol
        idx = np.where(mask)[0]

        cc = df[column].to_numpy()
        sub_cc = cc[idx]  # vista indiretta
        return sub_cc
        

    def _compute_fast(self, symbol, dataframe: pd.DataFrame, idx,from_local_index ):

        pass
    
    def compute(self, symbol, dataframe: pd.DataFrame, df_symbol: pd.DataFrame, from_local_index):
        pass

    def apply(self, symbol, dataframe: pd.DataFrame,df_symbol: pd.DataFrame, from_local_index=0):
        
        if not self.init:
            self.init=True
            self.initialize(dataframe)

        
        if from_local_index == -1:
            from_local_index = len(df_symbol)-1
        else:
            pass
            #logger.info(f"!! indicator {symbol} {self.__class__.__name__} l:{from_local_index}")
            
        if hasattr(self,"compute_fast"):
            if len(self.target_cols)==1 and not self.target_cols[0] in dataframe.columns:
                dataframe[self.target_cols[0] ] = 0.0

            mask = dataframe["symbol"].to_numpy() == symbol
            idx = np.where(mask)[0]
            self.compute_fast(symbol,dataframe,idx,from_local_index)

        else:
            self.compute(symbol, dataframe,df_symbol, from_local_index)

    # solo per tutto 
    def applyAll(self, dataframe: pd.DataFrame, from_global_index,filter_symbol=None):

        for symbol, group in dataframe.groupby("symbol"):
            
            if not filter_symbol or (filter_symbol and filter_symbol == symbol):
                if from_global_index == -1:
                    start_pos = 0
                else:
                    if from_global_index != 0:
                        raise Exception("AAAAAAAAAAAAA")
                    #mask = group.index >= from_global_index
                    #if not mask.any():
                    #    continue
                    #start_pos = group.index.get_indexer(group[mask].index)[0]

                self.apply(symbol, dataframe, group, from_global_index)
        
 
 #################################

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

class VWAPBands(Indicator):
    def __init__(self, vwap_col, upper_col, lower_col, perc_col,pos_col, price_col: str, volume_col: str, window=1440, k=2):
        super().__init__([vwap_col, upper_col, lower_col,pos_col,perc_col])

        self.price_col = price_col
        self.volume_col = volume_col
        self.perc_col = perc_col
        self.pos_col=pos_col

        self.vwap_col = vwap_col
        self.upper_col = upper_col
        self.lower_col = lower_col

        self.window = window
        self.k = k

        self.buffers = {}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        prices = dataframe[self.price_col].to_numpy()
        volumes = dataframe[self.volume_col].to_numpy()

        vwap_arr = dataframe[self.vwap_col].to_numpy()
        upper_arr = dataframe[self.upper_col].to_numpy()
        lower_arr = dataframe[self.lower_col].to_numpy()
        perc_arr = dataframe[self.perc_col].to_numpy()
        pos_arr = dataframe[self.pos_col].to_numpy()

        if symbol not in self.buffers:
            self.buffers[symbol] = {
                "pv_q": deque(),
                "vol_q": deque(),
                "p2v_q": deque(),
                "sum_pv": 0.0,
                "sum_vol": 0.0,
                "sum_p2v": 0.0
            }

        buf = self.buffers[symbol]

        start = max(0, from_local_index)

        for i_idx in range(start, len(symbol_idx)):
            idx = symbol_idx[i_idx]

            p = prices[idx]
            v = volumes[idx]

            pv = p * v
            p2v = (p * p) * v

            # add
            buf["pv_q"].append(pv)
            buf["vol_q"].append(v)
            buf["p2v_q"].append(p2v)

            buf["sum_pv"] += pv
            buf["sum_vol"] += v
            buf["sum_p2v"] += p2v

            # remove old
            if len(buf["pv_q"]) > self.window:
                buf["sum_pv"] -= buf["pv_q"].popleft()
                buf["sum_vol"] -= buf["vol_q"].popleft()
                buf["sum_p2v"] -= buf["p2v_q"].popleft()

            if buf["sum_vol"] > 0:
                vwap = buf["sum_pv"] / buf["sum_vol"]

                # varianza pesata
                variance = (buf["sum_p2v"] / buf["sum_vol"]) - (vwap * vwap)
                variance = max(variance, 0.0)

                std = math.sqrt(variance)

                upper = vwap + self.k * std
                lower = vwap - self.k * std

                vwap_arr[idx] = vwap
                upper_arr[idx] = upper
                lower_arr[idx] = lower

                perc_arr[idx] =  (upper-lower) / (lower) * 100
                if upper-lower !=0:
                    pos_arr[idx] =  (p - lower) / (upper-lower) * 100
                else:
                     pos_arr[idx] = 50 

            else:
                vwap_arr[idx] = p
                upper_arr[idx] = p
                lower_arr[idx] = p
                perc_arr[idx] = 0
                pos_arr[idx] = 50

      
class W_TREND(Indicator):
  
    def __init__(self,target_col, target_col_sign, source:str):
        super().__init__([target_col,target_col_sign])
        self.source=source
        self.target_col=target_col
        self.target_col_sign=target_col_sign

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        dest_sign = dataframe[self.target_col_sign].to_numpy()

        source = dataframe[self.source].to_numpy()

        close = dataframe["close"].to_numpy()

        count = 0
        sign = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]
            sign = dest_sign[symbol_idx[from_local_index-1]]

        #if not symbol in self.map:
        #     self.map[symbol] = 0

        for i_idx in range(from_local_index,len(symbol_idx) ):
            i = symbol_idx[i_idx]

            new_sign =  1 if close[i] > source[i] else -1
            #logger.info(f'{close[i]} {source[i]} {sign} -> {new_sign}')
            if sign != new_sign:
                 sign = new_sign
                 count = 1
            else:
                 count=count+1
            
            dest[i] = count
            dest_sign[i]=sign

            #logger.info(f'{dest[i] } {dest_sign[i]}')
                 
            #dest[symbol_idx[i_idx]] = source[symbol_idx[i_idx]]


class VWAPRolling(Indicator):
    def __init__(self, target_col, price_col: str, volume_col: str, window=1440):
        super().__init__([target_col])
        self.price_col = price_col
        self.volume_col = volume_col
        self.target_col = target_col
        self.window = window

        # buffer per simbolo
        self.buffers = {}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        prices = dataframe[self.price_col].to_numpy()
        volumes = dataframe[self.volume_col].to_numpy()
        dest = dataframe[self.target_col].to_numpy()

        if symbol not in self.buffers:
            self.buffers[symbol] = {
                "pv_queue": deque(),
                "vol_queue": deque(),
                "sum_pv": 0.0,
                "sum_vol": 0.0
            }

        buf = self.buffers[symbol]

        start = max(0, from_local_index)

        for i_idx in range(start, len(symbol_idx)):
            idx = symbol_idx[i_idx]

            pv = prices[idx] * volumes[idx]
            vol = volumes[idx]

            # aggiungi nuovo
            buf["pv_queue"].append(pv)
            buf["vol_queue"].append(vol)

            buf["sum_pv"] += pv
            buf["sum_vol"] += vol

            # rimuovi vecchio (rolling window)
            if len(buf["pv_queue"]) > self.window:
                buf["sum_pv"] -= buf["pv_queue"].popleft()
                buf["sum_vol"] -= buf["vol_queue"].popleft()

            # calcolo VWAP
            if buf["sum_vol"] > 0:
                dest[idx] = buf["sum_pv"] / buf["sum_vol"]
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
            dest[idx] =int(count)

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
            
class MAX_DAY(Indicator):

    def __init__(self, target_col, price_col: str):
        super().__init__([target_col])
        self.price_col = price_col
        self.target_col = target_col
        self.max ={}
        self.first ={}
       

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        timestamp = dataframe["timestamp"].to_numpy()
        dest = dataframe[self.target_col].to_numpy()
        price = dataframe[self.price_col].to_numpy()
            
        start = max(0, from_local_index)

        if not symbol in self.first:
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,from_local_index, True)
            #logger.info(f"FIRST ENTER {symbol} {first_enter}  ")    
            self.first[symbol] = first_enter

        first_enter = self.first[symbol]
        #logger.info(f"MAX_DAY {symbol} from_local_index {from_local_index}  symbol_idx {symbol_idx}  ")    

        for i_idx in range(start, len(symbol_idx)):
            if not symbol in self.max:
                   self.max[symbol] = price[symbol_idx[i_idx]]
            else:
                if timestamp[symbol_idx[i_idx]] > first_enter and timestamp[symbol_idx[i_idx-1]] < first_enter:
                    self.max[symbol] = price[symbol_idx[i_idx]]
                    #logger.info(f"MAX_DAY INIT {symbol} {price[symbol_idx[i_idx]]}  ")
                else:
                    self.max[symbol]= max(self.max[symbol], price[symbol_idx[i_idx]])

                dest[symbol_idx[i_idx]] =self.max[symbol]
                
class COPY(Indicator):
  
    def __init__(self,target_col, source:str):
        super().__init__([target_col])
        self.source=source
        self.target_col=target_col

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source].to_numpy()

        for i_idx in range(from_local_index,len(symbol_idx) ):
            dest[symbol_idx[i_idx]] = source[symbol_idx[i_idx]]

class GAIN(Indicator):
  
    def __init__(self,target_col, source:str, timeperiod:int):
        super().__init__([target_col])
        self.source=source
        self.target_col=target_col
        self.timeperiod=timeperiod

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source].to_numpy()

        start = max(from_local_index,self.timeperiod)
        for i_idx in range(start,len(symbol_idx) ):
            prev = source[symbol_idx[max(0,i_idx -self.timeperiod )]]
            current = source[symbol_idx[i_idx]]
            if prev>0:
                    dest[symbol_idx[i_idx]] = 100.0 * (current-prev ) / prev
            else:
                 dest[symbol_idx[i_idx]] =0


class DIFF(Indicator):
  
    def __init__(self,target_col, source_base:str, source_signal:str):
        super().__init__([target_col])
        self.source_base=source_base
        self.target_col=target_col
        self.source_signal=source_signal

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        warmup = max(0, from_local_index )

        dest = dataframe[self.target_col].to_numpy()
        source_base = dataframe[self.source_base].to_numpy()
        source_signal = dataframe[self.source_signal].to_numpy()

        for idx in [ symbol_idx[i_idx] for i_idx in range(warmup,len(symbol_idx) )]:
            dest[idx] = source_signal[idx] - source_base[idx]


class DIFF_PERC(Indicator):
  
    def __init__(self,target_col, source_base:str, source_signal:str):
        super().__init__([target_col])
        self.source_base=source_base
        self.target_col=target_col
        self.source_signal=source_signal

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        warmup = max(0, from_local_index )

        dest = dataframe[self.target_col].to_numpy()
        source_base = dataframe[self.source_base].to_numpy()
        source_signal = dataframe[self.source_signal].to_numpy()

        for idx in [ symbol_idx[i_idx] for i_idx in range(warmup,len(symbol_idx) )]:
            dest[idx] = 100.0 * (source_signal[idx] - source_base[idx]) / source_base[idx]

class SMA_old(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
        
        
        #warmup = max(0, from_local_index - self.window + 1)
        
       # if symbol == "KALA":
        #logger.info(f"SMA {symbol} idx #{symbol_idx} from_local_index {from_local_index}")

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

            #logger.info(f"i_idx {range(from_local_index + self.window,len(symbol_idx))}")

        for i_idx in range(from_local_index,len(symbol_idx) ):
                    sum=0.0
                    #logger.info(f"i_idx { range(max(0,i_idx- self.window+1), i_idx+1 )}")
                    r = range(max(0,i_idx- self.window+1), i_idx+1 )
                    for j_idx in r:
                        sum+= source[symbol_idx[j_idx]]
                    sum=sum/ len(r)
                    #logger.info(f"sum {i_idx} {symbol_idx[i_idx]}= {sum}")
                    dest[symbol_idx[i_idx]] =sum

class SMA(Indicator):

    def __init__(self, target_col, source_col: str, timeperiod: int):
        super().__init__([target_col])
        self.source_col = source_col
        self.target_col = target_col
        self.window = timeperiod

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        w = self.window

        # start corretto per mantenere continuità rolling
        start = max(0, from_local_index - w + 1)

        rolling_sum = 0.0

        for i in range(start, len(symbol_idx)):

            idx = symbol_idx[i]

            rolling_sum += source[idx]

            # rimuove elemento uscito dalla finestra
            if i >= w:
                old_idx = symbol_idx[i - w]
                rolling_sum -= source[old_idx]

            # dimensione finestra reale iniziale
            current_window = min(i + 1, w)

            dest[idx] = rolling_sum / current_window

class EMA(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
        self.alpha = 2.0 / (timeperiod + 1)
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        # inizializzazione (prima EMA = SMA iniziale oppure primo valore)
        if from_local_index == 0:
            first_idx = symbol_idx[0]
            dest[first_idx] = source[first_idx]

            start = 1
        else:
            start = from_local_index

        for i_idx in range(start, len(symbol_idx)):
            curr = symbol_idx[i_idx]
            prev = symbol_idx[i_idx - 1]

            dest[curr] = (
                self.alpha * source[curr]
                + (1 - self.alpha) * dest[prev]
            )

class MAX(Indicator):

    def __init__(self, target_col, source_col: str, timeperiod: int):
        super().__init__([target_col])
        self.source_col = source_col
        self.target_col = target_col
        self.window = timeperiod

    def compute_fast(self, symbol, dataframe, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        w = self.window

        dq = deque()

        start = max(0, from_local_index - w)

        for i in range(start, len(symbol_idx)):

            idx = symbol_idx[i]
            value = source[idx]

            # rimuove valori minori
            while dq and dq[-1][1] <= value:
                dq.pop()

            dq.append((i, value))

            # rimuove elementi fuori finestra
            while dq and dq[0][0] <= i - w:
                dq.popleft()

            dest[idx] = dq[0][1]


class MIN(Indicator):

    def __init__(self, target_col, source_col: str, timeperiod: int):
        super().__init__([target_col])
        self.source_col = source_col
        self.target_col = target_col
        self.window = timeperiod

    def compute_fast(self, symbol, dataframe, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        w = self.window

        dq = deque()

        start = max(0, from_local_index - w)

        for i in range(start, len(symbol_idx)):

            idx = symbol_idx[i]
            value = source[idx]

            # rimuove valori maggiori
            while dq and dq[-1][1] >= value:
                dq.pop()

            dq.append((i, value))

            # fuori finestra
            while dq and dq[0][0] <= i - w:
                dq.popleft()

            dest[idx] = dq[0][1]

class SUM(Indicator):

    def __init__(self, target_col, source_col: str, timeperiod: int):
        super().__init__([target_col])
        self.source_col = source_col
        self.target_col = target_col
        self.window = timeperiod

    def compute_fast(self, symbol, dataframe, symbol_idx, from_local_index):

        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        w = self.window

        start = max(0, from_local_index - w)

        rolling_sum = 0.0

        for i in range(start, len(symbol_idx)):

            idx = symbol_idx[i]

            rolling_sum += source[idx]

            if i >= w:
                old_idx = symbol_idx[i - w]
                rolling_sum -= source[old_idx]

            dest[idx] = rolling_sum

class MAX_ALL(Indicator):
  
    def __init__(self,target_col, source_col:str):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        M = 0
        if from_local_index>0:
            M = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            M= max(M,source[symbol_idx[i_idx]])
            dest[symbol_idx[i_idx]] =M

        ########

class TREND_LIMIT(Indicator):
  
    def __init__(self,target_col, signal:int, outlier_std=2):
        super().__init__([target_col])
        self.target_col=target_col
        self.signal=signal
        self.outlier_std = outlier_std
        self.trend_map={}

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.signal].to_numpy()

        count = 0
        if from_local_index>0:
            count = dest[symbol_idx[from_local_index-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            if  source[symbol_idx[i_idx]] >0:
                count=count+1
            else:
                count=0
            dest[symbol_idx[i_idx]] =count

class TOUCH(Indicator):
    def __init__(self,target_col,trend):
        super().__init__([target_col])
        self.target_col=target_col
        self.self.trend=trend

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
      
        dest = dataframe[self.target_col].to_numpy()
        trend = dataframe[self.trend].to_numpy()
        
        v_trend_prec = 0 if from_local_index==0 else trend[symbol_idx[i_idx-1]]

        for i_idx in range(from_local_index,len(symbol_idx) ):
            v_trend = trend[symbol_idx[i_idx]]
            if v_trend>0 and v_trend_prec==0:
                 dest[symbol_idx[i_idx]] =1
            else:
                 dest[symbol_idx[i_idx]] =0
            v_trend_prec= v_trend

 
class DAY_VOLUME(Indicator):
  
    def __init__(self,target_col, volume_name = "base_volume"):
        super().__init__([target_col])
        self.target_col=target_col    
        self.volume_name=volume_name
        
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.volume_name].to_numpy()
        source_ts = dataframe["timestamp"].to_numpy()

        DAY = 86400*1000
        VOL = 0
        prev_day = None
        # recupera stato precedente se esiste
        if from_local_index > 0:
            prev_i = symbol_idx[from_local_index - 1]
            VOL = dest[prev_i]
            prev_day = source_ts[prev_i] // DAY


        for i_idx in range(from_local_index, len(symbol_idx)):
            idx = symbol_idx[i_idx]

            ts = source_ts[idx]
            curr_day = ts // DAY

            # 🔥 reset se cambia giorno
            if prev_day is not None and curr_day != prev_day:
                VOL = 0

            VOL += source[idx]
            dest[idx] = VOL

            prev_day = curr_day

#rolling().mean() → ATR stile SMA (più semplice, meno fedele al classico)
# usata DA IB
'''
class ATR_SMA(Indicator):

    def __init__(self, target_col: str, timeperiod: int):
        super().__init__([target_col])
        self.target_col = target_col
        self.window = timeperiod

    def compute(self, dataframe, group, start_pos):

        warmup = max(0, start_pos - self.window)

        sub = group.iloc[warmup:].copy()

        high = sub["high"]
        low = sub["low"]
        close = sub["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = tr1.combine(tr2, max).combine(tr3, max)

        atr = true_range.rolling(window=self.window).mean()

        # Scrivi solo le nuove righe
        dataframe.loc[sub.index[start_pos - warmup:], self.target_col] = \
            atr.iloc[start_pos - warmup:].values

class ATR(Indicator):

    def __init__(self, target_col: str, timeperiod: int):
        super().__init__([target_col])
        self.target_col = target_col
        self.window = timeperiod

    def compute(self, dataframe, group, start_pos):

        warmup = max(0, start_pos - self.window * 2)

        sub = group.iloc[warmup:].copy()

        high = sub["high"]
        low = sub["low"]
        close = sub["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = tr1.combine(tr2, max).combine(tr3, max)

        # Wilder smoothing
        atr = true_range.ewm(alpha=1/self.window, adjust=False).mean()

        dataframe.loc[sub.index[start_pos - warmup:], self.target_col] = \
            atr.iloc[start_pos - warmup:].values
        
        
class VWAP_OPEN(Indicator):
    def __init__(self, target_col, variance_mult, price_name="close"):
        super().__init__([target_col,target_col+"_up",target_col+"_down"])
        self.target_col = target_col
        self.price_name = price_name
        self.variance_mult=variance_mult

    def compute(self, dataframe, group, start_pos):

        group = group.sort_values("timestamp")
        ts = pd.to_datetime(group["timestamp"], unit="ms")

        # sessione regular US (15:30 Italia)
        session = (ts - pd.Timedelta(hours=14, minutes=30)).dt.date
        #session = ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.date

        # prezzo tipico
        price = (group["high"] + group["low"] + group[self.price_name]) / 3

        # volume reale candela
        volume = group["base_volume"]

        # cumulativi per sessione
        cum_vol = volume.groupby(session).cumsum()

        cum_pv = (price * volume).groupby(session).cumsum()
        #
        cum_p2v  = (price * price * volume).groupby(session).cumsum()

        # VWAP
        vwap  = (cum_pv / cum_vol).replace([np.inf, -np.inf], np.nan)

        variance = (cum_p2v / cum_vol) - (vwap * vwap)
        variance = variance.clip(lower=0)
        std = np.sqrt(variance) 

        upper = vwap + self.variance_mult * std
        lower = vwap - self.variance_mult * std

        #variance = (cum_pv_2v / cum_vol- vwap_full*vwap_full).replace([np.inf, -np.inf], np.nan)

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap.values
            dataframe.loc[group.index, self.target_col+"_up"] = upper.values
            dataframe.loc[group.index, self.target_col+"_down"] = lower.values

        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap.iloc[start_pos:].values
            dataframe.loc[group.index[start_pos:], self.target_col+"_up"] = \
                upper.iloc[start_pos:].values
            dataframe.loc[group.index[start_pos:], self.target_col+"_down"] = \
                lower.iloc[start_pos:].values


class VWAP_DIFF(Indicator):
  
  def __init__(self,target_col):
        self.target_col=target_col
    
  def compute(self, dataframe, group, start_pos):
        
        close = group["close"]
        vwap = group["vwap"]

        diff_perc = ((close - vwap) / vwap) * 100
        
        dataframe.loc[group.index, self.target_col] = diff_perc

        #logger.info(f"VWAP_DIFF AFTER \n{group.tail(30)}")
        
class SMA(Indicator):
   
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod

    def compute(self, dataframe, group, start_pos):
        
        warmup = max(0, start_pos - self.window + 1)

        sub = group.iloc[warmup:].copy()

        sma = sub[self.source_col].rolling(window=self.window).mean()

        # Scrivi solo le righe nuove
        dataframe.loc[sub.index[start_pos - warmup:], self.target_col] = \
            sma.iloc[start_pos - warmup:].values
        
        #logger.info(f"group\n {group}")

class EMA(Indicator):
   
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod

    def compute(self, dataframe, group, start_pos):
        
        #logger.info(f"compute {start_pos} \n{group}")
        
        alpha = 2 / (self.window + 1)
        close = group[self.source_col]

        if start_pos == 0:
            ema = close.ewm(span=self.window, adjust=False).mean()
            dataframe.loc[group.index, self.target_col] = ema.values
            return

        # Recupera EMA precedente
        prev_index = group.index[start_pos - 1]
        prev_ema = dataframe.loc[prev_index, self.target_col]

        ema_values = []

        for i in range(start_pos, len(group)):
            price = close.iloc[i]
            prev_ema = alpha * price + (1 - alpha) * prev_ema
            ema_values.append(prev_ema)

        dataframe.loc[group.index[start_pos:],self.target_col] = ema_values

'''
class VWAP_OLD(Indicator):
    def __init__(self,target_col, price_name="close"):
        super().__init__([target_col])
        self.target_col=target_col
        self.price_name=price_name

    def compute(self, dataframe, group, start_pos):

        group = group.sort_values("timestamp")
        ts = pd.to_datetime(group["timestamp"], unit="ms")

        price = (group["high"] + group["low"] + group[self.price_name]) / 3
        day = ts.dt.date
        
        day_volume = group["day_volume"]  # cumulativo

        # volume reale della barra (differenza giornaliera)
        volume_bar = day_volume.groupby(day).diff()

        # prima barra del giorno → diff() = NaN → deve essere uguale a day_volume
        volume_bar = volume_bar.fillna(day_volume)

        # cumulativo prezzo * volume_bar
        cum_pv = (price * volume_bar).groupby(day).cumsum()

        vwap_full = cum_pv / day_volume
        vwap_full = vwap_full.replace([np.inf, -np.inf], np.nan)#.fillna(0)

        #logger.info(f"vwap_full {vwap_full}")

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap_full.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap_full.iloc[start_pos:].values
            
        '''
        volume = group["base_volume"]

      

        # cumulativi completi
        cum_pv = (price * volume).groupby(day).cumsum()
        cum_vol = volume.groupby(day).cumsum()

        vwap_full = cum_pv / cum_vol

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = vwap_full.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                vwap_full.iloc[start_pos:].values
        '''
##########################

class AVP(Indicator):

    def __init__(
        self,
        target_col_prefix:str,
        price_source:str,
        volume_source:str,
        window:int,
        steps:int,
        min_price=None,
        max_price=None
    ):

        self.price_source = price_source
        self.volume_source = volume_source

        self.window = window
        self.steps = steps

        self.min_price = min_price
        self.max_price = max_price

        self.target_cols = [
            f"{target_col_prefix}_{i}"
            for i in range(steps)
        ]

        super().__init__(self.target_cols)

    def compute_fast(
        self,
        symbol,
        dataframe: pd.DataFrame,
        symbol_idx,
        from_local_index
    ):

        prices = dataframe[self.price_source].to_numpy()
        volumes = dataframe[self.volume_source].to_numpy()

        targets = [
            dataframe[col].to_numpy()
            for col in self.target_cols
        ]

        start = max(from_local_index, self.window)

        for i_idx in range(start, len(symbol_idx)):

            # indice dataframe corrente
            current_df_idx = symbol_idx[i_idx]

            # finestra locale simbolo
            window_symbol_idx = symbol_idx[
                i_idx - self.window:i_idx + 1
            ]

            prices_window = prices[window_symbol_idx]
            volumes_window = volumes[window_symbol_idx]

            # range prezzo dinamico
            if self.min_price is None:
                pmin = prices_window.min()
            else:
                pmin = self.min_price

            if self.max_price is None:
                pmax = prices_window.max()
            else:
                pmax = self.max_price

            if pmax <= pmin:
                continue

            # histogram volume profile
            hist, _ = np.histogram(
                prices_window,
                bins=self.steps,
                range=(pmin, pmax),
                weights=volumes_window
            )


            # scrittura bucket
            #for bucket in range(self.steps):
            #    targets[bucket][current_df_idx] = hist[bucket]