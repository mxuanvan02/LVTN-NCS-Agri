import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.models import GreenhousePlant, Controllers, EdgeAIEventTrigger, TraceBasedChannel, LoRaEnergyModel

def run_dataset_eval(dataset_name, T_out_real, use_trace=False):
    T_sim = 300
    plant = GreenhousePlant()
    ctrl = Controllers()
    et_logic = EdgeAIEventTrigger()
    energy_mdl = LoRaEnergyModel()
    
    x0 = np.array([[T_out_real[0]]])

    def simulate(method):
        np.random.seed(2026)
        if use_trace:
            trace_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'empirical_lora_trace.csv')
            channel = TraceBasedChannel(trace_path)
        else:
            class DummyChannel:
                def step(self): return 1 if np.random.rand() > 0.3 else 0
            channel = DummyChannel()

        x = x0.copy(); x_last = x0.copy()
        u_seq = np.zeros(ctrl.N); last_pid = 0.0
        hist_x = [x[0,0]]; transmissions = 0
        drops = 0

        for k in range(T_sim - 1):
            is_trig = True if method == 'TT-MPC' else et_logic.check_trigger(x, x_last)
            packet_arrived = channel.step()
            if packet_arrived == 0: drops += 1
            
            if is_trig:
                transmissions += 1
                if packet_arrived == 1:
                    x_last = x.copy()
                    if 'MPC' in method:
                        t_traj = [T_out_real[min(k+i, T_sim-1)] for i in range(ctrl.N)]
                        u_seq = ctrl.solve_mpc(x_last, u_seq, t_traj, plant)
                        u_app = u_seq[0]
                    else:
                        u_app = ctrl.solve_pid(x_last)
                        last_pid = u_app
                else: # Loss
                    if 'MPC' in method:
                        u_seq = np.roll(u_seq, -1); u_seq[-1] = 0; u_app = u_seq[0]
                    else: u_app = last_pid
            else: # No trigger
                if 'MPC' in method:
                    u_seq = np.roll(u_seq, -1); u_seq[-1] = 0; u_app = u_seq[0]
                else: u_app = last_pid

            x = plant.step(x, u_app, T_out_real[k])
            hist_x.append(x[0,0])

        rmse = np.sqrt(np.mean((np.array(hist_x) - ctrl.x_ref)**2))
        energy_mj = energy_mdl.compute(transmissions, T_sim)
        real_loss_rate = (drops / T_sim) * 100
        return hist_x, energy_mj, rmse, real_loss_rate

    x_tt, e_tt, r_tt, lr = simulate('TT-MPC')
    x_pid, e_pid, r_pid, _ = simulate('ET-PID')
    x_et, e_et, r_et, _ = simulate('ET-MPC')
    
    return {'T_out': T_out_real, 'x_tt': x_tt, 'x_pid': x_pid, 'x_et': x_et, 
            'e_tt': e_tt, 'e_pid': e_pid, 'e_et': e_et, 
            'r_tt': r_tt, 'r_pid': r_pid, 'r_et': r_et, 'loss': lr}

