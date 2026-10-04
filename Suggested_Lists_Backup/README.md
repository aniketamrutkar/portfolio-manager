# Suggested lists — backup

The original suggestions generated for the three accounts, set aside on 4 Oct 2026 when the app switched to a clean slate
(accounts start empty; you add stocks yourself).

- `Account_Portfolios_20+20.csv` — 120 stocks: PEW-Angel, JPW-Angel, JPW-Zerodha × (20 Active + 20 To Invest), from the step-12 screen.
- `ETF_SGB_Per_Account.csv` — 27 ETF/SGB holdings: 9 per account, from step 13.

The pipeline keeps (re)writing these two files here (steps 12-13) and the Backtest tab (step 14) still runs on them.
To start the app pre-filled with them again, set `START_EMPTY = False` in `pipeline/common.py` and run `./run_all.sh`.
