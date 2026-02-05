import json
from logging.handlers import RotatingFileHandler
import os
import requests
import time
import logging
from datetime import datetime
import sqlite3
from utils import convert_json
from config import DB_FILE,CONFIG_FILE
import aiohttp
import asyncio
import pandas as pd


API_TOKEN = "OBItNcpz38A43dbFxGSE5JmALJ1gDrkFRh1sGgYU"  # Metti qui la tua API key
BASE_URL = "https://api.stockdata.org/v1/news/all"  # endpoint news

LOG_FILE = os.path.join("logs", "news.log")

logger = logging.getLogger(__name__)


with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
config = convert_json(config)

class NewService:

    def __init__(self):
        pass

    async def find(self,symbol):
        df = self.get_df("""
            SELECT symbol, dt_day, dt_hh, data
            FROM news
            WHERE symbol = ?
            ORDER BY dt_day DESC, dt_hh DESC
            LIMIT 5
        """, (symbol,))

        if len(df)>0:
            
            result = {
                "Symbol": None,
                "items": []
                }

            for _, row in df.iterrows():
                if len(row["data"] ) > 0:
                    if result["Symbol"] is None:
                        result["Symbol"] = row["symbol"]

                    dt = f"{row['dt_day']} {row['dt_hh']}"

                    result["items"].append({
                        "date": dt,
                        "data": json.loads(row["data"])
                    })
            if result["Symbol"]:
                return result
            else:
                return None
        else:
            return None

    async def scan(self,_symbols):
       

        min = config["news"]["live_range"]["min"]
        max = config["news"]["live_range"]["max"]
        
        # filtro per il giorno
        date_str = str(datetime.now().date())
        hh_str = datetime.now().strftime("%H")

        logger.info(f"SCAN {_symbols} {min}-{max}")

        if (int(hh_str) >= min and int(hh_str)<=max ):
            
            logger.info(f"NEW SCAN {_symbols}")

            symbols=[]
            for symbol in _symbols:
                df = self.get_df(f"""
                        SELECT dt_hh from news where symbol= ? and dt_day = ? 
                                order by dt_hh desc
                    """,(symbol,date_str))

                if len(df)==0: symbols.append(symbol)
                else:
                    dt_hh = int(df.iloc[0]["dt_hh"])
                    logger.info(f"FIND LAST: {symbol} {dt_hh}")
                    if (int(hh_str)> dt_hh):
                        symbols.append(symbol)

            if len(symbols)>0:
                logger.info(f"SCAN FOR NEWS: {symbols}")
            
                news_items = await self.get_stock_news(symbols, limit=30)
                #news_items= [{"uuid": "45d11b0e-4905-465e-a377-c339fa881c6b", "title": "Asia-Pacific markets mostly fall, tracking Wall Street losses after a tech-led pullback", "description": "Asia-Pacific markets mostly fell, tracking Wall Street losses as a sell-off in U.S. technology stocks weighed on sentiment.", "keywords": "Salesforce Inc, ServiceNow Inc, NVIDIA Corp, Apple Inc, Meta Platforms Inc, Microsoft Corp, NASDAQ Composite, Dow Jones Industrial Average, S&P 500 Index, Hang Seng Index, S&P/ASX 200, Nikkei 225 Index, Osaka, Chicago, Japan, Narendra Modi, India, Donald Trump, United States, business news", "snippet": "Hong Kong Hang Seng index futures were at 26,590, lower than the benchmark's last close of 26,834.77.\n\nShares of Nintendo fell 8% , despite maintaining its full...", "url": "https://www.cnbc.com/2026/02/04/asia-markets-today-wednesday-wall-street-tech-selloff-futures-lower-ai-software-hang-seng-nikkei-kospi.html", "image_url": "https://image.cnbcfm.com/api/v1/image/108223387-1762730856669-gettyimages-2196909643-13102024_tokyo_053.jpeg?v=1762731043&w=1920&h=1080", "language": "en", "published_at": "2026-02-04T00:29:57.000000Z", "source": "cnbc.com", "relevance_score": "null", "entities": [{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "null", "exchange_long": "null", "country": "us", "type": "equity", "industry": "Technology", "match_score": 11.329395, "sentiment_score": 0.6168, "highlights": [{"highlight": "Most tech shares were in the red, includ[+298 characters]", "sentiment": 0.6168, "highlighted_in": "main_text"}]}], "similar": []}]

                conn = sqlite3.connect(DB_FILE, isolation_level=None)
                cur = conn.cursor()
                find_symbols=[]
                for news in news_items:

                    def extract_symbols_from_news(news_dict):
                        symbols = []

                        entities = news_dict.get("entities", [])
                        for ent in entities:
                            symbol = ent.get("symbol")
                            if symbol:
                                symbols.append(symbol)

                        return symbols
                    
                    logger.info(f"Add new \n{news}")  
                    in_symbols = extract_symbols_from_news(news)
                    logger.info(f"symbols >> {in_symbols}")  

                    for s in in_symbols:
                        find_symbols.append(s)
                        cur.execute(
                            "INSERT INTO news (symbol, source, data, dt_day, dt_hh) VALUES (?,?, ?, ?, ?)",
                            (s, "stockdata", json.dumps(news), date_str,hh_str),
                        )
                
                for s in symbols:
                    if not s in find_symbols:
                        cur.execute(
                            "INSERT INTO news (symbol, source, data, dt_day, dt_hh) VALUES (?,?, ?, ?, ?)",
                            (s, "stockdata","", date_str,hh_str),
                        )
                conn.close()
    

    async def get_stock_news(self,symbols, limit=20):
        """
        Recupera async le ultime notizie per una lista di simboli.
        """
        params = {
            "api_token": API_TOKEN,
            "symbols": ",".join(symbols),
            "filter_entities": "true",
            "limit": limit
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    print("Errore API:", response.status, text)
                    return []

                data = await response.json()
                return data.get("data", [])
            
    def get_df(self,query, params=()):
            conn = sqlite3.connect(DB_FILE)
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df


def format_and_print_news(news_list):
    """
    Stampa le notizie in modo leggibile.
    """
    if not news_list:
        print("Nessuna notizia trovata.")
        return

    for news in news_list:
        title = news.get("title")
        tickers = news.get("tickers", [])
        pub_time = news.get("published_at")
        url = news.get("url")
        print(f"[{pub_time}] {title} — {tickers}")
        print(f"Link: {url}")
        print("-" * 70)

if __name__ == "__main__":

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Rotazione: max 5 MB, tieni 5 backup
    file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)


    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    ########################################


    formatter = logging.Formatter("%(asctime)s - %(levelname)s - " "[%(filename)s:%(lineno)d] \t%(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


    async def main():
        # Lista tickers da scandire
        symbols = ["AAPL", "TSLA", "MSFT"]

        service = NewService()

        await service.scan(symbols)

        a = await service.find("TSLA")
        logger.info(a)

    asyncio.run(main())

    #format_and_print_news(news_items)

    # Per fare polling continuo ogni X secondi:
    # while True:
    #     news_items = get_stock_news(symbols, limit=10)
    #     format_and_print_news(news_items)
    #     time.sleep(300)  # attende 5 minuti
