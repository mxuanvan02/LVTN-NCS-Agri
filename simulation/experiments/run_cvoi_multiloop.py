import os
import sys
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.append(ROOT)


@dataclass
class MultiLoopConfig:
    horizon: int = 360
    loops: tuple = ("temperature", "humidity", "co2", "soil_moisture")
    refs: tuple = (24.0, 70.0, 700.0, 0.32)
    safe_min: tuple = (20.0, 55.0, 450.0, 0.22)
    safe_max: tuple = (28.0, 85.0, 1100.0, 0.45)
    weights: tuple = (1.0, 0.55, 0.35, 0.75)
    taus: tuple = (0.78, 0.86, 0.82, 0.93)
    control_gains: tuple = (0.18, 0.10, 0.12, 0.08)
    disturbance_gains: tuple = (0.22, 0.09, 0.05, 0.035)
    noise_std: tuple = (0.08, 0.20, 8.0, 0.004)
    packet_sizes: tuple = (18, 18, 20, 16)
    bandwidth_bytes: int = 40
    tx_energy_per_byte_mj: float = 0.12
    sleep_energy_per_step_mj: float = 0.3


def load_weather(horizon: int):
    path = os.path.join(ROOT, 'data', 'vietnam_mekong_weather.csv')
    if os.path.exists(path):
        temp = pd.read_csv(path)['temp_c'].values[:horizon]
        if len(temp) >= horizon:
            return temp
    t = np.arange(horizon)
    return 30 + 5 * np.sin(2 * np.pi * t / 144) + 0.5 * np.sin(2 * np.pi * t / 36)


def disturbance_vector(out_temp: float, k: int, rng: np.random.Generator):
    # Exogenous tendencies. Values are scaled to each loop's unit.
    solar = max(0.0, np.sin(2 * np.pi * (k % 144) / 144))
    return np.array([
        out_temp - 24.0,
        4.0 * solar - 0.03 * (out_temp - 28.0),
        -120.0 * solar + 20.0 * rng.normal(),
        -0.02 * solar,
    ], dtype=float)


def step_plant(x, u, out_temp, k, cfg: MultiLoopConfig, rng):
    refs = np.array(cfg.refs)
    taus = np.array(cfg.taus)
    beta = np.array(cfg.control_gains)
    gamma = np.array(cfg.disturbance_gains)
    noise = rng.normal(0, np.array(cfg.noise_std))
    d = disturbance_vector(out_temp, k, rng)
    # Stable first-order dynamics around refs. Positive u moves state toward ref.
    x_next = refs + taus * (x - refs) + beta * u + gamma * d + noise
    return x_next


def p_controller(x_hat, cfg: MultiLoopConfig):
    refs = np.array(cfg.refs)
    # Simple proportional corrective action, clipped per loop.
    u = 1.8 * (refs - x_hat)
    return np.clip(u, -20, 20)


def cost_state(x, cfg: MultiLoopConfig):
    refs = np.array(cfg.refs)
    safe_min = np.array(cfg.safe_min)
    safe_max = np.array(cfg.safe_max)
    w = np.array(cfg.weights)
    norm = np.maximum(np.abs(np.array(cfg.safe_max) - np.array(cfg.safe_min)), 1e-6)
    err = ((x - refs) / norm) ** 2
    violation = np.maximum(0, x - safe_max) ** 2 / (norm ** 2) + np.maximum(0, safe_min - x) ** 2 / (norm ** 2)
    return float(np.sum(w * (err + 8.0 * violation)))


def predict_no_update_cost(i, x_hat, x_true, age, cfg: MultiLoopConfig):
    # Approximate expected cost if loop i is not refreshed: stale estimate remains,
    # uncertainty grows with age and hidden mismatch.
    x_est = x_hat.copy()
    mismatch = abs(x_true[i] - x_hat[i])
    norm = abs(cfg.safe_max[i] - cfg.safe_min[i])
    uncertainty_penalty = ((mismatch / norm) ** 2) * (1.0 + 0.15 * age[i])
    return cost_state(x_est, cfg) + cfg.weights[i] * uncertainty_penalty


def predict_with_update_cost(i, x_hat, x_true, age, cfg: MultiLoopConfig):
    x_est = x_hat.copy()
    x_est[i] = x_true[i]
    return cost_state(x_est, cfg)


def risk_score(i, x_state, cfg: MultiLoopConfig):
    """Normalized safety risk for loop i.

    Risk grows before a variable reaches a hard safety bound. This intentionally
    uses the best locally available state estimate; in the simulation the edge
    scheduler can observe the fresh local sensor value, while the controller may
    still hold a stale x_hat if the packet is not scheduled/successful.
    """
    safe_min = np.array(cfg.safe_min)
    safe_max = np.array(cfg.safe_max)
    norm = safe_max[i] - safe_min[i]
    margin = min(x_state[i] - safe_min[i], safe_max[i] - x_state[i]) / norm
    boundary_risk = max(0.0, 0.30 - margin) / 0.30
    violation_risk = max(0.0, x_state[i] - safe_max[i], safe_min[i] - x_state[i]) / norm
    return float(boundary_risk + 4.0 * violation_risk)


