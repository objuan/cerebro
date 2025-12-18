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

    def tick(self):
        if self.tickCont==0:
            if self.onStart() :
                self.tickCont=self.tickCont+1
        self.onTick()

    def onStart(self)-> bool:
        return True

    def onTick(self):
        pass

    def serialize(self):
        pass

    def render_html():
        pass



