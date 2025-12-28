import asyncio
import json
import websockets
import sqlite3
from datetime import datetime
import time
import os
import signal
import json
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import *
util.startLoop()  # uncomment this line when in a notebook

# https://rawgit.com/erdewit/ib_insync/master/docs/html/api.html#ib_insync.ib.IB.qualifyContracts

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

def get_market_data(symbol,exchange):
    
    contract = Stock(symbol, exchange, 'USD')
    ib.qualifyContracts(contract)

    ticker = ib.reqMktData(contract, '', False, False)
    ib.sleep(2)

    print("Last:", ticker.last)
    print("Bid:", ticker.bid)
    print("Ask:", ticker.ask)
    print("Volume:", ticker.volume)
    print("High:", ticker.high)
    print("Low:", ticker.low)

    logger.info(f"Market1 {symbol}")

    return {"status": "ok"}

def get_fundamentals():
    contract = Stock('NVDA', 'SMART', 'USD')
    ib.qualifyContracts(contract)
    ib.sleep(1)  # IMPORTANTISSIMO

    print(contract)
    xml_data = ib.reqFundamentalData(contract, 'CompanyOverview')

    print(xml_data[:500])  # preview XML

    ib.disconnect()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def get_yahoo_session():
    s = requests.Session()
    r = s.get("https://finance.yahoo.com", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return s


def get_floating_shares(symbol):
    session = get_yahoo_session()
    print(session)

    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {
        "modules": "defaultKeyStatistics"
    }

    r = session.get(url, headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()

    stats = r.json()["quoteSummary"]["result"][0]["defaultKeyStatistics"]

    return {
        "floatShares": stats["floatShares"]["raw"],
        "sharesOutstanding": stats["sharesOutstanding"]["raw"]
    }




######################################

if __name__ =="__main__":

    #############
    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
            "logs/tws_broker.log",
            maxBytes=5_000_000,
            backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    #############

    logger.info("=================================================")
    logger.info("               IBROKER TEST ")
    logger.info("=================================================")

    try:
       #get_market_data("NVDA","SMART")
       print(get_floating_shares("NVDA"))

    except:
        logger.error("ERROR", exc_info=True)
    #clean_up()