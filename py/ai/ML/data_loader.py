import pandas as pd
import sqlite3

DB_FILE ="C:\Lavoro\cerebro\py\db\crypto.db"

def get_df(query, params=()):
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

def load_data( timeframe,timestamp):
    #df = pd.read_parquet(path)
    sql =f"""
    SELECT * FROM ib_ohlc_history where  timeframe = '{timeframe}' and timestamp>= {timestamp} 
    """

    print(sql)

    df = get_df(sql)
    
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values(['symbol', 'datetime'])
    
    # separa per giorno
    df['date'] = df['datetime'].dt.date
    
    return df