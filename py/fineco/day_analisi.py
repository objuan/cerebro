import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys, traceback
from datetime import datetime, timedelta

from common import *
from strategy import *
from database import *
from utils import *
from analisi import scan_open_prob

import logging
from logging.handlers import RotatingFileHandler
import mplfinance as mpf
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- LOGGER CONFIG ---

logger = logging.getLogger(__name__)

def elapse(tickers,useHistory, lastDays,maxDayOrders)-> list[Order]:
    last_day = datetime.now()
    #last_day =(last_day - timedelta(days=1))
    first_day =(last_day - timedelta(days=lastDays))
    logger.info(f"SCAN FROM {first_day} to {last_day}")

    #tickers = select("SELECT id from ticker where fineco=1 ")["id"].to_list()
    #tickers = ["BMPS.MI"]
    logger.info(f"USER {tickers}")

    ret = scan_open_prob(tickers,first_day,last_day,useHistory,maxDayOrders)
    if (len(ret.keys())>1):
        logger.error("MULTIPLE DAY")
        return []
    elif (len(ret.keys())==0):
        logger.info("EMPTY DAY")
        return []
    else:
        key, value = next(iter(ret.items()))
        print(key)
        return value

if __name__ == "__main__":

    import os
   
    # Crea cartella logs
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=5_000_000,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


    #tickers = select("SELECT id from ticker where fineco=1 and market_cap = 'Large Cap' order by id ")["id"].to_list()
    tickers = select("SELECT distinct id from live_quotes  order by id ")["id"].to_list()

    #tickers = ["BMED.MI"]
    lastDays=2
    #if datetime.now.weekday() == 0:
    lastDays=4

    ret = elapse(tickers,useHistory=False,lastDays= lastDays,maxDayOrders=2222)
    print(ret)



    