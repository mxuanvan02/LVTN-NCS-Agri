import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os

# --- 1. CONFIGURATION & HARDWARE PROFILE ---
T_sim = 1000  # Extended to 1000 steps to show long-term reliability
alpha, beta, gamma = 0.85, 0.15, 0.15
x_ref = 24.0
N = 15
Q_weight, R_weight = 20.0, 0.5
sigma, delta = 0.05, 0.2

# Hardware energy profile (Semtech SX1276)
E_tx = 20.0     # mJ per active transmission
E_sleep = 3.0   # mJ baseline sleep energy per step

# --- 2. GENERATE "CORRELATED FAILURES" DATA ---
np.random.seed(42)
time_steps = np.arange(T_sim)

# Base weather: Mekong Delta diurnal cycle (avg 28C, swing 5C)
T_out = 28.0 + 5.0 * np.sin(2 * np.pi * time_steps / 240) + np.random.normal(0, 0.5, T_sim)
packet_loss_prob = np.ones(T_sim) * 0.10  # Normal condition: 10% packet loss

# Inject Extreme Storm 1 (Monsoon rain)
storm1_idx = (time_steps >= 300) & (time_steps <= 400)
T_out[storm1_idx] -= 8.0  # Sharp temperature drop due to rain
packet_loss_prob[storm1_idx] = 0.75  # 75% bursty packet loss due to RF attenuation

# Inject Extreme Storm 2
storm2_idx = (time_steps >= 700) & (time_steps <= 800)
T_out[storm2_idx] -= 6.0
packet_loss_prob[storm2_idx] = 0.65  # 65% loss

# Generate actual packet arrivals based on the dynamic probability
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
    
    total_tx = 0

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
            total_tx += 1
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
                    u_seq_optimal[-1] = u_seq_optimal[-2] # Prolonged outage fallback (ZOH on last optimal step)
                    u_apply = u_seq_optimal[0]
                else: # ET-PID: Zero Order Hold
                    u_apply = last_u_applied
        else:
            # Not triggered (Sleep)
            energy_history.append(E_sleep)
            if 'MPC' in method:
                u_seq_optimal = np.roll(u_seq_optimal, -1)
                u_seq_optimal[-1] = u_seq_optimal[-2] # Prolonged sleep fallback
                u_apply = u_seq_optimal[0]
            else:
                u_apply = last_u_applied
                
        # Plant Update
        w_noise = np.random.normal(0, 0.1)
        x = alpha * x + beta * u_apply + gamma * T_out[k] + w_noise
        x_history.append(x)
        
    rmse = np.sqrt(np.mean((np.array(x_history) - x_ref)**2))
    total_energy = sum(energy_history)
    return x_history, rmse, total_energy, energy_history

print("Running Simulations...")
x_tt_mpc, rmse_tt_mpc, e_tt_mpc, eh_tt_mpc = run_simulation('TT-MPC')
print(f"TT-MPC -> RMSE: {rmse_tt_mpc:.3f}, Energy: {e_tt_mpc:.1f} mJ")

x_et_pid, rmse_et_pid, e_et_pid, eh_et_pid = run_simulation('ET-PID')
print(f"ET-PID -> RMSE: {rmse_et_pid:.3f}, Energy: {e_et_pid:.1f} mJ")

x_et_mpc, rmse_et_mpc, e_et_mpc, eh_et_mpc = run_simulation('ET-MPC')
print(f"ET-MPC -> RMSE: {rmse_et_mpc:.3f}, Energy: {e_et_mpc:.1f} mJ")

# --- 5. VISUALIZATION (Q1 Standard Multi-panel) ---
fig = plt.figure(figsize=(14, 10))

# Subplot 1: Correlated Disturbance & Packet Loss
ax1 = plt.subplot(3, 1, 1)
ax1.plot(T_out, color='dimgray', label='External Temp (Mekong Delta)')
ax1.set_ylabel('Temperature ($^\circ$C)')
ax1.grid(True, linestyle=':', alpha=0.7)

ax2 = ax1.twinx()
ax2.fill_between(time_steps, packet_loss_prob * 100, color='red', alpha=0.2, label='Packet Loss % (Storm)')
ax2.set_ylabel('Packet Loss (%)', color='red')
ax2.tick_params(axis='y', labelcolor='red')
ax1.set_title('(a) Correlated Failures: Monsoon Rains and Bursty RF Attenuation')
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(handles1 + handles2, labels1 + labels2, loc='upper right')

# Subplot 2: Tracking Performance
ax3 = plt.subplot(3, 1, 2)
ax3.plot(x_tt_mpc, label=f'TT-MPC (Upper Bound) [RMSE: {rmse_tt_mpc:.2f}]', linestyle='--', color='blue', alpha=0.4)
ax3.plot(x_et_pid, label=f'ET-PID (SOTA Baseline) [RMSE: {rmse_et_pid:.2f}]', color='orange')
ax3.plot(x_et_mpc, label=f'ET-MPC (Proposed) [RMSE: {rmse_et_mpc:.2f}]', color='red', linewidth=1.5)
ax3.axhline(y=x_ref, color='green', linestyle='-', label='Setpoint ($24^\circ$C)')
# Highlight storms
ax3.axvspan(300, 400, color='gray', alpha=0.1)
ax3.axvspan(700, 800, color='gray', alpha=0.1)
ax3.set_ylabel('Indoor Temp ($^\circ$C)')
ax3.set_title('(b) Greenhouse Climate Tracking Performance under Correlated Failures')
ax3.legend(loc='lower right')
ax3.grid(True, linestyle=':', alpha=0.7)

# Subplot 3: Cumulative Energy Consumption
ax4 = plt.subplot(3, 1, 3)
ax4.plot(np.cumsum(eh_tt_mpc), label=f'TT-MPC Total: {e_tt_mpc/1000:.1f} Joules', color='blue', linestyle='--')
ax4.plot(np.cumsum(eh_et_pid), label=f'ET-PID Total: {e_et_pid/1000:.1f} Joules', color='orange')
ax4.plot(np.cumsum(eh_et_mpc), label=f'ET-MPC Total: {e_et_mpc/1000:.1f} Joules', color='red', linewidth=2)
ax4.set_ylabel('Cumulative Energy (mJ)')
ax4.set_xlabel('Time Step (k)')
ax4.set_title('(c) Sensor Node Energy Exhaustion Profile (Semtech SX1276)')
ax4.legend(loc='upper left')
ax4.grid(True, linestyle=':', alpha=0.7)

plt.tight_layout()
os.makedirs(os.path.dirname(os.path.abspath(__file__)) + '/../results', exist_ok=True)
pdf_path = os.path.dirname(os.path.abspath(__file__)) + '/../results/q1_eval_extreme.pdf'
plt.savefig(pdf_path, format='pdf', dpi=300)
print(f"Plot saved successfully to: {pdf_path}")
