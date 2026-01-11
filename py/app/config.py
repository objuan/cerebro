import json
import os
import logging

DB_FILE = "db/crypto.db"
CONFIG_FILE = "config/cerebro.json"
PROPS_FILE = "../config/properties.json"


logger = logging.getLogger(__name__)

'''
TIMEFRAME_UPDATE_SECONDS = {
    "1s": 1,
    "5s": 5,
    "10s": 10,
    "15s": 15,
    "30s": 30,
    "1m": 5,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 60*60,
    "2h": 7200,
    "4h": 14400,
    "1d": 60*60*12,
}
TIMEFRAME_LEN_CANDLES = {
    "1s": 1,
    "5s": 5,
    "10s": 10*6* 30,
    "15s": 15,
    "30s": 30,
    "1m": 60*24*4,# 2 gg
    "3m": 180,
    "5m": 12*24*2, #2gg
    "15m": 900,
    "30m": 1800,
    "1h": 24*7,
    "2h": 7200,
    "4h": 14400,
    "1d": 120, # 2 mesi
}
'''

TF_SEC_TO_DESC = {
    10 : "10s",
    30 : "30s",
    60 : "1m",
    300 : "5m",
}
