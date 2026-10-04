"""Step 17 - "v3" fund-manager score using EVERY parameter on the Ratio Cheat Sheet, then the top 10 stocks of each of NSE's
23 sectoral indices with a written rationale per stock. Independent of the account lists and of the step-12 score.
-> ../Score_v3_Nifty500.csv (every Nifty 500 stock), ../Sector_Top10_v3.csv (23 sectors x up to 10),
   ../Nifty100_v3.csv (all Nifty 100 members ranked), ../Returns_Nifty500.csv (1/3/5Y, via returns_135.py)

Method (quality-at-a-reasonable-price, the way a long-only fund manager ranks within a sector):
  * each parameter -> 0..1 from the cheat sheet's green / yellow / red zones (piecewise-linear between zone edges);
    "compare within the sector" items (margins, P/B for non-financials) blend absolute zones with the stock's sector percentile
  * pillars: Quality 28 · Growth 20 · Valuation 20 · Safety 17 · Shareholder & income 8 · Trend & liquidity 7  (= 100)
  * missing data: that parameter drops out and its pillar is re-weighted (never counted as zero)
  * financials (banks, NBFCs, insurers, AMCs): debt/equity, interest cover, EV/EBITDA, FCF and operating margin are not used; P/B uses bank zones
  * red-flag caps: loss-making 35 · repeated losses 45 · D/E > 150 or interest cover < 2 (non-financials) 45 ·
    promoter < 20% and down > 5 pts 45 · turnover < Rs 10 lakh/day 40 · P/E > 90 50
Sector membership: NSE's official constituent files for 19 indices (sector_constituents.json); Chemicals, Nifty500 Healthcare,
REITs & Realty and Cement have no published file yet and are derived from NSE sector / industry classification (flagged)."""
import json, math
import numpy as np, pandas as pd
from common import OUT, SUGGESTED, START_EMPTY

a = pd.read_csv(f'{OUT}/Nifty500_Analysis.csv')
a = a[a.Symbol.notna()].reset_index(drop=True)      # 4 REIT rows have no symbol in the analysis file - they would cross-join on merge
u = pd.read_csv(f'{OUT}/All_Scrips_NSE_BSE.csv', usecols=['Symbol', 'Avg Volume', 'Price'])
a = a.merge(u.rename(columns={'Price': 'PxU'}), on='Symbol', how='left')
p = pd.read_csv(f'{SUGGESTED}/Account_Portfolios_20+20.csv')
held = {} if START_EMPTY else dict(zip(p.Symbol, p.Account + ' · ' + p.Bucket.str.split(' (', regex=False).str[0]))   # the app fills this live
a['Sym'] = a.Symbol.str[4:]
FIN = a.Sector.eq('Financial Services')
a['Turnover (Lakh/day)'] = (a['Avg Volume'] * a['PxU'] / 1e5).round(1)
yrs3 = lambda r: ((1 + r / 100) ** (1 / 3) - 1) * 100 if pd.notna(r) and r > -100 else np.nan
yrs5 = lambda r: ((1 + r / 100) ** (1 / 5) - 1) * 100 if pd.notna(r) and r > -100 else np.nan
a['Long CAGR %'] = [yrs5(r5) if pd.notna(r5) else yrs3(r3) for r5, r3 in zip(a['Return 5y %'], a['Return 3y %'])]
pf = a['Profit yrs'].astype(str).str.split('/', expand=True)
a['ProfitYears'], a['NIYears'] = pd.to_numeric(pf[0], errors='coerce'), pd.to_numeric(pf[1], errors='coerce')


def lin(x, pts):
    """piecewise-linear score through (value, score) points; flat beyond the ends; NaN -> NaN"""
    if x is None or (isinstance(x, float) and math.isnan(x)): return np.nan
    xs, ys = zip(*pts)
    return float(np.interp(x, xs, ys))


def pct_in_sector(col, higher=True):
    r = a.groupby('Sector')[col].rank(pct=True)
    return r if higher else 1 - r + (1 / a.groupby('Sector')[col].transform('count'))


op_pct, net_pct, pb_pct, pe_pct = pct_in_sector('Operating Margin'), pct_in_sector('Net Margin'), pct_in_sector('P/B', False), pct_in_sector('P/E', False)

