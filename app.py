from flask import Flask, jsonify
from flask_cors import CORS
import requests, datetime

app = Flask(__name__)
CORS(app)

MARKET_TICKERS = [
    "^GSPC", "^IXIC", "^STOXX50E", "ACWI", "EEM", "ILF", "MCHI", "EWY",
    "EURUSD=X", "DX-Y.NYB", "EURJPY=X", "EURGBP=X", "USDJPY=X",
    "TTF=F", "BZ=F", "CL=F", "GC=F", "SI=F", "HG=F", "ALI=F", "NI=F", "ZNC=F",
    "^VIX", "OVS.EX"
]

HOLDING_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "BRK-B", "TSLA", "AVGO",
    "ASML", "SAP", "TSM", "BABA", "TCEHY", "PDD", "JD", "BIDU",
    "VALE", "PBR", "ITUB", "AMX", "FMX", "BBD", "INFY", "HDB",
]

# Yahoo Finance tickers for government bond yields
YIELD_TICKERS = {
    'US': {
        'y1':  'DTB1YR=F',   # US 1Y Treasury
        'y2':  '^IRX',        # US 13W (proxy)
        'y5':  '^FVX',        # US 5Y Treasury
        'y10': '^TNX',        # US 10Y Treasury
        'y30': '^TYX',        # US 30Y Treasury
    },
    'DE': {
        'y1':  'GDBR1Y=X',
        'y2':  'GDBR2Y=X',
        'y5':  'GDBR5Y=X',
        'y10': 'GDBR10Y=X',
        'y30': 'GDBR30Y=X',
    },
    'FR': {
        'y2':  'FRTR2Y=X',
        'y5':  'FRTR5Y=X',
        'y10': 'FRTR10Y=X',
        'y30': 'FRTR30Y=X',
    },
    'ES': {
        'y2':  'ESPTS2Y=X',
        'y5':  'ESPTS5Y=X',
        'y10': 'ESPTS10Y=X',
        'y30': 'ESPTS30Y=X',
    },
    'IT': {
        'y2':  'ITBTPS2Y=X',
        'y5':  'ITBTPS5Y=X',
        'y10': 'ITBTPS10Y=X',
        'y30': 'ITBTPS30Y=X',
    },
    'UK': {
        'y2':  'GBGB2YR=X',
        'y5':  'GBGB5YR=X',
        'y10': 'GBGB10YR=X',
        'y30': 'GBGB30YR=X',
    },
    'JP': {
        'y2':  'JPGB2YR=X',
        'y5':  'JPGB5YR=X',
        'y10': 'JPGB10YR=X',
        'y30': 'JPGB30YR=X',
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_quote(ticker, range_="3mo"):
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(ticker) + "?interval=1d&range=" + range_
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

        ytd_change = None
        for i, d in enumerate(dates):
            if d >= "2026-01-01":
                first_2026 = closes[i]
                ytd_change = round((price - first_2026) / first_2026 * 100, 2)
                break

        # Dividend yield
        div_yield = None
        try:
            info = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(ticker) + "?modules=summaryDetail",
                headers=HEADERS, timeout=6
            ).json()
            div_yield = info.get("quoteSummary", {}).get("result", [{}])[0].get("summaryDetail", {}).get("dividendYield", {}).get("raw")
            if div_yield:
                div_yield = round(float(div_yield) * 100, 2)
        except:
            pass

        return {
            "ticker":    ticker,
            "price":     round(float(price), 4),
            "prevClose": round(float(prev), 4) if prev else None,
            "change":    change,
            "ytd":       ytd_change,
            "divYield":  div_yield,
            "high52":    round(float(meta.get("fiftyTwoWeekHigh", price)), 4),
            "low52":     round(float(meta.get("fiftyTwoWeekLow",  price)), 4),
            "dates":     dates,
            "closes":    closes,
        }
    except Exception as e:
        print("Error " + ticker + ": " + str(e))
        return None

def fetch_yield_value(ticker):
    """Fetch just the current yield value for a bond ticker."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(ticker) + "?interval=1d&range=5d"
        r = requests.get(url, headers=HEADERS, timeout=8)
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if result:
            price = result[0].get("meta", {}).get("regularMarketPrice")
            if price:
                # TNX, FVX, TYX are in tenths of percent
                if ticker in ['^TNX', '^TYX', '^FVX', '^IRX']:
                    return round(float(price) / 10, 2) if float(price) > 10 else round(float(price), 2)
                return round(float(price), 2)
    except Exception as e:
        print(f"Yield error {ticker}: {e}")
    return None

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Market API running"})

@app.route("/api/all")
def all_data():
    result = {}
    for ticker in MARKET_TICKERS:
        data = fetch_quote(ticker)
        if data:
            result[ticker] = data
    return jsonify(result)

@app.route("/api/holdings")
def holdings():
    result = {}
    for ticker in HOLDING_TICKERS:
        data = fetch_quote(ticker, range_="1mo")
        if data:
            result[ticker] = {
                "ticker":  data["ticker"],
                "price":   data["price"],
                "change":  data["change"],
                "ytd":     data["ytd"],
            }
    return jsonify(result)

@app.route("/api/yields")
def yields():
    result = {}
    for country, tickers in YIELD_TICKERS.items():
        country_data = {}
        for tenor, ticker in tickers.items():
            val = fetch_yield_value(ticker)
            if val and 0 < val < 20:  # sanity check
                country_data[tenor] = val
        if country_data:
            result[country] = country_data
    return jsonify(result)

@app.route("/api/quote/<path:ticker>")
def quote(ticker):
    data = fetch_quote(ticker)
    if data:
        return jsonify(data)
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
