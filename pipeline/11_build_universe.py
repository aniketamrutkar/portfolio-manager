"""Step 11 - unified universe -> ../All_Scrips_NSE_BSE.csv: NSE equities (with BSE codes) + BSE-only equities + ETFs + REIT/InvIT + SGB + G-Sec + BSE-only ETFs."""
import pandas as pd, json, numpy as np, os
from common import OUT
num = lambda s: pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan)
ymap = {'Financial Services': 'Financial Services', 'Technology': 'Information Technology', 'Healthcare': 'Healthcare',
        'Consumer Defensive': 'Fast Moving Consumer Goods', 'Consumer Cyclical': 'Consumer Discretionary', 'Industrials': 'Capital Goods',
        'Energy': 'Oil Gas & Consumable Fuels', 'Basic Materials': 'Materials', 'Utilities': 'Power', 'Real Estate': 'Realty',
        'Communication Services': 'Media Entertainment & Telecom'}

# ---- bhavcopies (price/turnover for everything) ----
nb = pd.read_csv('nse_bhav.csv', skipinitialspace=True); nb.columns = [c.strip() for c in nb.columns]
nb['SERIES'] = nb['SERIES'].str.strip(); nb['SYMBOL'] = nb['SYMBOL'].str.strip()
nb = nb.set_index('SYMBOL')
bse = pd.read_csv('bse_all.csv'); bse_by_isin = bse.drop_duplicates('ISIN').set_index('ISIN')
bhav_b = pd.read_csv('bse_bhav.csv')
eq = pd.read_csv('EQUITY_L.csv'); eq.columns = [c.strip() for c in eq.columns]
nse_isins = set(eq['ISIN NUMBER'])

# ---- 1. NSE equities (rebuilt from raw.json so refetched rows are included) ----
raw = json.load(open('raw.json')); n500 = pd.read_csv('n500.csv')
rows = []
for s, d in raw.items():
    if d: d = dict(d); d['Sym'] = s; rows.append(d)
f = pd.DataFrame(rows)
base = eq.rename(columns={'SYMBOL': 'Sym', 'NAME OF COMPANY': 'Company', 'ISIN NUMBER': 'ISIN', 'SERIES': 'Series'})[['Sym', 'Company', 'Series', 'ISIN']]
extra = n500[~n500['Symbol'].isin(base['Sym'])].rename(columns={'Symbol': 'Sym', 'Company Name': 'Company', 'ISIN Code': 'ISIN'})[['Sym', 'Company', 'ISIN']]
extra['Series'] = 'EQ'
base = pd.concat([base, extra], ignore_index=True); base['Series'] = base['Series'].str.strip()
nse = base.merge(f, on='Sym', how='left').merge(n500[['Symbol', 'Industry']].rename(columns={'Symbol': 'Sym', 'Industry': 'NSE Sector'}), on='Sym', how='left')
for c in ['marketCap', 'trailingPE', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'dividendRate', 'dividendYield', 'trailingAnnualDividendRate', 'currentPrice',
          'regularMarketPrice', 'averageVolume', 'priceToBook', 'returnOnEquity', 'debtToEquity']: nse[c] = num(nse[c])
nse['Price'] = nse['currentPrice'].fillna(nse['regularMarketPrice'])
nse['Price'] = nse['Price'].fillna(nse['Sym'].map(nb['CLOSE_PRICE'].pipe(num)))                 # bhavcopy fallback
nse['MCap'] = (nse['marketCap'] / 1e7).round(0)
nse = nse.sort_values('MCap', ascending=False).reset_index(drop=True)
nse['rank'] = nse['MCap'].where(nse['MCap'].notna()).rank(ascending=False, method='first')
cut = {k: nse.loc[nse['rank'] == k, 'MCap'].iloc[0] for k in (100, 250, 500)}
def cap_by_mcap(m):
    if pd.isna(m): return ''
    return 'Large' if m >= cut[100] else 'Mid' if m >= cut[250] else 'Small' if m >= cut[500] else 'Micro'
nse['Cap'] = nse['MCap'].map(cap_by_mcap)
nse['SectorFinal'] = nse['NSE Sector'].fillna(nse['sector'].map(ymap)).fillna('Unclassified')

def frame(df, itype, exch, **k):
    o = pd.DataFrame({'Instrument Type': itype, 'Exchange': exch}, index=df.index)
    for a, b in k.items(): o[a] = b
    return o
u1 = pd.DataFrame({
    'Symbol': nse['Sym'], 'Company': nse['Company'], 'Instrument Type': 'Equity', 'Exchange': 'NSE', 'ISIN': nse['ISIN'], 'Series': nse['Series'],
    'Sector': nse['SectorFinal'], 'Industry': nse['industry'], 'Cap Class': nse['Cap'], 'Market Cap (Cr)': nse['MCap'], 'Price': nse['Price'].round(2),
    'P/E': num(nse['trailingPE']).where(nse['trailingPE'] > 0).round(1), 'P/B': nse['priceToBook'].round(2), '52W High': nse['fiftyTwoWeekHigh'].round(2),
    '52W Low': nse['fiftyTwoWeekLow'].round(2), 'Dividend/Share (annual)': nse['dividendRate'].fillna(nse['trailingAnnualDividendRate']).round(2),
    'Dividend Yield %': nse['dividendYield'].round(2), 'ROE %': (nse['returnOnEquity'] * 100).round(1), 'Debt/Equity': nse['debtToEquity'].round(1),
    'Avg Volume': nse['averageVolume'], 'Nifty500': nse['NSE Sector'].notna().map({True: 'Y', False: ''})})
