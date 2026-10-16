"""Step 06 - price history for the stock-popup chart: every Nifty 500 stock, from Yahoo daily closes (split-adjusted 'Close').
-> raw_chart.json  {SYM: {'w0': first weekly date, 'w': [weekly closes, last 5 years], 'm0': 'YYYY-MM', 'm': [month-end closes before that, up to 20 years]}}
Weekly = last close of each week (Fri), monthly = last close of each month, evenly spaced (gaps carry the last close); 4 significant digits. Resumable; re-fetches when END_DATE moves."""
import datetime as dt
import pandas as pd
from common import OUT, END_DATE, run_resumable, reset_if_stale

YEARS_MONTHLY, YEARS_WEEKLY = 20, 5
sig = lambda v: float(f'{v:.4g}')


def hist(sym):
    import yfinance as yf
    end = dt.date.fromisoformat(END_DATE)
    for attempt in range(3):
        try:
            h = yf.Ticker(sym + '.NS').history(start=f'{end.year - YEARS_MONTHLY}-{end.month:02d}-01', end=(end + dt.timedelta(days=1)).isoformat(), auto_adjust=False)
            if h is None or h.empty: return sym, None
            c = h['Close'].dropna(); c.index = c.index.tz_localize(None)
            cut = pd.Timestamp(end.year - YEARS_WEEKLY, end.month, end.day)
            w = c[c.index >= cut].resample('W-FRI').last().ffill()     # ffill: a week / month with no trades keeps the last close,
            m = c[c.index < cut].resample('ME').last().ffill()         # so the series stays evenly spaced (the app rebuilds dates from w0 / m0)
            if w.empty: return sym, None
            return sym, {'w0': w.index[0].strftime('%Y-%m-%d'), 'w': [sig(v) for v in w.values], 'last': [c.index[-1].strftime('%Y-%m-%d'), sig(c.iloc[-1])],
                         'm0': m.index[0].strftime('%Y-%m') if len(m) else None, 'm': [sig(v) for v in m.values]}
        except Exception:
            import time; time.sleep(2 * (attempt + 1))
    return sym, None


if __name__ == '__main__':
    reset_if_stale('raw_chart.json')
    syms = sorted(pd.read_csv(f'{OUT}/Nifty500_Analysis.csv').Symbol.dropna().str[4:].unique())
    out = run_resumable('chart-history', hist, syms, 'raw_chart.json', workers=2)
    ok = sum(1 for s in syms if out.get(s))
    print(f'chart history: {ok}/{len(syms)} stocks · weekly {YEARS_WEEKLY}y + monthly up to {YEARS_MONTHLY}y')
