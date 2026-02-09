import json
from logging.handlers import RotatingFileHandler
import os
import requests
import time
import logging
import sqlite3
from utils import convert_json
from config import DB_FILE,CONFIG_FILE
import aiohttp
import asyncio
import pandas as pd
from datetime import datetime, timedelta,timezone
from dateutil import parser
from zoneinfo import ZoneInfo
import uuid

LOG_FILE = os.path.join("logs", "news.log")

logger = logging.getLogger(__name__)
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
config = convert_json(config)

STOCKDATA_KEY = "OBItNcpz38A43dbFxGSE5JmALJ1gDrkFRh1sGgYU"  # Metti qui la tua API key
FINNHUB_KEY = "d63mkppr01ql6dj0lbk0d63mkppr01ql6dj0lbkg"
MARKETAUX_KEY = "Pv7vlvoLhKuSt7ySoQkOFwx4DX6oxRFHn8DNUzbb"
ALPHAVANTAGE_KEY = "DWFYHOZURRTF2IVK"
BENZINGA_KEY = "YOUR_BENZINGA_KEY"

#############

def get_df(query, params=()):
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

def normalize_news(provider, guid, source, symbol, title, image, url, published_at:int, summary):
    '''
    try:
        dt = parser.parse(published_at)
        published_at = dt.isoformat()
    except Exception:
        published_at = None
    '''
    return {
        "provider": provider,
        "guid": guid,
        "source": source,
        "symbol": symbol,
        "title": title,
         "image": image,
        "url": url,
        "published_at": published_at,
        "summary": summary,
    }



def insert_news(conn, news):
    #news = normalize_news(provider, source, title, image, url, published_at, summary)

    # Convertiamo il dict in JSON per il campo "data"
    data_json = json.dumps(news, ensure_ascii=False)

    #logger.info(f"INSERT NEWS {news}")

    # Parsing date per i campi derivati
    try:
        #dt = parser.parse(news["published_at"])
        # 1) La interpretiamo come UTC
       # dt_utc = datetime.fromisoformat(news["published_at"]).replace(tzinfo=ZoneInfo("UTC"))
        dt_utc = datetime.fromtimestamp(news["published_at"], tz=ZoneInfo("UTC"))

        # 2) La convertiamo in ora locale italiana
        dt_local = dt_utc.astimezone(ZoneInfo("Europe/Rome"))

        published_at_sql = dt_local.strftime("%Y-%m-%d %H:%M:%S")
        #published_at_sql = dt.strftime("%Y-%m-%d %H:%M:%S")
       
       # dt_day = dt.strftime("%Y-%m-%d")
       # dt_hh = dt.strftime("%H")
        dt_day = str(datetime.now().date())
        dt_hh = datetime.now().strftime("%H")
 
    except Exception:
        dt_day = None
        dt_hh = None
        published_at_sql = None

    # provider_last_dt = data più recente ricevuta dal provider
    #provider_last_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    provider_last_dt = datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M:%S")

    cur = conn.cursor()
    cur.execute("""
    INSERT INTO news (
        provider,
        guid,
        symbol,
        source,
        published_at,
        published_dt,
        data,
        provider_last_dt,
        dt_day,
        dt_hh
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    ON CONFLICT(provider, symbol, guid)
    DO UPDATE SET
        source = excluded.source,
        published_at = excluded.published_at,
        published_dt = excluded.published_dt,
        data = excluded.data,
        provider_last_dt = excluded.provider_last_dt,
        dt_day = excluded.dt_day,
        dt_hh = excluded.dt_hh
    """, (
        news["provider"],
        news["guid"],
        news["symbol"],
        news["source"],
        news["published_at"],
        published_at_sql,
        data_json,
        provider_last_dt,
        dt_day,
        dt_hh
    ))

    conn.commit()

###########################################