# parameter definitions: (pillar, name, weight, function(row, i) -> 0..1 or NaN, value shown in the rationale, unit)
P = []
def par(pillar, name, w, fn, shown, unit=''): P.append((pillar, name, w, fn, shown, unit))
# QUALITY 28
par('Quality', 'ROE 4y avg', 8, lambda r, i: lin(r['ROE % (avg 4y)'], [(5, 0), (8, .2), (10, .4), (15, .8), (20, 1)]), 'ROE % (avg 4y)', '%')
par('Quality', 'ROE latest', 4, lambda r, i: lin(r['ROE % (latest)'], [(5, 0), (8, .2), (10, .4), (15, .8), (20, 1)]), 'ROE % (latest)', '%')
par('Quality', 'ROE worst year', 3, lambda r, i: lin(r['ROE % (worst yr)'], [(0, 0), (8, .4), (12, .8), (15, 1)]), 'ROE % (worst yr)', '%')
par('Quality', 'Operating margin', 5, lambda r, i: np.nan if FIN[i] else np.nanmean([lin(r['Operating Margin'], [(5, 0), (8, .3), (20, .8), (30, 1)]), op_pct[i]]), 'Operating Margin', '%')
par('Quality', 'Net margin', 4, lambda r, i: np.nanmean([lin(r['Net Margin'], [(0, 0), (5, .2), (8, .5), (15, .9), (25, 1)]), net_pct[i]]), 'Net Margin', '%')
par('Quality', 'FCF yield', 4, lambda r, i: np.nan if FIN[i] else lin(r['FCF Yield %'], [(-2, 0), (0, .1), (2, .5), (5, 1)]), 'FCF Yield %', '%')
# GROWTH 20
par('Growth', 'Revenue CAGR', 8, lambda r, i: lin(r['Revenue CAGR %'], [(0, 0), (5, .2), (8, .5), (15, .9), (20, 1)]), 'Revenue CAGR %', '%')
par('Growth', 'Profit CAGR', 8, lambda r, i: (.75 if r['Profit CAGR %'] > 60 else lin(r['Profit CAGR %'], [(0, 0), (5, .2), (10, .5), (15, .9), (25, 1)])) if pd.notna(r['Profit CAGR %']) else np.nan, 'Profit CAGR %', '%')
par('Growth', 'Forward vs trailing P/E', 4, lambda r, i: lin(r['Forward P/E'] / r['P/E'], [(.8, 1), (.95, .8), (1, .5), (1.05, .3), (1.2, 0)]) if pd.notna(r['Forward P/E']) and pd.notna(r['P/E']) and r['P/E'] > 0 and r['Forward P/E'] > 0 else np.nan, 'Forward P/E', '')
# VALUATION 20
par('Valuation', 'PE vs sector', 6, lambda r, i: lin(r['PE vs sector'], [(.5, 1), (.8, .9), (1.2, .5), (1.5, .15), (2, 0)]), 'PE vs sector', '×')
par('Valuation', 'P/E', 3, lambda r, i: lin(r['P/E'], [(8, 1), (15, .9), (25, .65), (35, .5), (50, .15), (70, 0)]) if pd.notna(r['P/E']) and r['P/E'] > 0 else 0.0, 'P/E', '')
par('Valuation', 'PEG', 4, lambda r, i: (0.1 if r['PEG'] <= 0 else lin(r['PEG'], [(.5, 1), (1, .85), (2, .4), (3, 0)])) if pd.notna(r['PEG']) else np.nan, 'PEG', '')
par('Valuation', 'EV/EBITDA', 3, lambda r, i: np.nan if FIN[i] else lin(r['EV/EBITDA'], [(6, 1), (10, .85), (20, .45), (25, .2), (35, 0)]), 'EV/EBITDA', '×')
par('Valuation', 'P/B', 4, lambda r, i: lin(r['P/B'], [(.5, .25), (.7, .5), (1, 1), (2, 1), (3, .5), (4, .15), (6, 0)]) if FIN[i] else pb_pct[i], 'P/B', '')
# SAFETY 17
par('Safety', 'Debt/Equity', 5, lambda r, i: np.nan if FIN[i] else lin(r['Debt/Equity'], [(0, 1), (50, .9), (100, .5), (150, .15), (200, 0)]), 'Debt/Equity', '')
par('Safety', 'Interest cover', 4, lambda r, i: np.nan if FIN[i] else (lin(r['Interest Cover'], [(1, 0), (2, .3), (5, .85), (10, 1)]) if pd.notna(r['Interest Cover']) else (1.0 if pd.notna(r['Debt/Equity']) and r['Debt/Equity'] < 10 else np.nan)), 'Interest Cover', '×')
par('Safety', 'Beta', 2, lambda r, i: lin(r['Beta'], [(.6, 1), (1, .8), (1.3, .45), (1.5, .2), (2, 0)]), 'Beta', '')
par('Safety', 'Volatility', 2, lambda r, i: lin(r['Volatility %'], [(15, 1), (20, .85), (35, .45), (45, .15), (60, 0)]), 'Volatility %', '%')
par('Safety', 'Max drawdown 3y', 2, lambda r, i: lin(r['Max Drawdown 3y %'], [(-60, 0), (-50, .15), (-40, .45), (-20, .85), (-10, 1)]), 'Max Drawdown 3y %', '%')
par('Safety', 'Size (market cap)', 2, lambda r, i: lin(r['Market Cap (Cr)'], [(3000, .1), (13000, .45), (35000, .7), (100000, 1)]), 'Market Cap (Cr)', ' Cr')
# SHAREHOLDER & INCOME 8
par('Shareholder', 'Dividend yield', 3, lambda r, i: lin(r['Dividend Yield %'] if pd.notna(r['Dividend Yield %']) else 0, [(0, .3), (1, .55), (3, 1), (5, 1), (7, .6), (10, .3)]), 'Dividend Yield %', '%')
par('Shareholder', 'Payout ratio', 2, lambda r, i: lin(r['Payout Ratio'], [(0, .5), (20, 1), (60, 1), (90, .4), (110, 0)]), 'Payout Ratio', '%')
par('Shareholder', 'Promoter holding', 2, lambda r, i: np.nan if pd.notna(r['Promoter %']) and r['Promoter %'] < 1 else lin(r['Promoter %'], [(15, 0), (25, .2), (30, .45), (50, .95), (60, 1), (75, 1), (90, .75)]), 'Promoter %', '%')
par('Shareholder', 'Promoter change 1y', 1, lambda r, i: np.nan if pd.notna(r['Promoter %']) and r['Promoter %'] < 1 else lin(r['Promoter chg 1y (pp)'], [(-5, 0), (-3, .15), (-1, .6), (0, .8), (1, 1)]), 'Promoter chg 1y (pp)', ' pts')
# TREND & LIQUIDITY 7
par('Trend', 'Price vs 200-DMA', 2, lambda r, i: lin(r['Price vs 200DMA %'], [(-25, 0), (-15, .15), (-10, .35), (0, .65), (10, 1), (20, 1), (30, .6), (50, .2)]), 'Price vs 200DMA %', '%')
par('Trend', '% below 52W high', 1.5, lambda r, i: np.nan, '% Below 52W High', '%')     # filled after Quality (quality-aware)
par('Trend', 'Turnover/day', 2, lambda r, i: lin(r['Turnover (Lakh/day)'], [(10, 0), (50, .4), (100, .8), (500, 1)]), 'Turnover (Lakh/day)', ' L')
par('Trend', '3-5y CAGR', 1.5, lambda r, i: lin(r['Long CAGR %'], [(0, 0), (8, .3), (12, .6), (15, .85), (25, 1)]), 'Long CAGR %', '%')
PILLARS = {'Quality': 28, 'Growth': 20, 'Valuation': 20, 'Safety': 17, 'Shareholder': 8, 'Trend': 7}
assert abs(sum(w for _, _, w, *_ in P) - 100) < 1e-9

