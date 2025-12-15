from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
import pandas as pd
import sqlite3
import time
import ccxt
from datetime import datetime, timedelta

#from scanner.crypto import ohlc_history_manager

RETENTION_DAYS = 1

def ms(ts):
    return int(ts * 1000)

def now_ms():
    return int(time.time() * 1000)

def week_ago_ms():
    return ms(time.time() - RETENTION_DAYS * 86400)


class Job:

    def __init__(self):
       pass

    def tick(self):
       pass