# 1. Load Tokyo Data
tokyo_df = pd.read_csv(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyo_weather.csv'))
res_tokyo = run_dataset_eval('Tokyo', tokyo_df['temp_c'].values[1000:1300], use_trace=False)

# 2. Load Vietnam Mekong Data (with Empirical LoRa Trace)
vn_df = pd.read_csv(os.path.join(os.path.dirname(__file__), '..', 'data', 'vietnam_mekong_weather.csv'))
res_vn = run_dataset_eval('Mekong Delta', vn_df['temp_c'].values[:300], use_trace=True)

# ================= PLOTTING TO PDF =================
fig, axs = plt.subplots(2, 2, figsize=(14, 10))

# Top-Left: Tokyo Tracking
axs[0,0].plot(res_tokyo['x_tt'], label=f"TT-MPC (RMSE: {res_tokyo['r_tt']:.2f})", linestyle='--', color='blue', alpha=0.5)
axs[0,0].plot(res_tokyo['x_pid'], label=f"ET-PID (RMSE: {res_tokyo['r_pid']:.2f})", linestyle='-.', color='orange')
axs[0,0].plot(res_tokyo['x_et'], label=f"ET-MPC (RMSE: {res_tokyo['r_et']:.2f})", color='red', linewidth=1.5)
axs[0,0].plot(res_tokyo['T_out'], color='gray', alpha=0.3, label='Tokyo Weather')
axs[0,0].axhline(y=24.0, color='green', linestyle='-')
axs[0,0].set_title(f"Urban Tokyo (Bursty Loss: {res_tokyo['loss']:.1f}%)")
axs[0,0].set_ylabel('Temp ($^\circ$C)')
axs[0,0].legend(fontsize='small')
axs[0,0].grid(True, linestyle='--', alpha=0.5)

# Top-Right: Mekong Tracking
axs[0,1].plot(res_vn['x_tt'], label=f"TT-MPC (RMSE: {res_vn['r_tt']:.2f})", linestyle='--', color='blue', alpha=0.5)
axs[0,1].plot(res_vn['x_pid'], label=f"ET-PID (RMSE: {res_vn['r_pid']:.2f})", linestyle='-.', color='orange')
axs[0,1].plot(res_vn['x_et'], label=f"ET-MPC (RMSE: {res_vn['r_et']:.2f})", color='red', linewidth=1.5)
axs[0,1].plot(res_vn['T_out'], color='gray', alpha=0.3, label='Mekong Weather (Monsoon)')
axs[0,1].axhline(y=24.0, color='green', linestyle='-')
axs[0,1].set_title(f"Mekong Delta, VN (Bursty Loss: {res_vn['loss']:.1f}%)")
axs[0,1].set_ylabel('Temp ($^\circ$C)')
axs[0,1].legend(fontsize='small')
axs[0,1].grid(True, linestyle='--', alpha=0.5)

# Bottom-Left: Tracking Error Comparison
methods = ['TT-MPC', 'ET-PID', 'ET-MPC']
x_pos = np.arange(len(methods))
w = 0.35
axs[1,0].bar(x_pos - w/2, [res_tokyo['r_tt'], res_tokyo['r_pid'], res_tokyo['r_et']], w, label='Tokyo RMSE', color='skyblue')
axs[1,0].bar(x_pos + w/2, [res_vn['r_tt'], res_vn['r_pid'], res_vn['r_et']], w, label='Mekong RMSE', color='salmon')
axs[1,0].set_xticks(x_pos)
axs[1,0].set_xticklabels(methods)
axs[1,0].set_ylabel('RMSE ($^\circ$C)')
axs[1,0].set_title('Robustness Comparison (Tracking Error)')
axs[1,0].legend()
axs[1,0].grid(True, axis='y', linestyle='--', alpha=0.5)

# Bottom-Right: Energy Consumption
axs[1,1].bar(x_pos - w/2, [res_tokyo['e_tt'], res_tokyo['e_pid'], res_tokyo['e_et']], w, label='Tokyo Energy', color='skyblue')
axs[1,1].bar(x_pos + w/2, [res_vn['e_tt'], res_vn['e_pid'], res_vn['e_et']], w, label='Mekong Energy', color='salmon')
axs[1,1].set_xticks(x_pos)
axs[1,1].set_xticklabels(methods)
axs[1,1].set_ylabel('Energy Consumed (mJ)')
axs[1,1].set_title('Sensor Energy Efficiency (LoRa Model)')
axs[1,1].legend()
axs[1,1].grid(True, axis='y', linestyle='--', alpha=0.5)

plt.tight_layout()
out_path = os.path.join(os.path.dirname(__file__), '..', 'results', 'q1_eval.pdf')
plt.savefig(out_path, format='pdf', dpi=300)
print(f"Saved Q1 Evaluation Results to {out_path}")