def horizon_value_of_information(i, x_hat, x_true, age, cfg: MultiLoopConfig, horizon: int = 8):
    """Approximate multi-step control value of refreshing loop i.

    This is still lightweight enough for an edge scheduler: it compares a
    predicted closed-loop cost over H steps with and without refreshing one
    loop's state. Disturbances are omitted here by design; the objective is not
    to perfectly forecast the greenhouse but to estimate whether a stale value
    will materially change the next control decisions.
    """
    refs = np.array(cfg.refs)
    taus = np.array(cfg.taus)
    beta = np.array(cfg.control_gains)

    def rollout_cost(x_est):
        x_pred = x_est.copy()
        total = 0.0
        for _ in range(horizon):
            u = p_controller(x_pred, cfg)
            x_pred = refs + taus * (x_pred - refs) + beta * u
            total += cost_state(x_pred, cfg)
        return total

    stale = x_hat.copy()
    fresh = x_hat.copy()
    fresh[i] = x_true[i]
    mismatch = abs(x_true[i] - x_hat[i]) / max(abs(cfg.safe_max[i] - cfg.safe_min[i]), 1e-6)
    return (rollout_cost(stale) - rollout_cost(fresh)) + 0.8 * mismatch * (1.0 + 0.1 * age[i])


def choose_packets(policy: str, x_true, x_hat, age, last_sent, cfg: MultiLoopConfig, k: int):
    M = len(cfg.loops)
    sizes = np.array(cfg.packet_sizes)
    budget = cfg.bandwidth_bytes
    candidates = []

    if policy == 'periodic_all':
        scores = np.ones(M)
    elif policy == 'round_robin':
        scores = np.zeros(M)
        # Try to send one or more loops in rotating order subject to budget.
        for r in range(M):
            scores[(k + r) % M] = M - r
    elif policy == 'error_trigger':
        refs = np.array(cfg.refs)
        norm = np.array(cfg.safe_max) - np.array(cfg.safe_min)
        scores = np.abs((x_true - refs) / norm)
    elif policy == 'aoi':
        scores = age.astype(float)
    elif policy == 'risk':
        scores = np.array([risk_score(i, x_true, cfg) for i in range(M)])
    elif policy == 'cvoi':
        scores = np.zeros(M)
        risks = np.array([risk_score(i, x_true, cfg) for i in range(M)])
        for i in range(M):
            v = horizon_value_of_information(i, x_hat, x_true, age, cfg)
            r = risks[i]
            cost = sizes[i] / max(budget, 1)
            fairness = max(0.0, age[i] - 6.0) / 6.0
            stale_penalty = max(0.0, age[i] - 10.0) / 10.0
            # Safety-first CVoI: risk and multi-step value dominate; energy cost
            # only breaks ties when safety/control value is comparable.
            scores[i] = 3.2 * v + 4.5 * r + 0.12 * age[i] + 0.9 * fairness + 0.8 * stale_penalty - 0.15 * cost
    else:
        raise ValueError(policy)

    order = list(np.argsort(-scores))
    chosen = []
    used = 0

    # Hard safety guard for CVoI: if a loop is close to/over a safety boundary,
    # it is scheduled first when bandwidth permits. This tests whether CVoI can
    # be made safety-preserving rather than merely energy-saving.
    if policy == 'cvoi':
        risks = np.array([risk_score(i, x_true, cfg) for i in range(M)])
        urgent = [int(i) for i in np.argsort(-risks) if risks[i] >= 0.75]
        for i in urgent:
            if used + sizes[i] <= budget and i not in chosen:
                chosen.append(i)
                used += sizes[i]

    for i in order:
        if scores[i] <= 0 and policy not in ('periodic_all', 'round_robin', 'aoi'):
            continue
        if used + sizes[i] <= budget and i not in chosen:
            chosen.append(i)
            used += sizes[i]
    return chosen, used, scores


def make_channel(kind: str, seed: int):
    rng = np.random.default_rng(seed)
    bad = False

    def good():
        return True

    def bernoulli():
        return rng.random() > 0.15

    def burst():
        nonlocal bad
        if bad:
            ok = rng.random() > 0.65
            if rng.random() < 0.25:
                bad = False
        else:
            ok = rng.random() > 0.06
            if rng.random() < 0.04:
                bad = True
        return ok

    def congested():
        # Medium random loss; actual congestion drops are handled by bandwidth.
        return rng.random() > 0.25

    return {'good': good, 'bernoulli': bernoulli, 'burst': burst, 'congested': congested}[kind]


