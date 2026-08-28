#!/usr/bin/env python3
"""Enforce the two-tier rule across the audit logs.

The two-tier structure states that only Tier-1 (full text retrieved, read and
locator-coded) records feed counts, RoB and GRADE. Two inconsistencies remained
after the tier split:

  1. S46 was moved to Tier 2 because its publisher article type is "Review"
     (secondary evidence, excluded by the eligibility criteria), but it still
     carried an analytical RoB verdict and the `analytical_primary` role.
  2. GRADE claims C1 and C3 still listed Tier-2 records among their
     contributing IDs, so the claim-level certainty was partly derived from
     records that were never assessed for eligibility.

This script rewrites both logs so the tier rule holds, keeping every change
explicit and auditable. Tier-2 IDs are preserved in a separate column instead
of being deleted, so the reader can see which context records were set aside.
"""
from __future__ import annotations

import csv
from pathlib import Path

AUDIT = Path(__file__).resolve().parent

ROB = AUDIT / "rob_grade_audit_log.csv"
CLAIMS = AUDIT / "grade_claim_audit.csv"
TIERS = AUDIT / "two_tier_corpus.csv"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    tier = {r["id"]: r["tier"] for r in read(TIERS)}

    # ---------------------------------------------------------------- 1. S46
    rob = read(ROB)
    changed = []
    for row in rob:
        rid = row["record_id"]
        if tier.get(rid) == "tier1_core":
            continue
        if row["rob_overall"] in ("", "not_assessable"):
            continue
        # A Tier-2 record must not carry an analytical RoB verdict.
        old = row["rob_overall"]
        row["record_role"] = "context_secondary"
        row["rob_overall"] = "not_assessable"
        row["rob_basis"] = (
            "Excluded from analytical RoB synthesis: the publisher article type is a "
            "secondary review, which the eligibility criteria exclude from primary "
            f"evidence. The earlier locator-backed reading (previous verdict: {old}) is "
            "retained in the domain columns as a record of what was read, but it does "
            "not contribute to the Tier-1 RoB counts."
        )
        row["audit_status"] = "tier2_context_not_synthesised"
        changed.append((rid, old))

    if changed:
        write(ROB, rob)

    # ------------------------------------------------------------- 2. GRADE
    claims = read(CLAIMS)
    if "tier2_context_record_ids" not in claims[0]:
        for c in claims:
            c["tier2_context_record_ids"] = ""

    claim_report = []
    for c in claims:
        # The script must be idempotent. On a second run `included_record_ids`
        # already holds Tier-1 IDs only, so re-deriving the split from that
        # column alone would silently blank `tier2_context_record_ids` and
        # erase the provenance of the set-aside context records. Read both
        # columns back in and re-partition their union instead.
        ids = [
            x.strip()
            for x in (
                c["included_record_ids"]
                + ","
                + c.get("tier2_context_record_ids", "")
            ).replace(";", ",").split(",")
            if x.strip()
        ]
        seen: set[str] = set()
        ids = [i for i in ids if not (i in seen or seen.add(i))]
        t1 = [i for i in ids if tier.get(i) == "tier1_core"]
        t2 = [i for i in ids if tier.get(i) != "tier1_core"]
        c["included_record_ids"] = ", ".join(t1)
        c["tier2_context_record_ids"] = ", ".join(t2)

        if t2 and "Certainty is now computed on the" in c["certainty_rationale"]:
            # Rationale already carries the tier-split preamble; do not stack
            # another copy of it on every rerun.
            c["imprecision_downgrade"] = (
                "serious: the evidence base for this claim shrank to "
                f"{len(t1)} auditable record(s) after the tier split"
            )
        elif t2:
            c["certainty_rationale"] = (
                f"Certainty is now computed on the {len(t1)} Tier-1 contributing record(s) "
                f"({', '.join(t1)}) only. {len(t2)} record(s) previously counted towards this "
                f"claim ({', '.join(t2)}) could not be retrieved as full text and are therefore "
                "in the PRISMA 'Reports not retrieved' box; they are kept as context references "
                "but no longer support the claim. " + c["certainty_rationale"]
            )
            # Losing contributors makes imprecision worse, never better.
            c["imprecision_downgrade"] = (
                "serious: the evidence base for this claim shrank to "
                f"{len(t1)} auditable record(s) after the tier split"
            )
        claim_report.append((c["claim_id"], len(t1), len(t2), c["final_certainty"]))

    write(CLAIMS, claims)

    print("--- Tier-2 records stripped of analytical RoB verdicts ---")
    for rid, old in changed:
        print(f"  {rid}: {old} -> not_assessable (tier2 context)")
    if not changed:
        print("  (none)")

    print("\n--- GRADE claims after restricting to Tier 1 ---")
    for cid, n1, n2, final in claim_report:
        print(f"  {cid}: tier1={n1} tier2_moved_out={n2} final={final}")


if __name__ == "__main__":
    main()
