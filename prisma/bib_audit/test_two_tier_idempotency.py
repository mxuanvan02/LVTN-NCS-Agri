#!/usr/bin/env python3
"""Regression tests for the two-tier enforcement step.

Four defects motivated these tests.

1. **Non-idempotent tier split.** The script derived the Tier-1/Tier-2 split
   from `included_record_ids` alone. On a second run that column already held
   Tier-1 IDs only, so `tier2_context_record_ids` was rewritten as an empty
   string and the provenance of the set-aside context records was lost.
   Downstream prose citing those records then had no machine-readable source
   list to fall back on.
2. **Stacked rationale preamble.** The tier-split preamble was prepended to
   `certainty_rationale` on every run, so the text grew without bound.
3. **Untrue Tier-2 cause text.** One hard-coded sentence claimed every Tier-2
   record was excluded because "the publisher article type is a secondary
   review". Only one record in the corpus is a secondary review; 29 are simply
   not retrieved. The same branch also overwrote `record_role` for every
   Tier-2 record, demoting analytical studies that merely lacked full text.
4. **Missing PRISMA disposition and DOI.** The audit log recorded no PRISMA
   flow-diagram box, and S22 carried an empty DOI even though a verifiable
   one exists, so the tier split could not be checked against the reported
   flow diagram.

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
CORPUS = AUDIT / "lvtn_68_clean_corpus_FINAL.csv"

PREAMBLE = "Certainty is now computed on the"
SECONDARY_REVIEW_CAUSE = "the publisher article type is a secondary review"

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

# The PRISMA 2020 flow reported by the thesis: 33 included, 29 reports not
# retrieved, 1 methodological context source, 1 excluded after full-text
# review as a secondary review.
EXPECTED_DISPOSITION = {
    "included": 33,
    "report_not_retrieved": 29,
    "report_not_retrieved_context": 1,
    "fulltext_excluded_secondary_review": 1,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


class TwoTierEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="two_tier_test_"))
        for source in (SCRIPT, CLAIMS, ROB, TIERS, CORPUS):
            shutil.copy2(source, self.workdir / source.name)
        self.claims = self.workdir / CLAIMS.name
        self.rob = self.workdir / ROB.name
        self.tiers = self.workdir / TIERS.name
        self.corpus = self.workdir / CORPUS.name

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

    # ------------------------------------------------------------ idempotency
    def test_repeated_runs_leave_the_logs_unchanged(self) -> None:
        self.run_script()
        first_claims = digest(self.claims)
        first_rob = digest(self.rob)
        for run_index in range(2, 5):
            self.run_script()
            with self.subTest(run=run_index):
                self.assertEqual(digest(self.claims), first_claims)
                self.assertEqual(digest(self.rob), first_rob)

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
        tiers = {row["id"]: row["tier"] for row in read_csv(self.tiers)}
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

    # ------------------------------------------------- PRISMA disposition/DOI
    def test_every_record_gets_a_prisma_disposition(self) -> None:
        self.run_script()
        rows = read_csv(self.rob)
        self.assertIn("prisma_disposition", rows[0])
        counts: dict[str, int] = {}
        for row in rows:
            self.assertTrue(
                row["prisma_disposition"],
                f"{row['record_id']} has no PRISMA disposition",
            )
            counts[row["prisma_disposition"]] = counts.get(row["prisma_disposition"], 0) + 1
        self.assertEqual(counts, EXPECTED_DISPOSITION)

    def test_tier1_records_are_the_included_box(self) -> None:
        self.run_script()
        tiers = {row["id"]: row["tier"] for row in read_csv(self.tiers)}
        for row in read_csv(self.rob):
            with self.subTest(record=row["record_id"]):
                is_core = tiers.get(row["record_id"]) == "tier1_core"
                self.assertEqual(row["prisma_disposition"] == "included", is_core)

    def test_doi_is_synced_from_the_corpus(self) -> None:
        self.run_script()
        corpus_doi = {row["id"]: row.get("doi", "").strip() for row in read_csv(self.corpus)}
        for row in read_csv(self.rob):
            want = corpus_doi.get(row["record_id"], "")
            if want:
                with self.subTest(record=row["record_id"]):
                    self.assertEqual(row["doi"].strip(), want)

    def test_a_blank_doi_is_repaired_on_the_next_run(self) -> None:
        rows = read_csv(self.rob)
        target = next(row for row in rows if row["doi"].strip())
        record_id, expected = target["record_id"], target["doi"].strip()
        target["doi"] = ""
        write_csv(self.rob, rows)

        self.run_script()

        repaired = {row["record_id"]: row["doi"].strip() for row in read_csv(self.rob)}
        self.assertEqual(repaired[record_id], expected)

    # ---------------------------------------------------- Tier-2 cause honesty
    def test_not_retrieved_records_are_not_called_secondary_reviews(self) -> None:
        """A Tier-2 record demoted for lack of full text must not be labelled
        a secondary review, and must keep its declared analytical role."""
        rows = read_csv(self.rob)
        tiers = {row["id"]: row for row in read_csv(self.tiers)}
        target = next(
            row
            for row in rows
            if tiers.get(row["record_id"], {}).get("tier_reason") == "fulltext_not_retrieved"
            and tiers.get(row["record_id"], {}).get("tier") != "tier1_core"
        )
        record_id = target["record_id"]
        original_role = target["record_role"]
        # Force the enforcement branch to fire for this record.
        target["rob_overall"] = "high"
        write_csv(self.rob, rows)

        self.run_script()

        after = {row["record_id"]: row for row in read_csv(self.rob)}[record_id]
        self.assertEqual(after["rob_overall"], "not_assessable")
        self.assertNotIn(SECONDARY_REVIEW_CAUSE, after["rob_basis"])
        self.assertIn("no reviewable lawful full text", after["rob_basis"])
        self.assertEqual(
            after["record_role"],
            original_role,
            "a record missing full text must keep its declared role",
        )

    def test_the_real_secondary_review_still_gets_the_review_cause(self) -> None:
        rows = read_csv(self.rob)
        tiers = {row["id"]: row for row in read_csv(self.tiers)}
        target = next(
            row
            for row in rows
            if tiers.get(row["record_id"], {}).get("tier_reason")
            == "retrieved_but_secondary_review"
        )
        record_id = target["record_id"]
        target["rob_overall"] = "high"
        write_csv(self.rob, rows)

        self.run_script()

        after = {row["record_id"]: row for row in read_csv(self.rob)}[record_id]
        self.assertEqual(after["rob_overall"], "not_assessable")
        self.assertIn(SECONDARY_REVIEW_CAUSE, after["rob_basis"])
        self.assertEqual(after["record_role"], "context_secondary")

    def test_tier1_verdicts_are_left_alone(self) -> None:
        before = {
            row["record_id"]: (row["rob_overall"], row["record_role"])
            for row in read_csv(self.rob)
        }
        tiers = {row["id"]: row["tier"] for row in read_csv(self.tiers)}
        self.run_script()
        for row in read_csv(self.rob):
            if tiers.get(row["record_id"]) == "tier1_core":
                with self.subTest(record=row["record_id"]):
                    self.assertEqual(
                        (row["rob_overall"], row["record_role"]),
                        before[row["record_id"]],
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
