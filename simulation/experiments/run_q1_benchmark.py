import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.models import Controllers, EdgeAIEventTrigger, GreenhousePlant, LoRaEnergyModel, TraceBasedChannel


@dataclass
class Scenario:
    name: str
    weather: np.ndarray
    channel: str
    loss_rate: float = 0.30
    trace_file: str = ""


def make_channel(kind: str, seed: int, loss_rate: float, trace_file: str = ""):
    rng = np.random.default_rng(seed)

    class BernoulliChannel:
        def step(self):
            return 1 if rng.random() > loss_rate else 0

    class MarkovBurstChannel:
        def __init__(self):
            self.bad = False

        def step(self):
            # Good state: mostly successful, occasionally enters burst-loss state.
            # Bad state: mostly failed, occasionally recovers.
            if self.bad:
                success = rng.random() > 0.75
                if rng.random() < 0.35:
                    self.bad = False
            else:
                success = rng.random() > 0.08
                if rng.random() < 0.05:
                    self.bad = True
            return 1 if success else 0

    if kind == "bernoulli":
        return BernoulliChannel()
    if kind == "burst":
        return MarkovBurstChannel()
    if kind == "trace":
        return TraceBasedChannel(trace_file)
    raise ValueError(f"Unknown channel kind: {kind}")


def simulate(method: str, scenario: Scenario, seed: int, horizon: int = 300) -> Dict[str, float]:
    np.random.seed(seed)
    plant = GreenhousePlant()
    ctrl = Controllers()
    trigger = EdgeAIEventTrigger(sigma=0.002, delta=0.05)
    energy_model = LoRaEnergyModel()

    T_out = scenario.weather[:horizon]
    x = np.array([[T_out[0]]])
    x_last = x.copy()
    u_seq = np.zeros(ctrl.N)
    last_pid = 0.0
    hist_x = [float(x[0, 0])]
    hist_u = [0.0]
    transmissions = 0
    triggered = 0
    packet_losses = 0
    violation_steps = 0

    channel = make_channel(scenario.channel, seed, scenario.loss_rate, scenario.trace_file)

    for k in range(horizon - 1):
        is_mpc = "MPC" in method
        is_tt = method.startswith("TT")
        has_buffer = "NO-BUF" not in method
        is_triggered = True if is_tt else trigger.check_trigger(x, x_last)

        if is_triggered:
            triggered += 1
            transmissions += 1
            packet_arrived = channel.step()
            if packet_arrived == 0:
                packet_losses += 1
        else:
            packet_arrived = None

        if is_triggered and packet_arrived == 1:
            x_last = x.copy()
            if is_mpc:
                t_traj = np.array([T_out[min(k + i, horizon - 1)] for i in range(ctrl.N)])
                u_seq = ctrl.solve_mpc(x_last, u_seq, t_traj, plant)
                u_app = float(u_seq[0])
            else:
                u_app = float(ctrl.solve_pid(x_last))
                last_pid = u_app
        else:
            if is_mpc:
                if has_buffer:
                    u_seq = np.roll(u_seq, -1)
                    u_seq[-1] = u_seq[-2] if len(u_seq) > 1 else 0.0
                    u_app = float(u_seq[0])
                else:
                    u_app = 0.0
            else:
                u_app = float(last_pid)

        x = plant.step(x, u_app, T_out[k])
        hist_x.append(float(x[0, 0]))
        hist_u.append(u_app)
        if abs(float(x[0, 0]) - ctrl.x_ref) > 2.0:
            violation_steps += 1

    arr = np.array(hist_x)
    err = arr - ctrl.x_ref
    rmse = float(np.sqrt(np.mean(err ** 2)))
    iae = float(np.sum(np.abs(err)))
    energy = float(energy_model.compute(transmissions, horizon))
    return {
        "method": method,
        "scenario": scenario.name,
        "seed": seed,
        "rmse": rmse,
        "iae": iae,
        "energy_mj": energy,
        "transmissions": transmissions,
        "tx_rate_pct": 100.0 * transmissions / (horizon - 1),
        "packet_loss_pct": 100.0 * packet_losses / max(triggered, 1),
        "violation_pct": 100.0 * violation_steps / (horizon - 1),
    }


def load_scenarios() -> List[Scenario]:
    root = os.path.join(os.path.dirname(__file__), '..')
    tokyo = pd.read_csv(os.path.join(root, 'data', 'tokyo_weather.csv'))['temp_c'].values
    mekong = pd.read_csv(os.path.join(root, 'data', 'vietnam_mekong_weather.csv'))['temp_c'].values
    trace = os.path.join(root, 'data', 'empirical_lora_trace.csv')
    return [
        Scenario('Tokyo-Bernoulli', tokyo[1000:1600], 'bernoulli', loss_rate=0.30),
        Scenario('Tokyo-Burst', tokyo[1000:1600], 'burst'),
        Scenario('Mekong-Trace', mekong[:600], 'trace', trace_file=trace),
    ]


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby(['scenario', 'method']).agg(
        rmse_mean=('rmse', 'mean'), rmse_std=('rmse', 'std'),
        iae_mean=('iae', 'mean'), iae_std=('iae', 'std'),
        energy_mean=('energy_mj', 'mean'), energy_std=('energy_mj', 'std'),
        tx_rate_mean=('tx_rate_pct', 'mean'), tx_rate_std=('tx_rate_pct', 'std'),
        violation_mean=('violation_pct', 'mean'), violation_std=('violation_pct', 'std'),
        loss_mean=('packet_loss_pct', 'mean')
    ).reset_index()
    return agg


def main():
    methods = ['TT-PID', 'TT-MPC', 'ET-PID', 'ET-MPC-NO-BUF', 'ET-MPC']
    seeds = list(range(2026, 2036))
    rows = []
    for scenario in load_scenarios():
        print(f"Scenario: {scenario.name}")
        for seed in seeds:
            for method in methods:
                rows.append(simulate(method, scenario, seed))
    raw = pd.DataFrame(rows)
    summary = summarize(raw)

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, 'q1_benchmark_raw.csv')
    summary_path = os.path.join(out_dir, 'q1_benchmark_summary.csv')
    raw.to_csv(raw_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(f"Wrote {raw_path}")
    print(f"Wrote {summary_path}")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == '__main__':
    main()
