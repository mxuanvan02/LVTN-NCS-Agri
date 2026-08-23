import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"


def test_v2_artifact_accounting_and_factorial_complete():
    raw = pd.read_csv(OUT / "v2_primary_raw.csv")
    manifest = pd.read_csv(OUT / "v2_run_manifest.csv")
    assert len(raw) == len(manifest) == 2400
    assert set(manifest["status"]) == {"completed"}
    assert set(raw["plant"]) == {"greenhouse", "irrigation"}
    assert raw["network"].nunique() == 6
    assert set(raw["policy"]) == {"TT-MPC", "ET-MPC", "TT-PI", "ET-PI"}
    assert raw["seed"].nunique() == 50
    assert np.isfinite(raw.select_dtypes(include=["number"]).to_numpy()).all()


def test_v2_preregistered_gate_result_and_random_tape_scope():
    gates = pd.read_csv(OUT / "v2_decision_gates.csv")
    paired = pd.read_csv(OUT / "v2_primary_paired.csv")
    assert len(gates) == 24  # 2 plants x 2 controller families x 6 networks
    assert set(gates["controller_family"]) == {"MPC", "PI"}
    assert (gates[gates.plant == "greenhouse"].tradeoff_gate == "pass").all()
    assert (gates[gates.plant == "irrigation"].tradeoff_gate == "fail").all()
    assert set(gates["interval_scope"]) == {
        "unadjusted paired 95% t-CI; not simultaneous"
    }
    # This flag verifies equality of the stored process/sensor-noise digest.
    # Channel draws are reproducible from keyed RandomTape calls but are not
    # enumerated in that digest, so this is not a bytewise channel-trace check.
    assert paired["crn_gate"].all()


def test_v2_deadline_endpoint_is_declared_uninformative_here():
    raw = pd.read_csv(OUT / "v2_primary_raw.csv")
    paired = pd.read_csv(OUT / "v2_primary_paired.csv")
    assert raw["deadline_miss_pct"].eq(0).all()
    deadline = paired[paired.metric == "deadline_miss_pct"]
    assert deadline["mean_difference"].eq(0).all()
    assert deadline["p_value_holm"].eq(1).all()


def _holm(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(values) - rank) * values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def test_v2_holm_matches_preregistered_four_contrast_families():
    paired = pd.read_csv(OUT / "v2_primary_paired.csv")
    assert {"p_value", "p_value_holm", "holm_family"} <= set(paired.columns)
    groups = paired.groupby(["network", "metric"], sort=False)
    assert len(groups) == 36  # six networks x six endpoints
    for (network, metric), group in groups:
        assert len(group) == 4  # two plants x two controller families
        assert group["holm_family"].nunique() == 1
        assert group["holm_family"].iloc[0] == f"network_metric:{network}:{metric}"
        np.testing.assert_allclose(
            group["p_value_holm"].to_numpy(),
            _holm(group["p_value"].fillna(1).to_numpy()),
            rtol=0,
            atol=1e-14,
        )


def test_v2_sensitivity_is_separate_and_complete():
    sens = pd.read_csv(OUT / "v2_sensitivity_raw.csv")
    summary = pd.read_csv(OUT / "v2_sensitivity_summary.csv")
    assert len(sens) == 1800
    assert set(sens["status"]) == {"completed"}
    assert sens["setting_id"].nunique() == 10
    assert "forecast_oracle" in set(sens["setting_id"])
    assert len(summary) == 20
    assert set(summary["analysis_scope"]) == {"exploratory_sensitivity_only"}
    assert set(summary["n_runs"]) == {90}
    assert set(summary["n_seeds"]) == {15}
    assert set(summary["n_networks"]) == {6}
    raw = pd.read_csv(OUT / "v2_primary_raw.csv")
    assert set(raw["forecast"]) == {"persistence"}
    assert "oracle" not in set(raw["forecast"])


def test_v2_sil_scope_and_output_hashes():
    sil = json.loads((OUT / "v2_sil_loopback.json").read_text(encoding="utf-8"))
    assert len(sil["checks"]) == 1
    checks = sil["checks"][0]
    assert checks["scope"].startswith("software-in-the-loop/HIL-ready only")
    assert len(sil["runs"]) == 72
    assert checks["duplicate_and_stale_rejected"] is True
    assert checks["udp_localhost_duplicate_rejected"] is True

    hashes = json.loads((OUT / "v2_output_hashes.json").read_text(encoding="utf-8"))
    for name, expected in hashes.items():
        actual = hashlib.sha256((OUT / name).read_bytes()).hexdigest()
        assert actual == expected, name
