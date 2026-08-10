#!/usr/bin/env python3
"""Regenerate Chapter 3 descriptive figures from the Tier-1 core evidence set.

Difference from regen_ch3_figures.py (kept for provenance): that script plotted
title/metadata coding for 63 records, including 29 whose full text was never
retrieved. This script plots only Tier 1 - records whose full text was
retrieved, read, and coded with locators - so every cell in every figure traces
back to a quotation in bib_audit/pnce_recode/pnce_fulltext_recode.json.

Input : bib_audit/two_tier_corpus.csv
Output: figures/ch03/stacked_bar_trend_tier1.pdf
        figures/ch03/heatmap_codesign_tier1.pdf
        figures/ch03/evidence_type_tier1.pdf
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "bib_audit" / "two_tier_corpus.csv"
OUT = ROOT / "figures" / "ch03"
OUT.mkdir(parents=True, exist_ok=True)

with SRC.open(encoding="utf-8-sig") as f:
    rows = [r for r in csv.DictReader(f) if r["tier"] == "tier1_core"]

N = len(rows)
assert N == 33, N

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

# --------------------------------------------------------------- figure 1
APP_ORDER = [
    "irrigation_outdoor",
    "greenhouse_microclimate",
    "hydroponic_cea",
    "ncs_generic_nonagricultural",
    "not_stated",
]
APP_LABEL = {
    "irrigation_outdoor": "Tưới ngoài trời",
    "greenhouse_microclimate": "Vi khí hậu nhà kính",
    "hydroponic_cea": "Thủy canh/CEA",
    "ncs_generic_nonagricultural": "NCS phi nông nghiệp",
    "not_stated": "Không nêu rõ đối tượng",
}
COLORS = ["#4C78A8", "#59A14F", "#76B7B2", "#B07AA1", "#BAB0AC"]

years = sorted({int(r["year"]) for r in rows})
per_app = {a: Counter() for a in APP_ORDER}
for r in rows:
    per_app[r["p1_application"]][int(r["year"])] += 1

fig, ax = plt.subplots(figsize=(9.0, 4.6))
bottom = np.zeros(len(years))
for app, color in zip(APP_ORDER, COLORS):
    vals = np.array([per_app[app][y] for y in years])
    if vals.sum() == 0:
        continue
    ax.bar([str(y) for y in years], vals, bottom=bottom,
           label=APP_LABEL[app], color=color, width=0.75)
    bottom += vals
ax.set_ylabel("Số nguồn trong tập lõi")
ax.set_xlabel("Năm công bố")
ax.set_title(f"Phân bố {N} nguồn đã đọc toàn văn theo năm và đối tượng điều khiển")
ax.legend(frameon=False, ncol=2, loc="upper left", fontsize=8)
ax.grid(axis="y", alpha=0.25)
ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
fig.tight_layout()
fig.savefig(OUT / "stacked_bar_trend_tier1.pdf", bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------- figure 2
PROTO_ORDER = ["LoRa_LoRaWAN", "WiFi", "ZigBee_802154", "NB_IoT_cellular",
               "mixed", "none_no_network"]
PROTO_LABEL = ["LoRa/LoRaWAN", "Wi-Fi", "ZigBee/802.15.4", "Di động (NB-IoT/4G)",
               "Kết hợp", "Không có mạng"]
CTRL_ORDER = ["MPC", "Fuzzy", "RL_ML", "optimal_control", "ETC_event_triggered",
              "on_off_threshold", "none_monitoring_only", "not_stated"]
CTRL_LABEL = ["MPC", "Mờ/PID", "ML/RL", "Điều khiển tối ưu", "ETC/STC",
              "Ngưỡng đóng--ngắt", "Chỉ giám sát", "Không nêu rõ"]

pi = {v: i for i, v in enumerate(PROTO_ORDER)}
ci = {v: i for i, v in enumerate(CTRL_ORDER)}
matrix = np.zeros((len(PROTO_ORDER), len(CTRL_ORDER)), dtype=int)
for r in rows:
    matrix[pi[r["n1_protocol"]], ci[r["c1_strategy"]]] += 1
assert matrix.sum() == N, matrix.sum()

fig, ax = plt.subplots(figsize=(9.2, 4.6))
im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
ax.set_xticks(range(len(CTRL_LABEL)), labels=CTRL_LABEL, rotation=25, ha="right")
ax.set_yticks(range(len(PROTO_LABEL)), labels=PROTO_LABEL)
ax.set_xlabel("Chiến lược điều khiển (mã hóa từ toàn văn)")
ax.set_ylabel("Giao thức (mã hóa từ toàn văn)")
ax.set_title(f"Phân bố giao thức--điều khiển trong {N} nguồn đã đọc toàn văn")
for i in range(matrix.shape[0]):
    for j in range(matrix.shape[1]):
        v = matrix[i, j]
        ax.text(j, i, str(v), ha="center", va="center",
                color="white" if v > matrix.max() * 0.45 else "black",
                fontweight="bold" if v else "normal")
cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
cbar.set_label("Số nguồn")
fig.tight_layout()
fig.savefig(OUT / "heatmap_codesign_tier1.pdf", bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------- figure 3
EV_ORDER = ["field_deployment", "greenhouse_or_plot_experiment",
            "mixed_experiment_and_simulation", "lab_prototype_or_HIL",
            "simulation_only"]
EV_LABEL = ["Triển khai thực địa", "Thử nghiệm nhà kính/thửa",
            "Kết hợp thực nghiệm và mô phỏng", "Nguyên mẫu/HIL",
            "Chỉ mô phỏng"]
CMP_ORDER = ["concurrent_experimental", "within_model_comparison", "none"]
CMP_LABEL = ["Đối chứng đồng thời", "So sánh trong mô hình", "Không có mốc so sánh"]
CMP_COLORS = ["#59A14F", "#F28E2B", "#BAB0AC"]

ev_counts = {e: Counter() for e in EV_ORDER}
for r in rows:
    ev_counts[r["evidence_type"]][r["comparator_present"]] += 1

fig, ax = plt.subplots(figsize=(8.8, 4.2))
ypos = np.arange(len(EV_ORDER))
left = np.zeros(len(EV_ORDER))
for cmp_key, label, color in zip(CMP_ORDER, CMP_LABEL, CMP_COLORS):
    vals = np.array([ev_counts[e][cmp_key] for e in EV_ORDER])
    ax.barh(ypos, vals, left=left, label=label, color=color, height=0.65)
    left += vals
ax.set_yticks(ypos, labels=EV_LABEL)
ax.invert_yaxis()
ax.set_xlabel("Số nguồn trong tập lõi")
ax.set_title(f"Loại bằng chứng và mốc so sánh trong {N} nguồn đã đọc toàn văn")
ax.legend(frameon=False, fontsize=8, loc="lower right")
ax.grid(axis="x", alpha=0.25)
ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
fig.tight_layout()
fig.savefig(OUT / "evidence_type_tier1.pdf", bbox_inches="tight")
plt.close(fig)

print(f"Tier-1 figures regenerated for n={N}:")
for name in ("stacked_bar_trend_tier1.pdf", "heatmap_codesign_tier1.pdf",
             "evidence_type_tier1.pdf"):
    print(" ", (OUT / name).relative_to(ROOT))
