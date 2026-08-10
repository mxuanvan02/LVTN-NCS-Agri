#!/usr/bin/env python3
"""Import the six read-only full-text audit batches into the canonical audit logs.

The batch reports are preserved under bib_audit/fulltext_audit_batches/. Reviewed
records are upgraded only when the batch contains a locator-backed E2/E3 review.
Records that could not be retrieved remain E1 and RoB not assessable, while the
retrieval attempt is recorded explicitly.
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"
BATCH_DIR = AUDIT / "fulltext_audit_batches"
SOURCES = {
 "g1": BATCH_DIR/"g1_remaining_fulltext_audit_summary.md",
 "g2": BATCH_DIR/"g2_remaining_fulltext_audit_summary.md",
 "g3": BATCH_DIR/"g3_remaining_fulltext_audit_summary.md",
 "g4": BATCH_DIR/"g4_remaining_fulltext_audit_summary.md",
 "g5": BATCH_DIR/"g5_remaining_fulltext_audit_summary.md",
 "g6": BATCH_DIR/"g6_remaining_fulltext_audit_summary.md",
}

def read_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def write_csv(p, rows):
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
def extract_json(md):
    blocks=re.findall(r"```json\s*(.*?)\s*```", md, flags=re.S)
    if not blocks: raise ValueError("No JSON block")
    # use the largest machine-readable block (acceptance snippets are smaller)
    obj=json.loads(max(blocks, key=len))
    if isinstance(obj, list): return obj
    return obj["records"]
def judgement(x):
    if isinstance(x, dict): return x.get("judgement", ""), x.get("support", "")
    if isinstance(x, str):
        parts=re.split(r"\s+[—-]\s+", x, maxsplit=1)
        return parts[0].strip(), parts[1].strip() if len(parts)>1 else ""
    return "", ""
def attempts(rec):
    x=rec.get("retrieval_attempts", "")
    if isinstance(x, list): return " | ".join(x)
    return x or ""

BATCH_DIR.mkdir(exist_ok=True)
all_records={}
for key, src in SOURCES.items():
    if not src.exists(): raise FileNotFoundError(src)
    for rec in extract_json(src.read_text(encoding="utf-8")):
        rid=rec["record_id"]
        if rid=="S22":
            # repeated context checks agree; retain the first complete one.
            all_records.setdefault(rid, rec)
        else:
            if rid in all_records: raise ValueError(f"duplicate analytical result {rid}")
            all_records[rid]=rec

expected=set("S01 S02 S03 S04 S05 S06 S07 S08 S09 S10 S11 S12 S13 S14 S15 S16 S17 S18 S19 S21 S22 S23 S24 S25 S26 S27 S28 S29 S31 S32 S36 S37 S38 S39 S40 S44 S45 S46 S47 S49 S50 S51 S52 S56 S57 S59 S60 S61 S62 S63 S64 S65 S66 S67".split())
assert set(all_records)==expected, (expected-set(all_records), set(all_records)-expected)

rob_path=AUDIT/"rob_grade_audit_log.csv"
avail_path=AUDIT/"fulltext_availability_inventory.csv"
rob=read_csv(rob_path); avail=read_csv(avail_path)
rob_by={r["record_id"]:r for r in rob}; avail_by={r["record_id"]:r for r in avail}
for rid, rec in all_records.items():
    row=rob_by[rid]
    tier=rec.get("evidence_tier", "E1")
    if rid=="S22": tier="E1-context"
    reviewed=tier in {"E2","E3"} and bool(rec.get("exact_locator"))
    row["evidence_tier"]=tier
    row["evidence_basis"]="full_text" if reviewed else ("context_metadata" if rid=="S22" else "verified_metadata")
    row["fulltext_status"]="fulltext_reviewed" if reviewed else rec.get("fulltext_status", "inaccessible_after_attempts")
    row["fulltext_locator"]=rec.get("exact_locator") or ""
    for d in range(1,7):
        j,s=judgement(rec.get(f"D{d}", {}))
        if j: row[f"D{d}_{['selection','performance','detection','attrition','reporting','information_leakage'][d-1]}_judgement"]=j
        if s: row[f"D{d}_{['selection','performance','detection','attrition','reporting','information_leakage'][d-1]}_support"]=s
    row["rob_overall"]=rec.get("rob_overall", "not_assessable")
    row["rob_basis"]=("Locator-backed full-text adapted RoB audit." if reviewed else
                      "Full-text retrieval attempted but no reviewable lawful copy was obtained; method-dependent RoB remains not assessable.")
    row["applicability_note"]=rec.get("applicability_note", row["applicability_note"])
    # Preserve PNCE correction in the evidence note for traceability.
    corr=rec.get("pnce_corrections", "")
    if corr: row["pnce_evidence_note"] += " | Full-text audit: " + corr
    row["audit_status"]="fulltext_review_complete" if reviewed else ("context_only_verified" if rid=="S22" else "retrieval_attempted_fulltext_unavailable")
    row["reviewer_id"]="batch_fulltext_audit_2026"
    row["audit_date"]="2026-08-10"
    ar=avail_by[rid]
    ar["fulltext_status"]=row["fulltext_status"]
    url=rec.get("fulltext_url") or ""
    if reviewed and url: ar["pdf_url"]=url
    notes=attempts(rec)
    if notes: ar["lookup_note"]="Batch audit: "+notes

write_csv(rob_path, rob)
write_csv(avail_path, avail)

# Update claim-level rationales without changing the conservative final grades.
claims=read_csv(AUDIT/"grade_claim_audit.csv")
for c in claims:
    if c["claim_id"]=="C1_ETC_STC_RESOURCE_TRADEOFF":
        c["certainty_rationale"]="Full-text RoB is available for S16 and S30; the other contributing records remain E1. Outcomes, comparators, and application domains remain heterogeneous."
    elif c["claim_id"]=="C2_LORAWAN_IRRIGATION":
        c["certainty_rationale"]="All four contributing records now have full-text audits: S38, S45, and S48 are high RoB for effectiveness inference; S52 has some concerns and evaluates communication propagation rather than irrigation outcomes."
    elif c["claim_id"]=="C3_MPC_DELAY_LOSS":
        c["certainty_rationale"]="Full-text RoB is available for S20, S61, and S66; the remaining contributors are E1. Evidence mixes theory, prototypes, and simulation under heterogeneous plant/network assumptions."
write_csv(AUDIT/"grade_claim_audit.csv", claims)
print("Imported", len(all_records), "remaining-record results")
