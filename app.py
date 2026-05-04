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

# Fallback US yields from Yahoo if FRED fails
YAHOO_US_YIELDS = {
    'y2':  'ZT=F',    # 2Y Treasury futures
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
        # ECB Data Portal API
        url = f"https://data-api.ecb.europa.eu/service/data/{series_id}?lastNObservations=1&format=jsondata"
        r = requests.get(url, headers={**HEADERS, 'Accept': 'application/json'}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        datasets = data.get('dataSets', [])
        if not datasets:
            return None
        series_data = datasets[0].get('series', {})
        if not series_data:
            return None
        first_series = list(series_data.values())[0]
        obs = first_series.get('observations', {})
        if obs:
            latest_key = sorted(obs.keys(), key=lambda x: int(x))[-1]
            val = obs[latest_key][0]
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

# Tickers that get 5 years of history
FIVE_YEAR_TICKERS = {
    "^GSPC", "^IXIC", "^STOXX50E", "ACWI", "EEM", "ILF", "MCHI", "EWY",
    "EURUSD=X", "DX-Y.NYB", "EURJPY=X", "EURGBP=X", "USDJPY=X",
    "^VIX", "OVS.EX"
}

@app.route("/api/all")
def all_data():
    result = {}
    for ticker in MARKET_TICKERS:
        range_ = "5y" if ticker in FIVE_YEAR_TICKERS else "2y"
        data = fetch_quote(ticker, range_=range_)
        if data:
            result[ticker] = data
    return jsonify(result)

@app.route("/api/holdings")
def holdings():
    result = {}
    for ticker in HOLDING_TICKERS:
        data = fetch_quote(ticker, range_="2y")
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
    # Fallback for missing tenors
    if 'y2' not in us:
        val = fetch_yahoo_yield('ZT=F')
        if val and 0 < val < 20:
            # ZT=F is price not yield, skip; use interpolation
            if 'y1' in us and 'y5' in us:
                us['y2'] = round((us['y1'] + us['y5']) / 2, 2)
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

NEWS_API_KEY = 'd4176b33a2c44707b2c4376667a7a1ae'

NEWS_QUERIES = [
    {'q': 'stock market S&P 500 earnings', 'category': 'equities'},
    {'q': 'Federal Reserve interest rates inflation', 'category': 'rates'},
    {'q': 'ECB European Central Bank eurozone economy', 'category': 'rates'},
    {'q': 'credit spreads high yield corporate bonds', 'category': 'credit'},
    {'q': 'oil gold commodities energy metals', 'category': 'commodities'},
    {'q': 'GDP inflation macro economy trade', 'category': 'macro'},
]

@app.route("/api/news")
def news():
    all_articles = []
    try:
        for query in NEWS_QUERIES:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query['q'],
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 4,
                'apiKey': NEWS_API_KEY,
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=8)
            data = r.json()
            if data.get('status') == 'ok':
                for a in data.get('articles', []):
                    if a.get('title') and a['title'] != '[Removed]' and a.get('url'):
                        all_articles.append({
                            'title': a['title'],
                            'summary': (a.get('description') or '')[:200],
                            'category': query['category'],
                            'source': a.get('source', {}).get('name', 'News'),
                            'publishedAt': a.get('publishedAt', ''),
                            'url': a['url'],
                        })
    except Exception as e:
        print(f"News error: {e}")
    
    # Sort by date
    all_articles.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
    return jsonify(all_articles[:30])

# ICE BofA Credit Spread Series (FRED)
FRED_CREDIT_SERIES = {
    'us_ig':  'BAMLC0A0CM',      # US IG OAS spread
    'us_hy':  'BAMLH0A0HYM2',    # US HY OAS spread
    'eu_ig':  'BAMLHE00EHY0EY',  # EU HY spread (proxy for IG)
    'eu_hy':  'BAMLHE00EHY0EY',  # EU HY OAS spread
}

# More specific series
FRED_CREDIT_FULL = {
    'us_ig':  {'series': 'BAMLC0A0CM',       'name': 'EEUU Investment Grade',  'region': 'EEUU'},
    'us_hy':  {'series': 'BAMLH0A0HYM2',     'name': 'EEUU High Yield',        'region': 'EEUU'},
    'eu_ig':  {'series': 'BAMLHE00EHY0EY',   'name': 'Europa Investment Grade', 'region': 'Europa'},
    'eu_hy':  {'series': 'BAMLHE00EHY0EY',   'name': 'Europa High Yield',       'region': 'Europa'},
}

def fetch_fred_series(series_id, limit=500):
    """Fetch historical daily series from FRED."""
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': limit,
            'observation_start': '2023-01-01',
            'frequency': 'd',  # daily frequency
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        obs = data.get('observations', [])
        dates = []
        values = []
        for o in reversed(obs):
            if o.get('value') and o['value'] != '.':
                dates.append(o['date'])
                values.append(round(float(o['value']), 3))
        return dates, values
    except Exception as e:
        print(f"FRED series error {series_id}: {e}")
        return [], []

@app.route("/api/credit")
def credit():
    result = {}
    seen_series = {}
    
    # ICE BofA series - all from FRED
    # BAMLHE00EHY0EY = ICE BofA Euro High Yield OAS
    # BAMLHE00EHY0EY = EU HY (same series, no separate EU IG in FRED)
    # For EU IG we use BAMLC0A4CAAA = ICE BofA AAA US Corporate (best proxy available)
    # Better: BAMLHE00EHY0EY for EU HY, and derive EU IG from US IG * 1.2 spread factor
    series_map = {
        'us_ig': {'series': 'BAMLC0A0CM',      'name': 'Investment Grade', 'region': 'EEUU',   'type': 'ig'},
        'us_hy': {'series': 'BAMLH0A0HYM2',    'name': 'High Yield',       'region': 'EEUU',   'type': 'hy'},
        'eu_ig': {'series': 'BAMLHE00EHY0EY',  'name': 'Investment Grade', 'region': 'Europa', 'type': 'ig'},
        'eu_hy': {'series': 'BAMLHE00EHY0EY',  'name': 'High Yield',       'region': 'Europa', 'type': 'hy'},
    }
    eu_ig_series = 'BAMLC0A0CM'     # Use US IG as base, apply EU premium factor
    eu_hy_series = 'BAMLHE00EHY0EY' # ICE BofA Euro HY OAS (official EU HY)
    
    for credit_id, info in series_map.items():
        # Use correct series per credit type
        if credit_id == 'eu_ig':
            series = eu_ig_series  # US IG base
        elif credit_id == 'eu_hy':
            series = eu_hy_series  # EU HY official
        else:
            series = info['series']
        # Cache series data to avoid duplicate calls
        if series not in seen_series:
            dates, values = fetch_fred_series(series, limit=500)
            seen_series[series] = (dates, values)
        else:
            dates, values = seen_series[series]
        
        if values:
            current = values[-1]
            prev = values[-2] if len(values) > 1 else current
            change = round(current - prev, 1)
            # Convert to basis points (FRED data is in percentage)
            current_pb = round(current * 100, 0)
            prev_pb = round(prev * 100, 0)
            change_pb = round(change * 100, 1)
            # Apply EU IG premium: EU IG is typically ~25pb wider than US IG
            if credit_id == 'eu_ig':
                current_pb = current_pb + 25
                prev_pb = prev_pb + 25
            
            result[credit_id] = {
                'id': credit_id,
                'name': info['name'],
                'region': info['region'],
                'type': info['type'],
                'spread': int(current_pb),
                'change': int(change_pb),
                'dates': dates[-252:],   # Last year
                'values': [round(v * 100, 1) for v in values[-252:]],
            }
    
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
