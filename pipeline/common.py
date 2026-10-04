"""Shared paths + a resumable, throttle-aware Yahoo Finance runner used by the 0x_fetch_* steps."""
import json, os, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))          # .../Broking-Data/pipeline  (all inputs + raw json live here)
OUT = os.path.dirname(HERE)                                 # .../Broking-Data           (final deliverables)
os.chdir(HERE)                                              # every step reads/writes relative to pipeline/

# Broking accounts: internal id -> display name. Change names ONLY here; ids 1-3 are what the HTML app stores.
ACCOUNTS = {1: 'PEW-Angel', 2: 'JPW-Angel', 3: 'JPW-Zerodha'}
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
