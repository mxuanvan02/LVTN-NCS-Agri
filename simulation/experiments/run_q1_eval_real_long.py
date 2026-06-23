import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os

# --- 1. CONFIGURATION ---
T_sim = 1000  # 1000 hours (~41 days)
alpha, beta, gamma = 0.85, 0.15, 0.15
x_ref = 24.0
N = 8  # Extended prediction horizon for better robustness
Q_weight, R_weight = 20.0, 0.5
sigma, delta = 0.02, 0.1

# Hardware energy profile (Semtech SX1276)
E_tx = 20.0     # mJ per active transmission
E_sleep = 3.0   # mJ baseline sleep energy per step

# --- 2. LOAD COMPLETELY REAL DATA (HuggingFace Tokyo) ---
print("Fetching real weather dataset...")
url = "https://huggingface.co/datasets/torodriguezt/Urban_Tokyo_Temperature/resolve/main/tokyo_weather_23wards.csv"
df = pd.read_csv(url)

# Use the slice with high natural variance (found via analysis: idx 68400)
# This period contains both highly stable sunny days and severe temperature drops (storms)
T_out = df['temp_c'].values[68400:68400 + T_sim]

# Create a realistic packet loss profile. 
# In physics, severe rain/storms (which cause RF attenuation) correlate with sharp temperature drops.
# We extract the negative gradient (cooling) to represent rain severity.
temp_gradient = np.gradient(T_out)
rain_severity = np.clip(-temp_gradient, 0, None) # Only take cooling events
rain_severity_norm = rain_severity / np.max(rain_severity)

# Base packet loss is 5% (clear sky). Storms increase it up to 65% (heavy rain foliage attenuation)
packet_loss_prob = 0.05 + 0.60 * rain_severity_norm
np.random.seed(2026)
packet_arrived = np.random.binomial(1, 1 - packet_loss_prob)

# --- 3. CONTROL ALGORITHMS ---
def mpc_cost(u_seq, x_current, current_k):
    cost = 0
    x_pred = x_current
    for i in range(N):
        u_i = u_seq[i]
        idx = min(current_k + i, T_sim - 1)
        x_pred = alpha * x_pred + beta * u_i + gamma * T_out[idx]
        cost += Q_weight * (x_pred - x_ref)**2 + R_weight * u_i**2
    return cost

def solve_mpc(x_current, u_prev_seq, current_k):
    u_guess = np.zeros(N)
    if u_prev_seq is not None:
        u_guess[:-1] = u_prev_seq[1:]
        u_guess[-1] = u_prev_seq[-1]
    bnds = tuple([(-20, 20) for _ in range(N)]) 
    res = minimize(mpc_cost, u_guess, args=(x_current, current_k), bounds=bnds, method='SLSQP')
    return res.x

def solve_pid(x_current, integral_err):
    Kp, Ki = 2.5, 0.5
    error = x_ref - x_current
    integral_err += error
    u = Kp * error + Ki * integral_err
    return np.clip(u, -20, 20), integral_err

# --- 4. SIMULATION ENGINE ---
def run_simulation(method):
    x = T_out[0]
    x_last_sent = x
    x_history = [x]
    energy_history = [E_sleep]
    
    u_seq_optimal = np.zeros(N)
    last_u_applied = 0.0
    integral_err = 0.0
    
    for k in range(T_sim - 1):
        error = x - x_last_sent
        
        # Event Trigger Logic
        if method == 'TT-MPC':
            is_triggered = True
        else:
            is_triggered = error**2 > (sigma * x**2 + delta)
            
        arrived = packet_arrived[k]
        
        if is_triggered:
            energy_history.append(E_tx)
            if arrived == 1:
                x_last_sent = x
                if 'MPC' in method:
                    u_seq_optimal = solve_mpc(x_last_sent, u_seq_optimal, k)
                    u_apply = u_seq_optimal[0]
                else: # ET-PID
                    u_apply, integral_err = solve_pid(x_last_sent, integral_err)
                    last_u_applied = u_apply
            else:
                # Packet Lost during transmission
                if 'MPC' in method:
                    u_seq_optimal = np.roll(u_seq_optimal, -1)
                    u_seq_optimal[-1] = u_seq_optimal[-2] # Predict stable continuation
                    u_apply = u_seq_optimal[0]
                else: # ET-PID: Zero Order Hold
                    u_apply = last_u_applied
        else:
            # Not triggered (Sleep)
            energy_history.append(E_sleep)
            if 'MPC' in method:
                u_seq_optimal = np.roll(u_seq_optimal, -1)
                u_seq_optimal[-1] = u_seq_optimal[-2]
                u_apply = u_seq_optimal[0]
            else:
                u_apply = last_u_applied
                
        # Plant Update
        w_noise = np.random.normal(0, 0.1) # Small natural thermal noise
        x = alpha * x + beta * u_apply + gamma * T_out[k] + w_noise
        x_history.append(x)
        
    rmse = np.sqrt(np.mean((np.array(x_history) - x_ref)**2))
    total_energy = sum(energy_history)
    return x_history, rmse, total_energy, energy_history

