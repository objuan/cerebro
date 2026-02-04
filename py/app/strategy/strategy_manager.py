from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from company_loaders import *
from collections import deque

from strategy.indicators import Indicator
from strategy.strategies import *

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager


############################

class StrategyManager:

    def __init__(self, config,db:DBDataframe,client, render_page : RenderPage):
   
        self.db = db
        self.render_page=render_page
        self.client = client
        self.db.on_symbol_added += self.on_symbol_added
        self.db.on_symbol_removed += self.on_symbol_removed
                
        self.strategies = []
        if "stategies" in config:
            for strat_def in config["stategies"]:

                name = strat_def["class"]
                cls = globals().get(name)
                if cls is None:
                    raise ValueError(f"Strategy class {name} not found")

                strat = cls(self)
                strat.load(strat_def)

                logger.info(f"ADD STRAT {strat_def} {strat}")

                self.strategies.append(strat)

                #self.scheduler.schedule_every(strat.time, strat.handler,self, * strat.args)

            pass

    async def on_symbol_added(self, df : DBDataframe_TimeFrame, symbol):
         for strat in self.strategies:
            await strat.on_symbols_update(df,[symbol],[])

    async def on_symbol_removed(self,  df : DBDataframe_TimeFrame, symbol):
         for strat in self.strategies:
            await strat.on_symbols_update(df, [], [symbol])

    async def bootstrap(self):

        for strat in self.strategies:
            await strat.bootstrap()