rows = []
for i, r in a.iterrows():
    pts = {name: fn(r, i) for _, name, _, fn, _, _ in P}
    # quality-aware 52W rule: a quality stock 20-40% off its high is a buying zone; a weak one there is just weak
    qual = np.nansum([pts[n] * w for pl, n, w, *_ in P if pl == 'Quality' and not np.isnan(pts[n])]) / max(1e-9, sum(w for pl, n, w, *_ in P if pl == 'Quality' and not np.isnan(pts[n])))
    below = r['% Below 52W High']
    pts['% below 52W high'] = lin(below, [(0, .9), (10, .8), (20, 1), (40, 1), (50, .4), (70, 0)] if qual >= .65 else [(0, 1), (10, .85), (20, .6), (40, .35), (50, .15), (70, 0)])
    pill, score = {}, 0.0
    avail_total = sum(PILLARS[pl] for pl in PILLARS if any(not np.isnan(pts[n]) for p_, n, *_ in P if p_ == pl))
    for pl, W in PILLARS.items():
        items = [(n, w) for p_, n, w, *_ in P if p_ == pl and not np.isnan(pts[n])]
        if not items: pill[pl] = np.nan; continue
        frac = sum(pts[n] * w for n, w in items) / sum(w for _, w in items)
        pill[pl] = frac * W
        score += frac * W
    score = score * 100 / avail_total if avail_total else np.nan
    # red-flag caps
    flags, cap = [], 100
    def flag(cond, txt, c):
        nonlocal_cap = None
        if cond: flags.append(txt); return c
        return 100
    loss = not (pd.notna(r['P/E']) and r['P/E'] > 0)
    cap = min(cap, flag(loss, 'loss-making (no P/E)', 35))
    cap = min(cap, flag(pd.notna(r['NIYears']) and r['NIYears'] >= 3 and r['ProfitYears'] < r['NIYears'] - 1, 'losses in more than one recent year', 45))
    cap = min(cap, flag(not FIN[i] and pd.notna(r['Debt/Equity']) and r['Debt/Equity'] > 150, f"high debt (D/E {r['Debt/Equity']:.0f})" if pd.notna(r['Debt/Equity']) else '', 45))
    cap = min(cap, flag(not FIN[i] and pd.notna(r['Interest Cover']) and r['Interest Cover'] < 2, f"weak interest cover ({r['Interest Cover']:.1f}×)" if pd.notna(r['Interest Cover']) else '', 45))
    cap = min(cap, flag(pd.notna(r['Promoter %']) and r['Promoter %'] < 20 and pd.notna(r['Promoter chg 1y (pp)']) and r['Promoter chg 1y (pp)'] < -5, 'promoter exiting', 45))
    cap = min(cap, flag(pd.notna(r['Turnover (Lakh/day)']) and r['Turnover (Lakh/day)'] < 10, 'illiquid (< Rs 10 lakh/day)', 40))
    cap = min(cap, flag(pd.notna(r['P/E']) and r['P/E'] > 90, f"very expensive (P/E {r['P/E']:.0f})" if pd.notna(r['P/E']) else '', 50))
    final = min(score, cap) if not np.isnan(score) else np.nan
    # rationale: biggest contributions and biggest misses (weight x points), with the actual values
    def fmt(n):
        col, unit = next((s_, u_) for _, nn, _, _, s_, u_ in P if nn == n)
        v = r[col]
        if pd.isna(v): return n
        if n == 'Forward vs trailing P/E': return f"forward P/E {r['Forward P/E']:.1f} vs P/E {r['P/E']:.1f}"
        v = f'{v:,.0f}' if col == 'Market Cap (Cr)' else (f'{v:.2f}' if unit in ('', '×') and abs(v) < 10 else f'{v:.1f}')
        return f'{n} {v}{unit}'
    contrib = [(n, w * pts[n], w * (1 - pts[n])) for _, n, w, *_ in P if not np.isnan(pts[n])]
    if pd.notna(r['Promoter %']) and r['Promoter %'] < 1: notes_wh = ['widely held (no promoter) - promoter checks not applicable']
    else: notes_wh = []
    strong = [fmt(n) for n, g, _ in sorted(contrib, key=lambda x: -x[1]) if pts[n] >= .8][:4]
    weak = [fmt(n) for n, _, l in sorted(contrib, key=lambda x: -x[2]) if pts[n] <= .4][:3]
    rows.append({'Symbol': r['Symbol'], 'Score v3': round(final, 1) if not np.isnan(final) else None, 'Score v3 (before caps)': round(score, 1),
                 **{f'{pl} ({W})': round(pill[pl], 1) if not np.isnan(pill[pl]) else None for pl, W in PILLARS.items()},
                 'Strengths': '; '.join(strong), 'Weaknesses': '; '.join(weak), 'Red flags': '; '.join(f for f in flags if f), 'Notes': '; '.join(notes_wh),
                 'Params used': sum(1 for _, n, *_ in P if not np.isnan(pts[n])), **{f'pt: {n}': round(pts[n], 2) if not np.isnan(pts[n]) else None for _, n, *_ in P}})
