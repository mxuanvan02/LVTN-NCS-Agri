#!/usr/bin/env python3
"""Primary and sensitivity scalar NCS benchmark.

Primary design:
* causal persistence weather forecast (no future weather access),
* 50 seeds and common exogenous noise/channel realization across policies,
* TT/ET MPC and a real stateful discrete PI comparator,
* separated energy accounting,
* raw seed output, mean/SD/95% CI, and paired ET-MPC minus TT-MPC effects.

Oracle forecast is sensitivity-only.  The Mekong packet trace is synthetic and
weather-conditioned, not an empirical field measurement.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.models import Controllers, EdgeEventTrigger, GreenhousePlant, LoRaEnergyModel, PIController


@dataclass(frozen=True)
class Scenario:
    name: str
    weather: np.ndarray
    channel_kind: str
    loss_rate: float = 0.30
    trace: np.ndarray | None = None


def sha256(path: Path) -> str:
    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


def channel_realization(s: Scenario, seed: int, n: int, loss_scale=1.0, burst_scale=1.0):
    rng = np.random.default_rng(seed + 100_000)
    if s.channel_kind == "trace":
        base = np.resize(s.trace.astype(int), n).copy()
        # loss_scale sensitivity can only add independent failures or recover a
        # deterministic subset; primary scale=1 exactly replays the trace.
        if loss_scale > 1:
            base[(base == 1) & (rng.random(n) < min((loss_scale - 1) * .15, .8))] = 0
        elif loss_scale < 1:
            base[(base == 0) & (rng.random(n) < 1 - loss_scale)] = 1
        return base
    if s.channel_kind == "bernoulli":
        return (rng.random(n) > min(s.loss_rate * loss_scale, .95)).astype(int)
    bad, out = False, np.ones(n, dtype=int)
    enter = min(.05 * burst_scale * loss_scale, .8)
    recover = min(.35 / max(burst_scale, .1), .95)
    for k in range(n):
        if bad:
            out[k] = int(rng.random() > min(.75 * loss_scale, .98))
            if rng.random() < recover: bad = False
        else:
            out[k] = int(rng.random() > min(.08 * loss_scale, .95))
            if rng.random() < enter: bad = True
    return out


def causal_weather_forecast(weather: np.ndarray, k: int, N: int, regime: str, rng=None):
    """Return forecast made with information available at time k.

    Persistence is the primary regime and reads only ``weather[k]``. Oracle is
    explicit sensitivity-only. Noisy persistence adds seeded forecast error.
    """
    if regime == "persistence":
        return np.repeat(weather[k], N)
    if regime == "noisy_persistence":
        if rng is None:
            rng = np.random.default_rng(0)
        return np.repeat(weather[k], N) + rng.normal(0, 1.0, N)
    if regime == "oracle":
        return np.array([weather[min(k + i, len(weather) - 1)] for i in range(N)])
    raise ValueError(regime)


# Backward-compatible explicit name used by the experiment itself.
weather_forecast = causal_weather_forecast


def _exogenous_hash(noise: np.ndarray, channel: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.asarray(noise, dtype=np.float64).tobytes())
    h.update(np.asarray(channel, dtype=np.int8).tobytes())
    return h.hexdigest()


def generate_exogenous(s: Scenario, seed: int, n_steps: int, loss_scale=1.0, burst_scale=1.0):
    """Generate policy-independent process noise and full-step channel states."""
    noise = np.random.default_rng(seed).normal(0, .1, n_steps)
    channel = channel_realization(s, seed, n_steps, loss_scale, burst_scale)
    return {"noise": noise, "channel_success": channel,
            "hash": _exogenous_hash(noise, channel)}


def simulate(method: str, s: Scenario, seed: int, horizon=300, *,
             forecast="persistence", delta=.05, loss_scale=1., burst_scale=1.,
             alpha=.85, beta=.15, gamma=.15, exogenous=None) -> Dict[str, float]:
    plant, ctrl = GreenhousePlant(alpha, beta, gamma), Controllers()
    trigger, energy = EdgeEventTrigger(sigma=.002, delta=delta), LoRaEnergyModel()
    pi = PIController(kp=2.5, ki=.12)
    weather = s.weather[:horizon]
    n_steps = horizon - 1
    # CRN: arrays depend on scenario/seed, never policy. An explicit realization
    # may be injected by tests or paired-design callers.
    if exogenous is None:
        exogenous = generate_exogenous(s, seed, n_steps, loss_scale, burst_scale)
    noise = np.asarray(exogenous["noise"], dtype=float)
    channel = np.asarray(exogenous["channel_success"], dtype=int)
    exog_hash = exogenous.get("hash", _exogenous_hash(noise, channel))
    if len(noise) < n_steps or len(channel) < n_steps:
        raise ValueError("exogenous realization is shorter than simulation horizon")
    forecast_rng = np.random.default_rng(seed + 200_000)

    x = np.array([[float(weather[0])]])
    x_last, u_seq, last_pi = x.copy(), np.zeros(ctrl.N), 0.0
    states = [float(x[0, 0])]
    tx = losses = violations = 0
    for k in range(n_steps):
        is_mpc = "MPC" in method
        is_tt = method.startswith("TT")
        has_buffer = "NO-BUF" not in method
        attempt = True if is_tt else trigger.check_trigger(x, x_last)
        arrived = bool(channel[k]) if attempt else False
        if attempt:
            tx += 1; losses += int(not arrived)
        if attempt and arrived:
            x_last = x.copy()
            if is_mpc:
                fc = weather_forecast(weather, k, ctrl.N, forecast, forecast_rng)
                u_seq = ctrl.solve_mpc(x_last, u_seq, fc, plant)
                u = float(u_seq[0])
            else:
                u = pi.step(float(x_last[0, 0]), ctrl.x_ref); last_pi = u
        elif is_mpc:
            if has_buffer:
                u_seq = np.roll(u_seq, -1); u_seq[-1] = u_seq[-2]
                u = float(u_seq[0])
            else: u = 0.0
        else: u = last_pi
        x = plant.step(x, u, weather[k], noise=float(noise[k]))
        states.append(float(x[0, 0]))
        violations += int(abs(float(x[0, 0]) - ctrl.x_ref) > 2.)
    err = np.asarray(states) - ctrl.x_ref
    ec = energy.components(tx, horizon)
    return {"scenario": s.name, "method": method, "seed": seed,
            "forecast_regime": forecast, "trigger_delta": delta,
            "loss_scale": loss_scale, "burst_scale": burst_scale,
            "alpha": alpha, "beta": beta, "gamma": gamma,
            "exogenous_hash": exog_hash,
            "rmse": float(np.sqrt(np.mean(err**2))), "iae": float(np.abs(err).sum()),
            "transmissions": tx, "tx_rate_pct": 100*tx/n_steps,
            "packet_loss_pct": 100*losses/max(tx, 1),
            "violation_pct": 100*violations/n_steps, **ec}


def load_scenarios() -> List[Scenario]:
    tokyo = pd.read_csv(ROOT/"data/tokyo_weather.csv")["temp_c"].to_numpy()
    mekong = pd.read_csv(ROOT/"data/vietnam_mekong_weather.csv")["temp_c"].to_numpy()
    trace = pd.read_csv(ROOT/"data/synthetic_weather_conditioned_lora_trace.csv")["packet_status"].to_numpy()
    return [Scenario("Mekong-Synthetic", mekong[:600], "trace", trace=trace),
            Scenario("Tokyo-Bernoulli", tokyo[1000:1600], "bernoulli"),
            Scenario("Tokyo-Burst", tokyo[1000:1600], "burst")]


# Short internal alias retained for existing callers.
scenarios = load_scenarios


def ci95(series):
    a=np.asarray(series,float); return 1.96*a.std(ddof=1)/np.sqrt(len(a))


def summarize(raw):
    metrics=["rmse","iae","tx_energy_mj","baseline_energy_mj","total_modeled_energy_mj",
             "tx_rate_pct","packet_loss_pct","violation_pct"]
    rows=[]
    for (sc,m),g in raw.groupby(["scenario","method"], sort=False):
        r={"scenario":sc,"method":m,"n_seeds":len(g)}
        for x in metrics:
            r.update({x+"_mean":g[x].mean(),x+"_sd":g[x].std(ddof=1),x+"_ci95":ci95(g[x])})
        rows.append(r)
    return pd.DataFrame(rows)


def paired(raw):
    metrics=["rmse","iae","tx_energy_mj","total_modeled_energy_mj","transmissions","violation_pct"]
    rows=[]
    for sc,g in raw.groupby("scenario"):
        a=g[g.method=="ET-MPC"].set_index("seed"); b=g[g.method=="TT-MPC"].set_index("seed")
        for x in metrics:
            d=a[x]-b[x]; half=ci95(d)
            rows.append({"scenario":sc,"contrast":"ET-MPC_minus_TT-MPC","metric":x,
                         "n_pairs":len(d),"mean_difference":d.mean(),"sd_difference":d.std(ddof=1),
                         "ci95_low":d.mean()-half,"ci95_high":d.mean()+half})
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",type=int,default=50); args=ap.parse_args()
    methods=["TT-PI","TT-MPC","ET-PI","ET-MPC-NO-BUF","ET-MPC"]
    seeds=range(2026,2026+args.seeds); scs=scenarios(); rows=[]
    for s in scs:
        for seed in seeds:
            for method in methods: rows.append(simulate(method,s,seed))
    raw=pd.DataFrame(rows); out=ROOT/"results"; out.mkdir(exist_ok=True)
    raw.to_csv(out/"q1_benchmark_raw.csv",index=False)
    summarize(raw).to_csv(out/"q1_benchmark_summary.csv",index=False)
    paired(raw).to_csv(out/"q1_benchmark_paired_effects.csv",index=False)

    # Compact, minimum requested sensitivity matrix, 20 seeds each.
    sens=[]
    settings=[]
    for f in ["persistence","noisy_persistence","oracle"]: settings.append((f,.05,1.,1.,.85,.15,.15,"forecast"))
    for d in [.02,.05,.10]: settings.append(("persistence",d,1.,1.,.85,.15,.15,"trigger"))
    for ls,bs in [(.7,.7),(1.,1.),(1.3,1.5)]: settings.append(("persistence",.05,ls,bs,.85,.15,.15,"channel"))
    for a,b,g in [(.80,.135,.135),(.85,.15,.15),(.90,.165,.165)]: settings.append(("persistence",.05,1.,1.,a,b,g,"model"))
    seen=set()
    for f,d,ls,bs,a,b,g,factor in settings:
        key=(f,d,ls,bs,a,b,g,factor)
        if key in seen: continue
        seen.add(key)
        for s in scs:
            for seed in range(2026,2046):
                sens.append({"sensitivity_factor":factor, **simulate("ET-MPC",s,seed,forecast=f,delta=d,
                            loss_scale=ls,burst_scale=bs,alpha=a,beta=b,gamma=g)})
    pd.DataFrame(sens).to_csv(out/"q1_sensitivity_raw.csv",index=False)
    ssum=summarize(pd.DataFrame(sens).assign(method=lambda x: x.sensitivity_factor+":"+x.forecast_regime+":"+x.trigger_delta.astype(str)+":"+x.loss_scale.astype(str)+":"+x.alpha.astype(str)))
    ssum.to_csv(out/"q1_sensitivity_summary.csv",index=False)
    provenance={"source_repository":"https://github.com/mxuanvan02/LVTN-NCS-Agri",
      "source_commit":"968280dcde672de48b5a719b273d887d1e813a23","primary_forecast":"causal persistence",
      "primary_seeds":args.seeds,"seed_start":2026,"trace_kind":"synthetic weather-conditioned",
      "inputs":{str(p.relative_to(ROOT)):sha256(p) for p in [ROOT/"data/tokyo_weather.csv",ROOT/"data/vietnam_mekong_weather.csv",ROOT/"data/synthetic_weather_conditioned_lora_trace.csv"]}}
    (out/"benchmark_provenance.json").write_text(json.dumps(provenance,indent=2),encoding="utf-8")
    print(summarize(raw).to_string(index=False)); print("WROTE",len(raw),"primary rows and",len(sens),"sensitivity rows")

if __name__=="__main__": main()
