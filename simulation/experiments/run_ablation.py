import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.models import GreenhousePlant, Controllers, EdgeAIEventTrigger

def run_experiment():
    # 1. Load Data
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyo_weather.csv')
    df = pd.read_csv(data_path)
    T_out_real = df['temp_c'].values[1000:1300]
    T_sim = 300

    # 2. Init Modules
    plant = GreenhousePlant()
    ctrl = Controllers()
    et_logic = EdgeAIEventTrigger()
    
    packet_loss_rate = 0.30
    x0 = np.array([[T_out_real[0]]])

    def simulate(method):
        np.random.seed(2026)
        x = x0.copy()
        x_last = x0.copy()
        u_seq = np.zeros(ctrl.N)
        last_pid = 0.0
        
        hist_x, hist_u, triggers = [x[0,0]], [0.0], []
        transmissions = 0

        for k in range(T_sim - 1):
            # Event Triggering
            if method == 'TT-MPC':
                is_trig = True
            else:
                is_trig = et_logic.check_trigger(x, x_last)
                
            packet_arrived = np.random.binomial(1, 1 - packet_loss_rate)
            
            if is_trig:
                transmissions += 1
                if packet_arrived == 1:
                    triggers.append(k)
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
                        u_seq = np.roll(u_seq, -1)
                        u_seq[-1] = 0
                        u_app = u_seq[0]
                    else:
                        u_app = last_pid
            else: # No trigger
                if 'MPC' in method:
                    u_seq = np.roll(u_seq, -1)
                    u_seq[-1] = 0
                    u_app = u_seq[0]
                else:
                    u_app = last_pid

            # Plant update
            x = plant.step(x, u_app, T_out_real[k])
            hist_x.append(x[0,0])
            hist_u.append(u_app)

        rmse = np.sqrt(np.mean((np.array(hist_x) - ctrl.x_ref)**2))
        tr_rate = (transmissions / (T_sim - 1)) * 100
        return hist_x, tr_rate, rmse, triggers

    print("Running TT-MPC...")
    x_tt, tr_tt, rmse_tt, _ = simulate('TT-MPC')
    print("Running ET-PID (SOTA)...")
    x_pid, tr_pid, rmse_pid, _ = simulate('ET-PID')
    print("Running ET-MPC (Proposed)...")
    x_et, tr_et, rmse_et, tr_ev = simulate('ET-MPC')

    # Plot
    plt.figure(figsize=(12, 8))
    plt.subplot(3, 1, 1)
    plt.plot(T_out_real[:T_sim], color='gray', label='Urban Tokyo Weather')
    plt.ylabel('Temp ($^\circ$C)')
    plt.legend()

    plt.subplot(3, 1, 2)
    plt.plot(x_tt, label=f'TT-MPC - RMSE: {rmse_tt:.2f}', linestyle='--', color='blue', alpha=0.5)
    plt.plot(x_pid, label=f'ET-PID - RMSE: {rmse_pid:.2f}', linestyle='-.', color='orange')
    plt.plot(x_et, label=f'ET-MPC - RMSE: {rmse_et:.2f}', color='red', linewidth=1.5)
    plt.axhline(y=ctrl.x_ref, color='green', linestyle='-')
    plt.ylabel('Indoor Temp ($^\circ$C)')
    plt.legend(loc='lower right', fontsize='small')

    plt.subplot(3, 1, 3)
    plt.stem(tr_ev, np.ones_like(tr_ev), linefmt='r-', markerfmt='ro', basefmt=' ')
    plt.ylabel('Transmission')
    plt.xlabel('Time Step (k)')
    plt.title(f'ET-MPC Transmissions (Rate: {tr_et:.1f}%)')

    plt.tight_layout()
    out_path = os.path.join(os.path.dirname(__file__), '..', 'results', 'ablation_study.pdf')
    plt.savefig(out_path, format='pdf', dpi=300)
    print(f"Saved results to {out_path}")

if __name__ == "__main__":
    run_experiment()