V = pd.DataFrame(rows)
keep = ['Symbol', 'Company', 'Sector', 'Industry', 'Cap Class', 'Market Cap (Cr)', 'Price', 'P/E', 'PE vs sector', 'Forward P/E', 'PEG', 'EV/EBITDA', 'P/B', 'FCF Yield %',
        'ROE % (latest)', 'ROE % (avg 4y)', 'ROE % (worst yr)', 'Operating Margin', 'Net Margin', 'Revenue CAGR %', 'Profit CAGR %', 'Debt/Equity', 'Interest Cover',
        'Beta', 'Volatility %', 'Max Drawdown 3y %', 'Dividend Yield %', 'Payout Ratio', 'Promoter %', 'Promoter chg 1y (pp)', 'Price vs 200DMA %', '% Below 52W High',
        'Turnover (Lakh/day)', 'Long CAGR %', 'Score']
A = a[keep].rename(columns={'Score': 'Score v2 (portfolio screen)', 'Long CAGR %': '3-5y CAGR %'}).merge(V, on='Symbol')
A['In your lists'] = A.Symbol.map(held).fillna('')
import returns_135                                     # 1/3/5-year price returns (cached in raw_ret_hist.json)
RET = returns_135.build(sorted(a.Sym.unique()))
A = A.merge(RET, on='Symbol', how='left')
A.sort_values('Score v3', ascending=False).to_csv(f'{OUT}/Score_v3_Nifty500.csv', index=False)

