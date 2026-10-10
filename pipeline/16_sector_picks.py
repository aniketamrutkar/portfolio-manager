"""Step 16 - top-10 screened stocks in four focus groups (Metals & Mining, Pharma, Healthcare services, PSU Banks) with long-run
returns (1/2/3/5/10/15/20/25/30Y + since start), price-only and with dividends reinvested. Read-only w.r.t. the account lists.
-> ../Sector_Picks.csv   (history cache: raw_picks_hist.json, trimmed to the dates needed)
Ranking = the portfolio screen (step 12): stocks passing every filter, by Score; if a group has < 10 passers it is topped up with
the largest filtered-out names (flagged). Returns use Yahoo daily closes: 'Close' (split-adjusted) for price CAGR, 'Adj Close'
(split + dividend adjusted) for total-return CAGR. Partially-adjusted histories are corrected (see 14_backtest.fix_unadjusted);
other one-day moves beyond +/-35% are flagged as possible corporate actions (demerger, etc.) - not adjusted."""
import datetime as dt, json, time
import pandas as pd
from common import OUT, SUGGESTED, START_EMPTY, run_resumable, load_json

END_DATE = '2026-10-01'
HORIZONS = {'1Y': 1, '2Y': 2, '3Y': 3, '4Y': 4, '5Y': 5, '10Y': 10, '15Y': 15, '20Y': 20, '25Y': 25, '30Y': 30}
is_break = lambda m: m <= -45 or m > 50     # ~-50% = unadjusted 1:1 bonus/split; > +50% = bad data. Smaller moves (e.g. PNB +46% recap rally) are kept.
PSU_BANKS = ['SBIN', 'BANKBARODA', 'PNB', 'CANBK', 'UNIONBANK', 'INDIANB', 'BANKINDIA', 'IOB', 'CENTRALBK', 'UCOBANK', 'MAHABANK', 'PSB']
PHARMA_IND = ['Drug Manufacturers - Specialty & Generic', 'Drug Manufacturers - General', 'Biotechnology', 'Specialty Chemicals']
HC_IND = ['Medical Care Facilities', 'Diagnostics & Research', 'Medical Instruments & Supplies']
GROUP_INDEX = {'Metals & Mining': 'Nifty Metal', 'Pharma': 'Nifty Pharma', 'Healthcare': 'Nifty Healthcare Index', 'PSU Banks': 'Nifty PSU Bank'}

# ---- the 40 picks (same logic as the screen) ----
a = pd.read_csv(f'{OUT}/Nifty500_Analysis.csv')
p = pd.read_csv(f'{SUGGESTED}/Account_Portfolios_20+20.csv')
held = {} if START_EMPTY else dict(zip(p.Symbol, p.Account + ' · ' + p.Bucket.str.split(' (', regex=False).str[0]))   # the app fills this live
groups = {'Metals & Mining': a.Sector.eq('Metals & Mining'),
          'Pharma': a.Sector.eq('Healthcare') & a.Industry.isin(PHARMA_IND),
          'Healthcare': a.Sector.eq('Healthcare') & a.Industry.isin(HC_IND),
          'PSU Banks': a.Symbol.str[4:].isin(PSU_BANKS)}
picks = []
for g, m in groups.items():
    x = a[m]
    ok = x[x['Filtered Out Because'].isna()].sort_values('Score', ascending=False)
    bad = x[x['Filtered Out Because'].notna()].sort_values('Market Cap (Cr)', ascending=False)
    top = pd.concat([ok.head(10), bad.head(max(0, 10 - len(ok)))]).assign(Group=g)
    top['Rank'] = range(1, len(top) + 1)
    picks.append(top)
P = pd.concat(picks, ignore_index=True)
P['In your lists'] = P.Symbol.map(held).fillna('')
P['Sym'] = P.Symbol.str[4:]


# ---- price history ----
def hist(sym):
    import yfinance as yf
    for attempt in range(3):
        try:
            h = yf.Ticker(sym + '.NS').history(period='max', auto_adjust=False, actions=True)
            if h is None or h.empty: return sym, None
            h.index = h.index.tz_localize(None).strftime('%Y-%m-%d')
            h = h[h.index <= END_DATE]
            return sym, {'close': {d: round(float(v), 4) for d, v in h['Close'].dropna().items()},
                         'adj': {d: round(float(v), 4) for d, v in h['Adj Close'].dropna().items()},
                         'split': {d: float(v) for d, v in h['Stock Splits'].items() if v and v > 0}}
        except Exception:
            time.sleep(2 * (attempt + 1))
    return sym, None


def fix_unadjusted(closes, splits):
    """Same rule as step 14: a one-day jump matching a recorded split ratio within a year BEFORE that split = unadjusted history."""
    fixed = []
    for sd, k in splits.items():
        for i in range(1, len(closes)):
            d, r = closes[i][0], closes[i][1] / closes[i - 1][1]
            if d < sd and (dt.date.fromisoformat(sd) - dt.date.fromisoformat(d)).days <= 365 and abs(r * k - 1) < 0.02 and abs(r - 1) > 0.2:
                closes = [(x, v / k) for x, v in closes[:i]] + closes[i:]
                fixed.append((d, k)); break
    return closes, fixed


