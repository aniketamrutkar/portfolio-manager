"""Step 13 - ETF/SGB sleeve: 9 slots per account, a different fund per account (hand-picked by liquidity, see PICKS) -> ../Suggested_Lists_Backup/ETF_SGB_Per_Account.csv.
If a symbol disappears from the universe after a data refresh it is skipped with a warning - pick a replacement in PICKS."""
import pandas as pd
from common import OUT, ACCOUNTS, ACCOUNT_ID, SUGGESTED
u = pd.read_csv(f'{OUT}/All_Scrips_NSE_BSE.csv').set_index('Symbol')
PICKS = {  # slot: (account 1, account 2, account 3) - see ACCOUNTS in common.py for names
    'Large cap (Nifty 50)':   ('NIFTYBEES', 'SETFNIF50', 'NIFTY1'),
    'Mid cap':                ('MID150BEES', 'MIDCAPETF', 'MIDCAPIETF'),
    'Small cap':              ('HDFCSML250', 'MOSMALL250', 'SMALLCAP'),
    'Gold':                   ('GOLDBEES', 'GOLDIETF', 'TATAGOLD'),
    'Silver':                 ('SILVERBEES', 'HDFCSILVER', 'SILVERIETF'),
    'International':          ('MON100', 'MAFANG', 'MASPTOP50'),
    'Sector':                 ('BANKBEES', 'PHARMABEES', 'ITBEES'),
    'Liquid / cash':          ('LIQUIDBEES', 'LIQUIDCASE', 'LIQUID1'),
    'Sovereign Gold Bond':    ('SGBFEB32IV', 'SGBDE31III', 'SGBSEP31II'),
}
rows = []
for slot, syms in PICKS.items():
    for i, s in enumerate(syms):
        if 'NSE:' + s not in u.index: print(f'WARNING: {s} not in universe - skipped ({slot}, {ACCOUNTS[i+1]})'); continue
        r = u.loc['NSE:' + s]
        rows.append({'Account': ACCOUNTS[i+1], 'Slot': slot, 'Symbol': 'NSE:' + s, 'Name': r['Company'], 'Type': r['Instrument Type'], 'Underlying': r['Industry'],
                     'Price': r['Price'], '52W High': r['52W High'], '52W Low': r['52W Low'], '% Below 52W High': r['% Below 52W High'],
                     'Return 1y %': r['Return 1y %'], 'Return 3y %': r['Return 3y %'], 'Volatility %': r['Volatility %'], 'Max Drawdown 3y %': r['Max Drawdown 3y %'],
                     'Turnover Last Day (Lakh)': r['Turnover Last Day (Lakh)']})
d = pd.DataFrame(rows); assert d['Symbol'].is_unique
d.sort_values(['Account', 'Slot'], key=lambda c: c.map(ACCOUNT_ID) if c.name == 'Account' else c).to_csv(f'{SUGGESTED}/ETF_SGB_Per_Account.csv', index=False)
print(d.groupby('Account').size().to_dict(), 'unique', d['Symbol'].nunique())
print(d[d['Account'] == ACCOUNTS[1]][['Slot', 'Symbol', 'Price', 'Return 1y %', 'Volatility %', 'Turnover Last Day (Lakh)']].to_string(index=False))
