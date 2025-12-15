import asyncio
from binance_ws_stream import BinanceWSStream

async def on_tick(data):
    print(
        data["pair"],
        data["last_price"],
        data["quote_volume"]
    )

stream = BinanceWSStream()
asyncio.run(stream.run(callback=on_tick, limit_pairs=10))