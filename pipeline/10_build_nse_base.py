"""Step 10 - flatten raw.json + EQUITY_L + Nifty 500 sectors into pipeline/All_NSE_Scrips_Data.csv (intermediate used by step 12).
Cap class = rank by market cap: 1-100 Large, 101-250 Mid, 251-500 Small, rest Micro (SEBI/AMFI-style, computed - not the official AMFI list)."""
import pandas as pd, json, numpy as np
from common import OUT
eq = pd.read_csv('EQUITY_L.csv'); eq.columns = [c.strip() for c in eq.columns]
eq = eq.rename(columns={'SYMBOL': 'Symbol', 'NAME OF COMPANY': 'Company', 'ISIN NUMBER': 'ISIN', 'SERIES': 'Series'})
eq['Series'] = eq['Series'].str.strip()
n500 = pd.read_csv('n500.csv').rename(columns={'Symbol': 'Symbol', 'Industry': 'NSE Sector'})[['Symbol', 'NSE Sector']]
raw = json.load(open('raw.json'))
rows = []
for s, d in raw.items():
    if d:
        d['Symbol'] = s
        rows.append(d)
f = pd.DataFrame(rows)
df = eq[['Symbol', 'Company', 'Series', 'ISIN']].merge(f, on='Symbol', how='left').merge(n500, on='Symbol', how='left')
for c in ['marketCap','trailingPE','fiftyTwoWeekHigh','fiftyTwoWeekLow','dividendRate','dividendYield','trailingAnnualDividendRate','currentPrice','regularMarketPrice','averageVolume','priceToBook','returnOnEquity','debtToEquity','earningsGrowth','revenueGrowth','beta']:
    df[c] = pd.to_numeric(df[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
df['Price'] = df['currentPrice'].fillna(df['regularMarketPrice'])
df['MarketCap_Cr'] = (df['marketCap'] / 1e7).round(0)
df = df.sort_values('MarketCap_Cr', ascending=False).reset_index(drop=True)
df['McapRank'] = df['MarketCap_Cr'].rank(ascending=False, method='first')

# SEBI/AMFI convention: top 100 large, 101-250 mid, 251+ small; micro = rank > 500 (approximation)
def cap(r):
    if pd.isna(r): return ''
    return 'Large' if r <= 100 else 'Mid' if r <= 250 else 'Small' if r <= 500 else 'Micro'
df['Cap'] = df['McapRank'].where(df['MarketCap_Cr'].notna()).map(cap)

ymap = {'Financial Services': 'Financial Services', 'Technology': 'Information Technology', 'Healthcare': 'Healthcare',
        'Consumer Defensive': 'Fast Moving Consumer Goods', 'Consumer Cyclical': 'Consumer Discretionary',
        'Industrials': 'Capital Goods', 'Energy': 'Oil Gas & Consumable Fuels', 'Basic Materials': 'Materials',
        'Utilities': 'Power', 'Real Estate': 'Realty', 'Communication Services': 'Media Entertainment & Telecom'}
df['Sector'] = df['NSE Sector'].fillna(df['sector'].map(ymap)).fillna('Unclassified')
df['DivYield_%'] = df['dividendYield'].round(2)   # yfinance already returns percent
df['DivPerShare'] = df['dividendRate'].fillna(df['trailingAnnualDividendRate']).round(2)
df['PE'] = df['trailingPE'].where(df['trailingPE'] > 0).round(1)

full = pd.DataFrame({
    'Symbol': 'NSE:' + df['Symbol'], 'Company': df['Company'], 'ISIN': df['ISIN'], 'Series': df['Series'],
    'Sector': df['Sector'], 'Industry': df['industry'], 'Cap Class': df['Cap'], 'Market Cap (Cr)': df['MarketCap_Cr'],
    'Price': df['Price'].round(2), 'P/E': df['PE'], 'P/B': df['priceToBook'].round(2),
    '52W High': df['fiftyTwoWeekHigh'].round(2), '52W Low': df['fiftyTwoWeekLow'].round(2),
    '% Below 52W High': ((1 - df['Price'] / df['fiftyTwoWeekHigh']) * 100).round(1),
    'Dividend/Share (annual)': df['DivPerShare'], 'Dividend Yield %': df['DivYield_%'],
    'ROE %': (df['returnOnEquity'] * 100).round(1), 'Debt/Equity': df['debtToEquity'].round(1),
    'Avg Volume': df['averageVolume'],
    'Nifty500': df['NSE Sector'].notna().map({True: 'Y', False: ''}),
})
full.to_csv('All_NSE_Scrips_Data.csv', index=False)
print('full rows', len(full), 'with data', full['Price'].notna().sum())

