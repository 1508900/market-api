from flask import Flask, jsonify
from flask_cors import CORS
import requests, datetime

app = Flask(__name__)
CORS(app)

FRED_API_KEY = 'e1d62698562dd0ded5a7cada4ddd11c3'

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# FRED series for US Treasury yields (official Fed data)
FRED_US_SERIES = {
    'y1':  'DGS1',    # 1-Year Treasury Constant Maturity
    'y2':  'DGS2',    # 2-Year Treasury Constant Maturity
    'y5':  'DGS5',    # 5-Year Treasury Constant Maturity
    'y10': 'DGS10',   # 10-Year Treasury Constant Maturity
    'y30': 'DGS30',   # 30-Year Treasury Constant Maturity
}

# ECB API series for European sovereign yields
# Using ECB Statistical Data Warehouse
ECB_SERIES = {
    'DE': {
        'y1':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y',
        'y2':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y',
        'y5':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y',
        'y10': 'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y',
        'y30': 'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y',
    },
}

# For non-ECB EUR countries, use spread over Germany (approximate)
SPREAD_OVER_DE = {
    'FR': {'y1': 0.25, 'y2': 0.35, 'y5': 0.45, 'y10': 0.55, 'y30': 0.60},
    'ES': {'y1': 0.30, 'y2': 0.40, 'y5': 0.55, 'y10': 0.70, 'y30': 0.75},
    'IT': {'y1': 0.55, 'y2': 0.65, 'y5': 0.80, 'y10': 1.05, 'y30': 1.15},
}

# Yahoo Finance tickers for UK and Japan
YAHOO_YIELDS = {
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

def fetch_fred(series_id):
    """Fetch latest value from FRED API."""
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 5,
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        for obs in data.get('observations', []):
            if obs.get('value') and obs['value'] != '.':
                return round(float(obs['value']), 2)
    except Exception as e:
        print(f"FRED error {series_id}: {e}")
    return None

def fetch_ecb(series_id):
    """Fetch latest value from ECB API."""
    try:
        url = f"https://data-api.ecb.europa.eu/service/data/{series_id}"
        params = {'lastNObservations': 1, 'format': 'jsondata'}
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        datasets = data.get('dataSets', [{}])
        if not datasets:
            return None
        series_data = datasets[0].get('series', {})
        if series_data:
            obs = list(series_data.values())[0].get('observations', {})
            if obs:
                latest = sorted(obs.keys(), key=int)[-1]
                val = obs[latest][0]
                if val is not None:
                    return round(float(val), 2)
    except Exception as e:
        print(f"ECB error {series_id}: {e}")
    return None

def fetch_yahoo_yield(ticker):
    """Fetch yield from Yahoo Finance."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + requests.utils.quote(ticker) + "?interval=1d&range=5d"
        r = requests.get(url, headers=HEADERS, timeout=8)
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if result:
            price = result[0].get("meta", {}).get("regularMarketPrice")
            if price:
                return round(float(price), 2)
    except Exception as e:
        print(f"Yahoo yield error {ticker}: {e}")
    return None

def fetch_quote(ticker, range_="1y"):
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

        return {
            "ticker":    ticker,
            "price":     round(float(price), 4),
            "prevClose": round(float(prev), 4) if prev else None,
            "change":    change,
            "ytd":       ytd_change,
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
    for ticker in MARKET_TICKERS:
        data = fetch_quote(ticker, range_="1y")
        if data:
            result[ticker] = data
    return jsonify(result)

@app.route("/api/holdings")
def holdings():
    result = {}
    for ticker in HOLDING_TICKERS:
        data = fetch_quote(ticker, range_="1y")
        if data:
            result[ticker] = {
                "ticker": data["ticker"],
                "price":  data["price"],
                "change": data["change"],
                "ytd":    data["ytd"],
            }
    return jsonify(result)

@app.route("/api/yields")
def yields():
    result = {}

    # 1. US yields from FRED (official Fed data)
    us = {}
    for tenor, series in FRED_US_SERIES.items():
        val = fetch_fred(series)
        if val and 0 < val < 20:
            us[tenor] = val
    if us:
        result['US'] = us
        print(f"US yields from FRED: {us}")

    # 2. Germany from ECB (official ECB data)
    de = {}
    for tenor, series in ECB_SERIES['DE'].items():
        val = fetch_ecb(series)
        if val and -2 < val < 20:
            de[tenor] = val
    if de:
        result['DE'] = de
        print(f"DE yields from ECB: {de}")

        # 3. FR, ES, IT derived from DE + spread
        for country, spreads in SPREAD_OVER_DE.items():
            country_data = {}
            for tenor, spread in spreads.items():
                if tenor in de:
                    country_data[tenor] = round(de[tenor] + spread, 2)
            if country_data:
                result[country] = country_data

    # 4. UK and Japan from Yahoo Finance
    for country, tickers in YAHOO_YIELDS.items():
        country_data = {}
        for tenor, ticker in tickers.items():
            val = fetch_yahoo_yield(ticker)
            if val and 0 < val < 20:
                country_data[tenor] = val
        if country_data:
            result[country] = country_data
            print(f"{country} yields from Yahoo: {country_data}")

    return jsonify(result)

@app.route("/api/quote/<path:ticker>")
def quote(ticker):
    data = fetch_quote(ticker)
    if data:
        return jsonify(data)
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
