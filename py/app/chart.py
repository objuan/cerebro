import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from widget import *
from renderpage import RenderPage

class ChartWidget(Widget):

    def __init__(self,id, pair, timeframe,plot_config={}):
       self.id=id
       self.plot_config=plot_config
    
       self.set(pair,timeframe)
       
    def set(self,pair,timeframe):
        self.pair=pair
        self.timeframe=timeframe
        

    async def notify_candles(self, candles,page:RenderPage):

       for candle in candles:
           if candle["pair"] == self.pair and candle["tf"] == self.timeframe:
               #logger.info(f"notify_candles {candle}")

               await page.send({
                   "id" : self.id,
                   "type" : "candle",
                   "data": candle
               })
       

    def render_html():
        pass

    def from_data(self,data):
      
        self.pair = data["pair"]
        self.timeframe = data["timeframe"]
        self.plot_config = data["plot_config"]

    def serialize(self):
        #print( "...",self.plot_config)
        return {
            "type":"chart",
            "pair" : self.pair,
            "timeframe": self.timeframe,
            "plot_config":  self.plot_config,
        }