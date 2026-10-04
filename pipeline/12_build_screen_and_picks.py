"""Step 12 - Nifty 500 screen (hard filters + 0-100 score) -> ../Nifty500_Analysis.csv, then picks 120 stocks
(48 Large / 36 Mid / 36 Small, sector-weighted) and deals them into 3 accounts x (20 Active + 20 To Invest) -> ../Suggested_Lists_Backup/Account_Portfolios_20+20.csv.
Re-running this REGENERATES the picks from the current data."""
import pandas as pd, json, numpy as np, collections, os
from common import OUT, ACCOUNTS, ACCOUNT_ID, SUGGESTED
v1 = pd.read_csv('All_NSE_Scrips_Data.csv')
v1['Sym'] = v1['Symbol'].str.replace('NSE:', '', regex=False)
n500 = pd.read_csv('n500.csv')[['Symbol', 'Industry']].rename(columns={'Symbol': 'Sym', 'Industry': 'NSE Sector'})
r2 = pd.DataFrame([d for d in json.load(open('raw2.json')).values() if d]).rename(columns={'Symbol': 'Sym'})
r3 = json.load(open('raw3.json'))
def promo(sym):
    q = r3.get(sym)
    if not q: return (None, None, None)
    vals = [(x['date'], float(x['promoter'])) for x in q if x['promoter'] not in (None, '', '-')]
    if not vals: return (None, None, None)
    latest = vals[0][1]; yr = vals[4][1] if len(vals) > 4 else (vals[-1][1] if len(vals) > 1 else None)
    return (latest, None if yr is None else round(latest - yr, 2), vals[0][0])