raw = load_json('raw_picks_hist.json')
todo = [s for s in P.Sym if s not in raw]
if todo:
    full = run_resumable('picks-history', hist, todo, 'raw_picks_hist_full.tmp.json', workers=2)
    keep_windows = [(f'{y}-09-24', f'{y}-10-20') for y in range(1990, 2027)]
    for s in todo:
        h = full.get(s)
        if not h: raw[s] = None; continue
        c, fixed = fix_unadjusted(sorted(h['close'].items()), h['split'])
        adj = sorted(h['adj'].items())
        for d0, k in fixed: adj = [(x, v / k) if x < d0 else (x, v) for x, v in adj]
        jumps = []                                       # one-day moves beyond +/-35% that do NOT revert within 5 sessions
        for i in range(1, len(c)):                       # (reverting spikes are bad ticks and are ignored)
            r = c[i][1] / c[i - 1][1] - 1
            if abs(r) > 0.35 and not any(abs(v / c[i - 1][1] - 1) < 0.2 for _, v in c[i + 1:i + 6]):
                jumps.append([c[i][0], round(r * 100)])
        inwin = lambda d: any(a_ <= d <= b_ for a_, b_ in keep_windows) or d >= (dt.date.fromisoformat(END_DATE) - dt.timedelta(days=15)).isoformat()
        cd, ad = dict(c), dict(adj)
        first = c[0][0]
        raw[s] = {'close': {d: round(v, 4) for d, v in cd.items() if inwin(d) or d == first},
                  'adj': {d: round(v, 4) for d, v in ad.items() if inwin(d) or d == first},
                  'first': first, 'fixed': [f'{d} x{k:g}' for d, k in fixed], 'jumps': jumps}
    json.dump(raw, open('raw_picks_hist.json', 'w'))
    import os; os.remove('raw_picks_hist_full.tmp.json')

# ---- returns ----
eq = pd.read_csv('EQUITY_L.csv'); eq.columns = [c.strip() for c in eq.columns]
LISTED = dict(zip(eq.SYMBOL.str.strip(), pd.to_datetime(eq['DATE OF LISTING'], format='%d-%b-%Y', errors='coerce').dt.strftime('%Y-%m-%d')))
end = dt.date.fromisoformat(END_DATE)
yrs_between = lambda a_, b_: (dt.date.fromisoformat(b_) - dt.date.fromisoformat(a_)).days / 365.25
rows = []
for r in P.to_dict('records'):
    h = raw.get(r['Sym']) or {}
    c, ad = h.get('close', {}), h.get('adj', {})
    ds = sorted(c); z = max((d for d in ds if d <= END_DATE), default=None)
    rec = {k: r[k] for k in ['Group', 'Rank', 'Symbol', 'Company', 'Industry', 'Cap Class', 'Market Cap (Cr)', 'Score', 'Quality (0-100)', 'Safety (0-100)',
                              'Value (0-100)', 'Income (0-100)', 'Trend (0-100)', 'P/E', 'PE vs sector', 'P/B', 'ROE % (avg 4y)', 'Revenue CAGR %',
                              'Profit CAGR %', 'Debt/Equity', 'Interest Cover', 'Dividend Yield %', 'Promoter %', 'Promoter chg 1y (pp)',
                              '% Below 52W High', 'Filtered Out Because', 'In your lists']}
    for hz, y in HORIZONS.items():
        d0 = dt.date(end.year - y, 10, 1)
        a_d = next((d for d in ds if d0.isoformat() <= d <= (d0 + dt.timedelta(days=14)).isoformat()), None)
        broken = [j for j in h.get('jumps', []) if a_d and a_d < j[0] <= (z or '') and is_break(j[1])]
        if broken: a_d = None                            # horizon spans an unadjusted break (bad data / demerger): blank it
        for basis, src in (('', c), (' TR', ad)):
            if a_d and z and src.get(a_d) and src.get(z):
                t = src[z] / src[a_d]; n = yrs_between(a_d, z)
                rec[f'{hz}{basis} %'] = round((t - 1) * 100, 1); rec[f'{hz}{basis} CAGR %'] = round((t ** (1 / n) - 1) * 100, 1)
            else:
                rec[f'{hz}{basis} %'] = rec[f'{hz}{basis} CAGR %'] = None
    first = orig_first = h.get('first')
    rec['Data since'] = first
    if any(is_break(j[1]) for j in h.get('jumps', [])):    # since-start would span a break too: start after the last one
        first = max(j[0] for j in h['jumps'] if is_break(j[1]))
        first = next((d for d in ds if d >= first), first)
    if first and z and first in c and yrs_between(first, z) >= 1:
        n = yrs_between(first, z)
        for basis, src in (('', c), (' TR', ad)):
            if src.get(first): rec[f'Since start{basis} %'] = round((src[z] / src[first] - 1) * 100, 1); rec[f'Since start{basis} CAGR %'] = round(((src[z] / src[first]) ** (1 / n) - 1) * 100, 1)
    notes = []
    lst = LISTED.get(r['Sym'])
    if orig_first and lst and yrs_between(lst, orig_first) > 0.25: notes.append(f'Yahoo history starts {orig_first} (listed {lst}) - longer horizons missing')
    if first != orig_first: notes.append(f'since-start measured from {first}, after the last unadjusted break'); rec['Data since'] = orig_first
    notes += [f'split history corrected {x}' for x in h.get('fixed', [])]
    notes += [f'{d} {m:+d}% one-day move ' + ('not adjusted by Yahoo (bonus/split, demerger or bad data) - horizons spanning it are blanked' if is_break(m) else '(looks genuine, kept)') for d, m in h.get('jumps', [])]
    rec['Data notes'] = '; '.join(notes)
    rows.append(rec)
R = pd.DataFrame(rows)
R.to_csv(f'{OUT}/Sector_Picks.csv', index=False)
pd.set_option('display.width', 250)
print(R[['Group', 'Rank', 'Symbol'] + [f'{h} CAGR %' for h in HORIZONS] + ['Since start CAGR %', 'Data since']].to_string(index=False))
print('\nflags:'); print(R[R['Data notes'] != ''][['Symbol', 'Data notes']].to_string(index=False))
