#!/usr/bin/env python3
from pathlib import Path
import pandas as pd, matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
d=pd.read_csv(ROOT/'results/v2_primary_summary.csv')
fig,axs=plt.subplots(2,2,figsize=(11,7),sharex=True)
for i,plant in enumerate(['greenhouse','irrigation']):
 g=d[(d.plant==plant)&(d.policy.isin(['TT-MPC','ET-MPC']))]
 for pol,mark in [('TT-MPC','o'),('ET-MPC','s')]:
  q=g[g.policy==pol]
  axs[i,0].plot(q.network,q.nrmse_mean,marker=mark,label=pol)
  axs[i,1].plot(q.network,q.total_modeled_energy_mj_mean,marker=mark,label=pol)
 axs[i,0].set_ylabel(('Nhà kính' if plant=='greenhouse' else 'Tưới')+'\nNRMSE')
 axs[i,1].set_ylabel('Năng lượng mô hình (mJ)')
for ax in axs.ravel(): ax.tick_params(axis='x',rotation=35); ax.grid(alpha=.25); ax.legend(fontsize=8)
fig.suptitle('Benchmark v2: TT-MPC và ET-MPC trên hai plant, sáu cấu hình mạng (50 seed)')
fig.tight_layout(); out=ROOT.parent/'figures/ch04/v2_benchmark.pdf'; out.parent.mkdir(parents=True,exist_ok=True); fig.savefig(out,bbox_inches='tight'); print(out)
