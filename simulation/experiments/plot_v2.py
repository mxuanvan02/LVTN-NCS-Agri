#!/usr/bin/env python3
"""Plot preregistered paired ET-TT gate quantities with 95% CIs.

Input is the regenerated v2_decision_gates.csv.  Dashed lines are the three
preregistered thresholds.  Intervals are ordinary paired t-CIs, not
multiplicity-adjusted simultaneous intervals.
"""
from pathlib import Path
import argparse

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
})
ROOT = Path(__file__).resolve().parents[1]
NETWORKS = [f"N{i}_{name}" for i, name in enumerate([
    "ideal", "nominal", "iid_loss", "burst_loss", "contention_duty", "full_stress"
])]
COLORS = {"MPC": "#1f77b4", "PI": "#d95f02"}
MARKERS = {"MPC": "o", "PI": "s"}


def errbar(ax, x, mean, lo, hi, family, label):
    ax.errorbar(
        x, mean, yerr=np.vstack([mean - lo, hi - mean]), fmt=MARKERS[family] + "-",
        color=COLORS[family], capsize=3, linewidth=1.5, markersize=4.5, label=label,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=ROOT / "results/v2_decision_gates.csv")
    ap.add_argument("--output", type=Path, default=ROOT.parent / "figures/ch04/v2_benchmark.pdf")
    args = ap.parse_args()
    d = pd.read_csv(args.input)
    required = {
        "plant", "controller_family", "network",
        "transmission_reduction_pct_mean", "transmission_reduction_ci95_low", "transmission_reduction_ci95_high",
        "nrmse_difference_mean", "nrmse_difference_ci95_low", "nrmse_difference_ci95_high",
        "violation_difference_pp_mean", "violation_difference_pp_ci95_low", "violation_difference_pp_ci95_high",
    }
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"missing gate columns: {sorted(missing)}")

    fig, axs = plt.subplots(2, 3, figsize=(12.2, 7.2), sharex=True)
    x = np.arange(6)
    metric_specs = [
        ("transmission_reduction", "transmission_reduction_pct_mean", "Giảm số lần truyền (%)", 20.0, "≥ 20%"),
        ("nrmse_difference", "nrmse_difference_mean", "Chênh lệch NRMSE (ET − TT)", 0.10, "≤ 0,10"),
        ("violation_difference_pp", "violation_difference_pp_mean", "Chênh lệch vi phạm (điểm %)", 5.0, "≤ 5 điểm %"),
    ]
    for row, plant in enumerate(["greenhouse", "irrigation"]):
        for col, (stem, mean_col, ylabel, threshold, threshold_label) in enumerate(metric_specs):
            ax = axs[row, col]
            for family in ["MPC", "PI"]:
                q = d[(d.plant == plant) & (d.controller_family == family)].set_index("network").reindex(NETWORKS)
                if q[mean_col].isna().any():
                    raise ValueError(f"incomplete rows for {plant}/{family}/{stem}")
                mean = q[mean_col].to_numpy(float)
                lo = q[stem + "_ci95_low"].to_numpy(float)
                hi = q[stem + "_ci95_high"].to_numpy(float)
                errbar(ax, x, mean, lo, hi, family, family)
            ax.axhline(threshold, color="#555555", linestyle="--", linewidth=1.2)
            ax.text(5.02, threshold, threshold_label, va="bottom", ha="right", fontsize=8, color="#444444")
            ax.axhline(0, color="#aaaaaa", linewidth=.7, zorder=0)
            ax.grid(axis="y", alpha=.22)
            if row == 0:
                ax.set_title(ylabel, fontsize=10)
            if col == 0:
                ax.set_ylabel(("Nhà kính" if plant == "greenhouse" else "Tưới tổng hợp") + "\n" + ylabel)
            else:
                ax.set_ylabel(ylabel)
            ax.set_xticks(x, [f"N{i}" for i in range(6)])
            if row == 1:
                ax.set_xlabel("Điều kiện mạng")
    handles, labels = axs[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, loc="upper center", bbox_to_anchor=(.5, 1.01), frameon=False)
    fig.suptitle("Đánh đổi ET − TT: trung bình ghép cặp và CI 95% (50 seed)", y=1.045, fontsize=13, fontweight="bold")
    fig.text(.5, .005, "Đường đứt: ngưỡng cổng đã khai báo. CI ghép cặp chưa hiệu chỉnh đa bội.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, .965), h_pad=1.2, w_pad=1.0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, bbox_inches="tight")
    print(args.output)


if __name__ == "__main__":
    main()
