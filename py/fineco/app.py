from flask import Flask, render_template, request, jsonify
import sqlite3
from day_analisi import elapse
from database import *

app = Flask(__name__)

DB = "quotes.db"  # <-- metti il nome del tuo file sqlite

historyMode=False


def get_candles_for_id(asset_id):
    """Ritorna le candele per un dato id."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if historyMode:
        cur.execute("""
            SELECT timestamp, open, high, low, close 
            FROM candles_5m_history 
            WHERE id = ?
            ORDER BY timestamp ASC
        """, (asset_id,))
    else:
         cur.execute("""
            SELECT timestamp_5m as timestamp, open, high, low, close 
            FROM candles_5m 
            WHERE id = ?
            ORDER BY timestamp_5m ASC
        """, (asset_id,))
         
    rows = cur.fetchall()
    conn.close()

    # Formato richiesto da Chart.js financial: {t, o, h, l, c}
    candles = []
    for ts, o, h, l, c in rows:
        candles.append({
            "t": ts.replace(" ","T"),
            "o": float(o),
            "h": float(h),
            "l": float(l),
            "c": float(c)
        })
    return candles


@app.route("/")
def index():
    tickers = select("SELECT id from ticker where fineco=1 and market_cap = 'Large Cap' ")["id"].to_list()

    orders = elapse(tickers,historyMode, 3)
   
    for x in orders:
        print("ORDER",x.id)

    records = []
    for id in tickers:
        data = {}
        records.append(data)
        data["id"] = id

        order = next((x for x in orders if x.id == id), None)

        if order:
            data["gain"] ="A"
            #data["gain"] = order.profit_perc()
        else:
            data["gain"] ="-"

    return render_template("chart.html", datas=records)




@app.route("/data")
def api_data():
    asset_id = request.args.get("id")
    candles = get_candles_for_id(asset_id)
    
    return jsonify(candles)
    

if __name__ == "__main__":
    app.run(debug=True)
