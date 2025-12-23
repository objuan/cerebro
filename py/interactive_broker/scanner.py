import requests
import json
import urllib3
import yfinance as yf
import pandas as pd
import sqlite3

# Disabilita warning HTTPS non verificato (tipico di IBKR localhost)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DB_PATH = "db/crypto.db"

# -------------------------------------------------
# CREATE DB
# -------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
       CREATE TABLE IF NOT EXISTS contracts (
        symbol TEXT PRIMARY KEY,
        conidex TEXT,
        con_id INTEGER,
        available_chart_periods TEXT,
        company_name TEXT,
        contract_description_1 TEXT,
        listing_exchange TEXT,
        sec_type TEXT
        )
    """)
    conn.commit()
    conn.close()

##################

def scan():
    baseUrl = "https://localhost:5000/v1/api"

    request_url = f"{baseUrl}/iserver/scanner/run"

    # ihInsiderOfFloatPercAbove, ihInsiderOfFloatPercBelow
    json_content1 = {
        "instrument": "STK",
        "location": "STK.US.MAJOR",
        "type": "TOP_PERC_GAIN",
        "filter": [
            {
                "code": "priceAbove",
                "value": 10
            },
            {
                "code": "priceBelow",
                "value": 20000
            },
        {
                "code": "usdVolumeAbove",
                "value": 2000
            },
            {
                "code": "usdVolumeBelow",
                "value": 20009000000
            },
        
        ]
    }
    json_content = {
        "instrument": "STK",
        "location": "STK.US.MAJOR",
        "type": "TOP_PERC_GAIN",
        "filter": [
           
        {
                "code": "usdVolumeAbove",
                "value": 2000
            }
            
        ]
    }

    init_db()

    # ⚠️ regulatorySnapshot=False come richiesto
    params = {
        "regulatorySnapshot": "false"
    }

    session = requests.Session()

    response = session.post(
        url=request_url,
        json=json_content,
        params=params,
        verify=False   # necessario per localhost IBKR
    )

    # Controllo risposta
    if response.status_code != 200:
        print("Errore:", response.status_code)
        print(response.text)
    else:
        data = response.json()

        print(f'FIND #{len(data["contracts"])}')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # inserimento dati
        for c in data["contracts"] :
            print(c)

            sql = """
    INSERT INTO contracts (
        symbol,
        conidex,
        con_id,
        available_chart_periods,
        company_name,
        contract_description_1,
        listing_exchange,
        sec_type
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
        conidex = excluded.conidex,
        con_id = excluded.con_id,
        available_chart_periods = excluded.available_chart_periods,
        company_name = excluded.company_name,
        contract_description_1 = excluded.contract_description_1,
        listing_exchange = excluded.listing_exchange,
        sec_type = excluded.sec_type
    """

            conn.execute(sql, (
                c["symbol"],
                c["conidex"],
                c["con_id"],
                c["available_chart_periods"],
                c["company_name"],
                c["contract_description_1"],
                c["listing_exchange"],
                c["sec_type"]
            ))
                
            conn.commit()

        conn.close()

        # Scrive risultato su file
        with open("scanner_result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        #print("Scanner result salvato in scanner_result.json")

if __name__ == "__main__":
    scan()