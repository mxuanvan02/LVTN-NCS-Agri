#!/usr/bin/env python3
"""Merge human-adjudicated overrides into the rule-based PNCE recode.

The rule-based pass (build_recode.py) is deterministic and auditable, but three
failure modes were found by spot-checking against independently verified
sources:

  1. first-match rules can pick up a method described in the related-work
     section (S02 'optimal control' -> actually RL);
  2. papers that state a control rule without using a control-theory term get
     no match at all (S06, S36, S40 threshold/relay logic);
  3. papers that mix simulation with measurement get labelled by whichever
     phrase appears first (S52).

Every override therefore carries the rule's failure reason plus a verbatim body
quote and locator. Output marks each field with coding_basis = rule or
adjudicated so the provenance of every cell stays visible.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

recode = json.loads((HERE / "pnce_fulltext_recode.json").read_text(encoding="utf-8"))
ov = json.loads((HERE / "manual_overrides.json").read_text(encoding="utf-8"))["overrides"]

if isinstance(recode, dict) and "records" in recode:
    records = recode["records"]
else:
    records = recode

CODED_FIELDS = [
    "p1_application", "p2_dynamics_model", "p3_time_constant",
    "n1_protocol", "n2_latency", "n3_packet_loss",
    "c1_strategy", "c2_trigger", "c3_architecture",
    "e1_control_quality", "e2_network_resource", "e3_energy",
    "evidence_type", "comparator_present", "article_type_flag",
]

n_over = 0
for rec in records:
    rid = rec["id"]
    basis = {}
    locs = rec.get("locators", {})
    for f in CODED_FIELDS:
        val = rec.get(f)
        if val in (None, "", "not_stated", "not_reported", "none_stated", "not_applicable"):
            basis[f] = "absent"
        elif f in locs:
            basis[f] = "rule"
        else:
            basis[f] = "rule_no_locator"

    for field, spec in ov.get(rid, {}).items():
        rec[field] = spec["value"]
        locs[field] = {
            "locator": spec["locator"],
            "quote": spec["quote"][:240],
            "rule_error": spec["rule_error"],
        }
        basis[field] = "adjudicated"
        n_over += 1

    rec["locators"] = locs
    rec["coding_basis"] = basis
    rec["fields_with_locator"] = sum(
        1 for f in CODED_FIELDS if f in locs and locs[f].get("locator")
    )

out = {"records": records}
(HERE / "pnce_fulltext_recode.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
)

# Flat CSV for the manuscript pipeline.
cols = ["id"] + CODED_FIELDS + ["fields_with_locator"] + [f"basis_{f}" for f in CODED_FIELDS]
with (HERE / "pnce_fulltext_recode.csv").open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for rec in sorted(records, key=lambda r: int(r["id"][1:])):
        row = [rec["id"]] + [rec.get(f, "") for f in CODED_FIELDS]
        row.append(rec.get("fields_with_locator", 0))
        row += [rec["coding_basis"].get(f, "") for f in CODED_FIELDS]
        w.writerow(row)

# Locator evidence table, one row per coded cell that has support.
with (HERE / "pnce_recode_locators.csv").open("w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["record_id", "field", "value", "coding_basis", "locator", "quote", "rule_error"])
    for rec in sorted(records, key=lambda r: int(r["id"][1:])):
        for f in CODED_FIELDS:
            spec = rec.get("locators", {}).get(f)
            if not spec:
                continue
            w.writerow([
                rec["id"], f, rec.get(f, ""), rec["coding_basis"].get(f, ""),
                spec.get("locator", ""), " ".join(str(spec.get("quote", "")).split())[:220],
                spec.get("rule_error", ""),
            ])

from collections import Counter
bc = Counter(b for r in records for b in r["coding_basis"].values())
print(f"records {len(records)}  overrides applied {n_over}")
print("coding basis:", dict(bc))
print("mean fields with locator:", round(sum(r['fields_with_locator'] for r in records) / len(records), 2))
