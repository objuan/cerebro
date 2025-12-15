# ==============================================================
# STREAMLIT DASHBOARD - IBKR MOMENTUM SCANNER (FULL)
# - Tabella scanner
# - Filtri live
# - WebSocket solo titoli selezionati
# - Grafico candlestick + VWAP
# - Alert Telegram
# - Paper trade (simulato)
# ==============================================================

'''
scanner columns

TOP GAINERS (14:10:00 - 14-15_00) (online)
chANGE FROM CLOSE , sIMBOL/nEWS , volume , float, relative volume(dayly rate) , relative volume (5 min %) , Gap % , Short interest

SMALL CAP, hight od day momentum
time , symbol , proce, volume, float   dayly rate, vol 5% , gap , chanhe from close ,short  interestm strategy name
strategie : 
Up 10% in 10 min -> avviso di compressione
Low Flow Volatility Hunter // in rialzo con poche azioni
Momo Stock, titolo con momentum basso : in passato è salito di oltre 100% in un giorno


SCANNER IN ESECUZIONE
- startegy, running up alert -> avviso quando cerca di raggiunge il massimo  della giornata


SCANNER DI ARRESTO

'''

import streamlit as st
import pandas as pd
import time
import requests
from ibind import IbkrWsClient, IbkrWsKey

RESULTS_CSV = "scanner_results.csv"
REFRESH_SECONDS = 2

# ---------------- TELEGRAM ----------------
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"


def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        )
    except Exception:
        pass

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="IBKR Momentum Desk", layout="wide")
st.title("🚀 IBKR Momentum Trading Desk")

# ==============================================================
# LOAD DATA
# ==============================================================

@st.cache_data(ttl=5)
def load_results():
    try:
        return pd.read_csv(RESULTS_CSV)
    except Exception:
        return pd.DataFrame()

results = load_results()

if results.empty:
    st.warning("Nessun risultato disponibile")
    st.stop()

# ==============================================================
# SIDEBAR FILTERS
# ==============================================================

st.sidebar.header("🔎 Filtri")
min_rvol = st.sidebar.slider("RVOL minimo", 1.0, 20.0, 5.0)
min_day = st.sidebar.slider("% Giornaliero minimo", 1.0, 30.0, 10.0)

filtered = results[(results.rvol >= min_rvol) & (results.day_pct >= min_day)]

# ==============================================================
# TABLE + SELECTION
# ==============================================================

st.subheader("📊 Scanner Results")
selected = st.multiselect(
    "Seleziona titoli da monitorare",
    options=filtered.symbol.tolist(),
    default=filtered.symbol.tolist()[:3]
)

st.dataframe(filtered, use_container_width=True)

# ==============================================================
# WEBSOCKET LIVE DATA
# ==============================================================

@st.cache_resource
def start_ws(conids):
    ws = IbkrWsClient(start=True)
    for c in conids:
        ws.subscribe(channel=IbkrWsKey.MARKET_DATA.channel, conid=int(c))
    return ws

live_df = filtered[filtered.symbol.isin(selected)]
conids = live_df.conid.dropna().tolist()

live_prices = {}

if conids:
    ws = start_ws(conids)

    st.subheader("⚡ Live Monitor")
    placeholder = st.empty()

    for _ in range(200):
        rows = []
        for c in conids:
            data = ws.get(IbkrWsKey.MARKET_DATA, c)
            if data and "last" in data:
                live_prices[c] = data
                rows.append(data)
        if rows:
            placeholder.dataframe(pd.DataFrame(rows), use_container_width=True)
        time.sleep(REFRESH_SECONDS)

# ==============================================================
# CANDLESTICK + VWAP
# ==============================================================

import plotly.graph_objects as go

st.subheader("📈 Candlestick + VWAP")

selected_symbol = st.selectbox(
    "Seleziona titolo",
    options=live_df.symbol.tolist()
)

if selected_symbol:
    row = live_df[live_df.symbol == selected_symbol].iloc[0]
    conid = int(row.conid)

    # ---- historical intraday (1 min) ----
    hist = ws.history(conid=conid, period="1 D", bar="1 min")
    df = pd.DataFrame(hist)

    if not df.empty:
        df["vwap"] = (df.high + df.low + df.close) / 3

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df.open,
            high=df.high,
            low=df.low,
            close=df.close,
            name="Price"
        ))
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df.vwap,
            mode="lines",
            name="VWAP"
        ))

        fig.update_layout(height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================
# ALERT BUTTONS
# ==============================================================

st.subheader("🔔 Alert")
for _, r in live_df.iterrows():
    if st.button(f"Alert breakout {r.symbol}"):
        send_telegram(f"🚀 Breakout detected: {r.symbol}\nPrice: {r.price}")
        st.success("Alert inviato")

# ==============================================================
# PAPER TRADE (SIMULATO)
# ==============================================================

st.subheader("🤖 Paper Trade")
capital = st.number_input("Capitale simulato ($)", 1000, 100000, 10000)

for _, r in live_df.iterrows():
    qty = int(capital / r.price)
    if st.button(f"BUY {r.symbol} ({qty} shares)"):
        st.success(f"Paper BUY {qty} shares of {r.symbol} @ {r.price}")
        send_telegram(f"🧪 PAPER BUY {r.symbol} {qty} @ {r.price}")

st.caption("Aggiornamento live attivo")
