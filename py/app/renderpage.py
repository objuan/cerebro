from typing import List
import pandas as pd
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta

class WSManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, message: dict):
        for ws in self.connections:
            await ws.send_json(message)

# ====================================================

class RenderPage:

    def __init__(self, ws: WSManager):
        self.ws=ws
        pass
    
    async def send(self,msg):
         await self.ws.broadcast(msg)