pm = pd.DataFrame([(s, *promo(s)) for s in r3], columns=['Sym', 'Promoter %', 'Promoter chg 1y (pp)', 'Holding as of'])
d = n500.merge(v1, on='Sym', how='left').merge(r2, on='Sym', how='left').merge(pm, on='Sym', how='left')
for c in d.columns:
    if c not in ('Sym', 'NSE Sector', 'Symbol', 'Company', 'ISIN', 'Series', 'Sector', 'Industry', 'Cap Class', 'Nifty500', 'recommendationKey', 'Holding as of'):
        d[c] = pd.to_numeric(d[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
for c in ['Ret5y', 'Ret3y', 'Ret1y']:
    if c not in d: d[c] = np.nan
d['Sector'] = d['NSE Sector']
fin = d['Sector'].eq('Financial Services')
pe = d['P/E']; d['PE vs sector'] = (pe / d.groupby('Sector')['P/E'].transform('median')).round(2)
d['Price vs 200DMA %'] = ((d['Price'] / d['twoHundredDayAverage'] - 1) * 100).round(1)
d['Upside to target %'] = ((d['targetMeanPrice'] / d['Price'] - 1) * 100).round(1)
d['FCF Yield %'] = (d['freeCashflow'] / (d['Market Cap (Cr)'] * 1e7) * 100).round(2)
d['Profit yrs'] = d['ProfitYears'].astype(str) + '/' + d['NIYears'].astype(str)

# ------- hard filters (genuineness) -------
d['Reject'] = ''
def rej(mask, why): d.loc[mask & (d['Reject'] == ''), 'Reject'] = why
rej(d['Price'].isna() | (d['Avg Volume'] < 100000), 'illiquid/no data')
rej((d['NIYears'].fillna(0) >= 3) & (d['ProfitYears'].fillna(0) < d['NIYears'].fillna(0) - 1), 'losses in recent years')
rej(d['P/E'].isna(), 'loss-making / no P/E')
rej(d['P/E'] > 90, 'P/E > 90')
rej(d['ROE_avg'].fillna(-99) < 8, 'avg ROE < 8%')
rej(d['Promoter %'].notna() & (d['Promoter %'] < 20) & (d['Promoter chg 1y (pp)'].fillna(0) < -5), 'promoter selling heavily')
rej(~fin & (d['Debt/Equity'] > 150), 'debt/equity > 150')
rej(~fin & d['IntCover'].notna() & (d['IntCover'] < 2), 'interest cover < 2')
rej(~fin & (d['FCF_yrs'].fillna(0) >= 3) & (d['FCF_pos_yrs'].fillna(0) == 0), 'no positive FCF in any year')
rej(d['Cap Class'].isin(['Micro', '']) | d['Cap Class'].isna(), 'micro cap')
rej(d['Cap Class'].eq('Small') & (d['Market Cap (Cr)'] < 3000), 'small cap < 3000 Cr')

# ------- score: percentile ranks (0-1), banks/NBFC scored on a reduced set -------
def pr(s, high=True): return s.rank(pct=True, na_option='keep') if high else (1 - s.rank(pct=True, na_option='keep'))
ok = d['Reject'] == ''
P = d[ok].copy()
comp = pd.DataFrame(index=P.index)
comp['quality'] = pd.concat([pr(P['ROE_avg']), pr(P['ROE_min']), pr(P['operatingMargins']), pr(P['RevCAGR']), pr(P['NICAGR'])], axis=1).mean(axis=1)
comp['safety'] = pd.concat([pr(P['Debt/Equity'], False).where(~fin[P.index]), pr(P['IntCover']).where(~fin[P.index]),
                            pr(P['CashConv'].clip(-1, 3)).where(~fin[P.index]), pr(P['FCF Yield %']).where(~fin[P.index]),
                            pr(P['Promoter %'].clip(upper=75)), pr(P['Promoter chg 1y (pp)']), pr(P['MaxDD3y%']), pr(P['beta'], False)], axis=1).mean(axis=1)
comp['value'] = pd.concat([pr(P['PE vs sector'], False), pr(P['P/B'], False).where(fin[P.index]), pr(P['pegRatio'].where(P['pegRatio'] > 0), False),
                           pr(P['% Below 52W High']) * 0.5 + 0.25], axis=1).mean(axis=1)
payout_ok = (P['payoutRatio'].fillna(0.3) < 0.9).astype(float)
comp['income'] = pd.concat([pr(P['Dividend Yield %'].fillna(0)), pr(P['Div_yrs_paid_5'].fillna(0)), payout_ok, P['Div_growth'].fillna(0)], axis=1).mean(axis=1)
comp['trend'] = pd.concat([pr(P['Ret1y']), pr(P['Ret3y']), (P['Price vs 200DMA %'] > 0).astype(float)], axis=1).mean(axis=1)
P['Score'] = (comp['quality'] * 35 + comp['safety'] * 20 + comp['value'] * 20 + comp['income'] * 10 + comp['trend'] * 15).round(1)
for c in comp: P['S_' + c] = (comp[c] * 100).round(0)
d = d.merge(P[['Sym', 'Score'] + ['S_' + c for c in comp]], on='Sym', how='left')

# ------- selection: 48 L / 36 M / 36 S, spread over sectors -------
W = {'Financial Services': 6, 'Information Technology': 3, 'Healthcare': 3, 'Fast Moving Consumer Goods': 3, 'Automobile and Auto Components': 3,
     'Capital Goods': 3, 'Oil Gas & Consumable Fuels': 2, 'Metals & Mining': 2, 'Chemicals': 2, 'Construction': 2, 'Construction Materials': 2,
     'Consumer Durables': 2, 'Consumer Services': 2, 'Power': 2, 'Telecommunication': 1, 'Realty': 1, 'Textiles': 1, 'Services': 1,
     'Media Entertainment & Publication': 1, 'Diversified': 1, 'Forest Materials': 1}
pool = d[d['Score'].notna()]
picked = []
for c, q in {'Large': 48, 'Mid': 36, 'Small': 36}.items():
    p = pool[pool['Cap Class'] == c]; cnt = collections.Counter()
    for _ in range(q):
        avail = [(cnt[s] / w, s) for s, w in W.items() if not p[(p['Sector'] == s) & ~p['Sym'].isin(picked)].empty]
        if not avail: break
        sec = min(avail)[1]
        picked.append(p[(p['Sector'] == sec) & ~p['Sym'].isin(picked)].sort_values('Score', ascending=False).iloc[0]['Sym']); cnt[sec] += 1
sel = d[d['Sym'].isin(picked)].copy()
LISTS = [(a, k) for a in ACCOUNTS.values() for k in ('Active (20)', 'To Invest (20)')]
names = [f'{a} | {k}' for a, k in LISTS]
CAPN = {'Large': 8, 'Mid': 6, 'Small': 6}
cs = {n: collections.Counter() for n in names}; cc = {n: collections.Counter() for n in names}; ts = {n: 0.0 for n in names}
order = sel.assign(sc=sel.groupby('Sector')['Sym'].transform('count')).sort_values(['sc', 'Sector', 'Score'], ascending=[False, True, False])
sel['List'] = ''
for idx, r in order.iterrows():
    opts = [n for n in names if cc[n][r['Cap Class']] < CAPN[r['Cap Class']]]
    n = min(opts, key=lambda n: (cs[n][r['Sector']], ts[n]))      # fewest of that sector, then lowest total score (balances quality)
    sel.loc[idx, 'List'] = n; cs[n][r['Sector']] += 1; cc[n][r['Cap Class']] += 1; ts[n] += r['Score']
sel['Account'] = sel['List'].str.split(' \\| ').str[0]; sel['Bucket'] = sel['List'].str.split(' \\| ').str[1]
d['Selected'] = d['Sym'].isin(picked).map({True: 'Y', False: ''})
cols = ['Symbol', 'Company', 'Sector', 'Industry', 'Cap Class', 'Market Cap (Cr)', 'Price', '52W High', '52W Low', '% Below 52W High', 'P/E', 'PE vs sector', 'P/B',
        'forwardPE', 'pegRatio', 'enterpriseToEbitda', 'FCF Yield %', 'Dividend/Share (annual)', 'Dividend Yield %', 'Div_5y_avg', 'Div_yrs_paid_5', 'payoutRatio',
        'ROE %', 'ROE_avg', 'ROE_min', 'returnOnAssets', 'operatingMargins', 'profitMargins', 'RevCAGR', 'NICAGR', 'Profit yrs', 'Debt/Equity', 'IntCover', 'CashConv',
        'Promoter %', 'Promoter chg 1y (pp)', 'heldPercentInstitutions', 'Ret1y', 'Ret3y', 'Ret5y', 'Vol%', 'MaxDD3y%', 'Price vs 200DMA %', 'Upside to target %',
        'recommendationKey', 'beta', 'Score', 'S_quality', 'S_safety', 'S_value', 'S_income', 'S_trend', 'Reject']
ren = {'forwardPE': 'Forward P/E', 'pegRatio': 'PEG', 'enterpriseToEbitda': 'EV/EBITDA', 'payoutRatio': 'Payout Ratio', 'Div_5y_avg': 'Avg Annual Div (5y)',
       'Div_yrs_paid_5': 'Div Years Paid (of 5)', 'ROE %': 'ROE % (latest)', 'ROE_avg': 'ROE % (avg 4y)', 'ROE_min': 'ROE % (worst yr)', 'returnOnAssets': 'ROA',
       'operatingMargins': 'Operating Margin', 'profitMargins': 'Net Margin', 'RevCAGR': 'Revenue CAGR %', 'NICAGR': 'Profit CAGR %', 'IntCover': 'Interest Cover',
       'CashConv': 'Cash Conversion (OCF/NI)', 'heldPercentInstitutions': 'Institutional Held', 'Ret1y': 'Return 1y %', 'Ret3y': 'Return 3y %', 'Ret5y': 'Return 5y %',
       'Vol%': 'Volatility %', 'MaxDD3y%': 'Max Drawdown 3y %', 'recommendationKey': 'Analyst View', 'beta': 'Beta', 'S_quality': 'Quality (0-100)',
       'S_safety': 'Safety (0-100)', 'S_value': 'Value (0-100)', 'S_income': 'Income (0-100)', 'S_trend': 'Trend (0-100)', 'Reject': 'Filtered Out Because'}
full = d[cols + ['Selected']].rename(columns=ren)
for c in ['ROA', 'Operating Margin', 'Net Margin', 'Payout Ratio', 'Institutional Held']: full[c] = (full[c] * 100).round(1)
full.sort_values(['Score'], ascending=False).to_csv(f'{OUT}/Nifty500_Analysis.csv', index=False)
keep = ['Account', 'Bucket'] + cols[:3] + ['Cap Class', 'Market Cap (Cr)', 'Price', '52W High', '52W Low', 'P/E', 'PE vs sector', 'Dividend/Share (annual)', 'Dividend Yield %',
        'ROE_avg', 'RevCAGR', 'NICAGR', 'Debt/Equity', 'Promoter %', 'Promoter chg 1y (pp)', 'Ret1y', 'Ret3y', 'Score']
res = sel[keep].rename(columns=ren).sort_values(['Account', 'Bucket', 'Cap Class', 'Sector'], key=lambda c: c.map(ACCOUNT_ID) if c.name == 'Account' else c)
res = res.drop(columns=['Industry'], errors='ignore')
res.to_csv(f'{SUGGESTED}/Account_Portfolios_20+20.csv', index=False)
print('rejected breakdown:'); print(d[d['Reject'] != '']['Reject'].value_counts())
print('pool by cap', pool['Cap Class'].value_counts().to_dict(), 'picked', len(res))
print(res.groupby(['Account', 'Bucket', 'Cap Class']).size().unstack())
print(res.groupby(['Account', 'Bucket'])['Sector'].nunique().unstack(), res.groupby('Account')['Sector'].nunique().to_dict())
print(res.groupby(['Account', 'Bucket'])['Score'].mean().round(1).unstack())
