from flask import Flask, jsonify
from flask_cors import CORS
import requests, datetime

app = Flask(__name__)
CORS(app)

TICKERS = [
    "^GSPC", "^IXIC", "^STOXX50E", "ACWI", "EEM", "ILF", "MCHI", "EWY",
    "EURUSD=X", "DX-Y.NYB", "EURJPY=X", "EURGBP=X", "USDJPY=X",
    "TTF=F", "BZ=F", "CL=F", "GC=F", "SI=F", "HG=F", "ALI=F", "NI=F", "ZNC=F"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_quote(ticker):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(ticker) + "?interval=1d&range=3mo"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        timestamps = result[0].get("timestamp", [])
        closes_raw = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])

        price = meta.get("regularMarketPrice")
        prev  = meta.get("chartPreviousClose") or meta.get("regularMarketPreviousClose")
        if not price:
            return None

        dates  = [str(datetime.date.fromtimestamp(t)) for t in timestamps]
        closes = [round(float(c), 4) if c else None for c in closes_raw]
        pairs  = [(d, c) for d, c in zip(dates, closes) if c is not None]
        dates  = [p[0] for p in pairs]
        closes = [p[1] for p in pairs]

        change = round((price - prev) / prev * 100, 2) if prev else 0

        return {
            "ticker":    ticker,
            "price":     round(float(price), 4),
            "prevClose": round(float(prev), 4) if prev else None,
            "change":    change,
            "high52":    round(float(meta.get("fiftyTwoWeekHigh", price)), 4),
            "low52":     round(float(meta.get("fiftyTwoWeekLow",  price)), 4),
            "dates":     dates,
            "closes":    closes,
        }
    except Exception as e:
        print("Error " + ticker + ": " + str(e))
        return None

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Market API running"})

@app.route("/api/all")
def all_data():
    result = {}
    for ticker in TICKERS:
        data = fetch_quote(ticker)
        if data:
            result[ticker] = data
    return jsonify(result)

@app.route("/api/quote/<path:ticker>")
def quote(ticker):
    data = fetch_quote(ticker)
    if data:
        return jsonify(data)
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
