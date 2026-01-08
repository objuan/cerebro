import pandas as pd
import json
from datetime import datetime, timedelta
from chart import *
from renderpage import *
from reports.top_gain_report import *
from reports.db_dataframe import *
from mulo_client import MuloClient
import uuid
import logging
import asyncio


logger = logging.getLogger(__name__)

class Layout:

    def __init__(self, client: MuloClient, db : DBDataframe, config):
       self.components=[]
       self.client=client
       self.db = db
       self.config=config
       pass

    async def on_render_page_connect(self,render_page):
          for comp in self.components:
            await comp.on_render_page_connect(render_page)
            
    async def tick(self,render_page):
        for comp in self.components:
            await comp.tick(render_page)

    async def load(self):#,page:RenderPage):
        try:
            ''' at startup '''
            all=[]
            for comp in self.components:
                all.append(await comp.load())
            return all
        except:
            logger.error("ERROR",exc_info=True)

    def read(self,filePath):
        self.filePath=filePath
        try:
            with open(filePath, 'r', encoding='utf-8') as file:
                dati_python = json.load(file)
                logger.debug(f"LOAD LAYOUT {dati_python}")
                for comp  in dati_python["components"]:
                    logger.debug(f"LOAD {comp}")

                    w = self.create_widget(comp["id"],comp["widget"])
                    if w:
                        self.addWidget(comp["id"], w,comp["update_time_secs"]).rect = comp["rect"]
                
        except :
            logger.error("Error", exc_info=True)
    
    def saveFile(self,filePath):
        
        all = []
        save = {"components":all}
        for comp in self.components:
            all.append(comp.serialize())

        print(all)
        try:
            with open(filePath, 'w', encoding='utf-8') as file:
                json.dump(save, file, indent=4, ensure_ascii=False)
        except :
            logger.error("Error", exc_info=True)

    def from_data(self,datas):
        logger.info(f"save {datas}")
        if len(datas) != len(self.components):
            logger.error("LEN SIZE !!!!")
            return
        
        for i in range(0,len(datas) ):
            self.components[i].from_data(datas[i])

        self.saveFile(self.filePath)

    def setDefault(self):
        pass
        #chart = ChartWidget("BTC/USDC","1m")
        #self.addWidget( chart)

    def addWidget(self,id,widget,update_time_secs)-> "LayoutComponent":
        comp = LayoutComponent(id,update_time_secs)
        comp.setWidget(widget)
        self.components.append(comp)
        return comp


    def create_widget(self,id, cmd):
        if cmd["type"] =="chart":
                logger.debug(f'CREATE CHART {cmd}')
                return ChartWidget(id, cmd["symbol"] ,cmd["timeframe"],cmd["plot_config"] )
        
        if cmd["type"] =="multi_chart":
                logger.debug(f'CREATE CHART {cmd}')
                return ChartWidget(id, cmd["symbol"] ,0,cmd["plot_config"] )
    
        if cmd["type"] =="report":
                logger.debug(f'CREATE REPORT {cmd}')
                report_type = cmd["report_type"]
                if report_type =="top_gain":
                    return TopGainReportWidget(id,self.client,self.db)
                #return ChartWidget(id, cmd["symbol"] ,cmd["timeframe"],cmd["plot_config"] )
        return None
    
    async def process_cmd(self,cmd,page:RenderPage):
        if cmd["cmd"] =="add":
           id = str(uuid.uuid4())
           w = self.create_widget(id,cmd)
           comp = self.addWidget(id, w,cmd["update_time_secs"])
           comp.rect = {"w":4, "h":4}
           if comp :
               await comp.load(page)
        if cmd["cmd"] =="del":
           id = cmd["id"]
           comp  = next((u for u in self.components if u.id == id), None)
           logger.info(f"delete comp : {comp}")
           if comp:
               self.components.remove(comp)
               await page.send({"type":"del","id": id})

    async def notify_candles(self, candles,page:RenderPage):
        for comp in self.components:
            await comp.notify_candles(candles,page)
       
##################################################

class LayoutComponent:

    def __init__(self, id,update_time_secs):
       self.id=id
       self.rect=""
       self.widget=None
       self.update_time_secs=update_time_secs
       self.last_update = datetime.now()
       self.firstTime = True
       #self.id = str(uuid.uuid4())

    '''
    async def on_render_page_connect(self,render_page):
        if  self.firstTime:
            msg=self.serialize()
            logger.info(f"--> {msg}")
            await render_page.send(msg)
    
       #await self.widget.tick(render_page)
       # self.firstTime=False
    '''

    async def tick(self,render_page):
        if self.firstTime:
             await self.widget.tick(render_page)
             self.firstTime=False
        else:
            if (datetime.now() - self.last_update).total_seconds() > self.update_time_secs:
                self.last_update = datetime.now()
                await self.widget.tick(render_page)

    async def load(self):#,page:RenderPage):
        ''' at startup '''
        #await self.widget.tick(page)

        msg=self.serialize()
        #logger.info(f"LOAD --> {msg}")
        return msg
        #await page.send(msg)

        #await self.widget.tick(page)
        #self.widget.load(page)

    def from_data(self,data):
        self.rect = data["rect"]
        self.widget.from_data(data["data"])
        #logger.info(data)
        

    def serialize(self):
        return {
            "id": self.id ,
            "type": "comp",
            "rect" : self.rect,
            "update_time_secs" : self.update_time_secs,
            "widget" : self.widget.serialize()
        }

    def setWidget(self,widget:Widget):
        self.widget=widget

        
    async def notify_candles(self, candles,page:RenderPage):
        await self.widget.notify_candles(candles,page)



