from typing import List
import pandas as pd
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

class WSManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        logger.info(f"WS CONNECT {self.connections}")


    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)
        logger.info(f"WS DISCONNECT {self.connections}")

    async def send_safe(self,ws: WebSocket, data):
        try:
            await ws.send_json(data)
            return True
        except WebSocketDisconnect:
            logger.error("WebSocketDisconnect",exc_info=True)
            return False
        except RuntimeError:
            logger.error("RuntimeError",exc_info=True)
            return False

    async def broadcast(self, message: dict):
        #logger.info(f"WS SEND {self.connections} ->{message}")
        for ws in self.connections:
            await self.send_safe(ws,message)
            #await ws.send_json(message)

    async def broadcastObj(self, obj):
        #logger.info(f"WS SEND {self.connections} ->{message}")
        for ws in self.connections:
            await self.send_safe(ws,json.dumps(obj))
            #await ws.send_json(message)

# ====================================================

class RenderPage:

    def __init__(self, ws: WSManager, ws_orders: WSManager):
        self.ws=ws
        self.ws_orders=ws_orders    
        #self.connected=True
        pass
    
    async def send(self,msg):
         await self.ws.broadcast(msg)

    async def sendOrder(self,msg):
         await self.ws_orders.broadcast(msg)

