import asyncio
import ccxt.pro as ccxt
from datetime import datetime

class BinanceWSStream:
    def __init__(self, quotes=("USDT", "BTC")):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot"
            }
        })
        self.quotes = quotes
        self.running = True

    async def load_pairs(self):
        markets = await self.exchange.load_markets()
        return [
            p for p in markets
            if any(p.endswith(f"/{q}") for q in self.quotes)
        ]

    async def watch_pair(self, pair, callback=None):
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker(pair)
                info = ticker.get("info", {})

                data = {
                    "exchange": "binance",
                    "pair": pair,
                    "symbol": info.get("symbol"),

                    "last_price": ticker.get("last"),
                    "open": ticker.get("open"),
                    "high": ticker.get("high"),
                    "low": ticker.get("low"),
                    "close": ticker.get("close"),
                    "previous_close": ticker.get("previousClose"),

                    "base_volume": ticker.get("baseVolume"),
                    "quote_volume": ticker.get("quoteVolume"),

                    "open_price": info.get("openPrice"),
                    "open_time": info.get("openTime"),
                    "close_time": info.get("closeTime"),

                    "timestamp": ticker.get("timestamp"),
                    "datetime": datetime.utcnow().isoformat()
                }

                if callback:
                    await callback(data)
                else:
                    print(data)

            except Exception as e:
                print(f"[{pair}] WebSocket error:", e)
                await asyncio.sleep(1)

    async def run(self, callback=None, limit_pairs=None):
        pairs = await self.load_pairs()
        if limit_pairs:
            pairs = pairs[:limit_pairs]

        print(f"🚀 Binance WebSocket streaming {len(pairs)} pairs")

        await asyncio.gather(
            *[self.watch_pair(pair, callback) for pair in pairs]
        )

    async def close(self):
        self.running = False
        await self.exchange.close()

