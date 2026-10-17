"""Shared paths + a resumable, throttle-aware Yahoo Finance runner used by the 0x_fetch_* steps."""
import json, os, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))          # .../Broking-Data/pipeline  (all inputs + raw json live here)
OUT = os.path.dirname(HERE)                                 # .../Broking-Data           (final deliverables)
os.chdir(HERE)                                              # every step reads/writes relative to pipeline/

# Broking accounts: internal id -> display name. Change names ONLY here; ids 1-3 are what the HTML app stores.
ACCOUNTS = {1: 'PEW-Zerodha', 2: 'JPW-Angel', 3: 'JPW-Zerodha'}
ACCOUNT_ID = {v: k for k, v in ACCOUNTS.items()}

# Original suggested account lists (steps 12-13) live here as a backup; the app starts with EMPTY accounts when START_EMPTY.
SUGGESTED = os.path.join(OUT, 'Suggested_Lists_Backup')
os.makedirs(SUGGESTED, exist_ok=True)
START_EMPTY = True

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.9'}


def load_json(path):
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ---- sector = NSE's own 22-sector classification (NSE Indices "Industry Classification Structure", the 'Industry' column of
# its index files). Official where NSE publishes it (Nifty 500 + Nifty Total Market = ~750 stocks); for every other scrip it is
# derived from Yahoo's *industry* with the mapping below (built from how NSE classifies the 750 official stocks, then checked
# against the NSE structure: e.g. tractors / trucks / construction vehicles are Capital Goods, auto dealers are Automobile).
INDUSTRY_TO_NSE = {
    'Auto Parts': 'Automobile and Auto Components', 'Auto Manufacturers': 'Automobile and Auto Components', 'Auto & Truck Dealerships': 'Automobile and Auto Components',
    'Recreational Vehicles': 'Automobile and Auto Components',
    'Aerospace & Defense': 'Capital Goods', 'Specialty Industrial Machinery': 'Capital Goods', 'Electrical Equipment & Parts': 'Capital Goods',
    'Farm & Heavy Construction Machinery': 'Capital Goods', 'Metal Fabrication': 'Capital Goods', 'Building Products & Equipment': 'Capital Goods',
    'Electronic Components': 'Capital Goods', 'Solar': 'Capital Goods', 'Railroads': 'Capital Goods', 'Tools & Accessories': 'Capital Goods',
    'Packaging & Containers': 'Capital Goods', 'Scientific & Technical Instruments': 'Capital Goods', 'Semiconductors': 'Capital Goods',
    'Semiconductor Equipment & Materials': 'Capital Goods', 'Industrial Distribution': 'Services',
    'Engineering & Construction': 'Construction', 'Infrastructure Operations': 'Construction', 'Building Materials': 'Construction Materials',
    'Specialty Chemicals': 'Chemicals', 'Chemicals': 'Chemicals', 'Agricultural Inputs': 'Chemicals',
    'Steel': 'Metals & Mining', 'Aluminum': 'Metals & Mining', 'Copper': 'Metals & Mining', 'Other Industrial Metals & Mining': 'Metals & Mining',
    'Other Precious Metals & Mining': 'Metals & Mining', 'Gold': 'Metals & Mining', 'Silver': 'Metals & Mining',
    'Thermal Coal': 'Oil Gas & Consumable Fuels', 'Coking Coal': 'Oil Gas & Consumable Fuels', 'Oil & Gas Refining & Marketing': 'Oil Gas & Consumable Fuels',
    'Oil & Gas Integrated': 'Oil Gas & Consumable Fuels', 'Oil & Gas E&P': 'Oil Gas & Consumable Fuels', 'Oil & Gas Equipment & Services': 'Oil Gas & Consumable Fuels',
    'Oil & Gas Drilling': 'Oil Gas & Consumable Fuels', 'Oil & Gas Midstream': 'Oil Gas & Consumable Fuels', 'Utilities - Regulated Gas': 'Oil Gas & Consumable Fuels',
    'Utilities - Independent Power Producers': 'Power', 'Utilities - Renewable': 'Power', 'Utilities - Regulated Electric': 'Power', 'Utilities - Diversified': 'Power',
    'Utilities - Regulated Water': 'Utilities', 'Waste Management': 'Utilities', 'Pollution & Treatment Controls': 'Utilities',
    'Banks - Regional': 'Financial Services', 'Banks - Diversified': 'Financial Services', 'Credit Services': 'Financial Services', 'Asset Management': 'Financial Services',
    'Capital Markets': 'Financial Services', 'Insurance - Life': 'Financial Services', 'Insurance - Diversified': 'Financial Services', 'Insurance - Property & Casualty': 'Financial Services',
    'Insurance - Reinsurance': 'Financial Services', 'Insurance Brokers': 'Financial Services', 'Insurance - Specialty': 'Financial Services', 'Mortgage Finance': 'Financial Services',
    'Financial Conglomerates': 'Financial Services', 'Financial Data & Stock Exchanges': 'Financial Services', 'Healthcare Plans': 'Financial Services', 'Shell Companies': 'Financial Services',
    'Information Technology Services': 'Information Technology', 'Software - Application': 'Information Technology', 'Software - Infrastructure': 'Information Technology',
    'Computer Hardware': 'Information Technology', 'Consulting Services': 'Information Technology', 'Health Information Services': 'Information Technology',
    'Electronics & Computer Distribution': 'Information Technology',
    'Telecom Services': 'Telecommunication', 'Communication Equipment': 'Telecommunication',
    'Drug Manufacturers - Specialty & Generic': 'Healthcare', 'Drug Manufacturers - General': 'Healthcare', 'Biotechnology': 'Healthcare', 'Diagnostics & Research': 'Healthcare',
    'Medical Care Facilities': 'Healthcare', 'Medical Instruments & Supplies': 'Healthcare', 'Medical Devices': 'Healthcare', 'Medical Distribution': 'Healthcare',
    'Pharmaceutical Retailers': 'Healthcare',
    'Packaged Foods': 'Fast Moving Consumer Goods', 'Household & Personal Products': 'Fast Moving Consumer Goods', 'Beverages - Wineries & Distilleries': 'Fast Moving Consumer Goods',
    'Beverages - Brewers': 'Fast Moving Consumer Goods', 'Beverages - Non-Alcoholic': 'Fast Moving Consumer Goods', 'Tobacco': 'Fast Moving Consumer Goods',
    'Confectioners': 'Fast Moving Consumer Goods', 'Farm Products': 'Fast Moving Consumer Goods', 'Food Distribution': 'Fast Moving Consumer Goods',
    'Business Equipment & Supplies': 'Fast Moving Consumer Goods',
    'Luxury Goods': 'Consumer Durables', 'Furnishings, Fixtures & Appliances': 'Consumer Durables', 'Consumer Electronics': 'Consumer Durables', 'Footwear & Accessories': 'Consumer Durables',
    'Lodging': 'Consumer Services', 'Restaurants': 'Consumer Services', 'Travel Services': 'Consumer Services', 'Internet Retail': 'Consumer Services', 'Specialty Retail': 'Consumer Services',
    'Apparel Retail': 'Consumer Services', 'Department Stores': 'Consumer Services', 'Discount Stores': 'Consumer Services', 'Grocery Stores': 'Consumer Services',
    'Home Improvement Retail': 'Consumer Services', 'Internet Content & Information': 'Consumer Services', 'Education & Training Services': 'Consumer Services',
    'Resorts & Casinos': 'Consumer Services', 'Leisure': 'Consumer Services', 'Personal Services': 'Consumer Services',
    'Entertainment': 'Media Entertainment & Publication', 'Broadcasting': 'Media Entertainment & Publication', 'Publishing': 'Media Entertainment & Publication',
    'Advertising Agencies': 'Media Entertainment & Publication', 'Electronic Gaming & Multimedia': 'Media Entertainment & Publication',
    'Apparel Manufacturing': 'Textiles', 'Textile Manufacturing': 'Textiles',
    'Real Estate - Development': 'Realty', 'Real Estate - Diversified': 'Realty', 'Real Estate Services': 'Realty', 'Residential Construction': 'Realty',
    'Marine Shipping': 'Services', 'Integrated Freight & Logistics': 'Services', 'Trucking': 'Services', 'Airports & Air Services': 'Services', 'Airlines': 'Services',
    'Staffing & Employment Services': 'Services', 'Specialty Business Services': 'Services', 'Rental & Leasing Services': 'Services', 'Security & Protection Services': 'Services',
    'Paper & Paper Products': 'Forest Materials', 'Lumber & Wood Production': 'Forest Materials', 'Conglomerates': 'Diversified',
}
# last resort when Yahoo has a sector but an industry not in the table above
YSECTOR_TO_NSE = {'Financial Services': 'Financial Services', 'Technology': 'Information Technology', 'Healthcare': 'Healthcare', 'Consumer Defensive': 'Fast Moving Consumer Goods',
                  'Consumer Cyclical': 'Consumer Durables', 'Industrials': 'Capital Goods', 'Energy': 'Oil Gas & Consumable Fuels', 'Basic Materials': 'Chemicals',
                  'Utilities': 'Power', 'Real Estate': 'Realty', 'Communication Services': 'Telecommunication'}


