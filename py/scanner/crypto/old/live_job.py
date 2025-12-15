import ccxt
import time
from datetime import datetime

class BinanceLive:
    def __init__(self, quotes=("USDT", "BTC"), rate_limit=True):
        self.exchange = ccxt.binance({
            "enableRateLimit": rate_limit,
            "options": {
                "defaultType": "spot"
            }
        })
        self.quotes = quotes
        self.markets = None

    def load_pairs(self):
        self.markets = self.exchange.load_markets()
        return [
            p for p in self.markets
            if any(p.endswith(f"/{q}") for q in self.quotes)
        ]

    def fetch_ticker(self, pair):
        ticker = self.exchange.fetch_ticker(pair)
        info = ticker.get("info", {})

        return {
            "exchange": "binance",
            "pair": pair,
            "symbol": info.get("symbol"),

            "last": ticker.get("last"),
            "open": ticker.get("open"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "close": ticker.get("close"),
            "previousClose": ticker.get("previousClose"),

            "baseVolume": ticker.get("baseVolume"),
            "quoteVolume": ticker.get("quoteVolume"),

            "openPrice": info.get("openPrice"),
            "openTime": info.get("openTime"),
            "closeTime": info.get("closeTime"),

            "timestamp": ticker.get("timestamp"),
            "datetime": datetime.utcnow().isoformat()
        }

    def stream(self, interval=5, callback=None):
        """
        Polling loop
        interval: secondi
        callback: funzione che riceve il dict ticker
        """
        pairs = self.load_pairs()
        print(f"Loaded {len(pairs)} pairs")

        while True:
            for pair in pairs:
                try:
                    data = self.fetch_ticker(pair)
                    if callback:
                        callback(data)
                    else:
                        print(data)
                except Exception as e:
                    print("Error:", e)
            time.sleep(interval)

#############################

def on_tick(data):
    print(
        data["pair"],
        data["last"],
        data["quoteVolume"]
    )

client = BinanceLive()
client.stream(interval=10, callback=on_tick)