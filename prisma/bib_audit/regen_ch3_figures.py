#!/usr/bin/env python3
"""Regenerate Chapter 3 descriptive figures from the 63 primary studies.

S22 is retained in the 64-source reference set only as a methodological
background survey and is excluded from all descriptive content statistics.
"""
from pathlib import Path
import csv
from collections import Counter, defaultdict
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CODING = ROOT / "bib_audit" / "lvtn_68_coding_per_paper.csv"
CORPUS = ROOT / "bib_audit" / "lvtn_68_clean_corpus_FINAL.csv"
OUT = ROOT / "figures" / "ch03"
OUT.mkdir(parents=True, exist_ok=True)

with CODING.open(encoding="utf-8-sig") as f:
    coding = [r for r in csv.DictReader(f) if r["id"] != "S22"]
with CORPUS.open(encoding="utf-8-sig") as f:
    corpus = {r["id"]: r for r in csv.DictReader(f) if r["id"] != "S22"}
assert len(coding) == len(corpus) == 63

app_order = ["irrigation_outdoor", "greenhouse_microclimate", "ncs_iot_platform"]
app_label = {
    "irrigation_outdoor": "Tưới ngoài trời",
    "greenhouse_microclimate": "Nhà kính/thủy canh",
    "ncs_iot_platform": "Nền tảng NCS/IoT",
}
years = sorted({int(corpus[r["id"]]["year"]) for r in coding})
counts = {a: Counter() for a in app_order}
for r in coding:
    counts[r["application_class"]][int(corpus[r["id"]]["year"])] += 1

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
fig, ax = plt.subplots(figsize=(9.0, 4.8))
bottom = np.zeros(len(years))
colors = ["#4C78A8", "#59A14F", "#F28E2B"]
for a, color in zip(app_order, colors):
    vals = np.array([counts[a][y] for y in years])
    ax.bar([str(y) for y in years], vals, bottom=bottom, label=app_label[a], color=color, width=0.75)
    bottom += vals
ax.set_ylabel("Số nghiên cứu sơ cấp")
ax.set_xlabel("Năm công bố")
ax.set_title("Phân bố 63 nghiên cứu sơ cấp theo năm và nhóm ứng dụng")
ax.legend(frameon=False, ncol=3, loc="upper left")
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "stacked_bar_trend.pdf", bbox_inches="tight")
plt.close(fig)

proto_order = ["LoRaWAN_LPWAN", "NB-IoT", "ZigBee", "unspecified"]
ctrl_order = ["ETC_event_triggered", "MPC", "hybrid", "Fuzzy_PID", "ML_RL", "unspecified"]
proto_label = ["LoRaWAN/LPWAN", "NB-IoT", "ZigBee", "Không nêu rõ"]
ctrl_label = ["ETC/STC", "MPC", "Lai", "Fuzzy/PID", "ML/RL", "Không nêu rõ"]
matrix = np.zeros((len(proto_order), len(ctrl_order)), dtype=int)
pi = {v: i for i, v in enumerate(proto_order)}
ci = {v: i for i, v in enumerate(ctrl_order)}
for r in coding:
    matrix[pi[r["protocol_class"]], ci[r["control_strategy"]]] += 1
assert matrix.sum() == 63

fig, ax = plt.subplots(figsize=(8.7, 4.8))
im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
ax.set_xticks(range(len(ctrl_label)), labels=ctrl_label, rotation=25, ha="right")
ax.set_yticks(range(len(proto_label)), labels=proto_label)
ax.set_xlabel("Chiến lược điều khiển")
ax.set_ylabel("Giao thức nêu trong tiêu đề/siêu dữ liệu")
ax.set_title("Phân bố giao thức--điều khiển trong 63 nghiên cứu sơ cấp")
for i in range(matrix.shape[0]):
    for j in range(matrix.shape[1]):
        value = matrix[i, j]
        ax.text(j, i, str(value), ha="center", va="center",
                color="white" if value > matrix.max() * 0.45 else "black",
                fontweight="bold" if value else "normal")
cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
cbar.set_label("Số nghiên cứu")
fig.tight_layout()
fig.savefig(OUT / "heatmap_codesign.pdf", bbox_inches="tight")
plt.close(fig)

print("Regenerated figures for 63 primary studies:")
print(OUT / "stacked_bar_trend.pdf")
print(OUT / "heatmap_codesign.pdf")