def simulate(policy: str, network: str, seed: int, cfg: MultiLoopConfig) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    weather = load_weather(cfg.horizon)
    refs = np.array(cfg.refs, dtype=float)
    safe_min = np.array(cfg.safe_min)
    safe_max = np.array(cfg.safe_max)
    x = refs + rng.normal(0, [0.8, 2.0, 60.0, 0.02])
    x_hat = x.copy()
    age = np.zeros(len(cfg.loops), dtype=int)
    last_sent = x.copy()
    channel = make_channel(network, seed + 17)

    xs = []
    transmissions = 0
    bytes_sent = 0
    channel_losses = 0
    congestion_drops = 0
    violation_steps = 0
    total_violation_mag = 0.0
    age_sum = np.zeros(len(cfg.loops))
    max_age = np.zeros(len(cfg.loops))

    for k in range(cfg.horizon):
        chosen, used, scores = choose_packets(policy, x, x_hat, age, last_sent, cfg, k)
        # If policy wanted more than bandwidth, choose_packets already excludes them;
        # approximate congestion pressure as loops with positive score not sent.
        positive = np.sum(scores > 0)
        congestion_drops += max(0, int(positive) - len(chosen))

        for i in chosen:
            transmissions += 1
            bytes_sent += cfg.packet_sizes[i]
            if channel():
                x_hat[i] = x[i]
                age[i] = 0
                last_sent[i] = x[i]
            else:
                channel_losses += 1

        u = p_controller(x_hat, cfg)
        x = step_plant(x, u, weather[k], k, cfg, rng)
        age += 1
        xs.append(x.copy())
        viol_low = np.maximum(0, safe_min - x)
        viol_high = np.maximum(0, x - safe_max)
        viol = viol_low + viol_high
        if np.any(viol > 0):
            violation_steps += 1
            total_violation_mag += float(np.sum(viol / (safe_max - safe_min)))
        age_sum += age
        max_age = np.maximum(max_age, age)

    arr = np.array(xs)
    norm = safe_max - safe_min
    err = (arr - refs) / norm
    rmse = np.sqrt(np.mean(err ** 2, axis=0))
    iae = np.sum(np.abs(err), axis=0)
    avg_age = age_sum / cfg.horizon
    energy = bytes_sent * cfg.tx_energy_per_byte_mj + cfg.horizon * cfg.sleep_energy_per_step_mj
    fairness = (np.sum(avg_age) ** 2) / (len(avg_age) * np.sum(avg_age ** 2) + 1e-9)
    return {
        'policy': policy,
        'network': network,
        'seed': seed,
        'rmse_total': float(np.mean(rmse)),
        'iae_total': float(np.mean(iae)),
        'violation_pct': 100.0 * violation_steps / cfg.horizon,
        'violation_mag': total_violation_mag,
        'transmissions': transmissions,
        'bytes_sent': bytes_sent,
        'energy_mj': energy,
        'channel_loss_pct': 100.0 * channel_losses / max(transmissions, 1),
        'congestion_drops': congestion_drops,
        'avg_aoi': float(np.mean(avg_age)),
        'max_aoi': float(np.max(max_age)),
        'fairness': float(fairness),
        **{f'rmse_{name}': float(rmse[i]) for i, name in enumerate(cfg.loops)},
    }


def summarize(df: pd.DataFrame):
    metrics = ['rmse_total', 'iae_total', 'violation_pct', 'violation_mag', 'transmissions', 'bytes_sent', 'energy_mj', 'channel_loss_pct', 'congestion_drops', 'avg_aoi', 'max_aoi', 'fairness']
    agg = df.groupby(['network', 'policy'])[metrics].agg(['mean', 'std']).reset_index()
    agg.columns = ['_'.join([str(c) for c in col if c]) for col in agg.columns.values]
    return agg


def main():
    cfg = MultiLoopConfig()
    policies = ['periodic_all', 'round_robin', 'error_trigger', 'aoi', 'risk', 'cvoi']
    networks = ['good', 'bernoulli', 'burst', 'congested']
    seeds = range(2026, 2046)
    rows = []
    for network in networks:
        print(f'Network: {network}')
        for seed in seeds:
            for policy in policies:
                rows.append(simulate(policy, network, seed, cfg))
    raw = pd.DataFrame(rows)
    summary = summarize(raw)
    out_dir = os.path.join(ROOT, 'results')
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, 'cvoi_multiloop_raw.csv')
    summary_path = os.path.join(out_dir, 'cvoi_multiloop_summary.csv')
    raw.to_csv(raw_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(f'Wrote {raw_path}')
    print(f'Wrote {summary_path}')
    cols = ['network', 'policy', 'rmse_total_mean', 'violation_pct_mean', 'energy_mj_mean', 'congestion_drops_mean', 'avg_aoi_mean', 'fairness_mean']
    print(summary[cols].to_string(index=False, float_format=lambda x: f'{x:.3f}'))


if __name__ == '__main__':
    main()
