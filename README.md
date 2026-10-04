# Broking-Data

A reproducible pipeline that builds a database of **every Indian listed instrument except F&O**, screens the Nifty 500 for quality, and splits a portfolio across **3 broking accounts: PEW-Angel, JPW-Angel and JPW-Zerodha**. Each account gets 20 Active stocks, 20 To Invest stocks and 9 ETF/SGB holdings. The account lists can be edited in a self-contained HTML app (`Portfolio_Manager.html`) and downloaded as CSVs.

> **For AI agents:** read "Quick start" and "Gotchas" before running anything. Every step is idempotent and resumable. The repo already contains the fetched raw data (as of 1–2 Oct 2026), so `./run_all.sh` rebuilds all deliverables **offline in about 30 seconds**. Re-fetching from the internet is only needed to refresh the data.

---

## 1. Quick start

```bash
cd Broking-Data
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python 3.11+ (tested on 3.14, macOS)
./run_all.sh                 # rebuild deliverables from data already in pipeline/  (offline, ~30 s)
./run_all.sh --refresh       # download the latest exchange files + re-fetch everything (~1-1.5 h), then rebuild
./run_all.sh --resume        # finish an interrupted or throttled fetch without starting over, then rebuild
open Portfolio_Manager.html  # or double-click it; on Windows: start Portfolio_Manager.html
```

`run_all.sh` uses `$PYTHON` if set, then `.venv/bin/python`, then `python3`. On Windows without bash, run the step scripts in `pipeline/` one by one in numeric order (see §4).

**Verify a run** (do this after any change):
1. Every step prints no traceback. Step 18 prints `… 5097 scrips, 55 columns, 147 assigned …`, and step 14 prints the backtest return tables. The counts can change slightly after `--refresh`.
2. Open `Portfolio_Manager.html#selftest` in a browser. It should show `PASS` on all 53 lines and no `FAIL`. For a headless check:
   `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --virtual-time-budget=8000 --dump-dom "file://$PWD/Portfolio_Manager.html#selftest" | grep -c PASS` should print `53`.
   Chrome can hang after dumping, so wrap it in a timeout, for example `perl -e 'alarm 40; exec @ARGV' chrome …`.
3. `Account_Portfolios_20+20.csv` should have 120 rows: 3 accounts × (20 + 20), with 8 Large, 6 Mid and 6 Small in every list. `ETF_SGB_Per_Account.csv` should have 27 rows: 3 × 9.

---

## 2. Deliverables (repo root)

