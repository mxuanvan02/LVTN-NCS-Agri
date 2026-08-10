#!/usr/bin/env python3
"""Build the two-tier evidence structure and regenerate Chapter 3 denominators.

Rationale (PRISMA 2020): a record whose full text could not be retrieved never
reaches "Reports assessed for eligibility", so it cannot be an included study.
This script therefore splits the 64-source reference set into:

  Tier 1 (core evidence set)  : full text retrieved, read, and locator-coded.
                                Only these records feed counts, RoB and GRADE.
  Tier 2 (context references) : cited for field context only. Two reasons:
                                (a) full text not retrievable in this audit
                                    environment (paywalled), or
                                (b) retrieved but a secondary review/survey,
                                    which the eligibility criteria exclude
                                    from primary evidence (S22, S46).

Outputs
  bib_audit/two_tier_corpus.csv    one row per source with its tier and reason
  bib_audit/ch3_counts_tier1.json  Chapter 3 counts computed on Tier 1 only
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"

ROB = AUDIT / "rob_grade_audit_log.csv"
RECODE = AUDIT / "pnce_recode" / "pnce_fulltext_recode.csv"
CORPUS = AUDIT / "lvtn_68_clean_corpus_FINAL.csv"
RETRIEVAL = AUDIT / "fulltext_retrieval_log.csv"

OUT_CSV = AUDIT / "two_tier_corpus.csv"
OUT_JSON = AUDIT / "ch3_counts_tier1.json"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rob = {r["record_id"]: r for r in read(ROB)}
    recode = {r["id"]: r for r in read(RECODE)}
    corpus = {r["id"]: r for r in read(CORPUS)}

    # How many lawful retrieval routes were attempted per record.
    attempts = Counter()
    if RETRIEVAL.exists():
        for r in read(RETRIEVAL):
            attempts[r["record_id"]] += 1

    rows = []
    for sid in sorted(corpus, key=lambda s: int(s[1:])):
        rb = rob[sid]
        reviewed = rb["fulltext_status"] == "fulltext_reviewed"
        art = recode.get(sid, {}).get("article_type_flag", "")

        if reviewed and art == "secondary_review":
            tier, reason = "tier2_context", "retrieved_but_secondary_review"
        elif reviewed:
            tier, reason = "tier1_core", "fulltext_read_and_coded"
        elif rb["record_role"] == "context_secondary":
            tier, reason = "tier2_context", "methodological_context_source"
        else:
            tier, reason = "tier2_context", "fulltext_not_retrieved"

        rows.append({
            "id": sid,
            "year": corpus[sid].get("year", ""),
            "title": corpus[sid].get("title", "")[:120],
            "tier": tier,
            "tier_reason": reason,
            "record_role": rb["record_role"],
            "evidence_tier": rb["evidence_tier"],
            "rob_overall": rb["rob_overall"],
            "article_type_flag": art or "not_assessed",
            "retrieval_routes_attempted": attempts.get(sid, 0),
            "p1_application": recode.get(sid, {}).get("p1_application", ""),
            "n1_protocol": recode.get(sid, {}).get("n1_protocol", ""),
            "c1_strategy": recode.get(sid, {}).get("c1_strategy", ""),
            "c2_trigger": recode.get(sid, {}).get("c2_trigger", ""),
            "c3_architecture": recode.get(sid, {}).get("c3_architecture", ""),
            "evidence_type": recode.get(sid, {}).get("evidence_type", ""),
            "comparator_present": recode.get(sid, {}).get("comparator_present", ""),
        })

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tier1 = [r for r in rows if r["tier"] == "tier1_core"]
    tier2 = [r for r in rows if r["tier"] == "tier2_context"]

    def tally(field, subset):
        c = Counter(r[field] for r in subset if r[field])
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))

    ids_by = defaultdict(list)
    for r in tier1:
        ids_by[("application", r["p1_application"])].append(r["id"])
        ids_by[("protocol", r["n1_protocol"])].append(r["id"])
        ids_by[("strategy", r["c1_strategy"])].append(r["id"])

    years = Counter()
    for r in tier1:
        try:
            y = int(r["year"])
        except (TypeError, ValueError):
            continue
        years["pre2015" if y < 2015 else ("2024_2025" if y >= 2024 else "2015_2023")] += 1

    result = {
        "n_reference_set": len(rows),
        "n_tier1_core": len(tier1),
        "n_tier2_context": len(tier2),
        "tier2_breakdown": tally("tier_reason", tier2),
        "tier1_by_role": tally("record_role", tier1),
        "tier1": {
            "application": tally("p1_application", tier1),
            "protocol": tally("n1_protocol", tier1),
            "strategy": tally("c1_strategy", tier1),
            "trigger": tally("c2_trigger", tier1),
            "architecture": tally("c3_architecture", tier1),
            "evidence_type": tally("evidence_type", tier1),
            "comparator": tally("comparator_present", tier1),
            "rob_overall": tally("rob_overall", tier1),
            "year": dict(years),
        },
        "tier1_ids": [r["id"] for r in tier1],
        "tier2_ids": [r["id"] for r in tier2],
        "ids_by_group": {f"{k[0]}:{k[1]}": v for k, v in sorted(ids_by.items())},
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"reference set   {len(rows)}")
    print(f"tier 1 core     {len(tier1)}")
    print(f"tier 2 context  {len(tier2)}  {result['tier2_breakdown']}")
    print("\ntier1 by role:", result["tier1_by_role"])
    for cat in ("application", "protocol", "strategy", "trigger",
                "architecture", "evidence_type", "comparator", "rob_overall", "year"):
        print(f"\n## {cat}")
        for k, v in result["tier1"][cat].items():
            print(f"  {v:3d}  {k}")
    print(f"\nwrote {OUT_CSV.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
