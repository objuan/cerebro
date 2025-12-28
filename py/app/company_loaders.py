
import requests
import httpx
import asyncio
import json
import sqlite3
import pandas as pd
import logging
from datetime import datetime
from utils import convert_json
from config import DB_FILE,CONFIG_FILE
import yfinance as yf
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("yfinance").setLevel(logging.INFO)
logging.getLogger("peewee").setLevel(logging.INFO)


def init_company_db():
    conn = sqlite3.connect(DB_FILE, isolation_level=None)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS company (
        symbol TEXT NOT NULL,
        free_float REAL,
        float_shares INTEGER,
        outstanding_shares INTEGER,
        shares_source TEXT,
        shares_update_dt TEXT,
        PRIMARY KEY (symbol)
    );""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
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


def get_df(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

####################

class StockUtils:
    
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

###############################################

class Yahoo:
    
    def __init__(self):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.config = convert_json(self.config)
    # -------------------------------------------------
    # FETCH FUNDAMENTALS (Yahoo)
    # -
    
    def fetch_fundamentals(self,symbol):
        toupdate=True
        df = get_df("SELECT * FROM STOCKS WHERE SYMBOL = ?",(symbol,))
        if not df.empty:
            last_date = datetime.fromisoformat( df.iloc[0]["updated_at"])
            time_to_update_days = (datetime.now() - last_date).total_seconds()/(60*60*24)
         
            c_time = self.config["company"]["stock_update_days"]
            logger.info(f"time to update {time_to_update_days}/{c_time}")
            toupdate=time_to_update_days > c_time 
        
        if toupdate:
            logger.debug(f"GETTING {symbol}")
            try:
                t = yf.Ticker(symbol)
                info = t.info
            
                data =  {
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

                self.save_row(data)

            except Exception:
                logger.error("Errro", exc_info=True)
            df = get_df("SELECT * FROM stocks WHERE SYMBOL = ?",(symbol,))
        else:
            return df
        
    def save_row(self,row):
            logger.info(f"save {row}")
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO stocks VALUES (
                    :symbol, :name, :exchange, :currency, :sector, :price,
                    :volume, :avg_volume, :market_cap,
                    :float, :shares_outstanding, :updated_at
                )
            """, {**row, "updated_at": datetime.utcnow().isoformat()})
            conn.commit()
            conn.close()

    async def get_float_list(self,symbols):

        # 2. Chiama la funzione per ogni symbol
        float_dfs = []
        for symbol in symbols:
            data = self.fetch_fundamentals(symbol)
            #float_dfs.append(df)
            print(data)
            
        # 3. Unisci tutti i risultati in un unico DataFrame
        #float_df = pd.concat(float_dfs, ignore_index=True)
        #return float_df[["symbol","free_float",  "float_shares",  "outstanding_shares"]]


###################################################

class Financialmodelingprep:
    #https://site.financialmodelingprep.com/developer/docs/quickstart
    def __init__(self):
        self.API_KEY = "AUnTlLot9c6e2SFJHoWR2ZFJJq4IzoTz"
        self.URL = "https://financialmodelingprep.com/stable/"
        init_company_db()

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.config = convert_json(self.config)

    def upsert_company_data(self,db_path,  rows):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            shares_source="financialmodelingprep"
            sql = """
            INSERT INTO company (
                symbol,
                free_float,
                float_shares,
                outstanding_shares,
                shares_source,
                shares_update_dt

            ) VALUES (
                :symbol,
                :free_float,
                :float_shares,
                :outstanding_shares,
                :shares_source,
                :shares_update_dt
            )
            ON CONFLICT(symbol) DO UPDATE SET
                free_float = excluded.free_float,
                float_shares = excluded.float_shares,
                outstanding_shares = excluded.outstanding_shares,
                shares_source = excluded.shares_source,
                shares_update_dt = excluded.shares_update_dt
            """

            for r in rows:
                cur.execute(sql, {
                    "symbol": r["symbol"],
                    "free_float": r.get("freeFloat"),
                    "float_shares": r.get("floatShares"),
                    "outstanding_shares": r.get("outstandingShares"),
                    "shares_source" : shares_source,
                    "shares_update_dt": r.get("date")
                })

            conn.commit()
            conn.close()

    ############

    async def get_float(self,symbol):
    
        toupdate=True
        df = get_df("SELECT * FROM COMPANY WHERE SYMBOL = ?",(symbol,))
        if not df.empty:
            last_date = datetime.fromisoformat( df.iloc[0]["shares_update_dt"])
            time_to_update_days = (datetime.now() - last_date).total_seconds()/(60*60*24)
         
            c_time = self.config["company"]["stock_update_days"]
            logger.info(f"time to update {time_to_update_days}/{c_time}")
            toupdate=time_to_update_days > c_time 
        if toupdate:
            logger.info(f"get shares from financialmodelingprep.. {symbol}")
           
            url = "https://financialmodelingprep.com/stable/shares-float"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, params={"symbol": symbol, "apikey": self.API_KEY})
                r.raise_for_status()
            data = r.json()
          
            #data = [{'symbol': 'NVDA', 'date': '2025-12-27 20:05:05', 'freeFloat': 95.82465488386184, 'floatShares': 23330430000, 'outstandingShares': 24347001331, 'source': 'https://www.sec.gov/Archives/edgar/data/1045810/000104581025000230/nvda-20251026.htm'}]

            logger.info(f"--> {data}")

            self.upsert_company_data(
                db_path=DB_FILE,
                rows=data)
            
            df = get_df("SELECT * FROM COMPANY WHERE SYMBOL = ?",(symbol,))
        else:
            return df
    
    async def get_float_all(self):
        
        
        url = "https://financialmodelingprep.com/stable/shares-float-all?page=0&limit=1000&apikey=AUnTlLot9c6e2SFJHoWR2ZFJJq4IzoTz"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url,  params={ "apikey": self.API_KEY,"limit": 1000})
            r.raise_for_status()
        data=  r.json()
        print(data)

        self.upsert_company_data(
            db_path=DB_FILE,
            exchange="NASDAQ",
            rows=data)

    async def get_float_list(self,symbols):

        # 2. Chiama la funzione per ogni symbol
        float_dfs = []
        for symbol in symbols:
            df = await self.get_float(symbol)
            float_dfs.append(df)
            
        # 3. Unisci tutti i risultati in un unico DataFrame
        float_df = pd.concat(float_dfs, ignore_index=True)
        return float_df[["symbol","free_float",  "float_shares",  "outstanding_shares"]]

    async def fill_with_float(self,df):
        '''
        DF ha una colonna "symbol"
        '''
        symbols = df["symbol"].dropna().unique()
        # 2. Chiama la funzione per ogni symbol
        float_dfs = [
            await self.get_float(symbol)
            for symbol in symbols
        ]
        # 3. Unisci tutti i risultati in un unico DataFrame
        float_df = pd.concat(float_dfs, ignore_index=True)
        # 4. Merge finale
        df = df.merge(
            float_df,
            on="symbol",
            how="left"
        )
    
if __name__ =="__main__":

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    '''
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    '''
    
    logger.info("init")
    #init_company_db()

    async def main():
        f = Yahoo() # Financialmodelingprep()
        #data = await f.get_float("NVDA")
        #data = await f.get_float_all()
        data = await f.get_float_list(["NVDA","AAPL"])

        print(data)

    asyncio.run(main())