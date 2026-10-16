"""1/2/3/4/5-year price returns for every Nifty 500 stock (helper used by step 17). -> raw_ret_hist.json (cache) + ../Returns_Nifty500.csv
Each horizon starts on the first trading day on/after 1 October of 2025 / 2024 / 2023 / 2022 / 2021 and ends on the latest close on/before END_DATE,
the same convention as the Sectors / Sector Picks / Backtest tabs.
Also: year-by-year returns ('YoY 21→22 %' … the last one ends on END_DATE) between those same October start dates, and 'Price trend':
Declining = 1Y return < 0 · Slowing = 1Y at least 10 pts below both the 3Y and 5Y CAGR · Accelerating = 1Y at least 10 pts above both · else Steady. Yahoo split-adjusted closes; histories Yahoo adjusted only partly are
corrected; any horizon spanning an unadjusted break (non-reverting one-day move <= -45% or > +50%: bonus/split, demerger, bad data) is blanked."""
import datetime as dt, json, os, time
import pandas as pd
from common import OUT, END_DATE, run_resumable, load_json, reset_if_stale

H = {'1Y': 2025, '2Y': 2024, '3Y': 2023, '4Y': 2022, '5Y': 2021}
CACHE_V = 2                            # bump when H changes: cached entries keep only the closes around each horizon's start
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
            return sym, {'close': {d: round(v, 4) for d, v in c if keep(d)}, 'first': c[0][0], 'jumps': jumps, 'v': CACHE_V}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return sym, None


YOY = [(y, y + 1) for y in sorted(H.values())]                       # consecutive October-to-October years; the last ends on END_DATE
yoy_col = lambda y0, y1: f'YoY {y0 % 100:02d}→{y1 % 100:02d} %'
TREND_GAP = 10                                                       # pts the 1Y return must be below / above both the 3Y and 5Y CAGR


def trend(r1, c3, c5):
    if r1 is None or pd.isna(r1): return None
    cs = [c for c in (c3, c5) if c is not None and not pd.isna(c)]
    if r1 < 0: return 'Declining'
    if cs and r1 < min(cs) - TREND_GAP: return 'Slowing'
    if cs and r1 > max(cs) + TREND_GAP: return 'Accelerating'
    return 'Steady'


def build(symbols):
    reset_if_stale('raw_ret_hist.json')
    old = load_json('raw_ret_hist.json')
    if any(v and v.get('v') != CACHE_V for v in old.values()):   # cached before 2Y/4Y existed: re-fetch those symbols
        json.dump({k: v for k, v in old.items() if v and v.get('v') == CACHE_V}, open('raw_ret_hist.json', 'w'))
    raw = run_resumable('returns-1/2/3/4/5y', hist, symbols, 'raw_ret_hist.json', workers=2)
    rows = []
    for s in symbols:
        h = raw.get(s) or {}
        c = h.get('close', {}); ds = sorted(c); z = max((d for d in ds if d <= END_DATE), default=None)
        rec = {'Symbol': 'NSE:' + s}
        notes, starts = [], {}
        for hz, y in H.items():
            a = next((d for d in ds if f'{y}-10-01' <= d <= f'{y}-10-15'), None)
            br = [j for j in h.get('jumps', []) if a and a < j[0] <= (z or '') and is_break(j[1])]
            starts[y] = a                                            # start close of this October (before blanking: year-by-year checks its own window)
            if br: notes.append(f'{hz} blanked: unadjusted {br[0][1]:+d}% move on {br[0][0]}'); a = None
            if a and z:
                t = c[z] / c[a]; n = (dt.date.fromisoformat(z) - dt.date.fromisoformat(a)).days / 365.25
                rec[f'{hz} %'] = round((t - 1) * 100, 1); rec[f'{hz} CAGR %'] = round((t ** (1 / n) - 1) * 100, 1)
            else:
                rec[f'{hz} %'] = rec[f'{hz} CAGR %'] = None
                if not br and h.get('first') and h['first'] > f'{y}-10-15': notes.append(f'{hz} n/a: listed/data from {h["first"]}')
        starts[max(H.values()) + 1] = z                               # the last year ends on the data date
        for y0, y1 in YOY:
            a0, a1 = starts.get(y0), starts.get(y1)
            bad = a0 and a1 and any(a0 < j[0] <= a1 and is_break(j[1]) for j in h.get('jumps', []))
            rec[yoy_col(y0, y1)] = round((c[a1] / c[a0] - 1) * 100, 1) if a0 and a1 and not bad else None
        rec['Price trend'] = trend(rec['1Y %'], rec['3Y CAGR %'], rec['5Y CAGR %'])
        rec['Returns note'] = '; '.join(notes)
        rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(f'{OUT}/Returns_Nifty500.csv', index=False)
    return R


if __name__ == '__main__':
    a = pd.read_csv(f'{OUT}/Nifty500_Analysis.csv')
    R = build(sorted(a.Symbol.dropna().str[4:].unique()))
    print(R.describe().round(1).to_string()); print('blank 1Y..5Y:', *(R[f'{h} %'].isna().sum() for h in H))
