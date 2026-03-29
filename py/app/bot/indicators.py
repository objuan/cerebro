from typing import Dict
import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta
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

        for i_idx in range(from_local_index,len(symbol_idx) ):
            prev = source[symbol_idx[max(0,i_idx -self.timeperiod )]]
            current = source[symbol_idx[i_idx]]
            dest[symbol_idx[i_idx]] = 100.0 * (current-prev ) / prev


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

class SMA(Indicator):
  
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

class MAX(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
    
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe[self.source_col].to_numpy()

        for i_idx in range(from_local_index,len(symbol_idx) ):
            m=0.0
            for j_idx in range(max(0,i_idx- self.window+1), i_idx+1 ):
                m= max(m,source[symbol_idx[j_idx]])
            dest[symbol_idx[i_idx]] =m

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
  
    def __init__(self,target_col):
        super().__init__([target_col])
        self.target_col=target_col    
        
 
    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx ,from_local_index):
       
        dest = dataframe[self.target_col].to_numpy()
        source = dataframe["base_volume"].to_numpy()
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
class VWAP(Indicator):
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
        

'''
        
class GAIN(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        
       # logger.info(f"GAIN \n{dataframe.tail(30)}")

        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        dataframe[self.target_col] = (
            dataframe
                .groupby("symbol")[self.source_col]
                .transform(
                    lambda s: ((s - s.shift(self.timeperiod)) / s.shift(self.timeperiod)) * 100
                )
        )
       # logger.info(f"GAIN AFTER \n{dataframe.tail(30)}")
'''
'''
class AVG(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
     
        #dataframe[self.target_col]  =  ((dataframe[self.source_col] - dataframe[self.source_col].shift(self.timeperiod)) / dataframe[self.source_col].shift(self.timeperiod))* 100
        
        dataframe[self.target_col] = (
                dataframe
                .groupby("symbol")[self.source_col]
                .transform(lambda s: s.rolling(self.timeperiod, min_periods=self.timeperiod).mean())
        )
      

class FLOAT(Indicator):
    def __init__(self,target_col):
        super().__init__([target_col])
        self.target_col=target_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
     
        symbols = dataframe["symbol"].unique().tolist()
        #logger.info(f"FLOAT \n{symbols}")

        for symbol in symbols:
            if not symbol in self.cache:
                 #logger.info(f"get_fundamentals {self.client.get_fundamentals_dict(symbol)}")
                 self.cache[symbol] = self.client.get_fundamentals_dict(symbol)["float"]

        dataframe[self.target_col] = dataframe["symbol"].map(self.cache)


class SORT_POS(Indicator):
    def __init__(self,target_col, source_col):
        super().__init__([target_col])
        self.target_col=target_col
        self.source_col=source_col
        self.cache = {}

    def apply(self,dataframe : pd.DataFrame, from_global_index=0):
        #logger.info(f"GAIN \n{dataframe}")
       # 1️⃣ ultima riga per symbol (preserva indice)
        last_rows = (
            dataframe
            .sort_index()
            .groupby("symbol")
            .tail(1)
        )
        # 2️⃣ ordina per source_col e crea rank (1 = migliore)
        last_rows = last_rows.sort_values(self.source_col, ascending=False)
        last_rows[self.target_col] = range(1, len(last_rows) + 1)

        # 3️⃣ mappa symbol -> rank
        rank_map = last_rows.set_index("symbol")[self.target_col].to_dict()

        # 4️⃣ assegna a TUTTE le righe
        dataframe[self.target_col] = dataframe["symbol"].map(rank_map)

        #logger.info(f"rank_map \n{rank_map}")
        #logger.info(f"SORT_POS \n{dataframe}")

class VWAP_PERC(Indicator):
  
  def __init__(self,target_col):
        super().__init__([target_col])
        self.target_col=target_col
    
  def compute(self, dataframe, group, start_pos):
        
        close = group["close"]
        vwap = group["vwap"]
        vwap_up = group["vwap_up"]
        vwap_down = group["vwap_down"]

        band_h = vwap_up-vwap_down
        close_perc = 100* (close - vwap_down) / band_h

        dataframe.loc[group.index, self.target_col] = close_perc

        gain = close_perc - close_perc.shift(1)

        dataframe.loc[group.index, self.target_col + "_gain"] = gain

        variance = ((band_h) / vwap_down) * 100

        dataframe.loc[group.index, self.target_col + "_var"] = variance

############


class DIFF(Indicator):
  
    def __init__(self,target_col, source1_col:str, source2_col:str):
        super().__init__([target_col])
        self.source1_col=source1_col
        self.target_col=target_col
        self.source2_col=source2_col

    def compute(self, dataframe, group, start_pos):
        
        diff = group[self.source1_col] + group[self.source2_col] 

        if start_pos == 0:
            dataframe.loc[group.index, self.target_col] = diff.values
        else:
            dataframe.loc[group.index[start_pos:], self.target_col] = \
                diff.iloc[start_pos:].values
############


class GAIN(Indicator):
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.timeperiod=timeperiod

    def compute(self, symbol, dataframe: pd.DataFrame, group: pd.DataFrame, from_local_index):

        close = group[self.source_col]

        if from_local_index == 0:
            gain = (close - close.shift(self.timeperiod)) / close.shift(self.timeperiod) * 100
            dataframe.loc[group.index, self.target_col] = gain.values
            return

        warmup = max(0, from_local_index - self.timeperiod)

        sub = group.iloc[warmup:].copy()

        gain = (sub[self.source_col] - sub[self.source_col].shift(self.timeperiod)) / \
            sub[self.source_col].shift(self.timeperiod) * 100

        dataframe.loc[sub.index[from_local_index - warmup:], self.target_col] = \
            gain.iloc[from_local_index - warmup:].values       
        
class SMA_INT(Indicator):
  
    def __init__(self,target_col, source_col:str, timeperiod:int):
        super().__init__([target_col])
        self.source_col=source_col
        self.target_col=target_col
        self.window=timeperiod
        self.slope_col = f"{target_col}_slope"


    def compute(self, symbol, dataframe: pd.DataFrame, group: pd.DataFrame, from_local_index):
        
        warmup = max(0, from_local_index - self.window + 1)

        sub = group.iloc[warmup:].copy()

        sma = sub[self.source_col].rolling(window=self.window).mean()

         # derivata discreta (pendenza)
        #slope = sma.diff()
        

        #logger.info(f"sub {sub}")

        idx_slice = sub.index[from_local_index - warmup:]

        #logger.info(f"idx_slice {idx_slice}")

        dataframe.loc[idx_slice, self.target_col] = \
            sma.iloc[from_local_index - warmup:].values
            
        #dataframe.loc[idx_slice, self.slope_col] = \
        #    slope.iloc[start_pos - warmup:].values

class MAX_LIMIT(Indicator):
  
    def __init__(self,target_col, timeperiod:int, outlier_std=2):
        super().__init__([target_col])
        self.target_col=target_col
        self.window=timeperiod
        self.outlier_std = outlier_std

    def compute(self, symbol, dataframe: pd.DataFrame, group: pd.DataFrame, from_local_index):

        #logger.info(f"compute {symbol} idx {from_local_index} #{len(group)}" )

        warmup = max(0, from_local_index - self.window + 1)

        #gli indici restano quelli del dataframe originale.
        sub = group.iloc[warmup:]

        m = sub["high"].rolling(window=self.window).max()

        start = from_local_index - warmup

        idx = sub.index[start:]

        #logger.info(f"{symbol} idx {idx}" )

        dataframe.loc[idx, self.target_col] = m.iloc[start:].values   

class DIFF_PERC(Indicator):
  
    def __init__(self,target_col, source_base:str, source_signal:str):
        super().__init__([target_col])
        self.source_base=source_base
        self.target_col=target_col
        self.source_signal=source_signal

    def compute(self, symbol, dataframe: pd.DataFrame, group: pd.DataFrame, from_local_index):
        
        warmup = max(0, from_local_index )
        sub = group.iloc[warmup:]

        diff = 100 * (sub[self.source_signal] - sub[self.source_base] ) / sub[self.source_base]

        start = from_local_index - warmup
        idx = sub.index[start:]
        dataframe.loc[idx, self.target_col] = diff.iloc[start:].values  
'''