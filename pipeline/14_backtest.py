"""Step 14 - multi-horizon what-if backtest.
For each horizon (1Y..5Y ending END_DATE): Rs 50,000 in every holding of every account - the 40 stocks (Active + To Invest)
and, separately, the 9 ETF/SGB holdings - bought at the close of the first trading day on/after 1 Oct of the start year, held untouched.
Benchmarks: Nifty 50 (^NSEI) and Nifty 500 (^CRSLDX) price indices over the same window.

Rules: whole shares (leftover rupees stay as cash); Yahoo split-adjusted closes (auto_adjust=False) with an auto-fix for histories that
Yahoo only partly adjusted; dividends added as cash on their ex-date; a holding not yet listed at the start keeps its Rs 50,000 as cash
until its first trading day, then buys (flagged). No taxes, brokerage or reinvestment.
Outputs (repo root): Backtest_Summary.csv (horizon x portfolio), Backtest_Holdings.csv (every holding x horizon),
Backtest_Daily.csv (daily wealth per portfolio + benchmarks indexed to 100, per horizon). History cache: raw_hist5.json (resumable)."""
import datetime as dt, math, time
import pandas as pd
from common import OUT, ACCOUNTS, ACCOUNT_ID, SUGGESTED, run_resumable

END_DATE, PER_HOLDING, HIST_FROM = '2026-10-03', 50_000, '2021-09-01'
HORIZONS = {'1Y': 2025, '2Y': 2024, '3Y': 2023, '4Y': 2022, '5Y': 2021}          # label -> start year (1 Oct)
BENCH = {'^NSEI': 'Nifty 50', '^CRSLDX': 'Nifty 500'}
# ETFs whose Yahoo history starts long after listing: fill the gap with an ETF tracking the same index (scaled to join smoothly)
PROXY = {'MID150BEES': 'MIDCAPIETF', 'MIDCAPETF': 'MIDCAPIETF', 'GOLDIETF': 'GOLDBEES', 'HDFCSILVER': 'SILVERBEES', 'SILVERIETF': 'SILVERBEES'}
NOTES = {'LIQUIDBEES': 'pays its daily income as extra units, which price data does not capture - return understated (~6-7%/yr missing)'}


def hist(sym):
    import yfinance as yf
    for attempt in range(3):
        try:
            t = yf.Ticker(sym if sym.startswith('^') else sym + '.NS')
            h = t.history(start=HIST_FROM, end=(dt.date.fromisoformat(END_DATE) + dt.timedelta(days=1)).isoformat(), auto_adjust=False, actions=True)
            if h is None or h.empty: return sym, None
            h.index = h.index.tz_localize(None).strftime('%Y-%m-%d')
            return sym, {'close': {d: round(float(v), 4) for d, v in h['Close'].dropna().items()},
                         'div': {d: float(v) for d, v in h.get('Dividends', pd.Series(dtype=float)).items() if v and v > 0},
                         'split': {d: float(v) for d, v in h.get('Stock Splits', pd.Series(dtype=float)).items() if v and v > 0}}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return sym, None


def fix_unadjusted(closes, splits):
    """Yahoo sometimes split-adjusts only the stretch just before a split, leaving older prices raw - which shows up as a fake
    one-day crash of exactly 1/k (e.g. TRENT: -33% on 2026-01-01 for the x1.5 bonus Yahoo dates 2026-06-04).
    A jump is treated as unadjusted ONLY if it matches a recorded split ratio k within 2% AND falls before that split's date by
    at most a year - so genuine crashes (e.g. RECLTD -25% on 2024-06-04, election day) are left alone."""
    fixed = []
    for sd, k in splits.items():
        for i in range(1, len(closes)):
            d, r = closes[i][0], closes[i][1] / closes[i - 1][1]
            if d < sd and (dt.date.fromisoformat(sd) - dt.date.fromisoformat(d)).days <= 365 and abs(r * k - 1) < 0.02 and abs(r - 1) > 0.2:
                closes = [(x, v / k) for x, v in closes[:i]] + closes[i:]
                fixed.append(f'{d} x{k:g}')
                break
    return closes, fixed


# ---- holdings: 120 stocks + 27 ETF/SGB ----
st = pd.read_csv(f'{SUGGESTED}/Account_Portfolios_20+20.csv')     # backtest of the original suggested lists
et = pd.read_csv(f'{SUGGESTED}/ETF_SGB_Per_Account.csv')
hold = pd.concat([
    pd.DataFrame({'Account': st['Account'], 'Portfolio': 'Stocks', 'List': st['Bucket'].str.split(' (', regex=False).str[0], 'Symbol': st['Symbol'],
                  'Company': st['Company'], 'Sector': st['Sector'], 'Cap Class': st['Cap Class']}),
    pd.DataFrame({'Account': et['Account'], 'Portfolio': 'ETF/SGB', 'List': et['Slot'], 'Symbol': et['Symbol'],
                  'Company': et['Name'], 'Sector': et['Underlying'], 'Cap Class': ''})], ignore_index=True)
