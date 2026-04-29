from binance.client import Client

# NON servono API key per dati pubblici
client = Client()

# Portafoglio simulato
wallet = {
    "EUR": 1000.0,
    "BTC": 0.0
}

def get_btc_price():
    ticker = client.get_symbol_ticker(symbol="BTCEUR")
    return float(ticker["price"])

def buy_btc(amount_eur):
    price = get_btc_price()
    
    if wallet["EUR"] < amount_eur:
        print("Fondi insufficienti!")
        return
    
    btc_bought = amount_eur / price
    
    wallet["EUR"] -= amount_eur
    wallet["BTC"] += btc_bought
    
    print(f"Comprati {btc_bought:.6f} BTC a {price:.2f} EUR")
    print_wallet()

def print_wallet():
    print("------ PORTAFOGLIO ------")
    print(f"EUR: {wallet['EUR']:.2f}")
    print(f"BTC: {wallet['BTC']:.6f}")
    print("-------------------------")

# Esempio utilizzo
print("Prezzo attuale BTC:", get_btc_price())

buy_btc(200)  # compra 200€ di BTC