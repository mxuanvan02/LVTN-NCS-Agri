import numpy as np
from scipy.optimize import minimize

class GreenhousePlant:
    def __init__(self, alpha=0.85, beta=0.15, gamma=0.15):
        self.A = np.array([[alpha]])
        self.B = np.array([[beta]])
        self.gamma = gamma

    def step(self, x, u, t_out, noise_std=0.1):
        w_noise = np.random.normal(0, noise_std)
        return self.A @ x + self.B * np.array([[u]]) + self.gamma * t_out + w_noise

class Controllers:
    def __init__(self, N=5, Q=20.0, R=0.5, x_ref=24.0):
        self.N = N
        self.Q = np.array([[Q]])
        self.R = np.array([[R]])
        self.x_ref = x_ref

    def mpc_cost(self, u_seq, x_current, T_out_traj, plant):
        cost = 0
        x_pred = x_current.copy()
        for i in range(self.N):
            u_i = u_seq[i:i+1]
            t_out_pred = T_out_traj[i]
            x_pred = plant.A @ x_pred + plant.B @ u_i + plant.gamma * t_out_pred
            cost += (x_pred - self.x_ref).T @ self.Q @ (x_pred - self.x_ref) + u_i.T @ self.R @ u_i
        return cost.item()

    def solve_mpc(self, x_current, u_prev_seq, T_out_traj, plant):
        u_guess = np.zeros(self.N)
        if u_prev_seq is not None:
            u_guess[:-1] = u_prev_seq[1:]
            u_guess[-1] = u_prev_seq[-1]
        bnds = tuple([(-20, 20) for _ in range(self.N)]) 
        res = minimize(self.mpc_cost, u_guess, args=(x_current, T_out_traj, plant), bounds=bnds, method='SLSQP')
        if not res.success:
            raise RuntimeError(f'MPC optimization failed: {res.message}')
        return res.x

    def solve_pid(self, x_current, Kp=2.5, Ki=0.5):
        error = self.x_ref - x_current[0,0]
        return np.clip(Kp * error, -20, 20)

class EdgeEventTrigger:
    """Deterministic threshold-based edge event trigger.

    This is not a trained AI model. It implements the declared event-trigger rule
    used by the benchmark so that terminology remains auditable.
    """
    def __init__(self, sigma=0.05, delta=0.2):
        self.sigma = sigma
        self.delta = delta

    def check_trigger(self, x_current, x_last_sent):
        error = x_current - x_last_sent
        return bool(np.linalg.norm(error)**2 > (self.sigma * np.linalg.norm(x_current)**2 + self.delta))

# Backward-compatible alias for older experiment scripts.
EdgeAIEventTrigger = EdgeEventTrigger

class TraceBasedChannel:
    """Empirical packet loss trace replay"""
    def __init__(self, trace_file):
        import pandas as pd
        self.trace = pd.read_csv(trace_file)['packet_status'].values
        self.idx = 0

    def step(self):
        val = self.trace[self.idx % len(self.trace)]
        self.idx += 1
        return val

class LoRaEnergyModel:
    """Compute energy in mJ based on SX1276 params"""
    def __init__(self, e_tx=20.0, e_sleep=3.0):
        self.e_tx = e_tx
        self.e_sleep = e_sleep

    def compute(self, transmissions, total_steps):
        return (transmissions * self.e_tx) + (total_steps * self.e_sleep)