hold['Sym'] = hold['Symbol'].str.replace('NSE:', '', regex=False)
H = run_resumable('history-5y', hist, hold['Sym'].tolist() + list(BENCH), 'raw_hist5.json', workers=2)
FIX, FIXNOTE = {}, {}
for s in hold['Sym']:
    if H.get(s):
        FIX[s], f = fix_unadjusted(sorted(H[s]['close'].items()), H[s]['split'])
        FIX[s] = dict(FIX[s]); FIXNOTE[s] = f

# official listing dates (NSE masters) - to tell genuine late listings from Yahoo data gaps
LISTED = {}
_eq = pd.read_csv('EQUITY_L.csv'); _eq.columns = [c.strip() for c in _eq.columns]
for sy, d in zip(_eq['SYMBOL'], pd.to_datetime(_eq['DATE OF LISTING'], format='%d-%b-%Y', errors='coerce')): LISTED[sy.strip()] = d
_et = pd.read_csv('etf.csv'); _et.columns = [c.strip() for c in _et.columns]
for sy, d in zip(_et['Symbol'], pd.to_datetime(_et['DateofListing'], format='%d-%b-%y', errors='coerce')): LISTED[sy.strip()] = d
LISTED = {k: v.strftime('%Y-%m-%d') for k, v in LISTED.items() if pd.notna(v)}

PROXIED = {}
for s_, p_ in PROXY.items():
    if s_ in FIX and p_ in FIX:
        own, first = FIX[s_], min(FIX[s_])
        join = next((d for d in sorted(FIX[p_]) if d >= first), None)
        if join:
            k = own[first] / FIX[p_][join]
            gap = {d: v * k for d, v in FIX[p_].items() if LISTED.get(s_, '0000') <= d < first}
            if gap: FIX[s_] = {**gap, **own}; PROXIED[s_] = (p_, first)

