#!/usr/bin/env python3
"""Print a compact, locator-tagged evidence view for manual PNCE recoding.

Usage: python3 view_candidates.py S02 S03 ...
       python3 view_candidates.py --batch 1        (6 records per batch)

Only candidate evidence is shown. The coder still decides each value, and a
field with no usable candidate must be coded not_stated / not_reported.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAND = json.loads((HERE / "evidence_candidates.json").read_text(encoding="utf-8"))

ORDER = [
    "article_type_flag",
    "p1_application",
    "p1_crop",
    "p2_dynamics_model",
    "p3_time_constant",
    "n1_protocol",
    "n1_protocol_absent",
    "n2_latency",
    "n3_packet_loss",
    "c1_strategy",
    "c1_strategy_monitoring_only",
    "c2_trigger",
    "c3_architecture",
    "evidence_type",
    "comparator_present",
    "e1_control_quality",
    "e2_network_resource",
    "e3_energy",
]

MAXQ = int(sys.argv[sys.argv.index("--maxq") + 1]) if "--maxq" in sys.argv else 2
QLEN = int(sys.argv[sys.argv.index("--qlen") + 1]) if "--qlen" in sys.argv else 230


def ids_from_args() -> list[str]:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip = set()
    for flag in ("--maxq", "--qlen", "--batch"):
        if flag in sys.argv:
            skip.add(sys.argv[sys.argv.index(flag) + 1])
    args = [a for a in args if a not in skip]
    if "--batch" in sys.argv:
        n = int(sys.argv[sys.argv.index("--batch") + 1])
        allids = sorted(CAND, key=lambda s: int(s[1:]))
        return allids[(n - 1) * 6: n * 6]
    return args


for rid in ids_from_args():
    rec = CAND[rid]
    print("=" * 78)
    print(f"{rid}  ({rec['chars']} chars, {rec['n_page_markers']} page marks)")
    print("HEAD:", " ".join(rec["head"].split())[:190])
    for field in ORDER:
        hits = rec["fields"].get(field)
        if not hits:
            continue
        print(f"\n  [{field}]  {len(hits)} hit(s)")
        for h in hits[:MAXQ]:
            print(f"    @ {h['locator'][:78]}")
            print(f"      \"{h['quote'][:QLEN]}\"")
    print()