# ---- 23 sectoral indices ----
cons = json.load(open('sector_constituents.json'))
derived = {'NIFTY CHEMICALS': a.Sector.eq('Chemicals'),
           'NIFTY500 HEALTHCARE': a.Sector.eq('Healthcare'),
           'NIFTY REITS & REALTY': a.Sector.eq('Realty'),
           'NIFTY CEMENT': a.Industry.eq('Building Materials') | (a.Sector.eq('Construction Materials') & a.Company.str.contains('Cement', case=False, na=False))}
out = []
for idx, syms in cons.items():
    if syms: members, src = set(syms), 'NSE constituent file'
    else: members, src = set(a[derived[idx]].Sym), 'derived from NSE sector/industry (no constituent file published yet)'
    pool = A[A.Symbol.str[4:].isin(members)].sort_values('Score v3', ascending=False)
    missing = sorted(members - set(pool.Symbol.str[4:]))
    top = pool.head(10).copy()
    top.insert(0, 'Rank', range(1, len(top) + 1)); top.insert(0, 'Sector index', idx)
    top['Members'] = len(members); top['Members scored'] = len(pool); top['Membership source'] = src
    top['Not scored (outside Nifty 500 data)'] = ', '.join(missing)
    # why this rank: compare with the stock just above / below on pillar scores
    pl_cols = [f'{pl} ({W})' for pl, W in PILLARS.items()]
    why = []
    recs = top.to_dict('records')
    for k, rec in enumerate(recs):
        if k == 0 and len(recs) > 1:
            d = {c: (rec[c] or 0) - (recs[1][c] or 0) for c in pl_cols}
            lead = [f"{c.split(' (')[0]} {v:+.1f}" for c, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0.5][:2]
            why.append(f"#1, {rec['Score v3'] - recs[1]['Score v3']:.1f} pts ahead of {recs[1]['Symbol'][4:]}" + (f" — leads on {', '.join(lead)}" if lead else ''))
        elif k > 0:
            d = {c: (recs[k - 1][c] or 0) - (rec[c] or 0) for c in pl_cols}
            lag = [f"{c.split(' (')[0]} {v:-.1f}" for c, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0.5][:2]
            why.append(f"{rec['Score v3'] - recs[k - 1]['Score v3']:+.1f} vs #{k} {recs[k - 1]['Symbol'][4:]}" + (f" — behind on {', '.join(lag)}" if lag else ''))
        else: why.append('only scored member')
    top['Why this rank'] = why
    out.append(top)
T = pd.concat(out, ignore_index=True)
T.to_csv(f'{OUT}/Sector_Top10_v3.csv', index=False)

