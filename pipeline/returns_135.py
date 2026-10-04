"""1/3/5-year price returns for every Nifty 500 stock (helper used by step 17). -> raw_ret_hist.json (cache) + ../Returns_Nifty500.csv
Each horizon starts on the first trading day on/after 1 October of 2025 / 2023 / 2021 and ends on the latest close on/before END_DATE,
the same convention as the Sectors / Sector Picks / Backtest tabs. Yahoo split-adjusted closes; histories Yahoo adjusted only partly are
corrected; any horizon spanning an unadjusted break (non-reverting one-day move <= -45% or > +50%: bonus/split, demerger, bad data) is blanked."""
import datetime as dt, json, os, time
import pandas as pd
from common import OUT, run_resumable, load_json

END_DATE = '2026-10-01'
H = {'1Y': 2025, '3Y': 2023, '5Y': 2021}
is_break = lambda m: m <= -45 or m > 50


def hist(sym):
    import yfinance as yf
    for attempt in range(3):
        try:
            h = yf.Ticker(sym + '.NS').history(start='2021-09-01', end=(dt.date.fromisoformat(END_DATE) + dt.timedelta(days=1)).isoformat(), auto_adjust=False, actions=True)
            if h is None or h.empty: return sym, None
            h.index = h.index.tz_localize(None).strftime('%Y-%m-%d')
            c = [(d, float(v)) for d, v in h['Close'].dropna().items()]
            splits = {d: float(v) for d, v in h['Stock Splits'].items() if v and v > 0}
            for sd, k in splits.items():                         # partial-adjustment fix (same rule as steps 14/16)
                for i in range(1, len(c)):
                    d, r = c[i][0], c[i][1] / c[i - 1][1]
                    if d < sd and (dt.date.fromisoformat(sd) - dt.date.fromisoformat(d)).days <= 365 and abs(r * k - 1) < 0.02 and abs(r - 1) > 0.2:
                        c = [(x, v / k) for x, v in c[:i]] + c[i:]; break
            jumps = [[c[i][0], round((c[i][1] / c[i - 1][1] - 1) * 100)] for i in range(1, len(c))
                     if abs(c[i][1] / c[i - 1][1] - 1) > 0.35 and not any(abs(v / c[i - 1][1] - 1) < 0.2 for _, v in c[i + 1:i + 6])]
            keep = lambda d: any(f'{y}-09-28' <= d <= f'{y}-10-20' for y in H.values()) or d >= (dt.date.fromisoformat(END_DATE) - dt.timedelta(days=15)).isoformat()
            return sym, {'close': {d: round(v, 4) for d, v in c if keep(d)}, 'first': c[0][0], 'jumps': jumps}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return sym, None


def build(symbols):
    raw = run_resumable('returns-1/3/5y', hist, symbols, 'raw_ret_hist.json', workers=2)
    rows = []
    for s in symbols:
        h = raw.get(s) or {}
        c = h.get('close', {}); ds = sorted(c); z = max((d for d in ds if d <= END_DATE), default=None)
        rec = {'Symbol': 'NSE:' + s}
        notes = []
        for hz, y in H.items():
            a = next((d for d in ds if f'{y}-10-01' <= d <= f'{y}-10-15'), None)
            br = [j for j in h.get('jumps', []) if a and a < j[0] <= (z or '') and is_break(j[1])]
            if br: notes.append(f'{hz} blanked: unadjusted {br[0][1]:+d}% move on {br[0][0]}'); a = None
            if a and z:
                t = c[z] / c[a]; n = (dt.date.fromisoformat(z) - dt.date.fromisoformat(a)).days / 365.25
                rec[f'{hz} %'] = round((t - 1) * 100, 1); rec[f'{hz} CAGR %'] = round((t ** (1 / n) - 1) * 100, 1)
            else:
                rec[f'{hz} %'] = rec[f'{hz} CAGR %'] = None
                if not br and h.get('first') and h['first'] > f'{y}-10-15': notes.append(f'{hz} n/a: listed/data from {h["first"]}')
        rec['Returns note'] = '; '.join(notes)
        rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(f'{OUT}/Returns_Nifty500.csv', index=False)
    return R


if __name__ == '__main__':
    a = pd.read_csv(f'{OUT}/Nifty500_Analysis.csv')
    R = build(sorted(a.Symbol.dropna().str[4:].unique()))
    print(R.describe().round(1).to_string()); print('blank 1Y/3Y/5Y:', R['1Y %'].isna().sum(), R['3Y %'].isna().sum(), R['5Y %'].isna().sum())
