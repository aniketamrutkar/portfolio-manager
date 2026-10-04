"""Step 04 - Yahoo data (returns, volatility, drawdown, AUM if any) for NSE ETFs, REITs, InvITs. -> raw_other.json  (resumable)"""
import pandas as pd, yfinance as yf, time, numpy as np
from common import run_resumable
b = pd.read_csv('nse_bhav.csv', skipinitialspace=True); b.columns = [c.strip() for c in b.columns]
etf = pd.read_csv('etf.csv'); etf.columns = [c.strip() for c in etf.columns]
syms = sorted(set(etf['Symbol'].str.strip()) | set(b[b.SERIES.str.strip().isin(['IV', 'RR'])]['SYMBOL'].str.strip()))
IK = ['totalAssets', 'netAssets', 'navPrice', 'annualReportExpenseRatio', 'yield', 'category', 'fundFamily', 'trailingPE', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
      'currentPrice', 'regularMarketPrice', 'previousClose', 'averageVolume', 'marketCap', 'dividendRate', 'dividendYield', 'beta', 'fiftyDayAverage', 'twoHundredDayAverage', 'priceToBook']
def get(s):
    for a in range(3):
        try:
            t = yf.Ticker(s + '.NS'); i = t.info or {}
            o = {'Symbol': s}
            for k in IK: o[k] = i.get(k)
            h = t.history(period='5y', auto_adjust=True)['Close'].dropna()
            if len(h) > 60:
                p = h.iloc[-1]
                for lab, n in (('Ret1y', 252), ('Ret3y', 756), ('Ret5y', 1250)):
                    if len(h) > n: o[lab] = round((p / h.iloc[-n] - 1) * 100, 1)
                o['Vol%'] = round(float(h.pct_change().std() * (252 ** .5) * 100), 1)
                o['MaxDD3y%'] = round(float((h.iloc[-756:] / h.iloc[-756:].cummax() - 1).min() * 100), 1)
                o['Hist_yrs'] = round(len(h) / 252, 1)
            if o.get('currentPrice') or o.get('regularMarketPrice') or 'Ret1y' in o: return s, o
            return s, None
        except Exception:
            time.sleep(2 * (a + 1))
    return s, None
run_resumable('etf-reit-invit', get, syms, 'raw_other.json', workers=2)
