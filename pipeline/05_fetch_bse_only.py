"""Step 05 - Yahoo snapshot for BSE-only equities with meaningful turnover (> Rs 10 lakh on the bhavcopy day). -> raw_bse2.json  (resumable)
Yahoo's BSE tickers are the BSE ticker *names* (e.g. ABB.BO); numeric scrip codes (500002.BO) return nothing."""
import pandas as pd
from common import run_resumable, yahoo_basic
x = pd.read_csv('bse_only.csv')
x = x[~x['SctySrs'].isin(['F', 'E']) & (x['TtlTrfVal'] > 1e6)].sort_values('TtlTrfVal', ascending=False)
syms = [str(s).strip() for s in x['TckrSymb']]
run_resumable('bse-only', lambda s: yahoo_basic(s, '.BO'), syms, 'raw_bse2.json', workers=2)
