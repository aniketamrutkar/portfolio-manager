"""Step 02 - Nifty 500 deep dive from Yahoo: 4y financials (CAGR, ROE avg/min, interest cover, cash conversion, FCF),
5y dividends, 5y price history (returns, volatility, drawdown), margins/valuation/analyst fields. -> raw2.json  (resumable)"""
import pandas as pd, yfinance as yf, time, numpy as np
from common import run_resumable
syms = pd.read_csv('n500.csv')['Symbol'].tolist()
IK = ['operatingMargins','profitMargins','ebitdaMargins','returnOnAssets','forwardPE','pegRatio','enterpriseToEbitda',
      'priceToSalesTrailing12Months','currentRatio','totalDebt','totalCash','freeCashflow','operatingCashflow','payoutRatio',
      'fiveYearAvgDividendYield','targetMeanPrice','recommendationKey','numberOfAnalystOpinions','fiftyDayAverage',
      'twoHundredDayAverage','heldPercentInsiders','heldPercentInstitutions','netIncomeToCommon','beta']
def row(df, names):
    if df is None or df.empty: return None
    for n in names:
        if n in df.index: return [None if pd.isna(v) else float(v) for v in df.loc[n].values]   # newest first
def cagr(v):
    v = [x for x in (v or []) if x is not None]
    if len(v) >= 3 and v[0] > 0 and v[-1] > 0: return round(((v[0] / v[-1]) ** (1 / (len(v) - 1)) - 1) * 100, 1)
def get(s):
    for a in range(3):
        try:
            t = yf.Ticker(s + '.NS'); o = {'Symbol': s}
            i = t.info or {}
            for k in IK: o[k] = i.get(k)
            inc, bs, cf = t.income_stmt, t.balance_sheet, t.cashflow
            rev = row(inc, ['Total Revenue', 'Operating Revenue']); ni = row(inc, ['Net Income', 'Net Income Common Stockholders'])
            ebit = row(inc, ['EBIT', 'Operating Income']); intx = row(inc, ['Interest Expense'])
            eq = row(bs, ['Stockholders Equity', 'Common Stock Equity']); debt = row(bs, ['Total Debt'])
            ocf = row(cf, ['Operating Cash Flow']); fcf = row(cf, ['Free Cash Flow'])
            o['years'] = len(rev or [])
            o['RevCAGR'] = cagr(rev); o['NICAGR'] = cagr(ni)
            o['ProfitYears'] = sum(1 for x in (ni or []) if x is not None and x > 0); o['NIYears'] = len([x for x in (ni or []) if x is not None])
            if ebit and intx and ebit[0] is not None and intx[0]: o['IntCover'] = round(ebit[0] / abs(intx[0]), 1)
            if ni and eq:
                r = [n / e * 100 for n, e in zip(ni, eq) if n is not None and e]
                o['ROE_avg'] = round(sum(r) / len(r), 1) if r else None; o['ROE_min'] = round(min(r), 1) if r else None
            if ocf and ni and ni[0]: o['CashConv'] = round(ocf[0] / ni[0], 2)
            if fcf: o['FCF_pos_yrs'] = sum(1 for x in fcf if x is not None and x > 0); o['FCF_yrs'] = len([x for x in fcf if x is not None])
            d = t.dividends
            if d is not None and len(d):
                d.index = d.index.tz_localize(None); y = d.groupby(d.index.year).sum()
                last5 = [y.get(yr, 0.0) for yr in range(pd.Timestamp.now().year - 5, pd.Timestamp.now().year)]
                o['Div_5y_avg'] = round(float(np.mean(last5)), 2); o['Div_yrs_paid_5'] = int(sum(1 for x in last5 if x > 0))
                o['Div_growth'] = int(last5[-1] >= last5[0] and last5[0] > 0)
            h = t.history(period='5y', auto_adjust=True)['Close'].dropna()
            if len(h) > 250:
                p = h.iloc[-1]
                for lab, n in (('Ret1y', 252), ('Ret3y', 756), ('Ret5y', 1250)):
                    if len(h) > n: o[lab] = round((p / h.iloc[-n] - 1) * 100, 1)
                o['Vol%'] = round(float(h.pct_change().std() * (252 ** .5) * 100), 1)
                o['MaxDD3y%'] = round(float((h.iloc[-756:] / h.iloc[-756:].cummax() - 1).min() * 100), 1)
            return s, o
        except Exception as e:
            time.sleep(2 * (a + 1))
    return s, None
run_resumable('nifty500-deep', get, syms, 'raw2.json', workers=2)
