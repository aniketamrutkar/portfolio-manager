"""Step 18 - embed universe + deep-dive fields + current lists into portfolio_template.html -> ../Portfolio_Manager.html.
Open the result with #selftest appended to the URL to run the built-in checks."""
import pandas as pd, numpy as np, json, os, datetime
from common import OUT as B, HERE, load_json, ACCOUNTS, ACCOUNT_ID, SUGGESTED, START_EMPTY
u = pd.read_csv(f'{B}/All_Scrips_NSE_BSE.csv', dtype={'BSE Code': str})
if os.path.exists(f'{B}/Returns_Nifty500.csv'):        # consistent 1/2/3/4/5Y returns (step 17) override the older per-stock fields
    _r = pd.read_csv(f'{B}/Returns_Nifty500.csv').set_index('Symbol')
    for src, dst in (('1Y %', 'Return 1y %'), ('2Y %', 'Return 2y %'), ('3Y %', 'Return 3y %'), ('4Y %', 'Return 4y %'), ('5Y %', 'Return 5y %')):
        if src not in _r: continue
        m = u.Symbol.isin(_r.index); u.loc[m, dst] = u.loc[m, 'Symbol'].map(_r[src])
n = pd.read_csv(f'{B}/Nifty500_Analysis.csv')

EXTRA = ['Score', 'Quality (0-100)', 'Safety (0-100)', 'Value (0-100)', 'Income (0-100)', 'Trend (0-100)', 'ROE % (avg 4y)', 'Revenue CAGR %',
         'Profit CAGR %', 'PE vs sector', 'Forward P/E', 'PEG', 'EV/EBITDA', 'FCF Yield %', 'Payout Ratio', 'Interest Cover', 'Operating Margin',
         'Net Margin', 'Promoter %', 'Promoter chg 1y (pp)', 'Price vs 200DMA %', 'Upside to target %', 'Analyst View', 'Filtered Out Because']
FILL = ['Return 1y %', 'Return 3y %', 'Return 5y %', 'Volatility %', 'Max Drawdown 3y %']     # equities have these only in the deep-dive
m = n[['Symbol'] + EXTRA + FILL].rename(columns={c: c + '__n' for c in FILL})
u = u.merge(m, on='Symbol', how='left')
for c in FILL: u[c] = u[c].fillna(u[c + '__n']); u = u.drop(columns=c + '__n')
assert u['Symbol'].is_unique, u[u['Symbol'].duplicated()]['Symbol'].tolist()[:10]

CAT = {'Instrument Type', 'Exchange', 'Series', 'Sector', 'Cap Class', 'Nifty500', 'Analyst View', 'Filtered Out Because'}
TEXT = {'Symbol', 'Company', 'BSE Code', 'ISIN', 'Industry'}
DEC0 = {'Market Cap (Cr)', 'AUM (Cr)', 'Avg Volume', 'Score', 'Quality (0-100)', 'Safety (0-100)', 'Value (0-100)', 'Income (0-100)', 'Trend (0-100)'}
GROUP = {**{c: 'Identity' for c in ['Symbol', 'Company', 'Instrument Type', 'Exchange', 'BSE Code', 'ISIN', 'Series', 'Sector', 'Industry', 'Cap Class', 'Nifty500']},
         **{c: 'Valuation' for c in ['Market Cap (Cr)', 'AUM (Cr)', 'Price', 'P/E', 'P/B', 'PE vs sector', 'Forward P/E', 'PEG', 'EV/EBITDA', 'FCF Yield %']},
         **{c: 'Price & returns' for c in ['52W High', '52W Low', '% Below 52W High', 'Return 1y %', 'Return 2y %', 'Return 3y %', 'Return 4y %', 'Return 5y %', 'Volatility %',
                                            'Max Drawdown 3y %', 'Price vs 200DMA %', 'Upside to target %', 'Avg Volume', 'Turnover Last Day (Lakh)']},
         **{c: 'Dividends' for c in ['Dividend/Share (annual)', 'Dividend Yield %', 'Payout Ratio', 'Expense Ratio %']},
         **{c: 'Quality & growth' for c in ['ROE %', 'ROE % (avg 4y)', 'Revenue CAGR %', 'Profit CAGR %', 'Debt/Equity', 'Interest Cover', 'Operating Margin',
                                             'Net Margin', 'Promoter %', 'Promoter chg 1y (pp)', 'Analyst View']},
         **{c: 'Screen score' for c in ['Score', 'Quality (0-100)', 'Safety (0-100)', 'Value (0-100)', 'Income (0-100)', 'Trend (0-100)', 'Filtered Out Because']}}
