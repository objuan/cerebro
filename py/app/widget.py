import pandas as pd
import sqlite3
import time
import ccxt
from datetime import datetime, timedelta

from renderpage import *

class Widget:

    def __init__(self):
       self.tickCont=0
       pass

    async def tick(self,render_page):
        if self.tickCont==0:
            if self.onStart(render_page) :
                self.tickCont=self.tickCont+1
        await self.onTick(render_page)

    def onStart(self,render_page)-> bool:
        return True

    async def onTick(self,render_page):
        pass

    def serialize(self):
        pass

    def render_html():
        pass



