import yfinance as yf
import pandas as pd
import numpy as np

def load_data():

    df = yf.download(
        "BTC-USD",
        period="730d",
        interval="1h"
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[['Open','High','Low','Close','Volume']]

    df['Returns'] = df['Close'].pct_change()
    df['Range'] = (df['High'] - df['Low']) / df['Close']
    df['Vol_Change'] = df['Volume'].pct_change()

    df.replace([np.inf,-np.inf],np.nan,inplace=True)
    df.dropna(inplace=True)

    return df