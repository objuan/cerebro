import requests

def get_free_float(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    }

    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    circulating = data["market_data"]["circulating_supply"]
    total = data["market_data"]["total_supply"]
    max_supply = data["market_data"]["max_supply"]

    return {
        "coin": data["name"],
        "symbol": data["symbol"].upper(),
        "free_float_estimated": circulating,
        "total_supply": total,
        "max_supply": max_supply
    }

# ESEMPIO
if __name__ == "__main__":
    coin = "bitcoin"  # ethereum, solana, etc.
    info = get_free_float(coin)

    for k, v in info.items():
        print(f"{k}: {v}")