"""Step 00 - download exchange master lists + the latest NSE and BSE bhavcopies (no login needed).
Writes (in pipeline/): EQUITY_L.csv, n500.csv, etf.csv, nse_bhav.csv, bse_bhav.csv, bse_all.csv, bse_only.csv, inputs_meta.json"""
import datetime as dt, json, sys
import pandas as pd, requests
from common import UA

NSE = {'EQUITY_L.csv': 'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv',            # all NSE equities
       'n500.csv': 'https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv',         # Nifty 500 + NSE sector
       'etf.csv': 'https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv',           # NSE ETF master
       'nifty100.csv': 'https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv'}      # Nifty 100 members (step 17)
s = requests.Session()
for name, url in NSE.items():
    r = s.get(url, headers=UA, timeout=60)
    if r.status_code != 200 or len(r.content) < 5000: sys.exit(f'failed {url}: HTTP {r.status_code}')
    open(name, 'wb').write(r.content); print('ok', name, len(r.content))

def latest(fmt, min_bytes, sess, headers, days=12):
    """Walk back from today to the newest trading day whose file is complete (holidays give tiny stub files)."""
    d = dt.date.today()
    for i in range(days):
        x = d - dt.timedelta(days=i)
        if x.weekday() > 4: continue
        r = sess.get(fmt(x), headers=headers, timeout=60)
        if r.status_code == 200 and len(r.content) >= min_bytes: return x, r.content
    sys.exit('no complete bhavcopy found in the last %d days for %s' % (days, fmt(d)))

# NSE full bhavcopy: every non-F&O series (EQ, BE, SM, GB=SGB, GS=G-Sec, RR=REIT, IV=InvIT ...)
nd, data = latest(lambda x: f'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{x:%d%m%Y}.csv', 200_000, s, UA)
open('nse_bhav.csv', 'wb').write(data); print('ok nse_bhav.csv for', nd)

# BSE bhavcopy: their JSON API is blocked (403) for scripts, but the daily file works after visiting the homepage
b = requests.Session(); b.get('https://www.bseindia.com/', headers={'User-Agent': UA['User-Agent']}, timeout=30)
bh = dict(UA, Referer='https://www.bseindia.com/', Origin='https://www.bseindia.com')
bd, data = latest(lambda x: f'https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{x:%Y%m%d}_F_0000.CSV', 200_000, b, bh)
open('bse_bhav.csv', 'wb').write(data); print('ok bse_bhav.csv for', bd)

# BSE equities not listed on NSE (ISIN chars 8-9 == "01" marks equity shares)
bse = pd.read_csv('bse_bhav.csv')
eq = pd.read_csv('EQUITY_L.csv'); eq.columns = [c.strip() for c in eq.columns]
bse = bse[bse['FinInstrmTp'].eq('STK') & bse['ISIN'].astype(str).str[7:9].eq('01')].copy()
bse['OnNSE'] = bse['ISIN'].isin(eq['ISIN NUMBER'])
bse[['FinInstrmId', 'TckrSymb', 'FinInstrmNm', 'ISIN', 'SctySrs', 'ClsPric', 'TtlTradgVol', 'TtlTrfVal', 'OnNSE']].to_csv('bse_all.csv', index=False)
bse[~bse['OnNSE']].to_csv('bse_only.csv', index=False)
print(f'BSE equities {len(bse)}, BSE-only {int((~bse.OnNSE).sum())}')

json.dump({'nse_bhav_date': nd.isoformat(), 'bse_bhav_date': bd.isoformat(), 'downloaded': dt.date.today().isoformat()},
          open('inputs_meta.json', 'w'), indent=1)
