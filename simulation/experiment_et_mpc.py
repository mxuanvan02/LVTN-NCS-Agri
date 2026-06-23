import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import os

# ==========================================
# SYSTEM PARAMETERS (Greenhouse Temperature Model)
# ==========================================
# LTI discrete-time model: x(k+1) = Ax(k) + Bu(k) + w(k)
A = np.array([[0.95]])
B = np.array([[0.1]])
x0 = np.array([[20.0]]) # Initial temperature (e.g., 20 degrees)
x_ref = 25.0 # Target temperature

# MPC Parameters
N = 5 # Prediction horizon
Q = np.array([[10.0]]) # State penalty
R = np.array([[1.0]])  # Control penalty

# Network & Event-Trigger parameters
sigma = 0.05 # Relative threshold
delta = 0.1  # Absolute threshold to avoid Zeno behavior
packet_loss_rate = 0.2 # 20% packet loss probability

# Simulation parameters
T = 60 # Simulation steps
w_noise_std = 0.1 # Disturbance noise

# ==========================================
# MPC OPTIMIZATION FUNCTION
# ==========================================
def mpc_cost(u_seq, x_current):
    cost = 0
    x_pred = x_current.copy()
    for i in range(N):
        u_i = u_seq[i:i+1]
        x_pred = A @ x_pred + B @ u_i
        cost += (x_pred - x_ref).T @ Q @ (x_pred - x_ref) + u_i.T @ R @ u_i
    return cost.item()

def solve_mpc(x_current, u_prev_seq):
    # Initial guess from previous sequence (shifted)
    u_guess = np.zeros(N)
    if u_prev_seq is not None:
        u_guess[:-1] = u_prev_seq[1:]
        u_guess[-1] = u_prev_seq[-1]
        
    bnds = tuple([(-10, 10) for _ in range(N)]) # Control constraints
    res = minimize(mpc_cost, u_guess, args=(x_current,), bounds=bnds, method='SLSQP')
    return res.x # Returns the optimal control sequence

# ==========================================
# SIMULATION LOOP
# ==========================================
def run_simulation(is_event_triggered=True):
    np.random.seed(42)
    
    x_history = [x0[0,0]]
    u_history = [0.0]
    trigger_events = []
    
    x = x0.copy()
    x_last_sent = x0.copy()
    u_seq_optimal = np.zeros(N)
    
    transmissions = 0

    for k in range(T):
        # 1. Edge Node evaluates Event-Trigger Condition
        error = x - x_last_sent
        trigger_condition = np.linalg.norm(error)**2 > (sigma * np.linalg.norm(x)**2 + delta)
        
        is_triggered = trigger_condition if is_event_triggered else True
        
        # 2. Network Transmission (with packet loss)
        gamma = np.random.binomial(1, 1 - packet_loss_rate) # 1 if delivered, 0 if lost
        
        if is_triggered:
            trigger_events.append(k)
            transmissions += 1
            if gamma == 1:
                # Successfully received by controller
                x_last_sent = x.copy()
                u_seq_optimal = solve_mpc(x_last_sent, u_seq_optimal)
            else:
                # Packet lost -> Use previous MPC prediction
                u_seq_optimal = np.roll(u_seq_optimal, -1)
                u_seq_optimal[-1] = 0 # Assume zero terminal control or hold
        else:
            # No trigger -> Controller uses previous prediction
            u_seq_optimal = np.roll(u_seq_optimal, -1)
            u_seq_optimal[-1] = 0

        # Apply control input (first element of sequence)
        u_apply = u_seq_optimal[0]
        
        # Plant Dynamics Update
        w = np.random.normal(0, w_noise_std, (1,1))
        x = A @ x + B * u_apply + w
        
        x_history.append(x[0,0])
        u_history.append(u_apply)

    transmission_rate = (transmissions / T) * 100
    return x_history, u_history, trigger_events, transmission_rate

# Run both scenarios
print("Simulating Time-Triggered MPC (Periodic)...")
x_tt, u_tt, tr_tt, rate_tt = run_simulation(is_event_triggered=False)

print("Simulating Event-Triggered MPC with Edge-AI logic...")
x_et, u_et, tr_et, rate_et = run_simulation(is_event_triggered=True)

# ==========================================
# PLOTTING (IEEE Publication Quality)
# ==========================================
plt.figure(figsize=(10, 6))

# Subplot 1: System State (Temperature)
plt.subplot(2, 1, 1)
plt.plot(x_tt, label=f'Time-Triggered (Rate: {rate_tt:.1f}%)', linestyle='--', color='blue', alpha=0.7)
plt.plot(x_et, label=f'Event-Triggered (Rate: {rate_et:.1f}%)', color='red', linewidth=1.5)
plt.axhline(y=x_ref, color='green', linestyle=':', label='Reference')
plt.ylabel('Temperature (x)')
plt.title('State Response under Packet Loss (20%)')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)

# Subplot 2: Event Triggers
plt.subplot(2, 1, 2)
plt.stem(tr_et, np.ones_like(tr_et), linefmt='r-', markerfmt='ro', basefmt=' ')
plt.ylabel('Trigger Events')
plt.xlabel('Time Step (k)')
plt.title('Transmission Instants (Event-Triggered)')
plt.grid(True, linestyle='--', alpha=0.6)
plt.yticks([0, 1])

plt.tight_layout()
output_path = os.path.join(os.path.dirname(__file__), 'simulation_results.png')
plt.savefig(output_path, dpi=300)
print(f"Simulation completed. Savings in transmissions: {rate_tt - rate_et:.1f}%")
print(f"Results plot saved to: {output_path}")