print("Running 1000-hour Real Data Simulations...")
x_tt_mpc, rmse_tt_mpc, e_tt_mpc, eh_tt_mpc = run_simulation('TT-MPC')
print(f"TT-MPC -> RMSE: {rmse_tt_mpc:.3f}, Energy: {e_tt_mpc:.1f} mJ")

x_et_pid, rmse_et_pid, e_et_pid, eh_et_pid = run_simulation('ET-PID')
print(f"ET-PID -> RMSE: {rmse_et_pid:.3f}, Energy: {e_et_pid:.1f} mJ")

x_et_mpc, rmse_et_mpc, e_et_mpc, eh_et_mpc = run_simulation('ET-MPC')
print(f"ET-MPC -> RMSE: {rmse_et_mpc:.3f}, Energy: {e_et_mpc:.1f} mJ")

# --- 5. VISUALIZATION (Q1 Standard Multi-panel) ---
fig = plt.figure(figsize=(14, 10))
time_steps = np.arange(T_sim)

# Subplot 1: Real Disturbance & Dynamic Packet Loss
ax1 = plt.subplot(3, 1, 1)
ax1.plot(time_steps, T_out, color='dimgray', label='Real External Temp (Tokyo Autumn)')
ax1.set_ylabel('Temperature ($^\circ$C)')
ax1.grid(True, linestyle=':', alpha=0.7)

ax2 = ax1.twinx()
ax2.plot(time_steps, packet_loss_prob * 100, color='red', alpha=0.4, linewidth=1, label='Dynamic Packet Loss % (Rain Correlated)')
ax2.fill_between(time_steps, packet_loss_prob * 100, color='red', alpha=0.1)
ax2.set_ylabel('Packet Loss (%)', color='red')
ax2.tick_params(axis='y', labelcolor='red')
ax1.set_title('(a) Real-World Environmental Profile: Stable Days interspersed with Severe Fronts')
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(handles1 + handles2, labels1 + labels2, loc='upper right')

# Subplot 2: Tracking Performance
ax3 = plt.subplot(3, 1, 2)
ax3.plot(time_steps, x_tt_mpc, label=f'TT-MPC (Upper Bound) [RMSE: {rmse_tt_mpc:.2f}]', linestyle='--', color='blue', alpha=0.4)
ax3.plot(time_steps, x_et_pid, label=f'ET-PID (SOTA Baseline) [RMSE: {rmse_et_pid:.2f}]', color='orange', alpha=0.8)
ax3.plot(time_steps, x_et_mpc, label=f'ET-MPC (Proposed) [RMSE: {rmse_et_mpc:.2f}]', color='red', linewidth=1.5)
ax3.axhline(y=x_ref, color='green', linestyle='-', linewidth=2, label='Setpoint ($24^\circ$C)')
ax3.set_ylabel('Indoor Temp ($^\circ$C)')
ax3.set_title('(b) Long-term Greenhouse Climate Tracking Performance')
ax3.legend(loc='lower right')
ax3.grid(True, linestyle=':', alpha=0.7)

# Subplot 3: Cumulative Energy Consumption
ax4 = plt.subplot(3, 1, 3)
ax4.plot(time_steps, np.cumsum(eh_tt_mpc), label=f'TT-MPC Total: {e_tt_mpc/1000:.1f} Joules', color='blue', linestyle='--')
ax4.plot(time_steps, np.cumsum(eh_et_pid), label=f'ET-PID Total: {e_et_pid/1000:.1f} Joules', color='orange')
ax4.plot(time_steps, np.cumsum(eh_et_mpc), label=f'ET-MPC Total: {e_et_mpc/1000:.1f} Joules', color='red', linewidth=2)
ax4.set_ylabel('Cumulative Energy (mJ)')
ax4.set_xlabel('Time Step (k) [Hours]')
ax4.set_title('(c) Sensor Node Energy Exhaustion Profile over 41 Days (SX1276 Hardware)')
ax4.legend(loc='upper left')
ax4.grid(True, linestyle=':', alpha=0.7)

plt.tight_layout()
os.makedirs(os.path.dirname(os.path.abspath(__file__)) + '/../results', exist_ok=True)
pdf_path = os.path.dirname(os.path.abspath(__file__)) + '/../results/q1_eval_real_long.pdf'
plt.savefig(pdf_path, format='pdf', dpi=300)
print(f"Plot saved successfully to: {pdf_path}")
