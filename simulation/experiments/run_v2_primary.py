#!/usr/bin/env python3
"""Version-2 paired greenhouse/irrigation NCS benchmark.

This is a software-only, explicitly parameterised mechanism benchmark.  Plant
coefficients are declared synthetic benchmarks; network and energy values are
not field or hardware measurements.  Primary forecasts are causal persistence.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.plants_v2 import GreenhousePlantV2,IrrigationPlantV2
from src.network_v2 import RandomTape,NetworkEmulator,PROFILES
from src.interfaces_v2 import Observation,Command,JsonlTransport,InProcessTransport,replay_commands

POLICIES=("TT-MPC","ET-MPC","TT-PI","ET-PI")
PLANTS=("greenhouse","irrigation")
NETWORKS=tuple(PROFILES)
METRICS=("nrmse","violation_pct","transmissions","total_modeled_energy_mj","command_applied_pct","deadline_miss_pct")

def fhash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def config_hash(): return fhash(ROOT/'configs_v2.yaml')
def prereg_hash(): return fhash(ROOT/'preregistration_v2.yaml')

def exogenous(plant,net,seed,n,state_dim):
    tape=RandomTape(seed,plant,net)
    noise=np.array([[tape.normal('plant',k,j,scale=.012 if plant=='irrigation' else .025) for j in range(state_dim)] for k in range(n)])
    sensor=np.array([[tape.normal('sensor',k,j,scale=.003 if plant=='irrigation' else .03) for j in range(state_dim)] for k in range(n)])
    h=hashlib.sha256(noise.tobytes()+sensor.tobytes()+f'{seed}:{plant}:{net}'.encode()).hexdigest()
    return tape,noise,sensor,h

def controller_action(kind,plant,x,ref,integ,exog):
    err=ref-x
    if kind=='PI':
        kp=np.array([1.2,.8]) if plant.name=='greenhouse' else np.array([4.0,1.0])
        ki=np.array([.05,.03]) if plant.name=='greenhouse' else np.array([.08,.01])
        e=np.asarray(err); integ=np.clip(integ+e,-20,20)
        if plant.name=='greenhouse': u=np.array([kp[0]*e[0]+ki[0]*integ[0],-.5*kp[1]*e[1]-.2*ki[1]*integ[1]])
        else: u=np.array([kp[0]*e[0]+ki[0]*integ[0]])
    else:
        # Causal finite-horizon receding-horizon action. Candidate commands are
        # held over the declared 12-step horizon; only the first is applied.
        # This compact grid implementation keeps the full factorial practical
        # and never reads future disturbances in the primary analysis.
        if plant.name=='greenhouse':
            cand=np.array([[a,b] for a in np.linspace(-6,6,5) for b in np.linspace(-12,12,5)])
        else: cand=np.array([[a] for a in np.linspace(0,4,9)])
        xp=np.repeat(np.asarray(x,float)[None,:],len(cand),axis=0)
        costs=np.zeros(len(cand)); d=np.asarray(exog,float)[:2]
        for _ in range(plant.spec.horizon):
            if plant.name=='greenhouse':
                xp=plant.reference+(xp-plant.reference)@plant.A.T+cand@plant.B.T+(d-plant.disturbance_reference)@plant.E.T
            else:
                xp=np.array([plant.predict(xx,uu,d) for xx,uu in zip(xp,cand)])
            z=(xp-ref)/(plant.state_max-plant.state_min)
            costs += np.sum(z*z,axis=1)+.01*np.sum(cand*cand,axis=1)
        u=cand[int(np.argmin(costs))]
    return plant.clamp_u(u),integ

def disturbance(plant_name, k):
    if plant_name=='greenhouse':
        return np.array([18+7*math.sin(2*math.pi*k/288),55+12*math.cos(2*math.pi*k/288)])
    return np.array([0., max(0,4+2*math.sin(2*math.pi*k/48))/48])

def run_one(plant_name,policy,network,seed,event_log=None,*,trigger_delta=.035,
            forecast_regime='persistence',model_scale=1.0,fallback='hold'):
    plant=GreenhousePlantV2() if plant_name=='greenhouse' else IrrigationPlantV2()
    if plant_name=='greenhouse' and model_scale != 1.0:
        plant.A = plant.A * model_scale
    n=288 if plant_name=='greenhouse' else 336 # 24 h or 7 d, runtime-conscious
    tape,noise,snoise,xhash=exogenous(plant_name,network,seed,n,2)
    net=NetworkEmulator(PROFILES[network],tape)
    x=plant.reset(); ref=np.array([24.,65.]) if plant_name=='greenhouse' else np.array([.27,.25])
    last_sent=x.copy(); estimate=x.copy(); u=np.zeros(plant.control_dim); integ=np.zeros(2)
    errs=[]; viol=[]; tx=applied=deadline=0; energies={k:0. for k in ['tx','rx','listen','retry','compute','baseline','actuation']}
    sample_s=plant.sample_time_s
    for k in range(n):
        ex=disturbance(plant_name,k)
        if forecast_regime=='noisy_persistence':
            forecast_ex=ex+np.array([tape.normal('forecast',k,j,scale=.4 if plant_name=='greenhouse' else .01) for j in range(2)])
        elif forecast_regime=='oracle':
            forecast_ex=disturbance(plant_name,min(k+plant.spec.horizon,n-1))
        else: forecast_ex=ex
        meas=x+snoise[k]
        is_et=policy.startswith('ET'); scale=plant.state_max-plant.state_min
        trigger=(not is_et) or np.linalg.norm((meas-last_sent)/scale)>trigger_delta
        if trigger:
            tx+=1
            ok,lat,logs,en=net.transact(k,payload_bytes=48,deadline_s=.8*sample_s,
                                         compute_family='MPC' if 'MPC' in policy else 'PI',
                                         now_s=k*sample_s)
            for kk,v in en.items(): energies[kk]+=v
            if event_log is not None:
                for l in logs: event_log.write(json.dumps(l.__dict__,sort_keys=True)+'\n')
            if ok:
                estimate=meas.copy(); last_sent=meas.copy()
                u,integ=controller_action('MPC' if 'MPC' in policy else 'PI',plant,estimate,ref,integ,forecast_ex)
                applied+=1
            else:
                deadline+=int(lat>=.8*sample_s)
                if fallback=='zero' and 'MPC' in policy: u=np.zeros(plant.control_dim)
        x=plant.step(u,np.asarray(ex,float)[:2],noise=noise[k])
        energies['baseline']+=.06*sample_s/60
        energies['compute']+=.004 if trigger and 'MPC' in policy else (.001 if trigger else 0)
        energies['actuation']+=plant.actuation_energy_mj(u)
        ne=(x-ref)/scale; errs.append(ne); viol.append(np.mean((x<plant.state_min)|(x>plant.state_max)))
    e=np.asarray(errs); total=sum(energies.values())
    return {'plant':plant_name,'policy':policy,'network':network,'seed':seed,'forecast':forecast_regime,
      'trigger_delta':trigger_delta,'model_scale':model_scale,'fallback':fallback,
      'random_tape_sha256':xhash,'config_sha256':config_hash(),'preregistration_sha256':prereg_hash(),
      'nrmse':float(np.sqrt(np.mean(e*e))),'violation_pct':100*float(np.mean(viol)),
      'transmissions':tx,'command_applied_pct':100*applied/max(tx,1),'deadline_miss_pct':100*deadline/max(tx,1),
      **{f'{k}_energy_mj':v for k,v in energies.items()},'total_modeled_energy_mj':total,'status':'completed'}

def summarize(raw):
    rows=[]
    for keys,g in raw.groupby(['plant','network','policy']):
        r=dict(zip(['plant','network','policy'],keys)); r['n_completed']=len(g)
        for m in METRICS:
            a=g[m].to_numpy(float); q=stats.t.ppf(.975,len(a)-1); h=q*a.std(ddof=1)/math.sqrt(len(a))
            r.update({f'{m}_mean':a.mean(),f'{m}_sd':a.std(ddof=1),f'{m}_ci_low':a.mean()-h,f'{m}_ci_high':a.mean()+h})
        rows.append(r)
    return pd.DataFrame(rows)

def holm(p):
    p=np.asarray(p); order=np.argsort(p); out=np.empty(len(p)); running=0
    for rank,i in enumerate(order): running=max(running,(len(p)-rank)*p[i]); out[i]=min(1,running)
    return out

def paired(raw):
    rows=[]
    for plant in PLANTS:
      for net in NETWORKS:
       for contrast,a_name,b_name in [('ET-MPC_minus_TT-MPC','ET-MPC','TT-MPC'),('ET-PI_minus_TT-PI','ET-PI','TT-PI')]:
        g=raw[(raw.plant==plant)&(raw.network==net)]; a=g[g.policy==a_name].set_index('seed'); b=g[g.policy==b_name].set_index('seed')
        for m in METRICS:
          d=(a[m]-b[m]).dropna().to_numpy(float); n=len(d); q=stats.t.ppf(.975,n-1); se=d.std(ddof=1)/math.sqrt(n); lo,hi=d.mean()-q*se,d.mean()+q*se
          _,p=stats.ttest_1samp(d,0); dz=d.mean()/d.std(ddof=1) if d.std(ddof=1)>0 else float('nan')
          rows.append({'plant':plant,'network':net,'contrast':contrast,'metric':m,'n_pairs':n,'mean_difference':d.mean(),'sd_difference':d.std(ddof=1),'ci95_low':lo,'ci95_high':hi,'p_value':p,'cohen_dz':dz,'probability_A_better':float(np.mean(d<0)),'crn_gate':bool((a.random_tape_sha256==b.random_tape_sha256).all())})
    out=pd.DataFrame(rows); out['p_value_holm']=holm(out.p_value.fillna(1)); return out

def run_sensitivity(seeds=15):
    """Compact prespecified sensitivity/ablation grid (not primary inference)."""
    rows=[]
    settings=[]
    for d in (.02,.035,.07): settings.append((f'trigger_{d}',dict(trigger_delta=d)))
    for f in ('persistence','noisy_persistence','oracle'): settings.append((f'forecast_{f}',dict(forecast_regime=f)))
    for m in (.98,1.0,1.02): settings.append((f'model_{m}',dict(model_scale=m)))
    settings.append(('buffer_no_buffer',dict(fallback='zero')))
    for plant in PLANTS:
      for net in NETWORKS:
       for setting_id,kwargs in settings:
        for seed in range(2026,2026+seeds):
         r=run_one(plant,'ET-MPC',net,seed,**kwargs); r['setting_id']=setting_id; rows.append(r)
    return pd.DataFrame(rows)

def sil_smoke(out):
    log=out/'v2_sil_events.jsonl'; cmds=[]
    with log.open('w') as f:
      for plant in PLANTS:
       for policy in POLICIES:
        run_one(plant,policy,'N1_nominal',2026,event_log=f)
        c=Command('sil',1,1,1,999999,np.array([.1]),'normal'); cmds.append(c)
    direct=InProcessTransport(); direct.send({'kind':'smoke','seq':1}); assert direct.poll(1)
    jt=JsonlTransport(out/'v2_interface.jsonl'); jt.send({'kind':'smoke','seq':1}); assert jt.poll(1)
    replay_commands(cmds); return log

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--seeds',type=int,default=50); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    planned=len(PLANTS)*len(POLICIES)*len(NETWORKS)*args.seeds
    if args.dry_run: print(json.dumps({'planned_runs':planned,'plants':PLANTS,'policies':POLICIES,'networks':NETWORKS})); return
    out=ROOT/'results'; out.mkdir(exist_ok=True); rows=[]; manifest=[]; start=time.time()
    for plant in PLANTS:
     for net in NETWORKS:
      for seed in range(2026,2026+args.seeds):
       for policy in POLICIES:
        rid=f'{plant}:{net}:{seed}:{policy}'
        try: r=run_one(plant,policy,net,seed); rows.append(r); manifest.append({'run_id':rid,'status':'completed','failure_reason':''})
        except Exception as e: manifest.append({'run_id':rid,'status':'failed_runtime','failure_reason':repr(e)})
    raw=pd.DataFrame(rows); raw.to_csv(out/'v2_primary_raw.csv',index=False); summarize(raw).to_csv(out/'v2_primary_summary.csv',index=False); paired(raw).to_csv(out/'v2_primary_paired.csv',index=False); pd.DataFrame(manifest).to_csv(out/'v2_run_manifest.csv',index=False)
    run_sensitivity(min(15,args.seeds)).to_csv(out/'v2_sensitivity_raw.csv',index=False); sil_smoke(out)
    prov={'runtime_seconds':time.time()-start,'planned_runs':planned,'completed_runs':len(raw),'failed_runs':sum(x['status']!='completed' for x in manifest),'config_sha256':config_hash(),'preregistration_sha256':prereg_hash(),'claim_boundary':'software simulation and SIL/HIL-ready interfaces; no field or hardware validation'}
    (out/'v2_provenance.json').write_text(json.dumps(prov,indent=2),encoding='utf-8'); print(json.dumps(prov,indent=2))
if __name__=='__main__': main()