def official_sectors():
    """{SYMBOL: NSE sector} from NSE's own index files (Nifty 500 + Nifty Total Market)."""
    import pandas as pd
    out = {}
    for f in ('ntm.csv', 'n500.csv'):
        if os.path.exists(os.path.join(HERE, f)):
            d = pd.read_csv(os.path.join(HERE, f)); out.update(dict(zip(d['Symbol'].str.strip(), d['Industry'].str.strip())))
    return out


def nse_sector(official, industry, ysector):
    """official NSE sector > Yahoo industry mapped to NSE > Yahoo sector mapped to NSE > 'Unclassified' (pandas Series in, Series out)"""
    return official.fillna(industry.map(INDUSTRY_TO_NSE)).fillna(ysector.map(YSECTOR_TO_NSE)).fillna('Unclassified')


# Data date for every return / backtest calculation = the NSE bhavcopy day step 00 downloaded (the last trading day).
END_DATE = load_json(os.path.join(HERE, 'inputs_meta.json')).get('nse_bhav_date', '2026-10-01')


def reset_if_stale(path):
    """History caches hold closes up to the END_DATE they were fetched for; when END_DATE moves, drop the cache so it re-fetches."""
    tags = load_json('cache_end.json')
    if tags.get(path) != END_DATE:
        if os.path.exists(path):
            os.remove(path); print(f'{path}: fetched for {tags.get(path) or "an older date"}, re-fetching to {END_DATE}', flush=True)
        tags[path] = END_DATE; json.dump(tags, open('cache_end.json', 'w'), indent=1)


