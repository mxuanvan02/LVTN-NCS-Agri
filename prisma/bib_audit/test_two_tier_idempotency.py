#!/usr/bin/env python3
"""Regression tests for the two-tier enforcement step.

The enforcement script used to derive the Tier-1/Tier-2 split from
`included_record_ids` alone. That made it non-idempotent: on a second run the
column already held Tier-1 IDs only, so `tier2_context_record_ids` was
rewritten as an empty string and the provenance of the set-aside context
records was lost. Downstream prose that cited those records then had no
machine-readable source list to fall back on.

These tests lock in two properties:

  1. Re-running the script does not change the audit logs (idempotency).
  2. Claims whose original contributor list mixed tiers keep their Tier-2
     context IDs, and the certainty rationale preamble is not stacked.

Run with:
    python3 -m unittest discover -s prisma/bib_audit -p 'test_*.py' -v
"""
from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
SCRIPT = AUDIT / "enforce_two_tier_consistency.py"
CLAIMS = AUDIT / "grade_claim_audit.csv"
ROB = AUDIT / "rob_grade_audit_log.csv"
TIERS = AUDIT / "two_tier_corpus.csv"

PREAMBLE = "Certainty is now computed on the"

# Claim -> expected Tier-2 context records after enforcement. Taken from the
# original contributor lists in build_rob_grade_audit.py partitioned against
# two_tier_corpus.csv.
EXPECTED_TIER2 = {
    "C1_ETC_STC_RESOURCE_TRADEOFF": ["S17", "S21", "S23", "S28", "S29", "S39"],
    "C2_LORAWAN_IRRIGATION": [],
    "C3_MPC_DELAY_LOSS": ["S04", "S19", "S25", "S27", "S65"],
}

EXPECTED_TIER1 = {
    "C1_ETC_STC_RESOURCE_TRADEOFF": ["S16", "S30"],
    "C2_LORAWAN_IRRIGATION": ["S38", "S45", "S48", "S52"],
    "C3_MPC_DELAY_LOSS": ["S18", "S20", "S61", "S66"],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


class TwoTierEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="two_tier_test_"))
        for source in (SCRIPT, CLAIMS, ROB, TIERS):
            shutil.copy2(source, self.workdir / source.name)
        self.claims = self.workdir / CLAIMS.name

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def run_script(self) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, str(self.workdir / SCRIPT.name)],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_repeated_runs_leave_the_logs_unchanged(self) -> None:
        self.run_script()
        first = digest(self.claims)
        for run_index in range(2, 5):
            self.run_script()
            with self.subTest(run=run_index):
                self.assertEqual(digest(self.claims), first)

    def test_tier2_context_ids_survive_a_second_run(self) -> None:
        self.run_script()
        self.run_script()
        rows = {row["claim_id"]: row for row in read_csv(self.claims)}
        for claim_id, expected in EXPECTED_TIER2.items():
            with self.subTest(claim=claim_id):
                self.assertEqual(
                    split_ids(rows[claim_id]["tier2_context_record_ids"]), expected
                )

    def test_included_ids_stay_restricted_to_tier1(self) -> None:
        self.run_script()
        self.run_script()
        tiers = {row["id"]: row["tier"] for row in read_csv(self.workdir / TIERS.name)}
        rows = {row["claim_id"]: row for row in read_csv(self.claims)}
        for claim_id, expected in EXPECTED_TIER1.items():
            with self.subTest(claim=claim_id):
                included = split_ids(rows[claim_id]["included_record_ids"])
                self.assertEqual(included, expected)
                for record_id in included:
                    self.assertEqual(tiers.get(record_id), "tier1_core")

    def test_rationale_preamble_is_not_stacked(self) -> None:
        for _ in range(3):
            self.run_script()
        for row in read_csv(self.claims):
            with self.subTest(claim=row["claim_id"]):
                self.assertLessEqual(row["certainty_rationale"].count(PREAMBLE), 1)

    def test_no_record_appears_in_both_columns(self) -> None:
        self.run_script()
        for row in read_csv(self.claims):
            with self.subTest(claim=row["claim_id"]):
                tier1 = set(split_ids(row["included_record_ids"]))
                tier2 = set(split_ids(row["tier2_context_record_ids"]))
                self.assertEqual(tier1 & tier2, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
