import yfinance as yf
import financedatabase as fd  # se installi FinanceDatabase
import pandas as pd
import sqlite3
import json
from datetime import datetime, timezone
import zoneinfo  # disponibile da Python 3.9 in poi
import threading, time
from database import *

def nasdaq():
    # 1. Scarica la lista ticker (esempio – Nasdaq)
    url = "https://datahub.io/core/nasdaq-listings/r/nasdaq-listed.csv"
    df_tickers = pd.read_csv(url, usecols=["Symbol"])
    tickers = df_tickers["Symbol"].tolist()

    print(f"Numero di ticker caricati: {len(tickers)}")
    print("Prime 10:", tickers[:10])

    # 2. Usa yfinance per ottenere info per alcuni ticker
    sample = tickers[:5]
    data = yf.download(sample, period="1d")
    print(data.head())

def all():
    # 1. Carica la DB
    equities = fd.Equities()
    df_symbols = equities.select()   # questo restituisce DataFrame con tutti i simboli

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM ticker")
    conn.commit()

    it_data = df_symbols[df_symbols['country'] == 'Italy']
    for i, (index, row) in enumerate(it_data.iterrows()):
        print("..",index,row["name"])

        cur.execute(f"""
        INSERT INTO ticker (id,
            name, summary, currency, sector, industry_group, industry,
            exchange, market, country, state, city, zipcode, website,
            market_cap, isin, cusip, figi, composite_figi, shareclass_figi, fineco
        ) VALUES ('{index}', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,0)
            """, tuple(row[col] for col in [
                "name", "summary", "currency", "sector", "industry_group", "industry",
                "exchange", "market", "country", "state", "city", "zipcode", "website",
                "market_cap", "isin", "cusip", "figi", "composite_figi", "shareclass_figi"
            ]))
        conn.commit()

        #break
    
    conn.close()


def fill_yahoo(country):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"select id from ticker where country ='{country}'")
    _tickers=[]
    for row in  cur.fetchall():    
        _tickers.append(row[0]) 
    
    #print(tickers)
    
    pack = 0

    while (pack < len(_tickers)):
        tickers = _tickers[pack: pack +10]
        pack=pack+10

        print(tickers)

        if True:
            #tickers= ["ENI.MI","AAPL","KK"]
            #df = yf.download(["ENI.MI","AAPL","KK"], period="1d")
            df = yf.download(tickers,
                        period="1d",
                        group_by="ticker",
                        threads=True,
                        progress=True,
                        multi_level_index=False)
            #print(df)
        
            open_df = df.xs('Open', axis=1, level='Price')
            if len(open_df)>0:
                print(open_df)
                opens_dict = open_df.iloc[0].to_dict()
                print(opens_dict)

                for ticker in tickers:
                    if (str(opens_dict[ticker]) != "nan"):
                        print(ticker, opens_dict[ticker])
                        cur.execute(f"UPDATE ticker set yahoo=1 WHERE id='{ticker}'")
                        conn.commit()
 
    '''
    df = df.T
    df.index.names = ["Price","Ticker"]
    tickers = df.index.get_level_values("Ticker").unique().tolist()
    df = yf.download(["ENI.MI","AAPL","KK"], period="1d")

    #for i, (index, row) in enumerate(df.iterrows()):
    #print("..",index)

    present = []
    not_present = []

    for ticker in tickers:
        print("UPDATE",ticker)

        try:
            # verifica se il ticker ha dati nel DataFrame
            if ticker in df.columns.get_level_values(0):
                present.append(ticker)
            else:
                not_present.append(ticker)
        except Exception as e:
            not_present.append(ticker)
    
        #cur.execute(f"UPDATE ticker set yahoo=1 WHERE id='{ticker}'")
        #conn.commit()

    print(present)
    print(not_present)

    #print(tickers)
    conn.close()
    #for i, (index, row) in enumerate(data.iterrows()):
    #    print("..",row["Ticker"])
 '''
#all()

def fill_fineco(file,exchange,market, index,cap):

    # Apri e leggi il file
    with open(file,  "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]  # rimuove spazi e righe vuote
   
    # Dividi in gruppi di 6 righe
    groups = [lines[i:i+4] for i in range(0, len(lines), 4)]

    # Estrai la prima (nome) e la terza (ticker) di ogni gruppo
    estratti = [(g[0], g[1]) for g in groups if len(g) >= 2]

    conn = get_connection()
    cur = conn.cursor()
    #cur.execute(f"select id from ticker where country ='{country}'")

    for e in estratti:
        nome = e[0]
        id = e[1]
        print(id,nome)
        df = select("select * from ticker where id='"+id+"'")
        if (len(df)>0):
            print("FOUND")
            cur.execute(f"UPDATE ticker set fineco=1 WHERE id='{id}'")
            conn.commit()
        else:
             print("INSERT")
             cur.execute(f"""
                INSERT INTO ticker (id,name, exchange, market,market_index, market_cap,fineco
                ) VALUES (?, ?, ?, ?, ?,?,1 )
                    """, (id,nome,exchange,market,index,cap))
        conn.commit()

    #print(estratti)

fill_fineco("config/FTSEMIB.txt","MIL","Borsa Italiana","FTSEMIB","Large Cap")
fill_fineco("config/MI_MIDCAP.txt","MIL","Borsa Italiana","MIDCAP","Mid Cap")

#fill_yahoo("Italy")


