import json, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.plants_v2 import GreenhousePlantV2,IrrigationPlantV2
from src.network_v2 import RandomTape,NetworkEmulator,PROFILES,NetworkProfile
from src.interfaces_v2 import Command,InProcessTransport,JsonlTransport,replay_commands,UdpEnvelope,UdpLoopbackTransport
from experiments.run_v2_primary import run_one

def test_greenhouse_deterministic_and_bounds():
 p=GreenhousePlantV2(); a=p.reset(); b=p.reset(); assert np.array_equal(a,b)
 x=p.step([2,2],[20,60],noise=[0,0]); assert np.isfinite(x).all(); assert np.all(p.clamp_u([9,-20])==[5,-4])

def test_irrigation_nonnegative_and_conservation_fixture():
 p=IrrigationPlantV2(); x=p.reset(); assert p.clamp_u([-3])[0]==0
 dry=p.step([0],[0,0],noise=[0,0]); p.reset(x); wet=p.step([4],[0,0],noise=[0,0]); assert wet[0]>=dry[0]

def test_random_tape_keyed_policy_independence():
 a=RandomTape(7,'g','N').uniform('uplink',2,1); b=RandomTape(7,'g','N').uniform('uplink',2,1); assert a==b

def test_network_causality_and_energy_components():
 n=NetworkEmulator(PROFILES['N1_nominal'],RandomTape(2,'g','N1')); ok,lat,logs,e=n.transact(1,48,1000,'MPC',now_s=300.)
 assert lat>=0 and logs and all(l.arrival_timestamp>=l.tx_end>=l.tx_start>=300. for l in logs)
 assert {'tx','rx','listen','retry'}<=set(e)
 # Exact serialization and distinct uplink/downlink flow.
 up=logs[0]; assert abs((up.tx_end-up.tx_start)-8*48/PROFILES['N1_nominal'].bandwidth_bps)<1e-12
 assert {x.direction for x in logs}>={'uplink','downlink'}

def test_downlink_failure_holds_actuator_contract():
 p=NetworkProfile('downfail',downlink_loss=1.0)
 ok,_,logs,_=NetworkEmulator(p,RandomTape(9,'g','downfail')).transact(2,48,100,'PI',now_s=600.)
 assert not ok and logs[0].accepted and logs[-1].direction=='downlink' and not logs[-1].accepted

def test_udp_checksum_and_duplicate_rejection():
 payload={'run_id':'r','seq':1,'direction':'downlink'}
 t=UdpLoopbackTransport(); assert not t.roundtrip(payload)['duplicate']; assert t.roundtrip(payload)['duplicate']
 blob=bytearray(UdpEnvelope.pack(payload)); blob[0]^=1
 import pytest
 with pytest.raises(ValueError): UdpEnvelope.unpack(bytes(blob))

def test_full_stress_deterministic():
 a=run_one('greenhouse','ET-MPC','N5_full_stress',2026); b=run_one('greenhouse','ET-MPC','N5_full_stress',2026)
 for k in ['nrmse','transmissions','total_modeled_energy_mj','random_tape_sha256']: assert a[k]==b[k]

def test_primary_is_causal_and_both_plants():
 for p in ['greenhouse','irrigation']:
  r=run_one(p,'TT-PI','N0_ideal',2026); assert r['forecast']=='persistence' and np.isfinite(r['nrmse'])

def test_interfaces_and_replay(tmp_path):
 t=InProcessTransport(); t.send({'seq':1}); assert t.poll(1)[0]['seq']==1
 j=JsonlTransport(tmp_path/'x.jsonl'); j.send({'seq':2}); assert j.poll(1)[0]['seq']==2
 c=Command('x',1,1,0,3,np.array([1.]),'normal'); assert replay_commands([c])==[1]

def test_crn_equal_across_policies():
 hs={run_one('irrigation',p,'N3_burst_loss',2026)['random_tape_sha256'] for p in ['TT-MPC','ET-MPC','TT-PI','ET-PI']}; assert len(hs)==1
