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
        #self.socket = None
        self.stream_task = None

        self.symbols = []
        self.running = False
        self.summary = {}
        
        
        # 🔥 double buffer
        self.recv_buffer = []
        self.proc_buffer = []
        self.lock = asyncio.Lock()

        self.onReceive = None

    async def start(self, onReceive):
        self.onReceive=onReceive
        self.client = await AsyncClient.create()
        self.bm = BinanceSocketManager(self.client)
        self.running = True

    async def stop(self):
        self.running = False

        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

        if self.client:
            await self.client.close_connection()

    async def set_symbols(self, symbols):
        logger.info(f"BINANCE >> {symbols}")
        self.symbols = symbols

        # 🔥 chiude stream attuale
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                logger.info("🛑 Vecchio stream chiuso")

        # reset buffer
        async with self.lock:
            self.recv_buffer.clear()
            self.proc_buffer.clear()

        # 🔥 riavvia stream
        self.stream_task = asyncio.create_task(self._run_stream())

    # -------------------------
    # RECEIVER → riempie recv_buffer
    # -------------------------
    async def _receiver(self, stream):
        while self.running:
            msg = await stream.recv()

            async with self.lock:
                self.recv_buffer.append(msg)


    # -------------------------
    # PROCESSOR → usa proc_buffer
    # -------------------------
    async def _processor(self):
        while self.running:
            await asyncio.sleep(0)  # yield

            # 🔥 swap buffer O(1)
            async with self.lock:
                self.recv_buffer, self.proc_buffer = [], self.recv_buffer

            for msg in self.proc_buffer:
                await self._handle_message(msg,len(self.proc_buffer))

            self.proc_buffer.clear()

    async def _handle_message(self, msg, inQueue):
        try:
            if "data" not in msg:
                return

            event = msg["data"]
            symbol = event["s"]

            if symbol not in self.summary:
                self.summary[symbol] = {
                    "v_acc": 0,
                    "qv_day": 0,
                    "v_day": 0,
                    "g_day": 0
                }

            sum_data = self.summary[symbol]

            if event["e"] == "24hrTicker":
                sum_data["g_day"] = float(event["P"])
                sum_data["v_day"] = float(event["v"])
                sum_data["qv_day"] = float(event["q"])

            elif event["e"] == "aggTrade":
                qty = float(event["q"])
                price = float(event["p"])
                timestamp = event["T"] / 1000

                volume = qty
                sum_data["v_acc"] += volume

                await self.onReceive(
                    symbol,
                    timestamp,
                    price,
                    volume,
                    sum_data["v_acc"],
                    sum_data["v_day"],
                    sum_data["qv_day"],
                    sum_data["g_day"],
                    inQueue
                )

        except Exception:
            logger.error("STREAM", exc_info=True)

    '''
     {'stream': 'zkpusdc@ticker', 'data': {'e': '24hrTicker', 'E': 1777379751499, 's': 'ZKPUSDC', 'p': '0.01180000', 'P': '14.550', 'w': '0.08879922', 'x': '0.08100000', 'c': '0.09290000', 'Q': '1384.70000000', 'b': '0.09280000', 'B': '1000.00000000', 'a': '0.09300000', 'A': '8921.30000000', 'o': '0.08110000', 'h': '0.09650000', 'l': '0.08040000', 'v': '2327050.60000000', 'q': '206640.26845000', 'O': 1777293351328, 'C': 1777379751328, 'F': 425314, 'L': 426652, 'n': 1339}}
    '''
       # -------------------------
    # STREAM MAIN
    # -------------------------
    async def _run_stream(self):
        if not self.symbols:
            return

        streams = []
        for s in self.symbols:
            s = s.lower()
            streams.append(f"{s}@aggTrade")
            streams.append(f"{s}@ticker")

        socket = self.bm.multiplex_socket(streams)

        try:
            async with socket as stream:
                logger.info(f"✅ Streaming: {self.symbols}")

                recv_task = asyncio.create_task(self._receiver(stream))
                proc_task = asyncio.create_task(self._processor())

                await asyncio.gather(recv_task, proc_task)

        except asyncio.CancelledError:
            logger.warning("🔁 Stream riavviato")
        except Exception as e:
            logger.error(f"❌ Errore stream: {e}")

if __name__ =="__main__":

  
 
    async def main():

        s = BinanceStreamer()
        
        async def onReceive(symbol,time, price,volume, volume_acc,day_volume, day_quotevolume,gain_24_perc,inQueue):
            dt =  datetime.utcfromtimestamp(time)
            

            line = f"{symbol},{time},{dt}, {price:.4f},{volume},{volume_acc},{day_volume},{day_quotevolume},{gain_24_perc} {inQueue}\n"

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