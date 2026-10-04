"""Step 15 - returns of every live NSE equity index (sectoral, thematic, broad-market, strategy) over 1/2/3/5/10/15/20/25/30 years,
plus each index's data start and since-inception CAGR, from NSE's official index history. -> ../Sector_Returns.csv
Independent of the account lists (reads/writes nothing of steps 10-14).
Price-return indices (dividends excluded; NSE's TRI series are not served by this endpoint). A horizon starts on the first trading
day on/after 1 October of the start year and ends on the latest close on/before END_DATE.
Index list = NSE /api/allIndices (cached in nse_all_indices.json). History cache: raw_sector2.json (resumable)."""
import datetime as dt, json, os, re, time, urllib.parse as up
import pandas as pd, requests
from common import OUT, UA, load_json

END_DATE = '2026-10-01'
HORIZONS = {'1Y': 1, '2Y': 2, '3Y': 3, '5Y': 5, '10Y': 10, '15Y': 15, '20Y': 20, '25Y': 25, '30Y': 30}
CATS = {'SECTORAL INDICES': 'Sector', 'THEMATIC INDICES': 'Theme', 'BROAD MARKET INDICES': 'Broad market', 'STRATEGY INDICES': 'Strategy'}
EXTRA = {'NIFTY 50': 'Broad market', 'NIFTY NEXT 50': 'Broad market', 'NIFTY BANK': 'Sector', 'NIFTY FINANCIAL SERVICES': 'Sector', 'NIFTY MIDCAP SELECT': 'Broad market'}
SKIP = {'INDIA VIX', 'NIFTY50 TR 2X LEVERAGE', 'NIFTY50 PR 2X LEVERAGE', 'NIFTY50 TR 1X INVERSE', 'NIFTY50 PR 1X INVERSE', 'NIFTY50 DIVIDEND POINTS', 'NIFTY50 USD'}
H = dict(UA, Referer='https://www.nseindia.com/reports-indices-historical-index-data')
URL = 'https://www.nseindia.com/api/historicalOR/indicesHistory?indexType={}&from={}&to={}'
ACRO = {'IT', 'PSU', 'FMCG', 'MNC', 'CPSE', 'PSE', 'EV', 'IPO', 'ESG', 'REITS', 'SME', 'USD', 'TR', 'PR', 'MQVLV', 'FPI', 'G-SEC', '(MAATR)'}


def session():
    s = requests.Session()
    s.get('https://www.nseindia.com', headers=H, timeout=20)
    s.get('https://www.nseindia.com/reports-indices-historical-index-data', headers=H, timeout=20)
    return s


def pretty(name):
    words = name.replace('NIFTY500', 'NIFTY 500').replace('NIFTY50', 'NIFTY 50').replace('NIFTY100', 'NIFTY 100').replace('NIFTY200', 'NIFTY 200').split()
    return ' '.join(w if w in ACRO or re.match(r'^[\d/:.%&-]+$', w) else w.capitalize() for w in words).replace('Nifty ', 'Nifty ', 1)


# ---- index universe ----
s = session()
if not os.path.exists('nse_all_indices.json'):
    json.dump(s.get('https://www.nseindia.com/api/allIndices', headers=dict(UA, Referer='https://www.nseindia.com/'), timeout=30).json()['data'], open('nse_all_indices.json', 'w'))
UNI = {x['index']: CATS[x['key']] for x in json.load(open('nse_all_indices.json')) if x['key'] in CATS and x['index'] not in SKIP}
for k, v in EXTRA.items(): UNI.setdefault(k, v)


def window(name, a, b):
    """{date: close} between a and b (NSE serves at most ~1 year per request). None = request failed."""
    global s
    for attempt in range(3):
        try:
            r = s.get(URL.format(up.quote(name), a.strftime('%d-%m-%Y'), b.strftime('%d-%m-%Y')), headers=H, timeout=30)
            if r.status_code != 200: raise RuntimeError(r.status_code)
            out = {}
            for x in r.json().get('data') or []:
                if x.get('EOD_CLOSE_INDEX_VAL') is not None:
                    out[dt.datetime.strptime(x['EOD_TIMESTAMP'], '%d-%b-%Y').strftime('%Y-%m-%d')] = float(x['EOD_CLOSE_INDEX_VAL'])
            time.sleep(0.4)
            return out
        except Exception:
            time.sleep(3); s = session()
    return None


