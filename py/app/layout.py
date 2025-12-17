import pandas as pd
import json
from datetime import datetime, timedelta
from chart import *
from renderpage import *
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)

class Layout:

    def __init__(self):
       self.components=[]
       pass

    async def load(self,page:RenderPage):
        try:
            ''' at startup '''
            for comp in self.components:
                await comp.load(page)
        except:
            logger.error("ERROR",exc_info=True)

    def render_html():
        
        pass

    def read(self,filePath):
        self.filePath=filePath
        try:
            with open(filePath, 'r', encoding='utf-8') as file:
                dati_python = json.load(file)
                logger.info(f"LOAD LAYOUT {dati_python}")
                for comp  in dati_python["components"]:
                    logger.info(f"LOAD {comp}")

                    w = self.create_widget(comp["id"],comp["widget"])
                    if w:
                        self.addWidget(comp["id"], w).rect = comp["rect"]
                
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

    def addWidget(self,id,widget)-> "LayoutComponent":
        comp = LayoutComponent(id)
        comp.setWidget(widget)
        self.components.append(comp)
        return comp


    def create_widget(self,id, cmd):
        if cmd["type"] =="chart":
                logger.info(f'CREATE CHART {cmd}')
                return ChartWidget(id, cmd["pair"] ,cmd["timeframe"],cmd["plot_config"] )
        return None
    
    async def process_cmd(self,cmd,page:RenderPage):
        if cmd["cmd"] =="add":
           id = str(uuid.uuid4())
           w = self.create_widget(id,cmd)
           comp = self.addWidget(id, w)
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

    def __init__(self, id):
       self.id=id
       self.rect=""
       self.widget=None
       #self.id = str(uuid.uuid4())


    async def load(self,page:RenderPage):
        ''' at startup '''
        msg=self.serialize()
        logger.info(f"--> {msg}")
        await page.send(msg)
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
            "widget" : self.widget.serialize()
        }

    def setWidget(self,widget:Widget):
        self.widget=widget

        
    async def notify_candles(self, candles,page:RenderPage):
        await self.widget.notify_candles(candles,page)

    def render_html():
        pass


