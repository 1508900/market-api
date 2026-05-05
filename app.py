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

FRED_US_SERIES = {
    'y1':  'DGS1',
    'y2':  'DGS2',
    'y5':  'DGS5',
    'y10': 'DGS10',
    'y30': 'DGS30',
}

ECB_SERIES = {
    'DE': {
        'y1':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y',
        'y2':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y',
        'y5':  'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y',
        'y10': 'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y',
        'y30': 'YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y',
    },
}

SPREAD_OVER_DE = {
    'FR': {'y1': 0.25, 'y2': 0.35, 'y5': 0.45, 'y10': 0.55, 'y30': 0.60},
    'ES': {'y1': 0.30, 'y2': 0.40, 'y5': 0.55, 'y10': 0.70, 'y30': 0.75},
    'IT': {'y1': 0.55, 'y2': 0.65, 'y5': 0.80, 'y10': 1.05, 'y30': 1.15},
}

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

NEWS_QUERIES = [
    {'q': 'stock market S&P 500 earnings', 'category': 'equities'},
    {'q': 'Federal Reserve interest rates inflation', 'category': 'rates'},
    {'q': 'ECB European Central Bank eurozone economy', 'category': 'rates'},
    {'q': 'credit spreads high yield corporate bonds', 'category': 'credit'},
    {'q': 'oil gold commodities energy metals', 'category': 'commodities'},
    {'q': 'GDP inflation macro economy trade', 'category': 'macro'},
]

NEWS_API_KEY = 'd4176b33a2c44707b2c4376667a7a1ae'

FIVE_YEAR_TICKERS = {
    "^GSPC", "^IXIC", "^STOXX50E", "ACWI", "EEM", "ILF", "MCHI", "EWY",
    "EURUSD=X", "DX-Y.NYB", "EURJPY=X", "EURGBP=X", "USDJPY=X",
    "^VIX", "OVS.EX",
    "TTF=F", "BZ=F", "CL=F", "GC=F", "SI=F", "HG=F", "ALI=F", "NI=F", "ZNC=F"
}


# ---- HELPERS ----

def fetch_fred(series_id):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
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


def fetch_fred_series(series_id, limit=500):
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': limit,
            'observation_start': '2023-01-01',
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        obs = data.get('observations', [])
        dates, values = [], []
        for o in reversed(obs):
            if o.get('value') and o['value'] != '.':
                dates.append(o['date'])
                values.append(round(float(o['value']), 3))
        return dates, values
    except Exception as e:
        print(f"FRED series error {series_id}: {e}")
        return [], []


def fetch_ecb(series_id):
    try:
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


# ---- ROUTES ----

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Market API running"})


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


@app.route("/api/quote/<path:ticker>")
def quote(ticker):
    data = fetch_quote(ticker)
    if data:
        return jsonify(data)
    return jsonify({"error": "not found"}), 404


@app.route("/api/yields")
def yields():
    result = {}

    # 1. US from FRED
    us = {}
    for tenor, series in FRED_US_SERIES.items():
        val = fetch_fred(series)
        if val and 0 < val < 20:
            us[tenor] = val
    if us:
        result['US'] = us
        print(f"US yields from FRED: {us}")

    # 2. Germany from ECB
    de = {}
    for tenor, series in ECB_SERIES['DE'].items():
        val = fetch_ecb(series)
        if val and -2 < val < 20:
            de[tenor] = val
    if de:
        result['DE'] = de
        print(f"DE yields from ECB: {de}")
        # FR, ES, IT from DE + spread
        for country, spreads in SPREAD_OVER_DE.items():
            country_data = {}
            for tenor, spread in spreads.items():
                if tenor in de:
                    country_data[tenor] = round(de[tenor] + spread, 2)
            if country_data:
                result[country] = country_data

    # 3. UK and Japan from Yahoo
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


@app.route("/api/credit")
def credit():
    result = {}
    seen = {}

    series_map = {
        'us_ig': {'series': 'BAMLC0A0CM',     'name': 'Investment Grade', 'region': 'EEUU',   'type': 'ig'},
        'us_hy': {'series': 'BAMLH0A0HYM2',   'name': 'High Yield',       'region': 'EEUU',   'type': 'hy'},
        'eu_ig': {'series': 'BAMLC0A0CM',      'name': 'Investment Grade', 'region': 'Europa', 'type': 'ig'},  # US IG base + 25pb
        'eu_hy': {'series': 'BAMLHE00EHY0EY', 'name': 'High Yield',       'region': 'Europa', 'type': 'hy'},
    }

    for credit_id, info in series_map.items():
        series = info['series']
        if series not in seen:
            dates, values = fetch_fred_series(series, limit=500)
            seen[series] = (dates, values)
        else:
            dates, values = seen[series]

        if values:
            current = values[-1]
            prev = values[-2] if len(values) > 1 else current
            change_pb = round((current - prev) * 100, 1)
            current_pb = int(round(current * 100))
            if credit_id == 'eu_ig':
                current_pb += 25

            result[credit_id] = {
                'id':     credit_id,
                'name':   info['name'],
                'region': info['region'],
                'type':   info['type'],
                'spread': current_pb,
                'change': int(change_pb),
                'dates':  dates[-252:],
                'values': [round(v * 100, 1) for v in values[-252:]],
            }

    return jsonify(result)


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
                            'title':       a['title'],
                            'summary':     (a.get('description') or '')[:200],
                            'category':    query['category'],
                            'source':      a.get('source', {}).get('name', 'News'),
                            'publishedAt': a.get('publishedAt', ''),
                            'url':         a['url'],
                        })
    except Exception as e:
        print(f"News error: {e}")

    all_articles.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
    return jsonify(all_articles[:30])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
