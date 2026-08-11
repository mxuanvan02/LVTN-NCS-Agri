#!/usr/bin/env python3
"""Regenerate v2 decision/accounting tables from raw outputs only."""
from pathlib import Path
import hashlib, json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'
raw=pd.read_csv(OUT/'v2_primary_raw.csv'); paired=pd.read_csv(OUT/'v2_primary_paired.csv')
rows=[]
for plant in ('greenhouse','irrigation'):
 for net in sorted(raw.network.unique()):
  g=raw[(raw.plant==plant)&(raw.network==net)]
  et=g[g.policy=='ET-MPC'].set_index('seed'); tt=g[g.policy=='TT-MPC'].set_index('seed')
  pe=paired[(paired.plant==plant)&(paired.network==net)&(paired.contrast=='ET-MPC_minus_TT-MPC')].set_index('metric')
  reduction=100*(1-et.transmissions/tt.transmissions)
  # The preregistered gate uses the paired CI lower bound for transmission reduction.
  import scipy.stats as st, numpy as np
  q=st.t.ppf(.975,len(reduction)-1); half=q*reduction.std(ddof=1)/np.sqrt(len(reduction))
  rlo=float(reduction.mean()-half)
  n_hi=float(pe.loc['nrmse','ci95_high']); v_hi=float(pe.loc['violation_pct','ci95_high'])
  passed=bool(rlo>=20 and n_hi<=.10 and v_hi<=5)
  rows.append({'plant':plant,'network':net,'n_pairs':len(reduction),
   'transmission_reduction_pct_mean':reduction.mean(),'transmission_reduction_ci95_low':rlo,
   'transmission_reduction_ci95_high':reduction.mean()+half,
   'nrmse_difference_ci95_high':n_hi,'violation_difference_pp_ci95_high':v_hi,
   'tradeoff_gate':'pass' if passed else 'fail','failure_reason':'' if passed else 'transmission reduction lower CI <20%'})
pd.DataFrame(rows).to_csv(OUT/'v2_decision_gates.csv',index=False)
manifest=pd.read_csv(OUT/'v2_run_manifest.csv')
account=(manifest.groupby('status').size().rename('n').reset_index())
account.to_csv(OUT/'v2_run_accounting.csv',index=False)
files=['v2_primary_raw.csv','v2_primary_summary.csv','v2_primary_paired.csv','v2_sensitivity_raw.csv','v2_run_manifest.csv','v2_decision_gates.csv','v2_run_accounting.csv','v2_sil_events.jsonl','v2_interface.jsonl','v2_sil_loopback.json','v2_provenance.json']
hashes={f:hashlib.sha256((OUT/f).read_bytes()).hexdigest() for f in files}
(OUT/'v2_output_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(pd.DataFrame(rows).to_string(index=False)); print(account.to_string(index=False))
