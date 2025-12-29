import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from widget import *
from renderpage import RenderPage

class ChartWidget(Widget):

    def __init__(self,id, symbol, timeframe,plot_config={}):
       super().__init__()
       self.id=id
       self.plot_config=plot_config
    
       self.set(symbol,timeframe)
       
    def set(self,symbol,timeframe):
        self.symbol=symbol
        self.timeframe=timeframe
        

    async def notify_candles(self, candles,page:RenderPage):
       
       for candle in candles:
           #logger.info(candle["tf"] )
           if candle["symbol"] == self.symbol and candle["tf"] == self.timeframe:
               #logger.info(f"notify_candles {candle}")

               await page.send({
                   "id" : self.id,
                   "type" : "candle",
                   "data": candle
               })
       

    def render_html():
        pass

    def from_data(self,data):
      
        self.symbol = data["symbol"]
        self.timeframe = data["timeframe"]
        self.plot_config = data["plot_config"]

    def serialize(self):
        #print( "...",self.plot_config)
        return {
            "type":"chart",
            "symbol" : self.symbol,
            "timeframe": self.timeframe,
            "plot_config":  self.plot_config,
        }