# ---- consolidated: one row per unique stock across all 23 lists ----
pretty = lambda n: n.title().replace('Nifty500', 'Nifty 500').replace('It ', 'IT ').replace('Psu', 'PSU').replace('Fmcg', 'FMCG').replace('Reits', 'REITs').replace('Ex-Bank', 'ex-Bank').replace(' It', ' IT')
g = T.groupby('Symbol', sort=False)
C = g.first().reset_index()
C['In sector lists'] = g.apply(lambda x: '; '.join(f"{pretty(i)} #{r}" for i, r in sorted(zip(x['Sector index'], x['Rank']), key=lambda t: t[1])), include_groups=False).values
C['Best rank'] = g['Rank'].min().values
C['Sector lists'] = g.size().values
drop = ['Sector index', 'Rank', 'Members', 'Members scored', 'Membership source', 'Not scored (outside Nifty 500 data)', 'Why this rank'] + [c for c in C.columns if c.startswith('pt: ')]
C = C.drop(columns=[c for c in drop if c in C.columns]).sort_values('Score v3', ascending=False)
lead = ['Symbol', 'Company', 'Sector', 'Cap Class', 'Score v3', '1Y %', '3Y %', '5Y %', '3Y CAGR %', '5Y CAGR %', 'In sector lists', 'Best rank', 'Sector lists', 'In your lists']
C = C[lead + [c for c in C.columns if c not in lead]]
C.insert(0, 'Overall rank', range(1, len(C) + 1))
print(f'{len(C)} unique stocks across {len(T)} sector-list rows (used for the Nifty 100 "In sector lists" column)')

# ---- Nifty 100: all members ranked on the same v3 score, same reasons, plus the sector lists they appear in ----
n100 = set(pd.read_csv('nifty100.csv')['Symbol'].str.strip())
N = A[A.Symbol.str[4:].isin(n100)].sort_values('Score v3', ascending=False).reset_index(drop=True)
N.insert(0, 'Rank', range(1, len(N) + 1))
pl_cols = [f'{pl} ({W})' for pl, W in PILLARS.items()]
recs, why = N.to_dict('records'), []
for k, rec in enumerate(recs):
    if k == 0:
        d = {c: (rec[c] or 0) - (recs[1][c] or 0) for c in pl_cols}
        lead = [f"{c.split(' (')[0]} {v:+.1f}" for c, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0.5][:2]
        why.append(f"#1 of Nifty 100, {rec['Score v3'] - recs[1]['Score v3']:.1f} pts ahead of {recs[1]['Symbol'][4:]}" + (f" — leads on {', '.join(lead)}" if lead else ''))
    else:
        d = {c: (recs[k - 1][c] or 0) - (rec[c] or 0) for c in pl_cols}
        lag = [f"{c.split(' (')[0]} {v:-.1f}" for c, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0.5][:2]
        why.append(f"{rec['Score v3'] - recs[k - 1]['Score v3']:+.1f} vs #{k} {recs[k - 1]['Symbol'][4:]}" + (f" — behind on {', '.join(lag)}" if lag else ''))
N['Why this rank'] = why
lists = dict(zip(C.Symbol, C['In sector lists'])); nlists = dict(zip(C.Symbol, C['Sector lists']))
N['In sector lists'] = N.Symbol.map(lists).fillna(''); N['Sector lists'] = N.Symbol.map(nlists).fillna(0).astype(int)
N = N[[c for c in N.columns if not c.startswith('pt: ')]]
N.to_csv(f'{OUT}/Nifty100_v3.csv', index=False)
missing100 = sorted(n100 - set(N.Symbol.str[4:]))
print(f'nifty 100: {len(N)} ranked' + (f'; not scored (no fundamentals): {missing100}' if missing100 else ''))
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 120)
for idx, g in T.groupby('Sector index', sort=False):
    print(f"\n### {idx}  ({g['Members'].iloc[0]} members, {g['Members scored'].iloc[0]} scored)")
    for r in g.to_dict('records'):
        print(f"{r['Rank']:2}. {r['Symbol'][4:]:11} v3 {r['Score v3']:5} (v2 {r['Score v2 (portfolio screen)']}) | {r['Why this rank']} | + {r['Strengths']} | - {r['Weaknesses']} | ! {r['Red flags']}")