cal_all = sorted(x for x in (H.get('^NSEI') or {}).get('close', {}) if x <= END_DATE)
assert cal_all, 'Nifty 50 history missing - re-run this step'
val_day = cal_all[-1]
years_of = lambda a, b: (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days / 365.25
cagr = lambda end, start, yrs: round(((end / start) ** (1 / yrs) - 1) * 100, 2) if start and end > 0 and yrs > 0 else None

rows, summ, daily = [], [], []
for hz, y0 in HORIZONS.items():
    start = next(d for d in cal_all if d >= f'{y0}-10-01')
    cal = [d for d in cal_all if d >= start]
    yrs = years_of(start, val_day)
    paths = {}
    for r in hold.to_dict('records'):
        sym, key = r['Sym'], (r['Account'], r['Portfolio'])
        path = paths.setdefault(key, [0.0] * len(cal))
        base = {'Horizon': hz, 'Start': start, **{k: r[k] for k in ['Account', 'Portfolio', 'List', 'Symbol', 'Company', 'Sector', 'Cap Class']}}
        px = FIX.get(sym)
        tradable = sorted(d for d in (px or {}) if start <= d <= val_day)
        if not tradable:
            rows.append({**base, 'Qty': 0, 'Invested': 0, 'Cash Left': PER_HOLDING, 'Value Now': 0, 'Dividends': 0, 'Final Wealth': PER_HOLDING,
                         'P&L': 0, 'Total Return %': 0.0, 'CAGR %': 0.0, 'Note': 'no price history (e.g. SGB not on Yahoo) - held as cash'})
            for i in range(len(cal)): path[i] += PER_HOLDING
            continue
        buy_d = tradable[0]; buy_p = px[buy_d]
        qty = math.floor(PER_HOLDING / buy_p); invested = qty * buy_p; cash = PER_HOLDING - invested
        last_d = tradable[-1]; last_p = px[last_d]
        divs = sorted((d, v * qty) for d, v in H[sym]['div'].items() if buy_d < d <= last_d)
        div_total = sum(v for _, v in divs); value = qty * last_p; final = value + div_total + cash
        notes = []
        if buy_d > cal[min(3, len(cal) - 1)]:
            lst = LISTED.get(sym)
            if lst and years_of(max(lst, start), buy_d) * 365.25 > 30:
                notes.append(f'data gap: listed {lst} but Yahoo has no prices before {buy_d} - cash until then (return understated)')
            else:
                notes.append(f'not listed at start (listed {lst or buy_d}) - cash until first close {buy_d}')
        if sym in PROXIED and buy_d < PROXIED[sym][1]: notes.append(f'Yahoo has no prices before {PROXIED[sym][1]} - that stretch filled from {PROXIED[sym][0]} (tracks the same index)')
        if FIXNOTE.get(sym): notes.append('Yahoo history corrected for unadjusted ' + ', '.join(FIXNOTE[sym]))
        if sym in NOTES: notes.append(NOTES[sym])
        splits = ', '.join(f'{d} x{v:g}' for d, v in H[sym]['split'].items() if buy_d < d <= last_d)
        rows.append({**base, 'Buy Date': buy_d, 'Buy Price': round(buy_p, 2), 'Qty': qty, 'Invested': round(invested, 2), 'Cash Left': round(cash, 2),
                     'Value Date': last_d, 'Price Now': round(last_p, 2), 'Value Now': round(value, 2), 'Dividends': round(div_total, 2),
                     'Final Wealth': round(final, 2), 'P&L': round(final - PER_HOLDING, 2), 'Price Return %': round((last_p / buy_p - 1) * 100, 2),
                     'Total Return %': round((final / PER_HOLDING - 1) * 100, 2), 'CAGR %': cagr(final, PER_HOLDING, yrs),
                     'Splits/Bonus (adjusted)': splits, 'Note': '; '.join(notes)})
        last, di = None, 0
        for i, day in enumerate(cal):
            if day in px: last = px[day]
            while di < len(divs) and divs[di][0] <= day: cash += 0; di += 1
            if day < buy_d or last is None: path[i] += PER_HOLDING; continue
            path[i] += qty * last + (PER_HOLDING - invested) + sum(v for d, v in divs[:di])
    # portfolio summaries
    R = pd.DataFrame([x for x in rows if x['Horizon'] == hz])
    def add(name, acc, port, g):
        cap = PER_HOLDING * len(g); fin = g['Final Wealth'].sum(); tr = g['Total Return %']
        summ.append({'Horizon': hz, 'Start': start, 'End': val_day, 'Years': round(yrs, 2), 'Portfolio': name, 'Account': acc, 'Type': port,
                     'Holdings': len(g), 'Capital': cap, 'Final Wealth': round(fin), 'P&L': round(fin - cap), 'Total Return %': round((fin / cap - 1) * 100, 2),
                     'CAGR %': cagr(fin, cap, yrs), 'Dividends': round(g['Dividends'].sum()), 'Winners': int((tr > 0).sum()), 'Losers': int((tr <= 0).sum()),
                     'Late listings': int(g['Note'].fillna('').str.contains('not listed').sum()), 'Data gaps': int(g['Note'].fillna('').str.contains('data gap').sum()), 'No data': int(g['Note'].fillna('').str.contains('no price history').sum())})
    for port in ('Stocks', 'ETF/SGB'):
        for acc in ACCOUNTS.values():
            add(f'{acc} · {port}', acc, port, R[(R.Account == acc) & (R.Portfolio == port)])
        add(f'All accounts · {port}', 'All', port, R[R.Portfolio == port])
    for b, name in BENCH.items():
        c = H[b]['close']; a = c[start]; z = c[val_day]
        summ.append({'Horizon': hz, 'Start': start, 'End': val_day, 'Years': round(yrs, 2), 'Portfolio': name, 'Account': 'Benchmark', 'Type': 'Index',
                     'Total Return %': round((z / a - 1) * 100, 2), 'CAGR %': cagr(z, a, yrs)})
    # daily wealth path, indexed to 100 at start
    for i, day in enumerate(cal):
        rec = {'Horizon': hz, 'Date': day}
        for (acc, port), p in paths.items(): rec[f'{acc} · {port}'] = round(p[i] / (PER_HOLDING * len(hold[(hold.Account == acc) & (hold.Portfolio == port)])) * 100, 3)
        for port in ('Stocks', 'ETF/SGB'):
            tot = sum(p[i] for (acc, pp), p in paths.items() if pp == port)
            rec[f'All accounts · {port}'] = round(tot / (PER_HOLDING * int((hold.Portfolio == port).sum())) * 100, 3)
        for b, name in BENCH.items():
            lv = next((H[b]['close'][d] for d in reversed(cal[:i + 1]) if d in H[b]['close']), None)
            rec[name] = round(lv / H[b]['close'][start] * 100, 3) if lv else None
        daily.append(rec)
    # the daily path must land exactly on the summary
    end_all = daily[-1]['All accounts · Stocks'] / 100 * PER_HOLDING * int((hold.Portfolio == 'Stocks').sum())
    exp = next(s['Final Wealth'] for s in summ if s['Horizon'] == hz and s['Portfolio'] == 'All accounts · Stocks')
    assert abs(end_all - exp) < 500, (hz, end_all, exp)

A = pd.DataFrame(rows)
A['_h'] = A['Horizon'].str[0].astype(int); A['_a'] = A['Account'].map(ACCOUNT_ID)
A = A.sort_values(['_h', '_a', 'Portfolio', 'List', 'Total Return %'], ascending=[True, True, False, True, False]).drop(columns=['_h', '_a'])
A.to_csv(f'{OUT}/Backtest_Holdings.csv', index=False)
S = pd.DataFrame(summ); S.to_csv(f'{OUT}/Backtest_Summary.csv', index=False)
pd.DataFrame(daily).to_csv(f'{OUT}/Backtest_Daily.csv', index=False)

pd.set_option('display.width', 250)
piv = S.pivot_table(index='Portfolio', columns='Horizon', values='CAGR %', sort=False)
tot = S.pivot_table(index='Portfolio', columns='Horizon', values='Total Return %', sort=False)
print('TOTAL RETURN %'); print(tot.to_string()); print('\nCAGR %'); print(piv.to_string())
print('\nlate listings / no data per horizon:'); print(S[S.Account == 'All'][['Horizon', 'Type', 'Late listings', 'No data']].to_string(index=False))