u1['BSE Code'] = nse['ISIN'].map(bse_by_isin['FinInstrmId']).astype('Int64')
u1['Exchange'] = np.where(u1['BSE Code'].notna(), 'NSE+BSE', 'NSE')
u1['Turnover Last Day (Lakh)'] = nse['Sym'].map(nb['TURNOVER_LACS'].pipe(num)).round(1)

# ---- 2. BSE-only equities ----
bo = pd.read_csv('bse_only.csv'); bo['TckrSymb'] = bo['TckrSymb'].astype(str).str.strip()
rb = json.load(open('raw_bse2.json')) if os.path.exists('raw_bse2.json') else {}
rbf = pd.DataFrame([dict(v, Sym=s) for s, v in rb.items() if v])
bo = bo[~bo['SctySrs'].isin(['F', 'E'])].merge(rbf, left_on='TckrSymb', right_on='Sym', how='left')
for c in ['marketCap', 'trailingPE', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'dividendRate', 'dividendYield', 'trailingAnnualDividendRate', 'priceToBook',
          'returnOnEquity', 'debtToEquity', 'averageVolume']:
    bo[c] = num(bo[c]) if c in bo else np.nan
bo['MCap'] = (bo['marketCap'] / 1e7).round(0)
u2 = pd.DataFrame({
    'Symbol': bo['TckrSymb'], 'Company': bo['FinInstrmNm'], 'Instrument Type': np.where(bo['SctySrs'].isin(['M', 'MT', 'MS']), 'Equity (SME)', 'Equity'),
    'Exchange': 'BSE', 'BSE Code': bo['FinInstrmId'], 'ISIN': bo['ISIN'], 'Series': bo['SctySrs'], 'Sector': bo['sector'].map(ymap).fillna(bo['sector']).fillna('Unclassified'),
    'Industry': bo['industry'], 'Cap Class': bo['MCap'].map(cap_by_mcap), 'Market Cap (Cr)': bo['MCap'], 'Price': bo['ClsPric'].round(2),
    'P/E': bo['trailingPE'].where(bo['trailingPE'] > 0).round(1), 'P/B': bo['priceToBook'].round(2), '52W High': bo['fiftyTwoWeekHigh'].round(2),
    '52W Low': bo['fiftyTwoWeekLow'].round(2), 'Dividend/Share (annual)': bo['dividendRate'].fillna(bo['trailingAnnualDividendRate']).round(2),
    'Dividend Yield %': bo['dividendYield'].round(2), 'ROE %': (bo['returnOnEquity'] * 100).round(1), 'Debt/Equity': bo['debtToEquity'].round(1),
    'Avg Volume': bo['averageVolume'], 'Turnover Last Day (Lakh)': (bo['TtlTrfVal'] / 1e5).round(1), 'Nifty500': ''})

# ---- 3. ETFs, REIT, InvIT (NSE) ----
etf = pd.read_csv('etf.csv'); etf.columns = [c.strip() for c in etf.columns]
ro = {k: v for k, v in json.load(open('raw_other.json')).items() if v} if os.path.exists('raw_other.json') else {}
def other_row(sym, itype, name, isin, series, under, cat):
    d = ro.get(sym, {}); p = nb['CLOSE_PRICE'].get(sym); p = float(p) if p is not None and str(p).strip() not in ('', '-') else np.nan
    pr = num(pd.Series([d.get('currentPrice') or d.get('regularMarketPrice')])).iloc[0]
    return {'Symbol': sym, 'Company': name, 'Instrument Type': itype, 'Exchange': 'NSE', 'ISIN': isin, 'Series': series, 'Sector': cat, 'Industry': under,
            'Market Cap (Cr)': round(d['marketCap'] / 1e7) if d.get('marketCap') else (round(d['totalAssets'] / 1e7) if d.get('totalAssets') else None),
            'Price': round(pr if not np.isnan(pr) else p, 2), '52W High': d.get('fiftyTwoWeekHigh'), '52W Low': d.get('fiftyTwoWeekLow'),
            'P/E': d.get('trailingPE'), 'P/B': d.get('priceToBook'), 'Dividend Yield %': d.get('dividendYield') if itype != 'ETF' else d.get('yield'),
            'Dividend/Share (annual)': d.get('dividendRate'), 'Avg Volume': d.get('averageVolume'), 'Return 1y %': d.get('Ret1y'), 'Return 3y %': d.get('Ret3y'),
            'Return 5y %': d.get('Ret5y'), 'Volatility %': d.get('Vol%'), 'Max Drawdown 3y %': d.get('MaxDD3y%'), 'AUM (Cr)': round(d['totalAssets'] / 1e7) if d.get('totalAssets') else None,
            'Expense Ratio %': d.get('annualReportExpenseRatio'), 'Turnover Last Day (Lakh)': nb['TURNOVER_LACS'].get(sym)}