order = [c for g in ['Identity', 'Valuation', 'Price & returns', 'Dividends', 'Quality & growth', 'Screen score'] for c in GROUP if GROUP[c] == g]
missing = set(u.columns) - set(order); assert not missing, missing
u = u[order]
cols = [{'k': c, 't': 'cat' if c in CAT else 'text' if c in TEXT else 'num', 'd': 0 if c in DEC0 else 2, 'g': GROUP[c]} for c in order]

def clean(v):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))): return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating, float)): f = round(float(v), 2); return int(f) if f.is_integer() and abs(f) > 1e6 else f
    return v
rows = [[clean(v) for v in r] for r in u.itertuples(index=False, name=None)]

assign = {}
a = pd.read_csv(f'{SUGGESTED}/Account_Portfolios_20+20.csv')
for r in a.itertuples():
    assign[r.Symbol] = {'a': ACCOUNT_ID[r.Account], 'l': 'Active' if r.Bucket.startswith('Active') else 'To Invest'}
e = pd.read_csv(f'{SUGGESTED}/ETF_SGB_Per_Account.csv')
for r in e.itertuples():
    assert r.Symbol not in assign; assign[r.Symbol] = {'a': ACCOUNT_ID[r.Account], 'l': 'ETF / SGB'}
known = set(u['Symbol']); bad = [s for s in assign if s not in known]; assert not bad, bad

# ---- multi-horizon backtest (step 14) - optional: the Backtest tab is hidden if its files are missing ----
bt = None
if all(os.path.exists(f'{B}/{f}') for f in ('Backtest_Holdings.csv', 'Backtest_Summary.csv', 'Backtest_Daily.csv')):
    src = open(os.path.join(HERE, '14_backtest.py')).read()
    consts = {}; exec(src[src.index('END_DATE, PER_HOLDING'):src.index('BENCH = ')], consts)      # scenario constants only
    tbl = lambda df: {'cols': list(df.columns), 'rows': [[clean(v) for v in r] for r in df.itertuples(index=False, name=None)]}
    bh, bs, bd = (pd.read_csv(f'{B}/{f}') for f in ('Backtest_Holdings.csv', 'Backtest_Summary.csv', 'Backtest_Daily.csv'))
    bt = {'perHolding': consts['PER_HOLDING'], 'horizons': list(consts['HORIZONS']), 'holdings': tbl(bh), 'summary': tbl(bs), 'daily': tbl(bd)}
    print(f'backtest embedded: {len(bh)} holding-rows, {len(bs)} summary rows, {len(bd)} daily rows')

# ---- sector / index returns (step 15) - optional: the Sectors tab is hidden if the file is missing ----
sec = None
if os.path.exists(f'{B}/Sector_Returns.csv'):
    sr = pd.read_csv(f'{B}/Sector_Returns.csv')
    sec = {'cols': list(sr.columns), 'rows': [[clean(v) for v in r] for r in sr.itertuples(index=False, name=None)]}
    print(f'sector returns embedded: {len(sr)} indices')

