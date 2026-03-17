import streamlit as st
import plotly.graph_objects as go

from backtester import run_backtest

st.set_page_config(layout="wide")

st.title("Regime Based BTC Trading AI")

data,trades,total_return,win_rate = run_backtest()

latest = data.iloc[-1]

regime = latest.State

signal = "LONG" if regime==data.groupby("State")['Returns'].mean().idxmax() else "CASH"

col1,col2 = st.columns(2)

col1.metric("Current Signal",signal)
col2.metric("Detected Regime",regime)

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=data.index,
    open=data['Open'],
    high=data['High'],
    low=data['Low'],
    close=data['Close']
))

fig.update_layout(height=700)

st.plotly_chart(fig,use_container_width=True)

col1,col2,col3 = st.columns(3)

col1.metric("Total Return",f"{total_return*100:.2f}%")
col2.metric("Win Rate",f"{win_rate*100:.2f}%")
col3.metric("Trades",len(trades))