end = dt.date.fromisoformat(END_DATE)
starts = {hz: dt.date(end.year - y, 10, 1) for hz, y in HORIZONS.items()}
cache = load_json('raw_sector2.json')
for n, name in enumerate(UNI):
    c = cache.setdefault(name, {'closes': {}, 'done': [], 'first': None})
    def get(tag, a, b):
        if tag in c['done']: return True
        got = window(name, a, b)
        if got is None: return False
        c['closes'].update(got); c['done'].append(tag); return True
    get('end', end - dt.timedelta(days=12), end)
    last_ok, miss = None, None
    for hz, d0 in starts.items():                        # shortest -> longest; stop at the first horizon with no data
        get(hz, d0, d0 + dt.timedelta(days=14))
        if any(d0.isoformat() <= d <= (d0 + dt.timedelta(days=14)).isoformat() for d in c['closes']): last_ok = d0
        else: miss = d0; break
    if 'first' not in c['done']:                         # locate the data start: scan year by year between last good and first missing start
        lo = (last_ok or end)
        first = None
        years = [] if miss is None else range(miss.year, lo.year + 1)   # has 30Y of data -> no need to search further back
        for y in years:
            a = max(dt.date(y, 1, 1), dt.date(1990, 1, 1)); b = min(dt.date(y, 12, 31), lo)
            if a > b: continue
            got = window(name, a, b)
            if got: first = min(got); c['closes'].update({first: got[first]}); break
        c['first'] = first or (min(c['closes']) if miss is None and c['closes'] else None); c['done'].append('first')
    if n % 5 == 0: json.dump(cache, open('raw_sector2.json', 'w'))
    print(f'{n + 1}/{len(UNI)} {name}', flush=True)
json.dump(cache, open('raw_sector2.json', 'w'))

# ---- Sensex from Yahoo (BSE's own history is not scriptable), as an extra broad-market reference ----
try:
    import yfinance as yf
    hs = yf.Ticker('^BSESN').history(start='1996-09-01', end=(end + dt.timedelta(days=1)).isoformat())['Close'].dropna()
    cache['S&P BSE SENSEX'] = {'closes': {d.strftime('%Y-%m-%d'): float(v) for d, v in hs.items()}, 'done': [], 'first': hs.index[0].strftime('%Y-%m-%d')}
    UNI['S&P BSE SENSEX'] = 'Broad market'
except Exception as e:
    print('sensex skipped:', e)

rows = []
for name, cat in UNI.items():
    c = cache.get(name) or {}
    px = c.get('closes', {}); ds = sorted(px)
    z_d = max((d for d in ds if d <= END_DATE), default=None)
    if not z_d: continue
    rec = {'Index': 'S&P BSE Sensex' if name == 'S&P BSE SENSEX' else pretty(name), 'Category': cat, 'NSE name': name, 'Level now': px[z_d], 'As of': z_d}
    longest = None
    for hz, d0 in starts.items():
        a_d = next((d for d in ds if d0.isoformat() <= d <= (d0 + dt.timedelta(days=14)).isoformat()), None)
        if not a_d:
            rec[f'{hz} CAGR %'] = rec[f'{hz} %'] = None; continue
        yrs = (dt.date.fromisoformat(z_d) - dt.date.fromisoformat(a_d)).days / 365.25
        tot = px[z_d] / px[a_d]
        rec[f'{hz} %'] = round((tot - 1) * 100, 1); rec[f'{hz} CAGR %'] = round((tot ** (1 / yrs) - 1) * 100, 1); longest = hz
    first = c.get('first') or (ds[0] if ds else None)
    rec['Data since'] = first
    if first and first in px and first < z_d:
        yrs = (dt.date.fromisoformat(z_d) - dt.date.fromisoformat(first)).days / 365.25
        rec['Since start %'] = round((px[z_d] / px[first] - 1) * 100, 1)
        rec['Since start CAGR %'] = round(((px[z_d] / px[first]) ** (1 / yrs) - 1) * 100, 1) if yrs >= 1 else None
        rec['Since start years'] = round(yrs, 1)
    rec['Longest horizon'] = longest
    rows.append(rec)
R = pd.DataFrame(rows)
cols = ['Index', 'Category'] + [f'{h} CAGR %' for h in HORIZONS] + ['Since start CAGR %', 'Since start years', 'Data since', 'Longest horizon'] + \
       [f'{h} %' for h in HORIZONS] + ['Since start %', 'Level now', 'As of', 'NSE name']
for c_ in cols:
    if c_ not in R: R[c_] = None
R = R[cols].sort_values(['Category', '5Y CAGR %'], ascending=[True, False], na_position='last')
R.to_csv(f'{OUT}/Sector_Returns.csv', index=False)
pd.set_option('display.width', 260); pd.set_option('display.max_rows', 300)
print(R[['Index', 'Category'] + [f'{h} CAGR %' for h in HORIZONS] + ['Since start CAGR %', 'Data since']].to_string(index=False))
