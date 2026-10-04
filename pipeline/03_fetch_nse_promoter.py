"""Step 03 - promoter holding % (last 6 quarterly filings) for Nifty 500 from NSE's shareholding API. -> raw3.json  (resumable)
NSE's /api/* needs session cookies: visit the homepage + the filings page first, and re-create the session on errors."""
import json, time
import pandas as pd, requests
from common import UA, load_json

H = dict(UA, Referer='https://www.nseindia.com/')
URL = 'https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol={}'


def session():
    s = requests.Session()
    s.get('https://www.nseindia.com', headers=H, timeout=20)
    s.get('https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern', headers=H, timeout=20)
    return s


syms = pd.read_csv('n500.csv')['Symbol'].tolist()
out = load_json('raw3.json')
todo = [x for x in syms if not out.get(x)]
print(f'nse-promoter: {len(syms) - len(todo)} done, {len(todo)} to fetch', flush=True)
s = session()
for n, sym in enumerate(todo):
    for attempt in range(3):
        try:
            r = s.get(URL.format(requests.utils.quote(sym)), headers=H, timeout=20)
            if r.status_code != 200: raise RuntimeError(r.status_code)
            out[sym] = [{'date': x['date'], 'promoter': x.get('pr_and_prgrp'), 'xbrl': x.get('xbrl'), 'rid': x.get('recordId')} for x in r.json()[:6]]
            break
        except Exception:
            time.sleep(3); s = session()
    else:
        out[sym] = None
    if n % 25 == 0:
        print(f'nse-promoter: {n}/{len(todo)}', flush=True); json.dump(out, open('raw3.json', 'w'))
    time.sleep(0.4)                                   # be polite to NSE
json.dump(out, open('raw3.json', 'w'))
print('nse-promoter: done,', sum(1 for x in syms if out.get(x)), '/', len(syms), 'valid')
