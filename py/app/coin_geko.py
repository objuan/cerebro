import requests
from functools import lru_cache
import logging

logger = logging.getLogger()

BINANCE_QUOTE_ASSETS = [
    "USDT", "BUSD", "USDC",
    "BTC", "ETH", "BNB",
    "TRY", "EUR"
]


def extract_base_asset(symbol):
    for quote in BINANCE_QUOTE_ASSETS:
        if symbol.endswith(quote):
            return symbol[:-len(quote)]
    return symbol


def binance_to_coinpaprika(binance_symbol):

    base = (
        binance_symbol
        .replace("USDT", "")
        .replace("BUSD", "")
        .replace("USDC", "")
        .lower()
    )

    coins = requests.get(
        "https://api.coinpaprika.com/v1/coins"
    ).json()

    matches = [
        c for c in coins
        if c["symbol"].lower() == base
    ]

    return matches[:10]


def get_Data(id):
    url = f"https://api.coinpaprika.com/v1/tickers/{id}"

    try:
        #print(url)

        r = requests.get(url)
        
        data = r.json()

        #print(data)

        market_cap = data["quotes"]["USD"]["market_cap"]
        total_supply = data["total_supply"]
        max_supply = data["max_supply"]

        return {"name" : data["name"], "symbol" : data["symbol"], "rank": data["rank"],"market_cap" : market_cap, "total_supply" : total_supply, "max_supply" : max_supply   }
    
    except Exception as e:
        logger.error(f"Error fetching data for {id}: {e}")
     
def get_binance_base_data(symbol):
    logger.info(f"Fetching data for {symbol} from CoinPaprika") 
    cg_id = binance_to_coinpaprika(symbol)
    logger.info(f"cg_id {cg_id} ") 
    if len(cg_id)>= 0:
        data = get_Data(cg_id[0]["id"])
        return data
    return None
    
######################

def get_market_data(symbol):
    try:
        base = symbol.replace("USDC", "")

        url = (
            "https://min-api.cryptocompare.com/data/"
            f"pricemultifull?fsyms={base}&tsyms=USDC"
        )

        data = requests.get(url).json()
        #print(data)
        #raw = data["Data"][0]["RAW"]["USDC"]
        raw = data["RAW"][base]["USDC"]

        #print(raw)

        return {
            "symbol" : symbol,
            "name": symbol,
        # "name": data["Data"][0]["CoinInfo"]["FullName"],
            "price": raw["PRICE"],
            "market_cap": raw["MKTCAP"],
            "total_supply": raw["SUPPLY"]
        }
    except:
        logger.error(f"Error fetching market data for {symbol}", exc_info=True)
        return None 

'''

symbol = "CFGUSDC"

print(get_market_data(symbol))
'''

