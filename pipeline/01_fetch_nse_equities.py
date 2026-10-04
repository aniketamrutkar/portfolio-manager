"""Step 01 - Yahoo snapshot fundamentals for every NSE equity (+ Nifty 500 names missing from EQUITY_L). -> raw.json  (resumable)"""
import pandas as pd
from common import run_resumable, yahoo_basic
eq = pd.read_csv('EQUITY_L.csv'); eq.columns = [c.strip() for c in eq.columns]
syms = eq[eq['SERIES'].str.strip().isin(['EQ', 'BE', 'BZ', 'SM', 'ST'])]['SYMBOL'].tolist()
n500 = pd.read_csv('n500.csv')['Symbol'].tolist()
syms = sorted(set(syms) | set(n500), key=lambda s: (s not in n500, s))      # Nifty 500 first
run_resumable('nse-equities', yahoo_basic, syms, 'raw.json', workers=3)
