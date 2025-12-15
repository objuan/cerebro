from ibind import IbkrClient, IbkrWsClient,IbkrWsKey
from ibind.oauth.oauth1a import OAuth1aConfig
from ibind import ibind_logs_initialize
import pandas as pd
import time

ibind_logs_initialize()

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

client = IbkrClient()

# Call some endpoints
print('\n#### check_health ####')
print(client.check_health())

client.tickle()  # mantiene viva la sessione

symbols =[]

def get_conid(symbol):
    r = client.symbol_search(symbol)
    for item in r.data:
        if item["symbol"] == symbol and item["assetClass"] == "STK":
            return item["conid"]
    return None

for symbol in symbols:
    conid = get_conid(symbol)    

    #PREZZO TRA 2 E 20 $
    def get_price(conid):
        r = client.marketdata_snapshot(conids=[conid], fields=["31"])
        snap = r.data[0]
        return float(snap.get("31", 0))  # last price

    price = get_price(conid)
    if not (2 <= price <= 20):
        continue

    #VOLUME ≥ 5× MEDIA
    def get_daily_bars(conid):
        r = client.marketdata_history(
            conid=conid,
            period="30d",
            bar="1d",
            outsideRth=False
        )
        return pd.DataFrame(r.data)

    df = get_daily_bars(conid)
    avg_vol = df["volume"][:-1].mean()
    today_vol = df["volume"].iloc[-1]

    if today_vol < 5 * avg_vol:
        continue

    #PREMARKET ≥ +2
    def get_premarket_pct(conid):
        r = client.marketdata_history(
            conid=conid,
            period="1d",
            bar="5min",
            outsideRth=True
        )
        df = pd.DataFrame(r.data)
        pm = df[df["time"].str.contains("T")]  # semplificazione
        if len(pm) < 2:
            return 0
        return (pm.iloc[-1]["close"] - pm.iloc[0]["open"]) / pm.iloc[0]["open"] * 100
    
    if get_premarket_pct(conid) < 2:
        continue

    #GIORNO ≥ +10%
    def get_day_pct(conid):
        r = client.marketdata_history(
            conid=conid,
            period="1d",
            bar="5min",
            outsideRth=False
        )
        df = pd.DataFrame(r.data)
        return (df.iloc[-1]["close"] - df.iloc[0]["open"]) / df.iloc[0]["open"] * 100

    if get_day_pct(conid) < 10:
        continue

    #FLOAT (OBBLIGATORIO ESTERNO)
    '''
    Tipico “low float”:
    < 20M = molto aggressivo
    < 50M = ancora valido
    '''
    def get_float(symbol):
        return float_cache.get(symbol)  # es: < 30M

    if get_float(symbol) > 30_000_000:
        continue