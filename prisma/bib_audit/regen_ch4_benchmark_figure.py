#!/usr/bin/env python3
"""Regenerate the Chapter 4 benchmark figure from q1_benchmark_summary.csv.

The script intentionally uses only aggregate values stored in the thesis bundle.
It does not reconstruct time-series trajectories that are not available locally.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "figures" / "ch04" / "q1_benchmark_summary.csv"
OUT = ROOT / "figures" / "ch04" / "q1_benchmark_from_csv.pdf"

METHOD_ORDER = ["TT-MPC", "TT-PID", "ET-MPC", "ET-PID", "ET-MPC-NO-BUF"]
METHOD_LABELS = {
    "TT-MPC": "TT-MPC",
    "TT-PID": "TT-PID",
    "ET-MPC": "ET-MPC",
    "ET-PID": "ET-PID",
    "ET-MPC-NO-BUF": "ET-MPC\n(không bộ đệm)",
}
SCENARIO_LABELS = {
    "Mekong-Trace": "Mekong tổng hợp",
    "Tokyo-Bernoulli": "Tokyo–Bernoulli",
    "Tokyo-Burst": "Tokyo–Burst",
}
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2"]


def main() -> None:
    df = pd.read_csv(CSV)
    expected = {
        "scenario", "method", "rmse_mean", "rmse_std", "energy_mean",
        "energy_std", "violation_mean", "violation_std"
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    scenarios = list(dict.fromkeys(df["scenario"]))
    if set(scenarios) != set(SCENARIO_LABELS):
        raise ValueError(f"Unexpected scenarios: {scenarios}")

    fig, axes = plt.subplots(3, 1, figsize=(11.2, 10.0), sharex=True)
    metrics = [
        ("rmse_mean", "rmse_std", "RMSE (°C)"),
        ("energy_mean", "energy_std", "Năng lượng mô hình hóa (mJ)"),
        ("violation_mean", "violation_std", "Tỷ lệ vi phạm ngưỡng (%)"),
    ]

    x = np.arange(len(scenarios), dtype=float)
    width = 0.15
    offsets = (np.arange(len(METHOD_ORDER)) - (len(METHOD_ORDER) - 1) / 2) * width

    for ax, (mean_col, std_col, ylabel) in zip(axes, metrics):
        for i, method in enumerate(METHOD_ORDER):
            sub = (df[df["method"] == method]
                   .set_index("scenario")
                   .reindex(scenarios))
            if sub[mean_col].isna().any():
                raise ValueError(f"Missing {mean_col} values for {method}")
            ax.bar(
                x + offsets[i], sub[mean_col].to_numpy(), width,
                yerr=sub[std_col].to_numpy(), capsize=2.5,
                color=COLORS[i], edgecolor="black", linewidth=0.35,
                label=METHOD_LABELS[method], zorder=3,
            )
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].legend(
        ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.28),
        frameon=False, fontsize=9,
    )
    axes[-1].set_xticks(x, [SCENARIO_LABELS[s] for s in scenarios])
    axes[-1].set_xlabel("Kịch bản mô phỏng")
    fig.suptitle(
        "Đối sánh benchmark từ tệp q1_benchmark_summary.csv\n"
        "(trung bình ± độ lệch chuẩn, 10 hạt giống ngẫu nhiên)",
        y=0.995, fontsize=13, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94), h_pad=1.0)
    fig.savefig(OUT, bbox_inches="tight")
    print(OUT)


if __name__ == "__main__":
    main()
