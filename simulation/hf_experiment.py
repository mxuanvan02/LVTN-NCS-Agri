import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os
import pandas as pd
import urllib.request

# ==========================================
# FETCH REAL DATA FROM HUGGING FACE
# ==========================================
print("Fetching real temperature dataset from Hugging Face...")
url = "https://huggingface.co/datasets/torodriguezt/Urban_Tokyo_Temperature/resolve/main/tokyo_weather_23wards.csv"

# Fetching using pandas
df = pd.read_csv(url)

# Extract a segment of temperature data (e.g., first 100 days/hours) to act as outside weather disturbance
T_sim = 100
# Assuming 'temp_c' is the column for temperature in Celsius
T_out_real = df['temp_c'].values[:T_sim]

# ==========================================
# SYSTEM PARAMETERS (Greenhouse Temperature Model)
# ==========================================
# LTI discrete-time model: T_in(k+1) = alpha*T_in(k) + beta*u(k) + gamma*T_out(k) + w(k)
alpha = 0.85
beta = 0.15
gamma = 0.15
A = np.array([[alpha]])
B = np.array([[beta]])
# Initial indoor temperature
x0 = np.array([[T_out_real[0]]]) 
x_ref = 24.0 # Target indoor temperature

# MPC Parameters
N = 5 # Prediction horizon
Q = np.array([[20.0]]) # State penalty (strict temperature control)
R = np.array([[0.5]])  # Control penalty (energy saving)

# Network & Event-Trigger parameters
sigma = 0.05 # Relative threshold
delta = 0.2  # Absolute threshold
packet_loss_rate = 0.25 # 25% packet loss probability in rural area

# ==========================================
# MPC OPTIMIZATION FUNCTION
# ==========================================
def mpc_cost(u_seq, x_current, current_k):
    cost = 0
    x_pred = x_current.copy()
    for i in range(N):
        u_i = u_seq[i:i+1]
        
        # We assume the outside temperature prediction is constant over the horizon (naive forecast)
        # or we just use the current T_out for the prediction
        idx = min(current_k + i, T_sim - 1)
        t_out_pred = T_out_real[idx]
        
        x_pred = A @ x_pred + B @ u_i + gamma * t_out_pred
        cost += (x_pred - x_ref).T @ Q @ (x_pred - x_ref) + u_i.T @ R @ u_i
    return cost.item()

def solve_mpc(x_current, u_prev_seq, current_k):
    u_guess = np.zeros(N)
    if u_prev_seq is not None:
        u_guess[:-1] = u_prev_seq[1:]
        u_guess[-1] = u_prev_seq[-1]
        
    bnds = tuple([(-15, 15) for _ in range(N)]) # HVAC Cooling/Heating bounds
    res = minimize(mpc_cost, u_guess, args=(x_current, current_k), bounds=bnds, method='SLSQP')
    return res.x

# ==========================================
# SIMULATION LOOP
# ==========================================
def run_simulation(is_event_triggered=True):
    np.random.seed(2026)
    
    x_history = [x0[0,0]]
    u_history = [0.0]
    trigger_events = []
    
    x = x0.copy()
    x_last_sent = x0.copy()
    u_seq_optimal = np.zeros(N)
    
    transmissions = 0

    for k in range(T_sim - 1):
        # 1. Edge Node evaluates Event-Trigger Condition
        error = x - x_last_sent
        trigger_condition = np.linalg.norm(error)**2 > (sigma * np.linalg.norm(x)**2 + delta)
        
        is_triggered = trigger_condition if is_event_triggered else True
        
        # 2. Network Transmission (with packet loss)
        packet_arrived = np.random.binomial(1, 1 - packet_loss_rate)
        
        if is_triggered:
            trigger_events.append(k)
            transmissions += 1
            if packet_arrived == 1:
                x_last_sent = x.copy()
                u_seq_optimal = solve_mpc(x_last_sent, u_seq_optimal, k)
            else:
                # Packet lost
                u_seq_optimal = np.roll(u_seq_optimal, -1)
                u_seq_optimal[-1] = 0
        else:
            # No trigger
            u_seq_optimal = np.roll(u_seq_optimal, -1)
            u_seq_optimal[-1] = 0

        # Apply control input
        u_apply = u_seq_optimal[0]
        
        # Real Plant Dynamics Update
        t_out = T_out_real[k]
        w_noise = np.random.normal(0, 0.1) # Small unmodeled noise
        x = A @ x + B * u_apply + gamma * t_out + w_noise
        
        x_history.append(x[0,0])
        u_history.append(u_apply)

    transmission_rate = (transmissions / (T_sim - 1)) * 100
    return x_history, u_history, trigger_events, transmission_rate

# Run both scenarios
print("Simulating Time-Triggered MPC (Periodic)...")
x_tt, u_tt, tr_tt, rate_tt = run_simulation(is_event_triggered=False)

print("Simulating Event-Triggered MPC with Edge-AI logic...")
x_et, u_et, tr_et, rate_et = run_simulation(is_event_triggered=True)

# ==========================================
# PLOTTING
# ==========================================
plt.figure(figsize=(10, 8))

# Subplot 1: Real Disturbance
plt.subplot(3, 1, 1)
plt.plot(T_out_real[:T_sim], color='gray', label='Outside Weather (Hugging Face Real Data)')
plt.ylabel('Outside Temp ($^\circ$C)')
plt.title('Hugging Face Urban Weather Dataset (Disturbance)')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()

# Subplot 2: System State (Indoor Temp)
plt.subplot(3, 1, 2)
plt.plot(x_tt, label=f'Time-Triggered (Rate: {rate_tt:.1f}%)', linestyle='--', color='blue', alpha=0.7)
plt.plot(x_et, label=f'Event-Triggered Edge-AI (Rate: {rate_et:.1f}%)', color='red', linewidth=1.5)
plt.axhline(y=x_ref, color='green', linestyle='-', label=f'Target Setpoint ({x_ref}$^\circ$C)')
plt.ylabel('Indoor Temp ($^\circ$C)')
plt.title(f'NCS State Tracking under {packet_loss_rate*100}% Packet Loss')
plt.legend(loc='lower right')
plt.grid(True, linestyle='--', alpha=0.6)

# Subplot 3: Event Triggers
plt.subplot(3, 1, 3)
plt.stem(tr_et, np.ones_like(tr_et), linefmt='r-', markerfmt='ro', basefmt=' ')
plt.ylabel('Transmission')
plt.xlabel('Time Step (k)')
plt.title('Communication Events (Edge-AI Transmissions)')
plt.grid(True, linestyle='--', alpha=0.6)
plt.yticks([0, 1])

plt.tight_layout()
output_path = os.path.join(os.path.dirname(__file__), 'hf_real_data_simulation.png')
plt.savefig(output_path, dpi=300)
print(f"\nExperiment finished!")
print(f"Time-Triggered transmitted {int((T_sim-1)*rate_tt/100)} times ({rate_tt:.1f}% bandwidth).")
print(f"Event-Triggered transmitted {int((T_sim-1)*rate_et/100)} times ({rate_et:.1f}% bandwidth).")
print(f"Bandwidth saved: {rate_tt - rate_et:.1f}%")
print(f"Results plot saved to: {output_path}")
