import asyncio
from contextlib import asynccontextmanager
import json
import sqlite3
from datetime import datetime,time
import time as _time
import math
import os
import signal
import json
from typing import Optional
from collections import deque
import requests
import urllib3
import yfinance as yf
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from ib_insync import *
from utils import convert_json
util.startLoop()  # uncomment this line when in a notebook
from config import DB_FILE,CONFIG_FILE
from market import *
from utils import datetime_to_unix_ms,sanitize,floor_ts
from company_loaders import *
from renderpage import WSManager
from order import OrderManager
from mulo_job import MuloJob

class MuloSym:
    def __init__(self, symbol: str, ib: IB, ws_manager: WSManager, order_manager: OrderManager, config: dict):
        self.symbol = symbol
        self.ib = ib
        self.ws_manager = ws_manager
        self.order_manager = order_manager
        self.config = config
        self.logger = logging.getLogger(f'MuloSym-{self.symbol}')
        self.logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler(f'logs/{self.symbol}.log', maxBytes=1000000, backupCount=3)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.contract = Stock(self.symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(self.contract)
        self.market_data = {}
        self.orders = []
        self.jobs = []
        self.load_initial_data()

    def load_initial_data(self):
        self.logger.info(f'Loading initial data for {self.symbol}')
        ticker = yf.Ticker(self.symbol)
        hist = ticker.history(period="1mo", interval="1d")
        self.market_data['historical'] = hist
        self.logger.info(f'Loaded historical data for {self.symbol}')

    async def start(self):
        self.logger.info(f'Starting MuloSym for {self.symbol}')
        await self.subscribe_market_data()
        await self.process_orders()

    async def subscribe_market_data(self):
        self.logger.info(f'Subscribing to market data for {self.symbol}')
        ticker = self.ib.reqMktData(self.contract, '', False, False)
        while True:
            await asyncio.sleep(1)
            if ticker.last:
                self.market_data['last_price'] = ticker.last
                self.ws_manager.send_update(self.symbol, {'last_price': ticker.last})
                self.logger.debug(f'Updated last price for {self.symbol}: {ticker.last}')

    async def process_orders(self):
        self.logger.info(f'Processing orders for {self.symbol}')
        while True:
            await asyncio.sleep(5)
            for order in self.orders:
                if not order.filled:
                    self.logger.info(f'Checking order status for {order.orderId}')
                    trade = self.ib.trades().find(lambda t: t.order.orderId == order.orderId