import asyncio
from datetime import datetime
from decimal import Decimal
from binance import AsyncClient, BinanceSocketManager
import logging

if __name__ =="__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

logger = logging.getLogger()

class BinanceStreamer:
    def __init__(self):
        self.client = None
        self.bm = None
        self.socket = None
        self.stream_task = None
        self.symbols = []
        self.running = False
        self.summary = {}
     
    async def start(self, onReceive):
        self.onReceive=onReceive
        self.client = await AsyncClient.create()
        self.bm = BinanceSocketManager(self.client)
        self.running = True

    async def stop(self):
        self.running = False

        if self.stream_task:
            self.stream_task.cancel()

        if self.client:
            await self.client.close_connection()

    async def set_symbols(self, symbols):
        logger.info(f"BINANCE >> {symbols}")
        self.symbols = symbols

        # se già in esecuzione → riavvia stream
        if self.stream_task:
            self.stream_task.cancel()

        self.stream_task = asyncio.create_task(self._run_stream())

    '''
     {'stream': 'zkpusdc@ticker', 'data': {'e': '24hrTicker', 'E': 1777379751499, 's': 'ZKPUSDC', 'p': '0.01180000', 'P': '14.550', 'w': '0.08879922', 'x': '0.08100000', 'c': '0.09290000', 'Q': '1384.70000000', 'b': '0.09280000', 'B': '1000.00000000', 'a': '0.09300000', 'A': '8921.30000000', 'o': '0.08110000', 'h': '0.09650000', 'l': '0.08040000', 'v': '2327050.60000000', 'q': '206640.26845000', 'O': 1777293351328, 'C': 1777379751328, 'F': 425314, 'L': 426652, 'n': 1339}}
    '''
    async def _run_stream(self):
        #logger.info(f"✅ _run_stream: {self.symbols}")

        if not self.symbols:
            return
        #logger.info("1")
        #streams = [f"{s.lower()}@ticker" for s in self.symbols]
        #streams = [f"{s.lower()}@aggTrade" for s in self.symbols]
        streams = []
        for s in self.symbols:
            s = s.lower()
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@ticker")
            
        #logger.info("2")
        socket = self.bm.multiplex_socket(streams)
        
        #logger.info("3")
        try:
          

            async with socket as stream:
                logger.info(f"✅ Streaming: {self.symbols}")

                while self.running:
                    msg = await stream.recv()
                    
                    try:
                        

                        if "data" in msg:
                            event = msg["data"]
                            #logger.info(f"{event}")

                            symbol = event["s"]
                            if not symbol in self.summary:
                                self.summary[symbol]={"v_acc": 0 ,"qv_day": 0,"v_day" : 0 , "g_day" : 0}
                               
                            sum = self.summary[symbol]

                            if event["e"] == "24hrTicker":
                                sum["g_day"] = float(event["P"]) # in perc
                                sum["v_day"] =float(event["v"])
                                sum["qv_day"] =float(event["q"]) # volume in USDC

                            if event["e"] == "aggTrade":

                                #logger.info(f"{sum}")
                                qty = float(event["q"])      # 🔥 quantità reale trade
                                price = float(event["p"])
                                
                                volume = qty
                                quote_volume = qty * price
                                timestamp = event["T"] /1000 # ms

                                sum["v_acc"]+=volume
                            
                                '''
                                price = float(ticker["c"])
                                volume = float(ticker["v"])      # volume base asset
                                quote_volume = float(ticker["q"]) # volume in USDT
                                gain_24 = float(ticker["p"])
                                
                                timestamp = ticker["E"] /1000 # ms
                                '''

                                #change = float(ticker["P"])
                                #logger.info(f"{symbol} → {price:.2f} ({volume:.2f}) {timestamp} {self.onReceive}")

                                await self.onReceive(symbol,timestamp, price, volume,sum["v_acc"],sum["v_day"] ,sum["qv_day"],sum["g_day"])

                            #logger.info(f"{symbol} → {price:.2f} ({volume:.2f}) {timestamp} {self.onReceive}")
                    except:
                        logger.error("STREAM", exc_info=True)

        except asyncio.CancelledError:
            logger.error("🔁 Stream riavviato")
        except Exception as e:
            logger.error("❌ Errore stream:", e)

if __name__ =="__main__":

  
 
    async def main():

        s = BinanceStreamer()
        
        async def onReceive(symbol,time, price,volume, volume_acc,day_volume, day_quotevolume,gain_24_perc):
            dt =  datetime.utcfromtimestamp(time)
            

            line = f"{symbol},{time},{dt}, {price:.4f},{volume},{volume_acc},{day_volume},{day_quotevolume},{gain_24_perc}\n"

            #logger.info(f"{symbol} →  {time} {price:.2f} v:{volume} acc: {volume_acc} v : {day_volume} q : {day_quotevolume} g:{gain_24_perc}")
            logger.info(line)
            # Scrittura async-safe (semplice)
            async with asyncio.Lock():
                with open("market_data.csv", "a") as f:
                    f.write(line)
                                                
                          
        await s.start(onReceive)

        await s.set_symbols(["DOGSUSDC"])

        while True:
            await asyncio.sleep(0.1)
    
    asyncio.run(main())