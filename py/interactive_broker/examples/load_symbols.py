import yfinance as yf
import pandas as pd
import sqlite3
import requests
from datetime import datetime
from tqdm import tqdm

DB_PATH = "us_stocks.db"

# -------------------------------------------------
# CREATE DB
# -------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS us_stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT,
            currency TEXT,
            sector TEXT,
            price REAL,
            volume INTEGER,
            avg_volume INTEGER,
            market_cap INTEGER,
            float INTEGER,
            shares_outstanding INTEGER,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# -------------------------------------------------
# FETCH SYMBOL LIST (NASDAQ + NYSE)
# -------------------------------------------------

def fetch_symbols():
    nasdaq = pd.read_csv(
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        sep="|"
    )
    
    nasdaq = nasdaq[ 
        (nasdaq["ETF"] == "N") &
        (nasdaq["Test Issue"] == "N")]
    
    nyse = pd.read_csv(
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        sep="|"
    )
    nyse = nyse[ 
        (nyse["ETF"] == "N") &
        (nyse["Test Issue"] == "N")]

    symbols = set(nasdaq["Symbol"].dropna())
    symbols |= set(nyse["ACT Symbol"].dropna())

    # clean
    symbols = [s for s in symbols if s.isalpha()]


    
    return sorted(symbols)

# -------------------------------------------------
# FETCH FUNDAMENTALS (Yahoo)
# -------------------------------------------------

def fetch_fundamentals(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        #if (info["tradeable"] == "True"):
        if True:
            #print(info)
            return {
                "symbol": symbol,
                "name": info.get("shortName"),
                "exchange": info.get("exchange"),
                "sector": info.get("sectorKey"),
                "price": info.get("regularMarketPrice"),
                "currency": info.get("currency"),   
                "volume": info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "float": info.get("floatShares"),
                "shares_outstanding": info.get("sharesOutstanding"),
            }
    except Exception:
        return None

# -------------------------------------------------
# SAVE TO DB
# -------------------------------------------------

def save_row(row):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO us_stocks VALUES (
            :symbol, :name, :exchange, :currency, :sector, :price,
            :volume, :avg_volume, :market_cap,
            :float, :shares_outstanding, :updated_at
        )
    """, {**row, "updated_at": datetime.utcnow().isoformat()})
    conn.commit()
    conn.close()

# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    init_db()
    symbols = fetch_symbols()

    print(f"Trovati {len(symbols)} simboli USA")

    for sym in tqdm(symbols):
        data = fetch_fundamentals(sym)
        if data and data["price"]:
            save_row(data)
            #break

if __name__ == "__main__":
    main()
