import numpy as np
from scipy.optimize import minimize

class GreenhousePlant:
    def __init__(self, alpha=0.85, beta=0.15, gamma=0.15):
        self.A = np.array([[alpha]], dtype=float); self.B = np.array([[beta]], dtype=float); self.gamma = gamma
    def step(self, x, u, t_out, noise_std=0.1, noise=None):
        w = np.random.normal(0, noise_std) if noise is None else float(noise)
        return self.A @ x + self.B * np.array([[u]]) + self.gamma * t_out + w

class Controllers:
    def __init__(self, N=5, Q=20.0, R=0.5, x_ref=24.0):
        self.N=N; self.Q=np.array([[Q]]); self.R=np.array([[R]]); self.x_ref=x_ref
    def mpc_cost(self, u_seq, x_current, T_out_traj, plant):
        cost=0.; x=x_current.copy()
        for i in range(self.N):
            u=u_seq[i:i+1]; x=plant.A@x+plant.B@u+plant.gamma*T_out_traj[i]
            cost += (x-self.x_ref).T@self.Q@(x-self.x_ref)+u.T@self.R@u
        return float(cost.item())
    def solve_mpc(self, x_current, u_prev_seq, T_out_traj, plant):
        guess=np.zeros(self.N)
        if u_prev_seq is not None: guess[:-1]=u_prev_seq[1:]; guess[-1]=u_prev_seq[-1]
        res=minimize(self.mpc_cost,guess,args=(x_current,T_out_traj,plant),bounds=tuple([(-20,20)]*self.N),method='SLSQP')
        if not res.success: raise RuntimeError(res.message)
        return res.x

class PIController:
    """Discrete PI with clamped integral anti-windup."""
    def __init__(self, kp=2.5, ki=.12, u_min=-20., u_max=20., i_min=-100., i_max=100.):
        self.kp=kp; self.ki=ki; self.u_min=u_min; self.u_max=u_max; self.i_min=i_min; self.i_max=i_max; self.integral=0.
    def step(self, measurement, reference):
        error=float(reference-measurement); candidate=self.kp*error+self.ki*self.integral
        u=float(np.clip(candidate,self.u_min,self.u_max))
        # conditional integration prevents further windup at a saturated limit
        if not ((u >= self.u_max and error > 0) or (u <= self.u_min and error < 0)):
            self.integral=float(np.clip(self.integral+error,self.i_min,self.i_max))
        return u

class EdgeEventTrigger:
    def __init__(self,sigma=.05,delta=.2): self.sigma=sigma; self.delta=delta
    def check_trigger(self,x_current,x_last_sent):
        e=x_current-x_last_sent; return bool(np.linalg.norm(e)**2 > (self.sigma*np.linalg.norm(x_current)**2+self.delta))
EdgeAIEventTrigger=EdgeEventTrigger

class TraceBasedChannel:
    """Replay synthetic weather-conditioned packet-status trace."""
    def __init__(self,trace_file):
        import pandas as pd; self.trace=pd.read_csv(trace_file)['packet_status'].values; self.idx=0
    def step(self): val=self.trace[self.idx%len(self.trace)]; self.idx+=1; return val

class LoRaEnergyModel:
    def __init__(self,e_tx=20.,e_sleep=3.): self.e_tx=e_tx; self.e_sleep=e_sleep
    def components(self,transmissions,total_steps):
        tx=float(transmissions*self.e_tx); base=float(total_steps*self.e_sleep)
        return {'tx_energy_mj':tx,'baseline_energy_mj':base,'total_modeled_energy_mj':tx+base}
    def compute(self,transmissions,total_steps): return self.components(transmissions,total_steps)['total_modeled_energy_mj']
