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

exclude_titles = ["""What's going on in today's pre-market session""",
                  """Technology Stocks Moving In""",
                  """Top stock movements in today's session""",
                  """These stocks are gapping in today""",
                  """Top movers in Tuesday""",
                  """Here are the top movers in""",
                  """Industrials Stocks Moving In""",
                  """Which stocks are moving""",
                  """Consumer Staples Stocks Moving"""]

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

    # tolgo quelle che no nservono
    title = news["title"]
    if any(excluded in title for excluded in exclude_titles):
        logger.warning(f"SKIP {news}")
        return

    # Convertiamo il dict in JSON per il campo "data"
    data_json = json.dumps(news, ensure_ascii=False)

    df = get_df("SELECT * FROM news WHERE provider = ? AND guid = ? AND symbol = ?", (   
        news["provider"],
        news["guid"],
        news["symbol"],
    ))

    if len(df) == 0: 
        # cross provider check: se non esiste già una news con lo stesso URL per lo stesso simbolo, allora la inserisco 
        df = get_df("SELECT * FROM news WHERE  symbol = ? and url == ?", (   
                news["symbol"],
                news["url"],
            ))
                
        if len(df) == 0: 
            logger.info(f"INSERT NEWS {news}")

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
                url,
                data,
                provider_last_dt,
                dt_day,
                dt_hh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """, (
                news["provider"],
                news["guid"],
                news["symbol"],
                news["source"],
                news["published_at"],
                published_at_sql,
                news["url"],
                data_json,
                provider_last_dt,
                dt_day,
                dt_hh
            ))

            conn.commit()

            return True
        else:
            #logger.info(f"NEWS ALREADY EXISTS {news['guid']} {news['symbol']} {news['published_at']}")
            return False
    else:
        #logger.info(f"NEWS ALREADY EXISTS {news['guid']} {news['symbol']} {news['published_at']}")
        return False

###########################################

class NewsProvider:

    def __init__(self,provider,isDateFilter):
        self.provider= provider
        self.isDateFilter=isDateFilter
       
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
            from_unix_time = from_unix_time + 60*60 # tolgo 1 ora per sicurezza

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
# filtro per DATA
class Finnhub_Provider(NewsProvider):
      #https://finnhub.io/dashboard
    
    def __init__(self):
        super().__init__("finnhub",True)
        

    async def get_stock_symbol_news(self,symbol,from_unix_time:int):
            dt_utc = datetime.fromtimestamp(from_unix_time, tz=ZoneInfo("UTC"))

            url = "https://finnhub.io/api/v1/company-news"
            today = datetime.utcnow().date()
            #week_ago = today - timedelta(days=1)

            logger.info(f">> finnhub {symbol} after {dt_utc}")

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
        super().__init__("alphavantage",False)

    async def get_stock_symbol_news(self,symbol, from_unix_time:int):
    #async def get_stock_news(self,symbols, limit=20):
        url = "https://www.alphavantage.co/query"

        dt = datetime.fromtimestamp(from_unix_time, tz=timezone.utc)
        formatted = dt.strftime("%Y%m%dT%H%M")

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": symbol,
            "apikey": ALPHAVANTAGE_KEY,
            "time_from": formatted
        }

        logger.info(f"Alphavantage_Provider get_stock_symbol_news {symbol} from {formatted}")

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
        super().__init__(provider,False)
        self.API_TOKEN = API_TOKEN  
        self.BASE_URL = BASE_URL  

    #async def get_stock_news(self,symbols, limit=20):
    async def get_stock_symbol_news(self,symbol, from_unix_time:int):
        try:
            
            dt = datetime.fromtimestamp(from_unix_time, tz=timezone.utc)
            formatted = dt.strftime("%Y-%m-%dT%H:%M:%S")

            logger.info(f"MetaData_Provider get_stock_symbol_news {symbol} from {formatted}")

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
                "symbols": symbol,#",".join(symbols),
                "filter_entities": "true",
                "limit": 50,
                "published_after" : formatted #2026-02-08T11:10:48 
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

    def __init__(self,config):

        self.config=config

        self.providers1= [
             Finnhub_Provider(),
        ]

        self.providers = [
            Finnhub_Provider(),
            StockData_Provider(),
          #  Benzinga_Provider(),
            Alphavantage_Provider(),
            MARKETAUX_Provider()
        ]

    async def bootstrap(self):
        pass
        '''
        for t in config["news"]["schedule"]:
                    logger.info(f"Init news time {t['hh']}")

                    async def process_news(hh):
                        logger.info(f"GET NEWS AT {hh}")
                        
                        await client.scan_for_news()

        scheduler.schedule_at(today_at(t['hh'],0,0),process_news,t['hh'])
                    #scheduler.schedule_every(10,process_news)
        '''
    
    async def tick(self):
        pass

    async def on_symbols_update(self,symbols, to_add, to_remove):
        logger.info(f"NEWS on_symbols_update {symbols} to_add {to_add} to_remove {to_remove}")      

        self.symbols = symbols
        await self.scan(to_add)
        pass

    #######################

    async def testScan(self,symbols):
        for provider in self.providers:
            news_items = await provider.get_stock_news(symbols, limit=30)
            logger.info(f"news_items {provider.__class__} {news_items}")

    async def find(self,symbol):
        df = get_df("""
            SELECT symbol, published_at, data
            FROM news
            WHERE symbol = ?
            ORDER BY published_at DESC
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

                    #dt = f"{row['dt_day']} {row['dt_hh']}"
                    dt = row["published_at"]  

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

    ###
    async def scan(self,symbols,force=False):
       

        min = config["news"]["live_range"]["min"]
        max = config["news"]["live_range"]["max"]
        
        if (config["live_service"]["mode"] =="sym"):
            return
        
        # filtro per il giorno
        date_str = str(datetime.now().date())
        hh_str = datetime.now().strftime("%H")

        #logger.info(f"SCAN {_symbols} {min}-{max}")

        if (force or (int(hh_str) >= min and int(hh_str)<=max )):
            
            logger.info(f"NEW SCAN {symbols}")

            if len(symbols)>0:
                logger.info(f"SCAN FOR NEWS: {symbols}")

                conn = sqlite3.connect(DB_FILE, isolation_level=None)
                #seen_urls = set()

                for provider in self.providers:
                    try:
                        news_list =  await provider.get_stock_news(symbols, limit=30)
                        for n in news_list:
                            insert_news(conn,n)
                    except Exception as e:
                        logger.error(f"{provider.provider} error ",exc_info=True)

                conn.close()
 


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
        #symbols = ["AAPL", "TSLA", "MSFT"]
        symbols = [ "TSLA"]

        service = NewService()

        #await service.testScan(symbols)

        conn = sqlite3.connect(DB_FILE, isolation_level=None)
        
        #for n in  await Finnhub_Provider().get_stock_news(symbols):
        #    insert_news(conn,n)#

        #for n in  await Alphavantage_Provider().get_stock_news(symbols):
        #    #print(n)
        #    insert_news(conn,n)

        for n in  await MARKETAUX_Provider().get_stock_news(symbols):
            insert_news(conn,n)

        #for n in  await MARKETAUX_Provider().get_stock_news(symbols):
        #    insert_news(conn,n)


    

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
