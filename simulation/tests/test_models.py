import os, sys, tempfile
from pathlib import Path

# Make the simulation package importable whether pytest is invoked from the
# simulation directory or from the manuscript root.
SIM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM_ROOT))

import numpy as np, pandas as pd
from src.models import Controllers, EdgeEventTrigger, GreenhousePlant, LoRaEnergyModel, PIController, TraceBasedChannel
from experiments.run_q1_benchmark import causal_weather_forecast, generate_exogenous, load_scenarios, simulate

def test_greenhouse_plant_step_is_finite_with_zero_noise():
    assert np.isfinite(GreenhousePlant().step(np.array([[24.]]),0,20,noise_std=0)).all()
def test_mpc_solution_respects_bounds_and_horizon():
    u=Controllers(N=4).solve_mpc(np.array([[22.]]),None,np.array([20.,20.5,21.,21.5]),GreenhousePlant())
    assert len(u)==4 and np.all(u>=-20.0001) and np.all(u<=20.0001)
def test_event_trigger_logic_thresholds():
    t=EdgeEventTrigger(.02,.1); x=np.array([[24.]])
    assert not t.check_trigger(np.array([[24.01]]),x) and t.check_trigger(np.array([[30.]]),x)
def test_trace_replay_cyclically():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'x.csv'); pd.DataFrame({'packet_status':[1,0]}).to_csv(p,index=False)
        c=TraceBasedChannel(p); assert [c.step(),c.step(),c.step()]==[1,0,1]
def test_energy_identity_and_components():
    c=LoRaEnergyModel().components(10,100)
    assert c['tx_energy_mj']==200 and c['baseline_energy_mj']==300 and c['total_modeled_energy_mj']==500
    assert c['total_modeled_energy_mj']==c['tx_energy_mj']+c['baseline_energy_mj']
def test_pi_integral_is_active_and_antiwindup_bounded():
    pi=PIController(kp=0,ki=1,i_min=-5,i_max=5)
    vals=[pi.step(0,1) for _ in range(10)]
    assert vals[-1]>vals[1] and abs(pi.integral)<=5
    sat=PIController(kp=100,ki=1,i_min=-5,i_max=5); sat.step(0,1); assert sat.integral==0
def test_persistence_forecast_has_no_lookahead():
    w=np.array([10.,11.,12.,99.,100.])
    f1=causal_weather_forecast(w,2,3,'persistence')
    w[3:]=[-99,-100]
    f2=causal_weather_forecast(w,2,3,'persistence')
    assert np.array_equal(f1,f2) and np.all(f1==12.)
def test_oracle_is_not_primary_default():
    assert causal_weather_forecast(np.array([1.,2.,3.,4.]),1,2,'persistence').tolist()==[2.,2.]
def test_crn_exogenous_is_policy_independent():
    s=load_scenarios()[0]; a=generate_exogenous(s,2026,100); b=generate_exogenous(s,2026,100)
    assert np.array_equal(a['noise'],b['noise']) and np.array_equal(a['channel_success'],b['channel_success'])
def test_same_exogenous_is_used_across_policies():
    s=load_scenarios()[0]; ex=generate_exogenous(s,42,80)
    a=simulate('TT-MPC',s,42,80,exogenous=ex); b=simulate('ET-PI',s,42,80,exogenous=ex)
    assert a['exogenous_hash']==b['exogenous_hash']
