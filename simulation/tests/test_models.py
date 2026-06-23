import os
import tempfile

import numpy as np
import pandas as pd

from src.models import Controllers, EdgeAIEventTrigger, GreenhousePlant, LoRaEnergyModel, TraceBasedChannel


def test_greenhouse_plant_step_is_finite_with_zero_noise():
    plant = GreenhousePlant(alpha=0.85, beta=0.15, gamma=0.15)
    x_next = plant.step(np.array([[24.0]]), u=0.0, t_out=20.0, noise_std=0.0)
    assert x_next.shape == (1, 1)
    assert np.isfinite(x_next).all()


def test_mpc_solution_respects_bounds_and_horizon():
    plant = GreenhousePlant()
    ctrl = Controllers(N=4, Q=20.0, R=0.5, x_ref=24.0)
    u_seq = ctrl.solve_mpc(
        x_current=np.array([[22.0]]),
        u_prev_seq=None,
        T_out_traj=np.array([20.0, 20.5, 21.0, 21.5]),
        plant=plant,
    )
    assert len(u_seq) == 4
    assert np.all(u_seq >= -20.0001)
    assert np.all(u_seq <= 20.0001)


def test_event_trigger_logic_thresholds():
    trigger = EdgeAIEventTrigger(sigma=0.02, delta=0.1)
    x_last = np.array([[24.0]])
    assert trigger.check_trigger(np.array([[24.01]]), x_last) is False
    assert trigger.check_trigger(np.array([[30.0]]), x_last) is True


def test_trace_based_channel_replays_cyclically():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "trace.csv")
        pd.DataFrame({"packet_status": [1, 0]}).to_csv(path, index=False)
        channel = TraceBasedChannel(path)
        assert [channel.step(), channel.step(), channel.step()] == [1, 0, 1]


def test_lora_energy_model_matches_transmission_accounting():
    model = LoRaEnergyModel(e_tx=20.0, e_sleep=3.0)
    assert model.compute(transmissions=10, total_steps=100) == 500.0
