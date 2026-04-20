import yfinance as yf
import pandas as pd
import os
import time
import sqlite3

# --- CONFIGURAZIONE ---
TICKERS = ["PLTR", "SOUN", "CHGG", "AAL", "RIG", "BBAI", "MARA", "RIOT"]
CAPITALE_INIZIALE = 100  # Budget totale per il backtest
RISCHIO_PER_TRADE_USD = 10   # Quanto investiamo in ogni singolo trade

DATA_DIR = "market_data"
START_DATE = "2026-01-01"  # <--- FILTRO DATA DI INIZIO
DB_FILE = "db/crypto.db"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_df(query, params=()):
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
def get_data(ticker, interval="1d", period="2y"):
    file_path = os.path.join(DATA_DIR, f"{ticker}_{interval}.csv")
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        return df
    else:
        # auto_adjust=True mette i prezzi reali, multi_level=False semplifica le colonne
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
        if not df.empty:
            # Rimuoviamo il MultiIndex se presente (per versioni yfinance >= 0.2.50)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.to_csv(file_path)
            time.sleep(0.5)
        return df
    
def get_clean_data(ticker):
    df = yf.download(ticker, period="2y", interval="1d", auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.copy()

def run_backtest(ticker, start_date, rischio_usd=100):
    # 1. Scarico dati (estesi per calcolare la SMA200)
    start_dt = pd.to_datetime(start_date)
    df = get_data(ticker)
    
    if df.empty or len(df) < 200: 
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 2. Calcolo Indicatori
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean() # Filtro Trend Istituzionale
    
    # Logica Candele
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['Min_OC'] = df[['Open', 'Close']].min(axis=1)
    df['Lower_Shadow'] = df['Min_OC'] - df['Low']
    
    is_hammer = (df['Lower_Shadow'] > (df['Body'] * 2)) & (df['Body'] > 0)
    is_engulfing = (df['Close'] > df['Open']) & (df['Open'] < df['Close'].shift(1)) & (df['Close'] > df['Open'].shift(1))
    
    # 3. Logica Pullback sul Trend
    # A. Trend: SMA20 > SMA50 E Prezzo > SMA200
    # B. Pullback: Low tocca la SMA20 (tolleranza 1.5% per titoli volatili)
    condition_trend = (df['SMA20'] > df['SMA50']) & (df['Close'] > df['SMA200'])
    condition_pullback = (df['Low'] <= df['SMA20'] * 1.015) & (df['Low'] >= df['SMA20'] * 0.985)
    condition_signal = (is_hammer | is_engulfing)

    df['Signal'] = condition_trend & condition_pullback & condition_signal

    # Filtriamo per la data di inizio desiderata
    df = df[df.index >= start_dt]

    trades = []
    in_position = False
    
    # 4. Ciclo di Simulazione Trade
    for i in range(len(df) - 1):
        if df['Signal'].iloc[i] and not in_position:
            # Entry: Apertura giorno dopo
            entry_price = df['Open'].iloc[i+1]
            # Stop Loss: Minimo candela segnale (o SMA20 se più vicina)
            stop_loss = df['Low'].iloc[i] 
            dist_stop = entry_price - stop_loss
            
            if dist_stop <= 0.05: continue # Evita trade con rischio troppo piccolo/errori
            
            # Position Sizing
            shares = rischio_usd // dist_stop
            if shares <= 0: continue

            target_price = entry_price + (dist_stop * 2) # Risk/Reward 1:2
            in_position = True
            entry_date = df.index[i+1]
            
            # Monitoraggio Trade
            for j in range(i+1, len(df)):
                if df['Low'].iloc[j] <= stop_loss:
                    trades.append({
                        'Ticker': ticker, 'Entry_Date': entry_date, 'Exit_Date': df.index[j],
                        'Entry_P': entry_price, 'Exit_P': stop_loss, 
                        'PnL_$': (stop_loss - entry_price) * shares, 'Status': 'Loss'
                    })
                    in_position = False; break
                elif df['High'].iloc[j] >= target_price:
                    trades.append({
                        'Ticker': ticker, 'Entry_Date': entry_date, 'Exit_Date': df.index[j],
                        'Entry_P': entry_price, 'Exit_P': target_price, 
                        'PnL_$': (target_price - entry_price) * shares, 'Status': 'Win'
                    })
                    in_position = False; break
                    
    return pd.DataFrame(trades)

# --- ESECUZIONE ---
all_results = []
TICKERS = get_df("SELECT DISTINCT symbol  FROM  ib_day_watch")["symbol"].tolist()
print(TICKERS)
for t in TICKERS:
    try:
        res = run_backtest(t, START_DATE)
        all_results.append(res)
    except Exception as e:
        print(f"Errore su {t}: {e}")

all_trades = pd.concat(all_results)

if not all_trades.empty:
    print(f"\n--- REPORT DAL {START_DATE} ---")
    print(f"Profitto Totale Netto: ${all_trades['PnL_$'].sum():.2f}")
    print(f"Win Rate: {(all_trades['Status'] == 'Win').mean()*100:.2f}%")
    print(f"Numero di operazioni: {len(all_trades)}")
    print("\nDettaglio ultimi trade:")
    print(all_trades.tail())
else:
    print("Nessun segnale trovato nel periodo selezionato.")