rows = []
for _, r in etf.iterrows():
    sym = r['Symbol'].strip(); und = str(r['Underlying Asset']); kind = str(r['ETF Underlying'])
    cap = 'Large' if 'Nifty 50' in und or 'Sensex' in und or 'Nifty 100' in und or 'Top 10' in und or 'Bank' in und else 'Mid' if 'Midcap' in und else 'Small' if 'Smallcap' in und else ''
    o = other_row(sym, 'ETF', r['SecurityName'], r['ISINNumber'], 'EQ', und, 'ETF · ' + kind.title()); o['Cap Class'] = cap if kind.upper() == 'EQUITY' else ''; rows.append(o)
for sym in nb[nb['SERIES'].isin(['IV', 'RR'])].index:
    t = 'REIT' if nb.loc[sym, 'SERIES'] == 'RR' else 'InvIT'
    rows.append(other_row(sym, t, sym, '', nb.loc[sym, 'SERIES'], t, 'Real Estate' if t == 'REIT' else 'Infrastructure'))
u3 = pd.DataFrame(rows)
# REITs/InvITs that are also in the Nifty 500 already exist as equity rows: keep one row, typed REIT/InvIT, with the return stats
dup = u3['Symbol'].isin(u1['Symbol'])
for _, r in u3[dup].iterrows():
    m = u1['Symbol'] == r['Symbol']
    u1.loc[m, 'Instrument Type'] = r['Instrument Type']
    for c in ['Return 1y %', 'Return 3y %', 'Return 5y %', 'Volatility %', 'Max Drawdown 3y %']:
        if c not in u1: u1[c] = np.nan
        u1.loc[m, c] = r[c]
u3 = u3[~dup]
# ---- 4. SGB and G-Secs (price only) ----
def debt(series_list, itype, cat):
    x = nb[nb['SERIES'].isin(series_list)]
    return pd.DataFrame({'Symbol': x.index, 'Company': x.index, 'Instrument Type': itype, 'Exchange': 'NSE', 'Series': x['SERIES'], 'Sector': cat,
                         'Price': num(x['CLOSE_PRICE']).values, '52W High': np.nan, 'Avg Volume': num(x['TTL_TRD_QNTY']).values, 'Turnover Last Day (Lakh)': num(x['TURNOVER_LACS']).values})
u4 = pd.concat([debt(['GB'], 'SGB', 'Gold'), debt(['GS'], 'G-Sec', 'Government Debt')], ignore_index=True)
# ---- 5. BSE-only ETFs / funds ----
bx = bhav_b[bhav_b['SctySrs'].eq('F') & bhav_b['ISIN'].astype(str).str.startswith('INF') & ~bhav_b['ISIN'].isin(set(etf['ISINNumber']))]
u5 = pd.DataFrame({'Symbol': bx['TckrSymb'].astype(str).str.strip(), 'Company': bx['FinInstrmNm'], 'Instrument Type': 'ETF/Fund (BSE)', 'Exchange': 'BSE', 'BSE Code': bx['FinInstrmId'],
                   'ISIN': bx['ISIN'], 'Series': 'F', 'Sector': 'ETF/Fund', 'Price': bx['ClsPric'].round(2), 'Turnover Last Day (Lakh)': (bx['TtlTrfVal'] / 1e5).round(1)})

U = pd.concat([u1, u2, u3, u4, u5], ignore_index=True)
U['% Below 52W High'] = ((1 - num(U['Price']) / num(U['52W High'])) * 100).round(1)
order = ['Symbol', 'Company', 'Instrument Type', 'Exchange', 'BSE Code', 'ISIN', 'Series', 'Sector', 'Industry', 'Cap Class', 'Market Cap (Cr)', 'AUM (Cr)', 'Price', 'P/E', 'P/B',
         '52W High', '52W Low', '% Below 52W High', 'Dividend/Share (annual)', 'Dividend Yield %', 'ROE %', 'Debt/Equity', 'Expense Ratio %', 'Return 1y %', 'Return 3y %',
         'Return 5y %', 'Volatility %', 'Max Drawdown 3y %', 'Avg Volume', 'Turnover Last Day (Lakh)', 'Nifty500']
for c in order:
    if c not in U: U[c] = np.nan
U = U[order]
U['Symbol'] = np.where(U['Exchange'].isin(['BSE']), 'BSE:' + U['Symbol'].astype(str), 'NSE:' + U['Symbol'].astype(str))
U.to_csv(f'{OUT}/All_Scrips_NSE_BSE.csv', index=False)
print(U.groupby(['Instrument Type', 'Exchange']).size())
print('total', len(U), '| with price', U['Price'].notna().sum())
print('BSE-only by cap:', U[U['Exchange'].eq('BSE') & U['Instrument Type'].str.startswith('Equity')]['Cap Class'].value_counts().to_dict())
print('cap cutoffs (Cr):', cut)
