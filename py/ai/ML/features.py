# src/features.py

import pandas as pd
import numpy as np

#Qui ragioniamo per giornata di trading.

def compute_vwap(df):
    df = df.copy()
    
    # prezzo tipico (molto meglio del close)
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    
    # prodotto prezzo * volume
    df['pv'] = df['typical_price'] * df['base_volume']
    
    # cumulato per simbolo + giorno
    df['cum_pv'] = df.groupby(['symbol', 'date'])['pv'].cumsum()
    df['cum_vol'] = df.groupby(['symbol', 'date'])['base_volume'].cumsum()
    
    # VWAP
    df['vwap'] = df['cum_pv'] / (df['cum_vol'] + 1e-9)
    
    return df

def compute_features(df):
    df = df.copy()
    
    # returns
    df['ret_1'] = df.groupby('symbol')['close'].pct_change()
    df['ret_5'] = df.groupby('symbol')['close'].pct_change(5)
    
    # volatilità
    df['volatility'] = df.groupby('symbol')['ret_1'].rolling(20).std().reset_index(0, drop=True)
    
    # volume spike
    df['vol_spike'] = df['base_volume'] / df.groupby('symbol')['base_volume'].rolling(20).mean().reset_index(0, drop=True)
    
    # distanza da VWAP (molto utile intraday)
    df['vwap_dist'] = (df['close'] - df['vwap']) / df['vwap']
    
    return df

def get_open_window(df, minutes=30):
    df = df.copy()
    
    df['time'] = df['datetime'].dt.time
    
    # prendi prime N barre per ogni giorno/simbolo
    return df.groupby(['symbol', 'date']).head(minutes)

def build_daily_target(df):
    df = df.copy()
    
    # prezzo apertura (prima barra)
    open_price = df.groupby(['symbol', 'date'])['close'].first()
    
    # prezzo chiusura (ultima barra)
    close_price = df.groupby(['symbol', 'date'])['close'].last()
    
    daily_return = (close_price / open_price) - 1
    
    target = (daily_return > 0).astype(int)
    
    return target

def pad_sequence(arr, target_len):
    if len(arr) >= target_len:
        return arr[:target_len]
    
    pad = np.zeros((target_len - len(arr), arr.shape[1]))
    return np.vstack([arr, pad])


def build_daily_patterns(df_open, window=30):
    X = []
    keys = []
    
    for (symbol, date), group in df_open.groupby(['symbol', 'date']):
        
        group = group[['ret_1','ret_5','volatility','vol_spike','vwap_dist']].dropna()
        
        # 🔴 se completamente vuoto, skip
        if len(group) == 0:
            continue
        
        # ✅ QUI USI pad_sequence
        fixed = pad_sequence(group.values, window)
        
        X.append(fixed.flatten())
        keys.append((symbol, date))
    
    return X, keys


def clean_features(df):
    df = df.copy()
    
    # sostituisce inf
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # rimuove righe con NaN critici
    df = df.dropna(subset=[
        'ret_1','ret_5','volatility','vol_spike','vwap_dist'
    ])
    
    return df

def build_windows(df, window=30):
    X = []
    idx = []
    
    for i in range(len(df) - window):
        window_data = df.iloc[i:i+window][['ret_1','ret_5','volatility','vol_spike']].values
        
        X.append(window_data.flatten())
        idx.append(df.index[i+window])
    
    return np.array(X), idx

#Previsione: “sale nei prossimi 30 minuti?”
def build_target(df, horizon=30):
    future_return = df['close'].shift(-horizon) / df['close'] - 1
    target = (future_return > 0).astype(int)
    
    return target


def aggregate_features(group):
    return {
        "ret_mean": group['ret_1'].mean(),
        "ret_std": group['ret_1'].std(),
        "ret_5_mean": group['ret_5'].mean(),
        "volatility_mean": group['volatility'].mean(),
        "vol_spike_max": group['vol_spike'].max(),
        "vwap_dist_mean": group['vwap_dist'].mean(),
        "vwap_dist_std": group['vwap_dist'].std(),
    }

def build_ranking_dataset(df_open, df_full):
    rows = []
    
    for (symbol, date), group in df_open.groupby(['symbol','date']):
        
        if len(group) < 10:
            continue
        
        features = aggregate_features(group)
        
        # prezzi giornalieri
        day_data = df_full[(df_full['symbol']==symbol) & (df_full['date']==date)]
        
        if len(day_data) == 0:
            continue
        
        open_price = day_data['close'].iloc[0]
        close_price = day_data['close'].iloc[-1]
        
        daily_return = (close_price / open_price) - 1
        
        features['symbol'] = symbol
        features['date'] = date
        features['target'] = daily_return
        
        rows.append(features)
    
    return pd.DataFrame(rows)

#########################################

def compute_features(df):
    df = df.copy()

    df['ret_1'] = df.groupby('symbol')['close'].pct_change()
    df['ret_5'] = df.groupby('symbol')['close'].pct_change(5)

    df['volatility'] = df.groupby('symbol')['ret_1'].rolling(20).std().reset_index(0, drop=True)

    df['vol_spike'] = df['base_volume'] / (
        df.groupby('symbol')['base_volume'].rolling(20).mean().reset_index(0, drop=True) + 1e-6
    )

    df['vwap_dist'] = (df['close'] - df['vwap']) / (df['vwap'] + 1e-6)

    return df

def compute_vwap(df):
    df = df.copy()

    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical_price'] * df['base_volume']

    df['cum_pv'] = df.groupby(['symbol','date'])['pv'].cumsum()
    df['cum_vol'] = df.groupby(['symbol','date'])['base_volume'].cumsum()

    df['vwap'] = df['cum_pv'] / (df['cum_vol'] + 1e-9)

    return df

def clean_features(df):
    import numpy as np
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=['ret_1','ret_5','volatility','vol_spike','vwap_dist'])
    return df

def get_open_window(df, minutes=30):
    return df.groupby(['symbol','date']).head(minutes)

def aggregate_features(group):
    return {
        "ret_mean": group['ret_1'].mean(),
        "ret_std": group['ret_1'].std(),
        "ret_5_mean": group['ret_5'].mean(),
        "volatility_mean": group['volatility'].mean(),
        "vol_spike_max": group['vol_spike'].max(),
        "vwap_dist_mean": group['vwap_dist'].mean(),
        "vwap_dist_std": group['vwap_dist'].std(),
    }

def build_ranking_dataset(df_open, df_full):
    import pandas as pd
    rows = []

    for (symbol, date), group in df_open.groupby(['symbol','date']):
        if len(group) < 10:
            continue

        features = aggregate_features(group)

        day_data = df_full[(df_full['symbol']==symbol) & (df_full['date']==date)]
        if len(day_data) == 0:
            continue

        open_price = day_data['close'].iloc[0]
        close_price = day_data['close'].iloc[-1]

        daily_return = (close_price / open_price) - 1

        features['symbol'] = symbol
        features['date'] = date
        features['target'] = daily_return

        rows.append(features)

    return pd.DataFrame(rows)