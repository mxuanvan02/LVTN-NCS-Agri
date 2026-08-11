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


def test_v2_preregistered_gate_result_and_crn():
    gates = pd.read_csv(OUT / "v2_decision_gates.csv")
    paired = pd.read_csv(OUT / "v2_primary_paired.csv")
    assert len(gates) == 12
    assert (gates[gates.plant == "greenhouse"].tradeoff_gate == "pass").all()
    assert (gates[gates.plant == "irrigation"].tradeoff_gate == "fail").all()
    assert paired["crn_gate"].all()


def test_v2_sensitivity_is_separate_and_complete():
    sens = pd.read_csv(OUT / "v2_sensitivity_raw.csv")
    assert len(sens) == 1800
    assert set(sens["status"]) == {"completed"}
    assert sens["setting_id"].nunique() == 10
    assert "forecast_oracle" in set(sens["setting_id"])
    raw = pd.read_csv(OUT / "v2_primary_raw.csv")
    assert set(raw["forecast"]) == {"persistence"}


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