| File | Rows | What it is |
|---|---|---|
| `Portfolio_Manager.html` | – | Offline app for browsing all scrips and editing the 3 accounts. Downloads account-wise CSVs or a ZIP. See §6. |
| `All_Scrips_NSE_BSE.csv` | 5,097 | The universe: NSE-listed equities (2,594, with BSE codes when dual-listed), BSE-only equities (2,023, incl. 411 SME), NSE ETFs (351) + BSE-only ETFs/funds (8), SGB (44), G-Sec (55), REIT (6), InvIT (16). |
| `Nifty500_Analysis.csv` | ~501 | Deep dive and screen on the Nifty 500. Covers multi-year growth, ROE consistency, margins, leverage, cash flow, promoter holding, returns, a 0–100 score with sub-scores, the reason a stock was filtered out, and a `Selected` flag. |
| `Suggested_Lists_Backup/Account_Portfolios_20+20.csv` | 120 | Stock picks: `Account` (`PEW-Angel`, `JPW-Angel`, `JPW-Zerodha`) × `Bucket` (`Active (20)` / `To Invest (20)`). |
| `Suggested_Lists_Backup/ETF_SGB_Per_Account.csv` | 27 | ETF/SGB holdings: 9 slots per account, with no fund repeated across accounts. |
| `Backtest_Summary.csv` / `Backtest_Holdings.csv` / `Backtest_Daily.csv` | 50 / 735 / ~3,700 | What-if backtest over **1, 2, 3, 4 and 5 years**, all ending on the 1 Oct 2026 close. ₹50,000 goes into each of the 40 stocks per account (₹20 L) and, separately, each of its 9 ETF/SGB holdings (₹4.5 L), compared with Nifty 50 and Nifty 500. The files give total return and CAGR per account, portfolio and horizon, every holding × horizon, and daily wealth indexed to 100. |
| `Sector_Returns.csv` | 121 | Every live NSE equity index: 23 sectoral, 41 thematic (Defence, Railways PSU, CPSE, PSE, Capital Markets, EV, Digital, Tourism, SME Emerge and more), 21 broad-market and 36 strategy/factor indices, plus the Sensex. Gives CAGR and total return over 1, 2, 3, 5, 10, 15, 20, 25 and 30 years to 1 Oct 2026, with data-start date and since-inception CAGR. These are price indices, so dividends are excluded. Independent of the account lists. |
| `Sector_Picks.csv` | 40 | Top 10 screened stocks in Metals & Mining, Pharma, Healthcare services and PSU Banks, ranked by the portfolio screen, with every fundamental and score. Gives returns over 1–30 years (price-only and with dividends reinvested), data start, and data notes. Read-only with respect to the account lists. |
| `Score_v3_Nifty500.csv` / `Sector_Top10_v3.csv` | 497 / 224 | **v3 fund-manager score** built from all 28 cheat-sheet parameters (zone-graded, sector-aware, with red-flag caps), and the top 10 of each of NSE's 23 sectoral indices. Each stock gets its pillar points, strengths, weaknesses, red flags and a "why this rank" note. Independent of the account lists and the step-12 score. |
| `Nifty100_v3.csv` | 100 | Every Nifty 100 member (NSE's official list, `pipeline/nifty100.csv`) ranked by the same v3 score, with the same columns and reasons as Sector Top 10, plus the sector top-10 lists it appears in. |
| `Returns_Nifty500.csv` | 497 | 1/3/5-year price returns and CAGR for every Nifty 500 stock, on the same dates as the other tabs. Used by step 17 and fed into every HTML table. |
| `Ratio_Cheat_Sheet.html` / `.pdf` | – | Hand-written one-page reference for 28 fundamental ratios: meaning, which direction is better, good/okay/check zones and examples. The PDF prints on one A4 landscape page. Step 18 also embeds it as the **Ratio Cheat Sheet** tab, isolated in a shadow root; edit the .html file and rebuild to update both. |

Main universe columns: `Symbol` (`NSE:XXX` or `BSE:XXX`), `Company`, `Instrument Type`, `Exchange` (`NSE`, `NSE+BSE`, `BSE`), `BSE Code`, `ISIN`, `Series`, `Sector`, `Industry`, `Cap Class`, `Market Cap (Cr)`, `Price`, `P/E`, `P/B`, `52W High/Low`, `% Below 52W High`, `Dividend/Share (annual)`, `Dividend Yield %`, `ROE %`, `Debt/Equity`, `Return 1y/3y/5y %`, `Volatility %`, `Max Drawdown 3y %`, `Avg Volume`, `Turnover Last Day (Lakh)` and `Nifty500` (Y/blank). Money is in ₹ and market cap is in ₹ crore.

---

## 2b. Clean slate (since 4 Oct 2026)

- **The app starts with all three accounts empty.** You add stocks yourself, from any tab or stock popup.
- **The original suggestions are backed up** in `Suggested_Lists_Backup/` (see its README). Steps 12–13 keep writing them there, and the Backtest tab still runs on them.
- **One switch controls this:** `START_EMPTY` in `pipeline/common.py`. Set it to False and run `./run_all.sh` to start pre-filled again.
- **"In your lists" columns are live:** in Sector Top 10, Nifty 100, Sector Picks and Compare they reflect what is in the accounts now.
- **Old browser edits are not carried over:** a saved browser state made against a different starting list (`baseline`) has its assignments dropped and a notice shown. Column, freeze and Compare preferences are kept. Use **State ▾ → Save/Load state** to move your own lists between devices.

## 3. Folder layout

```
Broking-Data/
├── README.md, requirements.txt, run_all.sh, .gitignore
├── *.csv, Portfolio_Manager.html          ← deliverables (generated)
└── pipeline/
    ├── common.py                          ← account names (ACCOUNTS), paths (OUT = repo root, chdir to pipeline/), resumable Yahoo runner, shared Yahoo fetch
    ├── 00_download_inputs.py … 05_*.py    ← data acquisition (network)
    ├── 10_build_nse_base.py … 15_*.py     ← transforms, selection, backtest and HTML (offline once the caches exist)
    ├── portfolio_template.html            ← source of the HTML app (step 18 injects data at /*DATA*/)
    ├── EQUITY_L.csv, n500.csv, etf.csv    ← NSE masters            (step 00)
    ├── nse_bhav.csv, bse_bhav.csv         ← latest daily bhavcopies (step 00)
    ├── bse_all.csv, bse_only.csv          ← BSE equities / BSE-only (step 00)
    ├── inputs_meta.json                   ← bhavcopy dates (shown in the HTML as "market data as of")
    ├── raw.json, raw2.json, raw3.json,    ← fetched API data (steps 01-05); committed so rebuilds work offline
    │   raw_other.json, raw_bse2.json
    └── All_NSE_Scrips_Data.csv            ← intermediate (step 10 → step 12)
```

All scripts locate themselves through `common.py`, so they run from any working directory. There are no hardcoded user paths and no credentials.

---

## 4. Pipeline steps

| Step | Source | Output | Time | Notes |
|---|---|---|---|---|
| `00_download_inputs.py` | NSE archives, BSE download site | masters, `nse_bhav.csv`, `bse_bhav.csv`, `bse_all/only.csv`, `inputs_meta.json` | <1 min | Walks back from today to the newest *complete* bhavcopy. Holidays produce tiny stub files, which are skipped by size. |
| `01_fetch_nse_equities.py` | Yahoo `.info` (`SYMBOL.NS`) | `raw.json` | 20–40 min | ~2,600 symbols, Nifty 500 first. |
| `02_fetch_nifty500_deep.py` | Yahoo `.info` + income statement, balance sheet, cash flow, dividends, 5y price history | `raw2.json` | 10–20 min | Computes CAGR, ROE avg/min, interest cover, cash conversion, FCF years, dividend history, returns, volatility, drawdown. |
| `03_fetch_nse_promoter.py` | NSE `/api/corporate-share-holdings-master` | `raw3.json` | ~5 min | Promoter % for the last 6 quarters. Needs NSE cookies, which the script handles. |
| `04_fetch_etf_reit_invit.py` | Yahoo | `raw_other.json` | ~5 min | ETFs, REITs and InvITs. |
| `05_fetch_bse_only.py` | Yahoo (`TICKERNAME.BO`) | `raw_bse2.json` | ~5 min | Only BSE-only equities with turnover above ₹10 lakh on the bhavcopy day (~470). The rest keep bhavcopy price and turnover only. |
| `10_build_nse_base.py` | raw.json + masters | `pipeline/All_NSE_Scrips_Data.csv` | s | Cap class by market-cap rank. |
| `11_build_universe.py` | everything above | `All_Scrips_NSE_BSE.csv` | s | Merges REITs/InvITs that are also in the Nifty 500 into a single row. |
| `12_build_screen_and_picks.py` | step 10 CSV + raw2/raw3 | `Nifty500_Analysis.csv`, `Account_Portfolios_20+20.csv` | s | **Regenerates the stock picks** (§5). |
| `13_build_etf_lists.py` | universe | `ETF_SGB_Per_Account.csv` | s | Fixed `PICKS` table. Missing symbols are skipped with a warning. |
| `14_backtest.py` | Yahoo daily history since Sep 2021 for the 147 holdings + ^NSEI/^CRSLDX (cached in `raw_hist5.json`) | `Backtest_Summary.csv`, `Backtest_Holdings.csv`, `Backtest_Daily.csv` | ~5 min first run, then seconds | See §5b. Change `END_DATE`, `PER_HOLDING` or `HORIZONS` at the top. Asserts that each daily wealth path ends exactly on its summary. |
| `18_build_html.py` | universe + analysis + pick CSVs + backtest CSVs + template | `Portfolio_Manager.html` | s | Asserts that symbols are unique and every picked symbol exists. The Backtest tab is hidden if the step 14 files are missing. |
| `15_sector_returns.py` | NSE `api/allIndices` (index list, cached in `nse_all_indices.json`) and `api/historicalOR/indicesHistory` (cookie session; cached in `raw_sector2.json`); Sensex from Yahoo | `Sector_Returns.csv` | ~8 min first run, then seconds | Fetches levels around 1 Oct of each start year, stopping at the first horizon an index doesn't reach, then finds its data start. NSE's API serves only recent history for many young indices; those earlier years are often back-calculated anyway. |
| `16_sector_picks.py` | `Nifty500_Analysis.csv` + Yahoo full daily history (`period=max`; trimmed cache `raw_picks_hist.json`) | `Sector_Picks.csv` | ~2 min first run | Uses Close for price returns and Adj Close for returns with dividends. Fixes partially-adjusted splits. One-day moves that don't revert within 5 sessions are breaks if they are −45% or worse (unadjusted bonus) or above +50% (bad data/demerger); any horizon spanning a break is blanked, as with HINDZINC's pre-listing data, VEDL's 2026 demerger and JSL's 2015 restructuring. Smaller genuine moves, such as PNB's +46% recap rally, are kept. Yahoo's NSE history mostly starts in 2002, so stock 25–30Y figures are usually blank. |
| `17_sector_top10_v3.py` | `Nifty500_Analysis.csv` + universe turnover + NSE constituent files (`sector_constituents.json`; 19 official, 4 derived) | `Score_v3_Nifty500.csv`, `Sector_Top10_v3.csv` | seconds | Pillars: Quality 28, Growth 20, Valuation 20, Safety 17, Shareholder 8, Trend 7. Missing data is re-weighted, never scored as zero. Financials skip D/E, interest cover, EV/EBITDA, FCF and operating margin. Widely-held companies skip the promoter checks. Caps: loss 35, repeated losses 45, D/E>150 or interest cover<2 45, promoter exiting 45, illiquid 40, P/E>90 50. Drops the 4 symbol-less REIT rows from the analysis file. |
| `returns_135.py` (called by step 17) | Yahoo daily closes since Sep 2021 (trimmed cache `raw_ret_hist.json`) | `Returns_Nifty500.csv` | ~10 min first run | Corrects partially-adjusted splits and blanks any horizon spanning an unadjusted break, as in step 16. Extreme returns (Cupid ~75× over 3Y, Sterlite Tech +686% over 1Y) were cross-checked against an independent download and NSE closing prices. |

All fetch steps are **resumable**. Re-running one fetches only symbols that are missing or failed. To force a full re-fetch, delete the matching `raw*.json`; `run_all.sh --refresh` does this for all of them.

---

## 5. Methodology

**Cap class** is computed, not the official AMFI list. NSE equities are ranked by Yahoo market cap: 1–100 Large, 101–250 Mid, 251–500 Small, the rest Micro. BSE-only scrips use the market-cap cutoffs of those ranks, which were about ₹1,05,886 / ₹34,965 / ₹13,180 Cr in Oct 2026. Equity ETFs are classed from their index name (Nifty 50 → Large, Midcap → Mid, Smallcap → Small).

**Sector** is NSE's macro sector from the Nifty 500 list (about 21 sectors). Elsewhere it is Yahoo's sector mapped to similar names. ETFs show `ETF · Equity`, `ETF · Commodity`, `ETF · Debt` and so on.

**Screen (step 12, Nifty 500 only).** A stock is rejected (`Filtered Out Because`) if any of these hold:
- illiquid or no data (average volume below 100k)
- losses in more than one of the last 3–4 years
- no P/E (loss-making)
- P/E above 90
- average 4-year ROE below 8%
- promoter holding below 20% *and* down more than 5 points in a year
- micro cap, or small cap below ₹3,000 Cr

Non-financials are also rejected for:
- debt/equity above 150
- interest cover below 2
- no positive free cash flow in any year

Financial Services stocks skip the debt, interest-cover and cash-flow tests and are judged on P/B instead.

**Score (0–100)** is built from percentile ranks: quality 35%, safety 20%, value 20%, income 10%, trend 15%.
- Quality: ROE avg and min, operating margin, revenue and profit CAGR.
- Safety: D/E, interest cover, cash conversion, FCF yield, promoter level and trend, drawdown, beta.
- Value: P/E against the sector median, PEG, distance from the 52-week high, P/B for financials.
- Income: dividend yield, years paid, payout below 90%, dividend growth.
- Trend: 1y and 3y return, price above the 200-day average.

**Selection.**
- Quota: 48 Large, 36 Mid and 36 Small stocks, chosen sector by sector with weights `W` (Financial Services 6; IT, Healthcare, FMCG, Auto and Capital Goods 3 each; most others 1–2). The best-scoring stock in each sector is taken first.
- Dealing into 6 lists (3 accounts × Active/To Invest): each list holds exactly 8 L, 6 M and 6 S (`CAPN`). Every stock goes to the list holding the fewest stocks of its sector, with ties broken by the lowest total score so quality stays balanced.
- Result: each list covers 15 sectors and each account 16–17, with no stock in two places.

**ETF/SGB holdings (step 13).** The same 9 slots in each account, each filled by a different fund: Nifty 50, Midcap, Smallcap, Gold, Silver, International, Sector, Liquid and SGB. Funds were ranked by last-day turnover. Series with data glitches were excluded (SILVER1, SETFGOLD, BSLNIFTY, TATSILV).

**Account names.** These are defined once, in `ACCOUNTS` in `pipeline/common.py`: `{1: 'PEW-Angel', 2: 'JPW-Angel', 3: 'JPW-Zerodha'}`. Steps 12–14 and the HTML read the names from there, so to rename an account, change that dict and run `./run_all.sh`. Internally the HTML stores account **ids 1–3**, so saved browser edits survive a rename. Account-wise downloads are named after the account, for example `PEW-Angel_Portfolio_<date>.csv`.

**Tuning knobs.**
- Step 12: the `rej(...)` filter lines, the score weights in `P['Score'] = …`, the quotas `{'Large': 48, 'Mid': 36, 'Small': 36}`, `CAPN`, and the sector weights `W`.
- Step 13: `PICKS`.
- `portfolio_template.html`: the default visible columns `DEF_ALL` and `DEF_ACC`.

---

## 5b. Backtest method (step 14)

- **Scenario:** each account's 40 stocks, and separately its 9 ETF/SGB holdings, get ₹50,000 each on the first trading day on or after 1 October of 2025, 2024, 2023, 2022 or 2021 (1Y–5Y). They are held untouched and valued at the latest close (1 Oct 2026).
- **Per holding:**
  - quantity = floor(50,000 ÷ buy close), whole shares; the leftover stays as cash
  - value = quantity × latest close; dividends (per share × quantity on each ex-date) are kept as cash
  - final = value + dividends + cash; return = final ÷ 50,000 − 1; CAGR = (final ÷ 50,000)^(1/years) − 1
- **Portfolio:** the sum of holdings' final wealth. Holding contributions (P&L ÷ portfolio capital) add up to the portfolio return.
- **Benchmarks:** the Nifty 50 and Nifty 500 **price** indices, which exclude dividends of about 1–1.5% a year.
- **Not yet listed at the start** (per NSE's listing date): cash until the first close, then buy. **Yahoo data gaps:** filled from a same-index ETF. **No data (SGB):** held as cash.
- **Not modelled:** taxes, brokerage, STT, stamp duty, reinvestment, or interest on cash.
- **Strong bias warning:** the lists were picked with 2026 data from companies that are large today, which is look-ahead and survivorship bias. Long-horizon results are therefore heavily flattered. The HTML repeats this warning.

## 6. Portfolio_Manager.html

The HTML is a single offline file. The data is embedded as JSON, it has no external dependencies, and it works over `file://`.

- **Tabs:**
  - **All Scrips:** the whole universe, with an Assigned badge or a `＋ Assign` button.
  - **Board:** the 3 accounts side by side, with drag and drop between accounts and lists.
  - **PEW-Angel / JPW-Angel / JPW-Zerodha:** one tab per account, with summary cards per list (count against an editable target, the large/mid/small split, sectors), plus Add/Move/Remove.
  - **Changes:** differences from the lists the file was built with, each with a Revert button.
- **Frozen columns:** every table pins its identifying column (Symbol, or Index on Sectors) while you scroll sideways. **📌 Freeze ▾** lets you freeze up to any column, or none, and the choice is remembered per table. The default freeze is skipped below 720px width. Implemented as `T.applyFreeze()` in the template using per-table sticky CSS.
- **Tables:** global multi-word search, sort by clicking a header, a filter per column, a column picker over all 55 fields, pagination, multi-select with bulk Assign/Remove, and **Export view**. Column filters work as follows:
  - text columns match "contains"
  - category columns use a dropdown
  - number columns accept `>20`, `<=15`, `10..30`, `5-15` or `blank`
- **Better-direction marks** in every column header: green **↑** (higher is better), green **↓** (lower is better), or amber **~** (depends). The sort control is the separate grey **⇅**, which becomes a blue ▲ or ▼ when sorted.
- **ⓘ glossary:** an info icon next to every column header, popup label, Columns-picker entry and summary metric. Hover or focus it for a tooltip; click or tap to pin it. Each entry gives:
  - the meaning in plain English
  - **which direction is better** (↑ higher, ↓ lower, or ↕ depends)
  - a rule-of-thumb ideal range for Indian markets

  The text lives in the `GL` object in `portfolio_template.html`. Every column must have an entry, and the self-test enforces it.
- **Backtest tab:**
  - a horizon switch (1Y–5Y) and a returns-across-horizons matrix (total return or CAGR) for each account's stocks and ETF/SGB holdings, against Nifty 50 and 500
  - headline tiles and per-account cards: return, CAGR, gap to the Nifty, Active vs To Invest, dividends, best/worst
  - a "growth of ₹100" line chart with hover and keyboard crosshair, with an option to show the ETF lines
  - breakdowns by account and list, cap and sector
  - a sortable, filterable table of every holding (click a row for the stock popup)
  - a full "How it was calculated" section with a worked example and per-horizon data notes
  - CSV downloads

  It shows the lists as built; edits made in the app aren't backtested.
- **★ Stars and Shortlist tab:**
  - ☆ appears beside every stock: All Scrips, account tabs, Sector Top 10, Nifty 100, Sector Picks, Backtest, the Compare header and the stock popup. One click shortlists it.
  - The **★ Shortlist** tab lists the starred stocks, sorted by v3 score, with tiles showing how many are already in each account.
  - From there you can tick stocks and **Assign to…** to divide them into PEW-Angel, JPW-Angel or JPW-Zerodha (Active / To Invest / ETF·SGB), send up to 10 to **⚖ Compare**, **Unstar** them, or clear the list (click twice to confirm).
  - Stars are stored in `S.stars`. They survive the clean-slate baseline switch and are included in State ▾ save/load.
- **Compare tab:** pick 2–10 stocks (search box, **⚖ Compare** in any stock popup, or from ★ Shortlist) and see them side by side on every calculated field:
  - overview and account/list membership
  - v3 score and the six pillars, plus the v2 score
  - 1/3/5Y returns and CAGR
  - all valuation, profitability, growth, safety, dividend and ownership fields
  - v3 strengths, weaknesses and red flags, and all 28 per-parameter grades

  ★ marks the best value in each row, using the cheat-sheet direction, and a best-in-row count sums it up. CSV export is available, and the selection is saved in `S.cmp`. Step 18 embeds `Score_v3_Nifty500.csv` for this.
- **Nifty 100 tab:** all 100 members ranked by v3 score. Summary tiles show the 80+ count, red-flagged count, how many you hold, and the average 1/3/5Y against the Nifty 100 index. Same columns and reasons as Sector Top 10, plus ×n sector-list badges.
- **Sector Top 10 tab:**
  - a picker for any of the 23 NSE sectoral indices, showing its top 10 by v3 score with 1/3/5Y returns; **All sectors** shows each stock once, with a ×n badge and its best placement
  - for each stock: why it ranks there, strengths and weaknesses with real values, red flags, and points per pillar
  - the full method, a CSV download, and a click on a stock opens its popup
- **Sector Picks tab:**
  - the 40 focus-sector stocks, grouped, with each group's sector index row for comparison
  - a group snapshot comparing the index CAGR with the median stock
  - toggles for CAGR or total return, and price-only or with dividends
  - every screen field available through Columns ▾, and a click on a stock opens its popup
- **Sectors tab:**
  - all 121 NSE indices, filterable by Sectors, Themes, Broad market or Strategy, showing CAGR or total return
  - a leaders-and-laggards bar chart for any horizon (1Y–30Y or since start), with Nifty 50 and 500 reference lines
  - a sortable table of every horizon, with cells shaded by CAGR
  - notes on the data, and a CSV download
- **Stock detail popup:** click any row, Board chip or Changes row to open it. It shows:
  - which account and list the stock is in, with **Move…** and **Remove** buttons
  - key tiles: price, market cap, P/E against the sector median, dividend yield, ROE, 1-year return and score
  - a 52-week range bar
  - every non-blank field, grouped
  - score sub-bars, and the Nifty 500 screen verdict with the filter-out reason
  - links to the NSE quote, Screener, TradingView and Google Finance

  Use ‹ › or the ← → keys to step through the current filtered view, and Esc to close. The popup refreshes live after a move, remove or undo.
- **Assign grid:** 3 accounts × 3 lists (`Active`, `To Invest`, `ETF / SGB`), with live counts and targets. A scrip lives in at most one account, so assigning it again moves it.
- **Add scrip:** search the universe, or add a custom scrip that isn't in the data. The custom scrip is stored with your state.
- **Undo/redo:** header buttons, Cmd/Ctrl+Z and Shift+Cmd/Ctrl+Z, and the toast after each change.
- **Downloads (⬇ Download CSVs):**
  - one CSV per account
  - a combined CSV
  - a ZIP of all of them (written by an in-page zip implementation, validated with `unzip -t`)

  Each CSV has `Account` and `List` columns plus every data column, and a UTF-8 BOM so Excel opens it cleanly.
- **Persistence:** edits auto-save to `localStorage` under the key `portfolio-manager-v1`, separately for each browser and file location. **State ▾** offers:
  - Save state to `.json` and Load it back, for moving edits to another device or browser
  - Reset to the original lists
  - Light/dark toggle
- **URL hashes:** `#tab=a1|a2|a3|board|chg|bt|sec|picks|top10|n100|star|cmp|cheat|all` opens a tab, and `#scrip=MARUTI` (or `NSE:MARUTI`) opens a stock's popup; combine them as `#tab=a1&scrip=MARUTI`. `#selftest` runs 53 checks without touching saved state, then prints PASS/FAIL and a base64 ZIP for verification.
- **Rebuilding** (step 18) replaces the embedded data and the "original" lists. Saved browser edits still load, with any symbols no longer in the universe dropped. Save state to a file before a big refresh.

---

## 7. Gotchas: data access

- **Yahoo Finance (yfinance) rate-limits aggressively.** Running more than 3 parallel workers, or several jobs at once, leads to `401 Invalid Crumb`, `User is unable to access this feature` or `429`. Nearly every call then fails for 5–30 minutes. `common.run_resumable` therefore:
  - uses 2–3 workers with a 0.4 s pause
  - probes before starting and waits 3 minutes at a time while throttled
  - cools down 4 minutes after 10 consecutive failures

  **Never run two fetch steps at the same time.**
- **BSE on Yahoo** uses ticker names (`ABB.BO`), not numeric scrip codes (`500002.BO` returns nothing).
- **Yahoo value quirks:**
  - `dividendYield` is already a percentage.
  - Some numeric fields arrive as strings such as `"Infinity"`; builds coerce them with `pd.to_numeric(errors='coerce')`.
  - Equity cash-flow and dividend data is patchy.
  - Some ETFs have unadjusted splits, which shows up as absurd volatility or returns.
  - A 5-year history is often just under 1,250 trading days, so `Return 5y %` is frequently blank.
  - AUM and expense ratio are not available for Indian ETFs.
- **NSE:** the `nsearchives.nseindia.com` files need only a browser User-Agent. `www.nseindia.com/api/*` needs cookies from visiting the homepage first, and the session must be re-created on errors. Keep the request rate low.
- **BSE:**
  - `api.bseindia.com` (the scrip-list API) returns **403 to scripts**. The daily bhavcopy CSV at `/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_YYYYMMDD_F_0000.CSV` works after a session visit to the homepage.
  - The bhavcopy covers only scrips that traded that day.
  - **ISIN characters 8–9 = `01`** marks equity shares; other values are debentures, warrants and so on.
  - BSE series: `X`/`XT` trade-for-trade, `M`/`MT`/`MS` SME, `F` ETFs/funds, `G` government securities.
- **NSE bhavcopy series used:** `EQ`/`BE`/`BZ`/`SM`/`ST` equities and SME, `GB` SGB, `GS` G-Sec, `RR` REIT, `IV` InvIT.
- **Yahoo split adjustment can be partial.** TRENT's history was ×1.5-adjusted only from Jan 2026 onward, which produced a fake −33% day. Step 14 corrects a one-day jump only if it matches a split ratio Yahoo records and falls within a year *before* that split's date. A looser rule once mistook REC's real −25% election-day crash (4 Jun 2024) for an unadjusted bonus. The screen's `Return 1y %` (step 02) does **not** get this fix yet.
- **Yahoo history can start years after listing** (MID150BEES has only 2 weeks; GOLDIETF, MIDCAPETF, HDFCSILVER and SILVERIETF start late). Step 14 uses NSE's official listing dates to tell these apart from real late listings, and fills the missing stretch from a same-index ETF (`PROXY` map). SGBs have no Yahoo data at all and are held as cash.
- **REITs in the Nifty 500** (Embassy, Brookfield, Bagmane) would appear twice. Step 11 merges them into one REIT row.

---

## 8. Known limitations

- **Not investment advice.** Picks come from a mechanical screen on one data snapshot, so verify each one. A few values look wrong (for example ZFCVINDIA P/E 2.5, probably a one-off gain).
- **Promoter pledge** isn't covered. It sits inside NSE's XBRL filings and isn't parsed. Promoter % comes from NSE's summary API; Yahoo's `heldPercentInsiders` is only a proxy.
- **BSE-only equities:** about 1,600 illiquid ones have bhavcopy price and turnover only, with no fundamentals. Only NSDL (Small) and the NSE exchange stock (Large) qualified by size, and neither has the multi-year data the screen needs, so neither is in the picks.
- **SGB:** price and volume only. The premium or discount to gold isn't computed.
- **Cap classes** are computed from market-cap rank, not the official AMFI semi-annual list.

---

## 9. Angel One SmartAPI (not used)

An attempt was made to use the owner's Angel One SmartAPI subscription for prices. Credentials lived in a separate private repo (`TradingRecords_Angel/data/config.json`, git-ignored), never in this project. Login with a code-generated TOTP worked, but every data endpoint returned `Invalid API Key` (Oct 2026). The likely causes are an expired key or a static-IP requirement. The project runs entirely without Angel. If it's revived, use SmartAPI only for quotes, 52-week range and OHLC; it has no fundamentals. Read credentials from that config at runtime, and never copy them here.

---

## 10. History

- 2026-10-04: added ☆ stars on every stock, a ★ Shortlist tab (assign, compare and unstar in bulk), and raised Compare to 10 stocks (fixed-width columns above 3 stocks).
- 2026-10-04: **clean slate.** The app's accounts start empty and the original suggestions moved to `Suggested_Lists_Backup/` (`START_EMPTY` in common.py). "In your lists" columns are now live. The Compare selection now persists.
- 2026-10-04: added a Compare tab (2–4 stocks, every parameter, best-in-row ★) and a ⚖ Compare button in the stock popup.
- 2026-10-04: removed the Top Picks tab (Sector Top 10 → All sectors already shows the unique list with ×n badges).
- 2026-10-04: added a Nifty 100 tab (all members ranked by v3, step 17 → `Nifty100_v3.csv`).
- 2026-10-04: added the Top Picks consolidated page, 1/3/5Y returns in every list (All Scrips, account tabs, Sector Top 10, Top Picks), and unique stocks with ×n badges in Sector Top 10 → All.
- 2026-10-04: added the v3 fund-manager score (all 28 cheat-sheet parameters) and the top 10 for each of the 23 NSE sectors (step 17, plus a Sector Top 10 tab). The HTML build is now step 18.
- 2026-10-04: added the Ratio Cheat Sheet (HTML, a one-page PDF, and a tab in the app).
- 2026-10-03: frozen columns (sticky left) on every table, with a 📌 Freeze picker.
- 2026-10-03: added a **Sector Picks** tab and step 16: top 10 screened stocks in Metals, Pharma, Healthcare and PSU Banks, with 1–30Y returns. The HTML build is now step 17.
- 2026-10-03: added returns for all 121 NSE indices over 1–30 years (step 15, `Sector_Returns.csv`) and a **Sectors** tab. The HTML build is now step 16.
- 2026-10-03: added the multi-horizon backtest (1–5Y, stocks and ETF/SGB against Nifty 50/500) as step 14, and a **Backtest** tab in the HTML. The HTML build is now step 16. Also added better-direction arrows in the headers.
- 2026-10-03: added ⓘ glossary tooltips (meaning, better-direction and ideal range) for every field.
- 2026-10-03: added the stock detail popup (row, chip or Changes click; `#scrip=` deep link).
- 2026-10-03: accounts renamed to PEW-Angel (1), JPW-Angel (2) and JPW-Zerodha (3) throughout: CSVs, HTML and downloads. The picks are unchanged.
- 2026-10-03: first build. NSE universe and v1 screen, then v2 deep dive (multi-year financials, NSE promoter data), then BSE-only scrips, ETFs, SGB, REIT/InvIT and G-Sec, then the ETF/SGB holdings per account and the HTML manager. The pipeline was refactored into numbered, resumable, path-independent steps, and the refactor was verified to reproduce byte-identical deliverables.
