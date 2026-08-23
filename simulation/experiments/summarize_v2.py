#!/usr/bin/env python3
"""Regenerate v2 derived artifacts from the frozen primary raw data.

The 2,400 primary runs are read-only.  This script recomputes descriptive
summaries, paired ET-TT statistics, the preregistered three-criterion gate for
both controller families, run accounting, and output hashes.

Holm adjusts p-values within each network x metric family containing the four
plant/controller contrasts.  The paired 95% t intervals and the decision gate
are unadjusted; they must not be described as family-wise simultaneous CIs.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd
import scipy.stats as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.run_v2_primary import paired, summarize  # noqa: E402

OUT = ROOT / "results"
RAW = OUT / "v2_primary_raw.csv"


def matched_arms(frame: pd.DataFrame, policy_a: str, policy_b: str) -> pd.DataFrame:
    """Return strictly matched seed pairs; reject duplicates or missing arms."""
    cols = ["seed", "transmissions"]
    a = frame.loc[frame.policy == policy_a, cols].rename(columns={"transmissions": "a"})
    b = frame.loc[frame.policy == policy_b, cols].rename(columns={"transmissions": "b"})
    if a.seed.duplicated().any() or b.seed.duplicated().any():
        raise ValueError(f"duplicate seed in {policy_a}/{policy_b}")
    merged = a.merge(b, on="seed", how="inner", validate="one_to_one")
    if len(merged) != len(a) or len(merged) != len(b):
        raise ValueError(f"unmatched seed in {policy_a}/{policy_b}: {len(a)} vs {len(b)}")
    return merged.sort_values("seed")


def failed_criteria(rlo: float, n_hi: float, v_hi: float) -> str:
    failures = []
    if rlo < 20:
        failures.append("transmission reduction lower CI <20%")
    if n_hi > 0.10:
        failures.append("NRMSE increase upper CI >0.10")
    if v_hi > 5:
        failures.append("violation increase upper CI >5 pp")
    return "; ".join(failures)


def main() -> None:
    raw = pd.read_csv(RAW)
    summarize(raw).to_csv(OUT / "v2_primary_summary.csv", index=False)
    paired_df = paired(raw)
    paired_df.to_csv(OUT / "v2_primary_paired.csv", index=False)

    rows = []
    contrasts = [
        ("MPC", "ET-MPC", "TT-MPC", "ET-MPC_minus_TT-MPC"),
        ("PI", "ET-PI", "TT-PI", "ET-PI_minus_TT-PI"),
    ]
    for plant in ("greenhouse", "irrigation"):
        for net in sorted(raw.network.unique()):
            g = raw[(raw.plant == plant) & (raw.network == net)]
            for family, et_name, tt_name, contrast in contrasts:
                matched = matched_arms(g, et_name, tt_name)
                reduction = 100 * (1 - matched.a / matched.b)
                n = len(reduction)
                q = st.t.ppf(0.975, n - 1)
                half = q * reduction.std(ddof=1) / np.sqrt(n)
                rmean = float(reduction.mean())
                rlo, rhi = rmean - half, rmean + half
                pe = paired_df[
                    (paired_df.plant == plant)
                    & (paired_df.network == net)
                    & (paired_df.contrast == contrast)
                ].set_index("metric")
                n_lo = float(pe.loc["nrmse", "ci95_low"])
                n_hi = float(pe.loc["nrmse", "ci95_high"])
                v_lo = float(pe.loc["violation_pct", "ci95_low"])
                v_hi = float(pe.loc["violation_pct", "ci95_high"])
                reason = failed_criteria(rlo, n_hi, v_hi)
                rows.append({
                    "plant": plant,
                    "controller_family": family,
                    "contrast": contrast,
                    "network": net,
                    "n_pairs": n,
                    "transmission_reduction_pct_mean": rmean,
                    "transmission_reduction_ci95_low": rlo,
                    "transmission_reduction_ci95_high": rhi,
                    "nrmse_difference_mean": float(pe.loc["nrmse", "mean_difference"]),
                    "nrmse_difference_ci95_low": n_lo,
                    "nrmse_difference_ci95_high": n_hi,
                    "violation_difference_pp_mean": float(pe.loc["violation_pct", "mean_difference"]),
                    "violation_difference_pp_ci95_low": v_lo,
                    "violation_difference_pp_ci95_high": v_hi,
                    "tradeoff_gate": "pass" if not reason else "fail",
                    "failure_reason": reason,
                    "interval_scope": "unadjusted paired 95% t-CI; not simultaneous",
                })
    gates = pd.DataFrame(rows)
    gates.to_csv(OUT / "v2_decision_gates.csv", index=False)

    manifest = pd.read_csv(OUT / "v2_run_manifest.csv")
    manifest.groupby("status").size().rename("n").reset_index().to_csv(
        OUT / "v2_run_accounting.csv", index=False
    )

    files = [
        "v2_primary_raw.csv", "v2_primary_summary.csv", "v2_primary_paired.csv",
        "v2_sensitivity_raw.csv", "v2_run_manifest.csv", "v2_decision_gates.csv",
        "v2_run_accounting.csv", "v2_sil_events.jsonl", "v2_interface.jsonl",
        "v2_sil_loopback.json", "v2_provenance.json",
    ]
    hashes = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files}
    (OUT / "v2_output_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")

    print(f"raw_rows={len(raw)} paired_rows={len(paired_df)} gate_rows={len(gates)}")
    print("gate_counts=", gates.groupby(["plant", "controller_family", "tradeoff_gate"]).size().to_dict())
    print("holm_family_sizes=", paired_df.groupby(["network", "metric"]).size().value_counts().to_dict())
    print(f"frozen_output_hashes={len(hashes)}")


if __name__ == "__main__":
    main()