def yahoo_alive():
    import yfinance as yf
    try:
        return bool(yf.Ticker('RELIANCE.NS').info.get('marketCap'))
    except Exception:
        return False


def wait_for_yahoo(max_minutes=90):
    """Yahoo answers 401 'Invalid Crumb' / 429 when hit too hard. Wait it out instead of hammering."""
    t0 = time.time()
    while not yahoo_alive():
        if time.time() - t0 > max_minutes * 60:
            raise SystemExit('Yahoo Finance still throttling after %d min - try again later' % max_minutes)
        print('Yahoo throttled; waiting 3 min', flush=True)
        time.sleep(180)


def run_resumable(name, get, symbols, outfile, workers=2, pause=0.4):
    """Fetch get(symbol) -> (symbol, dict|None) for every symbol not already valid in outfile.
    Safe to re-run: completed symbols are skipped. Cools down after a run of failures (throttling)."""
    out = load_json(outfile)
    todo = [s for s in symbols if not out.get(s)]
    print(f'{name}: {len(symbols)} symbols, {len(symbols) - len(todo)} already done, {len(todo)} to fetch', flush=True)
    if not todo:
        return out
    wait_for_yahoo()
    fails = 0

    def g(s):
        time.sleep(pause)
        return get(s)

    with ThreadPoolExecutor(workers) as ex:
        for n, (s, d) in enumerate(ex.map(g, todo)):
            if d:
                out[s] = d; fails = 0
            else:
                out.setdefault(s, None); fails += 1
                if fails >= 10:
                    print('many failures in a row - cooling down 4 min', flush=True)
                    time.sleep(240); fails = 0
            if n % 25 == 0:
                print(f'{name}: {n}/{len(todo)}', flush=True)
                json.dump(out, open(outfile, 'w'))
    json.dump(out, open(outfile, 'w'))
    ok = sum(1 for s in symbols if out.get(s))
    print(f'{name}: done, {ok}/{len(symbols)} valid ({len(symbols) - ok} missing - re-run this step to retry them)', flush=True)
    return out


BASIC_KEYS = ['sector', 'industry', 'marketCap', 'trailingPE', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'dividendRate', 'dividendYield',
              'trailingAnnualDividendRate', 'currentPrice', 'regularMarketPrice', 'averageVolume', 'priceToBook', 'returnOnEquity',
              'debtToEquity', 'earningsGrowth', 'revenueGrowth', 'beta']


def yahoo_basic(symbol, suffix='.NS'):
    """Snapshot fundamentals from Yahoo .info. NSE tickers use '.NS'; BSE uses the BSE *ticker name* + '.BO' (not the numeric code)."""
    import yfinance as yf
    for attempt in range(3):
        try:
            i = yf.Ticker(symbol + suffix).info
            if i and (i.get('marketCap') or i.get('currentPrice') or i.get('regularMarketPrice')):
                return symbol, {k: i.get(k) for k in BASIC_KEYS}
            return symbol, None
        except Exception:
            time.sleep(2 * (attempt + 1))
    return symbol, None