# ---- focus-sector picks (step 16) - optional ----
picks = None
if os.path.exists(f'{B}/Sector_Picks.csv'):
    sp = pd.read_csv(f'{B}/Sector_Picks.csv')
    picks = {'cols': list(sp.columns), 'rows': [[clean(v) for v in r] for r in sp.itertuples(index=False, name=None)]}
    print(f'sector picks embedded: {len(sp)} stocks')

# ---- ratio cheat sheet (../Ratio_Cheat_Sheet.html, hand-written) - optional: the tab is hidden if the file is missing ----
cheat = None
if os.path.exists(f'{B}/Ratio_Cheat_Sheet.html'):
    import re
    src = open(f'{B}/Ratio_Cheat_Sheet.html', encoding='utf-8').read()
    css = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
    body = re.search(r'<main>(.*?)</main>', src, re.S).group(1)
    # rendered inside a shadow root: :root -> :host, theme attribute is mirrored onto the host element
    css = (css.replace(':root:not([data-theme="light"])', ':host(:not([data-theme="light"]))')
              .replace(':root[data-theme="dark"]', ':host([data-theme="dark"])')
              .replace(':root', ':host')
              .replace('body{', ':host{display:block;')
              .replace('main{max-width:1280px;margin:0 auto;padding:18px 16px 32px}', 'main{max-width:1280px;margin:0 auto}'))
    cheat = {'css': css, 'html': body}
    print('cheat sheet embedded')

# ---- v3 sector top-10 (step 17) - optional ----
top10 = None
if os.path.exists(f'{B}/Sector_Top10_v3.csv'):
    t10 = pd.read_csv(f'{B}/Sector_Top10_v3.csv')
    t10 = t10[[c for c in t10.columns if not c.startswith('pt: ')]]
    top10 = {'cols': list(t10.columns), 'rows': [[clean(v) for v in r] for r in t10.itertuples(index=False, name=None)]}
    print(f'sector top-10 (v3) embedded: {len(t10)} rows')

n100 = None
if os.path.exists(f'{B}/Nifty100_v3.csv'):
    nd = pd.read_csv(f'{B}/Nifty100_v3.csv')
    n100 = {'cols': list(nd.columns), 'rows': [[clean(v) for v in r] for r in nd.itertuples(index=False, name=None)]}
    print(f'nifty 100 (v3) embedded: {len(nd)} stocks')

v3all = None
if os.path.exists(f'{B}/Score_v3_Nifty500.csv'):   # full v3 detail (incl. per-parameter grades) for the Compare tab
    va = pd.read_csv(f'{B}/Score_v3_Nifty500.csv')
    v3all = {'cols': list(va.columns), 'rows': [[clean(v) for v in r] for r in va.itertuples(index=False, name=None)]}
    print(f'v3 detail embedded: {len(va)} stocks')

# original suggestions are kept as 'suggested' (self-test fixture / future old-lists tab); the app's starting lists are assign0
data = {'suggested': assign, 'baseline': 'clean-2026-10-04' if START_EMPTY else 'suggested', 'v3all': v3all, 'n100': n100, 'top10': top10, 'cheat': cheat, 'picks': picks, 'sec': sec, 'bt': bt, 'accounts': ACCOUNTS, 'cols': cols, 'rows': rows, 'assign0': {} if START_EMPTY else assign, 'asOf': datetime.date.fromisoformat(load_json('inputs_meta.json').get('nse_bhav_date', '2026-10-01')).strftime('%d %b %Y').lstrip('0'), 'built': datetime.date.today().isoformat()}
blob = json.dumps(data, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')
html = open(os.path.join(HERE, 'portfolio_template.html'), encoding='utf-8').read().replace('/*DATA*/', blob)
out = f'{B}/Portfolio_Manager.html'
open(out, 'w', encoding='utf-8').write(html)
print(f'{out}: {len(rows)} scrips, {len(cols)} columns, {len(assign)} assigned, {os.path.getsize(out)/1e6:.2f} MB')
