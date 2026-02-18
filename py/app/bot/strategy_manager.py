from typing import Dict
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from company_loaders import *
from collections import deque

import importlib
import sys
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bot.indicators import Indicator
#from strategy.strategies import *

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler

class StrategyReloader(FileSystemEventHandler):

    def __init__(self, bot, config,client, strategies_path):
        self.bot = bot
        self.client=client
        self.strategies_path = strategies_path
        self.config = config
        self._last_event = {}  # file -> timestamp
        self._debounce_seconds = 0.5
        self._reload_lock = asyncio.Lock()

    def on_modified(self, event):

        if event.is_directory:
            return

        if not event.src_path.endswith(".py"):
            return

        file_path = Path(event.src_path)
        now = time.time()

        last_time = self._last_event.get(event.src_path, 0)

        # se evento troppo ravvicinato → ignora
        if now - last_time < self._debounce_seconds:
            return

        self._last_event[event.src_path] = now

        async def task():
            await self.bot.reload_strategies(file_path.stem)

        #print(self.client.ib_loop)
        self.client.ib_loop.call_soon_threadsafe(
                asyncio.create_task,
                self.bot.reload_strategies(file_path.stem)
            )
        
        #asyncio.create_task(task)

        #self.bot.reload_strategies(file_path.stem)

############################

class StrategyManager:

    def __init__(self, config,db:DBDataframe,client, render_page : RenderPage):
        
        self.config=config
        self.logger=logger
        self.db = db
        self.render_page=render_page
        self.client = client
        self.db.on_symbol_added += self.on_symbol_added
        self.db.on_symbol_removed += self.on_symbol_removed
        self._modules_cache = {}
           
        strategy_folder = self.config["live_service"]["strategy_folder"]
        self.package_name = strategy_folder

        self.strategies = []


    async def bootstrap(self):
        self.load_strategies()
        self.start_watcher()
        for strat in self.strategies:
            await strat["instance"].bootstrap()

    def start_watcher(self):
        root = self.config["live_service"]["root_folder"]
        strategy_folder = self.config["live_service"]["strategy_folder"]
        strategies_path = Path.cwd() /root/strategy_folder

        logger.info(f"strategies PATH {strategies_path}")
        event_handler = StrategyReloader(self, self.config,self.client,strategies_path)
        observer = Observer()
        observer.schedule(event_handler, path=strategies_path, recursive=False)
        observer.start()

    # -------------------------
    # LOAD STRATEGIES
    # -------------------------
    def load_strategies(self):

        self.strategies.clear()

        if "stategies" in self.config:
            for strat_def in self.config["stategies"]:

                module_name = self.package_name+"."+strat_def["module"]   # es: strategies.my_strategy
                class_name = strat_def["class"]

                self.logger.info(f"LOAD MODULE {module_name}")
                #module = importlib.import_module(module_name)
                   # -------------------------
                # LOAD MODULE (con cache)
                # -------------------------
                if module_name in self._modules_cache:
                    module = self._modules_cache[module_name]
                    self.logger.info(f"MODULE FROM CACHE {module_name}")
                else:
                 
                    module = importlib.import_module(module_name)
                    self._modules_cache[module_name] = module
                    self.logger.info(f"LOAD MODULE DONE {module}")

                 # -------------------------
                # LOAD CLASS
                # -------------------------
                cls = getattr(module, class_name)

                strat = cls(self)
                strat.load(strat_def)

                self.logger.info(f"ADD STRAT {strat_def} {strat}")


                self.strategies.append({
                    "instance": strat,
                    "def" : strat_def,
                    "module": module,
                    "module_name": module_name,
                    "class_name": class_name
                })

    async def reload_strategies(self, module):

        module = self.package_name+"."+module

        self.logger.info(f"Reloading strategies '{module}'")

        reloaded_modules = {}

        for strat_info in self.strategies:

            module_name = strat_info["module_name"]

            if module_name == module:
                logger.info(f"ELAB MODULE '{module_name}'")
                # Reload solo una volta per modulo
                if module_name not in reloaded_modules:

                    self.logger.info(f"RELOAD MODULE {module_name}")

                    module = importlib.reload(self._modules_cache[module_name])
                    self._modules_cache[module_name] = module
                    reloaded_modules[module_name] = module
                else:
                    module = reloaded_modules[module_name]

                class_name = strat_info["class_name"]

                try:
                    cls = getattr(module, class_name)

                    old_instance = strat_info["instance"]

                    # opzionale: stop pulito
                    if hasattr(old_instance, "dispose"):
                        old_instance.dispose()

                    new_instance = cls(self)
               
                    strat_def = strat_info["def"]

                    new_instance.load(strat_def)

                    self.logger.info(f"ADD STRATEGY {strat_def} {new_instance}")

                    strat_info["instance"] = new_instance

                    self.logger.info(f"RELOADED {class_name}")

                    await new_instance.bootstrap()

                except Exception as e:
                    self.logger.error(f"Reload failed for {class_name}: {e}", exc_info=True)

    #################

    async def on_symbol_added(self, df : DBDataframe_TimeFrame, symbol):
         for strat in self.strategies:
            await strat["instance"].on_symbols_update(df,[symbol],[])

    async def on_symbol_removed(self,  df : DBDataframe_TimeFrame, symbol):
         for strat in self.strategies:
            await strat["instance"].on_symbols_update(df, [], [symbol])

    def live_indicators(self,symbol,timeframe,since):
        list = []
        for strat in self.strategies:
            i = strat["instance"].live_indicators(symbol,timeframe,since)
            if i:
                list.append(i)
        return list
############################################


   