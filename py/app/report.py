import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from widget import *
from renderpage import RenderPage

class ReportWidget(Widget):

    def __init__(self,id):
       super().__init__()
       self.id=id
       
   
    def fill(df):
        pass

    async def notify_candles(self, candles,page:RenderPage):
       pass
       

    def render_html():
        pass

    def from_data(self,data):
        pass
        #type = data["sss"]


    def serialize(self):

        return {
            "report_type":"report",
        }