class NewsProvider:

    def __init__(self,provider):
        self.provider= provider
       
    def getLast(self,symbol):
        df = get_df("""
            SELECT *
            FROM news
            WHERE provider = ? and  symbol = ?  
            ORDER BY published_at DESC
            LIMIT 1
        """, ( self.provider, symbol,))

        if len(df)>0:
             row = df.iloc[0]
             data = json.loads(row["data"])
             return {
                 "provider": row["provider"],
                "symbol": row["symbol"],
                "source":row["source"],
                "published_at":int(row["published_at"]),

                "title":data["title"],
                "image":data["image"],
                "url":data["url"],
                "summary":data["summary"],
            }
        else:
            return None

    #
    def get_scan_begin_at(self, symbol) -> int:
            last = self.getLast(symbol)
            if not last:
                # from_unix_time attuale
                tz = ZoneInfo("Europe/Rome")
                today_local = datetime.now(tz).date()
                from_dt_local = datetime.combine(today_local - timedelta(days=3),
                                 datetime.min.time(), tz)
                from_unix_time = int(from_dt_local.astimezone(ZoneInfo("UTC")).timestamp())
            else:
                from_unix_time = last["published_at"]
            return from_unix_time
    
    async def get_stock_news(self,symbols, limit=20):
        list = []
        for symbol in symbols:
            from_unix_time = self.get_scan_begin_at(symbol)

            news = await self.get_stock_symbol_news(symbol,from_unix_time)
            list.extend(
                {**n, "symbol": symbol}
                for n in news)
            
            logger.info(f"Finnhub_Provider ind {symbol} find #{len(news)}")

        #logger.info(f"Finnhub_Provider find #{len(list)}")
        return list
    
    async def get_stock_symbol_news(self,symbol, from_unix_time:int):
        pass

######################################

class Finnhub_Provider(NewsProvider):
      #https://finnhub.io/dashboard
    
    def __init__(self):
        super().__init__("finnhub")

    async def get_stock_symbol_news(self,symbol,from_unix_time:int):
            dt_utc = datetime.fromtimestamp(from_unix_time, tz=ZoneInfo("UTC"))

            url = "https://finnhub.io/api/v1/company-news"
            today = datetime.utcnow().date()
            #week_ago = today - timedelta(days=1)

            logger.info(f"get_stock_symbol_news {symbol} after {dt_utc}")

            params = {
                "symbol": symbol,
                "from": dt_utc.date().isoformat(),
                "to": today.isoformat(),
                "token": FINNHUB_KEY,
            }

            r = requests.get(url, params=params).json()
            news = []
            #logger.info(f">> {r}")
    
            for n in r:
                news.append(
                    normalize_news(
                        "finnhub",
                        n.get("id"),
                        n.get("source"),
                        symbol,
                        n.get("headline"),
                        n.get("image"),
                        n.get("url"),
                        int(n.get("datetime")), #UNIX TIME
                        #datetime.utcfromtimestamp(n.get("datetime")).isoformat(),
                        n.get("summary"),
                    )
                )

            return news


class Alphavantage_Provider(NewsProvider):

    def __init__(self):
        super().__init__("alphavantage")

    async def get_stock_news(self,symbols, limit=20):
        url = "https://www.alphavantage.co/query"

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": symbols,
            "apikey": ALPHAVANTAGE_KEY,
        }

        r = requests.get(url, params=params).json()
        news = []

        logger.info(r)

        for n in r.get("feed", []):
            dt = datetime.strptime(n.get("time_published"), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            unix_time = int(dt.timestamp())

            guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, n.get("title")+str(unix_time)))

            for item in n.get("ticker_sentiment", {}):
                symbol = item["ticker"]

                news.append(
                    normalize_news(
                        self.provider,
                        guid,
                        n.get("source"),
                        symbol,
                        n.get("title"),
                        n.get("banner_image"),
                        n.get("url"),
                        unix_time,#n.get("time_published"), #20260208T145910
                        n.get("summary"),
                    )
                )
           

        return news

