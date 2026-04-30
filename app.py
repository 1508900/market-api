from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

TICKERS = {
    "indices": ["^GSPC", "^IXIC", "^STOXX50E", "ACWI", "EEM", "ILF", "MCHI", "EWY"],
    "forex":   ["EURUSD=X", "DX-Y.NYB", "EURJPY=X", "EURGBP=X", "USDJPY=X"],
    "energy":  ["TTF=F", "BZ=F", "CL=F"],
    "precious":["GC=F", "SI=F"],
    "industrial": ["HG=F", "ALI=F", "NI=F", "ZNC=F"],
}

def get_price(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.last_price
        prev  = info.previous_close
        if price and prev:
            change = round((price - prev) / prev * 100, 2)
            return {
                "ticker": ticker,
                "price": round(float(price), 4),
                "prevClose": round(float(prev), 4),
                "change": change,
                "high52": round(float(info.fifty_two_week_high or price), 4),
                "low52":  round(float(info.fifty_two_week_low  or price), 4),
            }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
    return None

def get_history(ticker, period="3mo"):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval="1d")
        if hist.empty:
            return [], []
        dates  = [str(d.date()) for d in hist.index]
        closes = [round(float(c), 4) for c in hist["Close"]]
        return dates, closes
    except Exception as e:
        print(f"Error history {ticker}: {e}")
        return [], []

@app.route("/api/prices")
def prices():
    result = {}
    all_tickers = []
    for group in TICKERS.values():
        all_tickers.extend(group)
    for ticker in all_tickers:
        data = get_price(ticker)
        if data:
            result[ticker] = data
    return jsonify(result)

@app.route("/api/history/<path:ticker>")
def history(ticker):
    dates, closes = get_history(ticker)
    return jsonify({"ticker": ticker, "dates": dates, "closes": closes})

@app.route("/api/all")
def all_data():
    result = {}
    all_tickers = []
    for group in TICKERS.values():
        all_tickers.extend(group)
    for ticker in all_tickers:
        data = get_price(ticker)
        if data:
            dates, closes = get_history(ticker)
            data["dates"]  = dates
            data["closes"] = closes
            result[ticker] = data
    return jsonify(result)

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Market API running"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
