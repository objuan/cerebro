import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
from data_loader import load_data

import ta

START_CAPITAL = 10000
LEVERAGE = 2.5

def train_hmm(data):

    X = data[['Returns','Range','Vol_Change']].values

    model = GaussianHMM(
        n_components=7,
        covariance_type="full",
        n_iter=1000,
        random_state=42
    )

    model.fit(X)

    states = model.predict(X)
    data['State'] = states

    stats = data.groupby("State")['Returns'].mean()

    bull_state = stats.idxmax()
    bear_state = stats.idxmin()

    return data, bull_state, bear_state


def compute_indicators(data):

    data['RSI'] = ta.momentum.RSIIndicator(data['Close']).rsi()

    data['Momentum'] = data['Close'].pct_change(12)

    data['Volatility'] = data['Returns'].rolling(24).std()

    data['Vol_SMA20'] = data['Volume'].rolling(20).mean()

    data['ADX'] = ta.trend.ADXIndicator(
        data['High'],
        data['Low'],
        data['Close']
    ).adx()

    data['EMA50'] = data['Close'].ewm(span=50).mean()

    macd = ta.trend.MACD(data['Close'])

    data['MACD'] = macd.macd()
    data['Signal'] = macd.macd_signal()

    return data


def confirmations(row):

    checks = [

        row.RSI < 90,
        row.Momentum > 0.01,
        row.Volatility < 0.06,
        row.Volume > row.Vol_SMA20,
        row.ADX > 25,
        row.Close > row.EMA50,
        row.MACD > row.Signal

    ]

    return sum(checks)


def run_backtest():

    data = load_data()

    data, bull, bear = train_hmm(data)

    data = compute_indicators(data)

    capital = START_CAPITAL
    position = 0
    entry_price = 0
    cooldown = 0

    trades = []

    for i,row in data.iterrows():

        if cooldown > 0:
            cooldown -= 1

        conf = confirmations(row)

        if position == 0:

            if (
                row.State == bull
                and conf >= 7
                and cooldown == 0
            ):
                position = capital * LEVERAGE / row.Close
                entry_price = row.Close

        else:

            if row.State == bear:

                pnl = (row.Close-entry_price) * position
                capital += pnl

                trades.append(pnl)

                position = 0
                cooldown = 48

    total_return = (capital-START_CAPITAL)/START_CAPITAL

    win_rate = sum([t>0 for t in trades])/len(trades) if trades else 0

    return data, trades, total_return, win_rate