class Benzinga_Provider(NewsProvider):
    async def get_stock_news(self,symbols, limit=20):
        url = "https://api.benzinga.com/api/v2/news"

        params = {
            "tickers": symbols,
            "token": BENZINGA_KEY,
        }

        r = requests.get(url, params=params).json()
        news = []

        for n in r:
            news.append(
                normalize_news(
                    "Benzinga",
                    n.get("title"),
                    n.get("url"),
                    n.get("created"),
                    n.get("description"),
                )
            )

        return news

##########################################

class MetaData_Provider(NewsProvider):
    
    def __init__(self,provider,API_TOKEN,BASE_URL):
        super().__init__(provider)
        self.API_TOKEN = API_TOKEN  
        self.BASE_URL = BASE_URL  

    async def get_stock_news(self,symbols, limit=20):
        try:
            
            def extract_symbols_from_news(news_dict):
                        symbols = []

                        entities = news_dict.get("entities", [])
                        for ent in entities:
                            symbol = ent.get("symbol")
                            if symbol:
                                symbols.append(symbol)

                        return symbols
              
            #from_unix_time = self.get_scan_begin_at(symbol)

            """
            Recupera async le ultime notizie per una lista di simboli.
            """
            params = {
                "api_token": self.API_TOKEN,
                "symbols": ",".join(symbols),
                "filter_entities": "true",
                "limit": limit
                #"published_after" :  #2026-02-08T11:10:48 
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        text = await response.text()
                        print("Errore API:", response.status, text)
                        return []

                    r = await response.json()
                 
                    news=[]
                    for n in r.get("data", []):

                        ##logger.info(f"Add new \n{n}")  
                        
                        in_symbols = extract_symbols_from_news(n)
                        logger.info(f"symbols >> {in_symbols}")  
                 
                        for symbol in in_symbols:
                           
                            dt = datetime.fromisoformat(n.get("published_at").replace("Z", "+00:00"))
                            unix_time = int(dt.timestamp())

                            news.append(
                                normalize_news(
                                    self.provider,
                                    n.get("uuid"),
                                    n.get("source"),
                                    symbol,
                                    n.get("title"),
                                    n.get("image_url"),
                                    n.get("url"),
                                    unix_time,#,n.get("published_at"),
                                    n.get("description"),
                                )
                            )

                    return news
        except:
            logger.error(f"Errro", exc_info=True)

######### sembrano la stessa cosa 

class StockData_Provider(MetaData_Provider):
  
    def __init__(self):
        super().__init__("stockdata",STOCKDATA_KEY,"https://api.stockdata.org/v1/news/all" )

class MARKETAUX_Provider(MetaData_Provider):
    def __init__(self):
        super().__init__("marketaux",MARKETAUX_KEY, "https://api.marketaux.com/v1/news/all" )


#############################################################

class NewService:

    def __init__(self):

        self.providers= [
             Finnhub_Provider(),
        ]

        self.providers1 = [
            Finnhub_Provider(),
#            StockDataProvider(),
          #  Benzinga_Provider(),
          #  Alphavantage_Provider(),
          #  MARKETAUX_Provider()
        ]
        pass

    async def testScan(self,symbols):
        for provider in self.providers:
            news_items = await provider.get_stock_news(symbols, limit=30)
            logger.info(f"news_items {provider.__class__} {news_items}")

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
        
        if (config["live_service"]["mode"] =="sym"):
            return
        
        # filtro per il giorno
        date_str = str(datetime.now().date())
        hh_str = datetime.now().strftime("%H")

        #logger.info(f"SCAN {_symbols} {min}-{max}")

        if (int(hh_str) >= min and int(hh_str)<=max ):
            
            logger.info(f"NEW SCAN {_symbols}")

            symbols=[]
            for symbol in _symbols:
                df = self.get_df(f"""
                        SELECT dt_hh from news where symbol= ? and dt_day = ? 
                                order by dt_hh desc
                    """,(symbol,date_str))

                if len(df)==0: 
                    symbols.append(symbol)
                else:
                    dt_hh = int(df.iloc[0]["dt_hh"])
                    logger.debug(f"FIND LAST: {symbol} {dt_hh}")
                    if (int(hh_str)> dt_hh):
                        symbols.append(symbol)

            if len(symbols)>0:
                logger.info(f"SCAN FOR NEWS: {symbols}")

                all_news = []
                seen_urls = set()

                for provider in self.providers:
                    try:
                        news_list =  await provider.get_stock_news(symbols, limit=30)
                        for n in news_list:
                            if n["url"] and n["url"] not in seen_urls:
                                seen_urls.add(n["url"])
                                all_news.append(n)
                    except Exception as e:
                        logger.error(f"{provider.__name__} error on {symbol}:", e)

                #news_items= [{"uuid": "45d11b0e-4905-465e-a377-c339fa881c6b", "title": "Asia-Pacific markets mostly fall, tracking Wall Street losses after a tech-led pullback", "description": "Asia-Pacific markets mostly fell, tracking Wall Street losses as a sell-off in U.S. technology stocks weighed on sentiment.", "keywords": "Salesforce Inc, ServiceNow Inc, NVIDIA Corp, Apple Inc, Meta Platforms Inc, Microsoft Corp, NASDAQ Composite, Dow Jones Industrial Average, S&P 500 Index, Hang Seng Index, S&P/ASX 200, Nikkei 225 Index, Osaka, Chicago, Japan, Narendra Modi, India, Donald Trump, United States, business news", "snippet": "Hong Kong Hang Seng index futures were at 26,590, lower than the benchmark's last close of 26,834.77.\n\nShares of Nintendo fell 8% , despite maintaining its full...", "url": "https://www.cnbc.com/2026/02/04/asia-markets-today-wednesday-wall-street-tech-selloff-futures-lower-ai-software-hang-seng-nikkei-kospi.html", "image_url": "https://image.cnbcfm.com/api/v1/image/108223387-1762730856669-gettyimages-2196909643-13102024_tokyo_053.jpeg?v=1762731043&w=1920&h=1080", "language": "en", "published_at": "2026-02-04T00:29:57.000000Z", "source": "cnbc.com", "relevance_score": "null", "entities": [{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "null", "exchange_long": "null", "country": "us", "type": "equity", "industry": "Technology", "match_score": 11.329395, "sentiment_score": 0.6168, "highlights": [{"highlight": "Most tech shares were in the red, includ[+298 characters]", "sentiment": 0.6168, "highlighted_in": "main_text"}]}], "similar": []}]
                   # Ordina per data
                all_news = [n for n in all_news if n["published_at"]]
                all_news.sort(key=lambda x: x["published_at"], reverse=True)

                '''
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
                '''
    

####################################################################
####################################################################

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
        #symbols = [ "TSLA"]

        service = NewService()

        #await service.testScan(symbols)

        conn = sqlite3.connect(DB_FILE, isolation_level=None)
        
        #for n in  await Finnhub_Provider().get_stock_news(symbols):
        #    insert_news(conn,n)

        #for n in  await StockData_Provider().get_stock_news(symbols):
        #    insert_news(conn,n)

        #for n in  await MARKETAUX_Provider().get_stock_news(symbols):
        #    insert_news(conn,n)


        for n in  await Alphavantage_Provider().get_stock_news(symbols):
            #print(n)
            insert_news(conn,n)

        #await Finnhub_Provider().get_stock_news(["TSLA"])

        #last = Finnhub_Provider().getLast("TSLA")
        #logger.info(f"LAST {last}")
        #await service.scan(symbols)

        #a = await service.find("TSLA")
        #logger.info(a)

    asyncio.run(main())

    #format_and_print_news(news_items)

    # Per fare polling continuo ogni X secondi:
    # while True:
    #     news_items = get_stock_news(symbols, limit=10)
    #     format_and_print_news(news_items)
    #     time.sleep(300)  # attende 5 minuti
