import asyncio
from binance import AsyncClient, BinanceSocketManager
import logging

logger = logging.getLogger()

class BinanceStreamer:
    def __init__(self):
        self.client = None
        self.bm = None
        self.socket = None
        self.stream_task = None
        self.symbols = []
        self.running = False

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
        streams = [f"{s.lower()}@ticker" for s in self.symbols]
        #logger.info("2")
        socket = self.bm.multiplex_socket(streams)
        #logger.info("3")
        try:
          

            async with socket as stream:
                logger.info(f"✅ Streaming: {self.symbols}")

                while self.running:
                    msg = await stream.recv()
                    
                    try:
                      #logger.info(f"{msg}")

                        if "data" in msg:
                            ticker = msg["data"]

                            symbol = ticker["s"]
                            price = float(ticker["c"])
                            volume = float(ticker["v"])      # volume base asset
                            quote_volume = float(ticker["q"]) # volume in USDT

                            timestamp = ticker["E"] /1000 # ms

                            #change = float(ticker["P"])
                            #logger.info(f"{symbol} → {price:.2f} ({volume:.2f}) {timestamp} {self.onReceive}")

                            await self.onReceive(symbol,price,volume,quote_volume,timestamp)

                            #logger.info(f"{symbol} → {price:.2f} ({volume:.2f}) {timestamp} {self.onReceive}")
                    except:
                        logger.error("STREAM", exc_info=True)

        except asyncio.CancelledError:
            logger.error("🔁 Stream riavviato")
        except Exception as e:
            logger.error("❌ Errore stream:", e)