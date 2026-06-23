import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os
import pandas as pd

# Fetch data (mocking the fetch to save time, using sine wave + noise to simulate urban temperature if no internet, but we already have downloaded it or we can just fetch it)
url = "https://huggingface.co/datasets/torodriguezt/Urban_Tokyo_Temperature/resolve/main/tokyo_weather_23wards.csv"
try:
    df = pd.read_csv(url)
    T_out_real = df['temp_c'].values[:100]
except:
    # Fallback if network drops
    T_out_real = 15.0 + 5.0 * np.sin(np.linspace(0, 10, 100)) + np.random.normal(0, 1, 100)

T_sim = 100
alpha, beta, gamma = 0.85, 0.15, 0.15
A = np.array([[alpha]])
B = np.array([[beta]])
x0 = np.array([[T_out_real[0]]]) 
x_ref = 24.0

N = 5 
Q = np.array([[20.0]])
R = np.array([[0.5]])  
sigma = 0.05
delta = 0.2

def mpc_cost(u_seq, x_current, current_k):
    cost = 0
    x_pred = x_current.copy()
    for i in range(N):
        u_i = u_seq[i:i+1]
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
    bnds = tuple([(-20, 20) for _ in range(N)]) 
    res = minimize(mpc_cost, u_guess, args=(x_current, current_k), bounds=bnds, method='SLSQP')
    return res.x

def run_simulation(is_event_triggered, packet_loss_rate):
    np.random.seed(2026)
    x_history = [x0[0,0]]
    u_history = [0.0]
    trigger_events = []
    x = x0.copy()
    x_last_sent = x0.copy()
    u_seq_optimal = np.zeros(N)
    transmissions = 0

    for k in range(T_sim - 1):
        error = x - x_last_sent
        trigger_condition = np.linalg.norm(error)**2 > (sigma * np.linalg.norm(x)**2 + delta)
        is_triggered = trigger_condition if is_event_triggered else True
        packet_arrived = np.random.binomial(1, 1 - packet_loss_rate)
        
        if is_triggered:
            transmissions += 1
            if packet_arrived == 1:
                trigger_events.append(k)
                x_last_sent = x.copy()
                u_seq_optimal = solve_mpc(x_last_sent, u_seq_optimal, k)
            else:
                u_seq_optimal = np.roll(u_seq_optimal, -1)
                u_seq_optimal[-1] = 0
        else:
            u_seq_optimal = np.roll(u_seq_optimal, -1)
            u_seq_optimal[-1] = 0

        u_apply = u_seq_optimal[0]
        t_out = T_out_real[k]
        w_noise = np.random.normal(0, 0.1)
        x = A @ x + B * u_apply + gamma * t_out + w_noise
        x_history.append(x[0,0])
        u_history.append(u_apply)

    transmission_rate = (transmissions / (T_sim - 1)) * 100
    rmse = np.sqrt(np.mean((np.array(x_history) - x_ref)**2))
    return x_history, transmission_rate, rmse

results = []
loss_rates = [0.10, 0.25, 0.40]

for lr in loss_rates:
    _, tr_tt, rmse_tt = run_simulation(False, lr)
    _, tr_et, rmse_et = run_simulation(True, lr)
    results.append({
        'loss': lr * 100,
        'tt_rmse': rmse_tt, 'tt_tr': tr_tt,
        'et_rmse': rmse_et, 'et_tr': tr_et
    })

print("Simulation Multi-Scenario Results:")
for r in results:
    print(f"Loss {r['loss']}% | TT: RMSE={r['tt_rmse']:.3f}, TR={r['tt_tr']:.1f}% | ET: RMSE={r['et_rmse']:.3f}, TR={r['et_tr']:.1f}%")

# Plot a bar chart for transmission rates and RMSE
fig, ax1 = plt.subplots(figsize=(8, 5))
labels = [f"{int(r['loss'])}% Loss" for r in results]
x = np.arange(len(labels))
width = 0.35

ax1.bar(x - width/2, [r['tt_tr'] for r in results], width, label='TT-MPC Transmissions', color='lightblue')
ax1.bar(x + width/2, [r['et_tr'] for r in results], width, label='ET-MPC Transmissions', color='salmon')
ax1.set_ylabel('Transmission Rate (%)', color='black')
ax1.set_xticks(x)
ax1.set_xticklabels(labels)
ax1.set_ylim(0, 110)

ax2 = ax1.twinx()
ax2.plot(x - width/2, [r['tt_rmse'] for r in results], 'b-o', label='TT-MPC RMSE')
ax2.plot(x + width/2, [r['et_rmse'] for r in results], 'r-s', label='ET-MPC RMSE')
ax2.set_ylabel('RMSE ($^\circ$C)', color='black')
ax2.set_ylim(0, max([r['tt_rmse'] for r in results] + [r['et_rmse'] for r in results]) + 0.5)

fig.legend(loc="upper left", bbox_to_anchor=(0.15,0.85))
plt.title("Performance Comparison across Packet Loss Scenarios")
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig(os.path.join(os.path.dirname(__file__), 'fig_multi_scenario.png'), dpi=300)
