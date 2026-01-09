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
        

    async def notify_candles(self, candle,page:RenderPage):
       
       #for candle in candles:
           #logger.info(f"{candle['tf']} { self.timeframe} { self.symbol}" )
           if candle["s"] == self.symbol and (self.timeframe==0 or candle["tf"] == self.timeframe):
               #logger.info(f"notify_candles {candle}")

               await page.send({
                   "id" : self.id,
                   "type" : "candle",
                   "data": candle
               })
       
    async def notify_ticker(self, ticker,page:RenderPage):
        #logger.info(f"notify_ticker {ticker}")
        await page.send({
                   "type" : "ticker",
                   "data": ticker
               })

    def render_html():
        pass

    def from_data(self,data):
      
        if "timeframe" in data:
            self.timeframe = data["timeframe"]

        self.symbol = data["symbol"]
        self.plot_config = data["plot_config"]

    def serialize(self):
        #print( "...",self.plot_config)
        if self.timeframe == 0:
            return {
                "type":"multi_chart",
                "symbol" : self.symbol,
                "timeframe": self.timeframe,
                "plot_config":  self.plot_config,
        }
        else:
            return {
                "type":"chart",
                "symbol" : self.symbol,
                "timeframe": self.timeframe,
                "plot_config":  self.plot_config,
            }