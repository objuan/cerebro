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

    def __init__(self, config,db:DBDataframe,render_page : RenderPage):
   
        self.db = db
        self.render_page=render_page
                
        self.strategies = []
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

    async def bootstrap(self):

        for strat in self.strategies:
            await strat.bootstrap()