# LVTN evidence corpus and audit package

The active reference set contains **64 sources**. After lawful full-text retrieval it is split into two tiers, following PRISMA 2020: a record whose full text was never retrieved sits in `Reports not retrieved`, which precedes `Reports assessed for eligibility`, so it cannot be counted as an included study.

- **Tier 1, core evidence set (n = 33):** full text retrieved, read, and coded on all 12 PNCE variables with a locator per value. Only Tier 1 feeds counts, percentages, RoB, and GRADE.
- **Tier 2, context references (n = 31):** 29 records whose full text could not be retrieved through any logged lawful route, the S22 background survey, and S46, which is a publisher-labelled secondary review and therefore excluded from primary evidence by the eligibility criteria. Tier 2 records are still cited to describe the field, never counted as assessed evidence.

Historical filenames retain the string `68` because the earlier candidate set contained 68 records; four duplicate/replaced entries were resolved before the final 64-source set was fixed.

Active files:

- `lvtn_68_clean_corpus_FINAL.csv` — bibliographically verified 64-source reference set.
- `lvtn_68_clean_corpus_FINAL.bib` — BibTeX records for the reference set.
- `lvtn_68_coding_per_paper.csv` — the earlier title/metadata-based PNCE classification, retained only to reproduce superseded numbers.
- `pnce_recode/pnce_fulltext_recode.csv` and `.json` — the 12-variable PNCE recoding of all 34 read sources, with a locator and verbatim quote per coded value and a `coding_basis` marking each value as `rule`, `adjudicated`, or `absent`.
- `pnce_recode/manual_overrides.json` — the nine human-adjudicated corrections, each with the rule failure and the supporting body-text quote.
- `two_tier_corpus.csv` — one row per source with its tier and tier reason.
- `ch3_counts_tier1.json` and `ch3_tier1_regen.json` — Chapter 3 counts and per-group cite keys computed on Tier 1 only.
- `core68_source_audit_trail.csv` — bibliographic provenance for the 64 retained sources.
- `fulltext_availability_inventory.csv` — full-text discovery and review status; a discovered PDF URL is not treated as reviewed evidence.
- `rob_grade_audit_log.csv` — record-level evidence tier, source locator, adapted D1--D6 RoB judgements, and applicability notes.
- `grade_claim_audit.csv` — claim-level provisional adapted-GRADE decisions and contributing record IDs.
- `fulltext_retrieval_log.csv` and `fulltext_retrieval_results.json` — every lawful retrieval route attempted per record, with HTTP/content outcome.
- `fulltext_audit_batches/` — the read-only batch audit reports behind the record-level judgements.
- `build_rob_grade_audit.py` — reconstructs the conservative metadata-level audit and full-text availability inventory.
- `apply_fulltext_rob_reviews.py`, `import_remaining_fulltext_audits.py`, `apply_pass2_fulltext_reviews.py` — reapply the completed locator-backed full-text reviews after the base audit is rebuilt.
- `fetch_remaining_fulltext.py`, `fetch_remaining_fulltext_pass2.py`, `fetch_remaining_fulltext_pass3.py`, `refetch_reviewed_fulltext.py` — lawful OA retrieval passes (OpenAlex/Unpaywall/DOAJ/Europe PMC/OpenAIRE/Semantic Scholar/arXiv/institutional repositories/publisher static mirrors).
- `pnce_recode/extract_evidence_v2.py`, `pnce_recode/probe_matrix.py`, `pnce_recode/build_recode.py`, `pnce_recode/apply_overrides.py` — the recoding pipeline: reference-list trimming, locator indexing, field probes, rule-based coding, then adjudicated overrides.
- `build_two_tier_corpus.py`, `regen_ch3_tier1.py`, `regen_ch3_figures_tier1.py` — build the two-tier split and regenerate Chapter 3 tables and figures on the Tier 1 denominator.
- `REPLACEMENT9_REPORT.md`, `METADATA_AUDIT_REPORT.md`, and `README_AUDIT.md` — provenance and verification notes.

Current evidence status at thesis freeze:

- 64/64 sources have verified bibliographic identity;
- 34/64 have locator-backed full-text review (22 at E3 and 12 at E2); 33 of these form Tier 1, because S46 is reclassified to Tier 2 as a secondary review;
- lawful full-text retrieval was attempted for every remaining source across multiple routes and 174 logged attempts; 29 analytical records could not be retrieved, almost entirely paywalled publisher records;
- among the 33 Tier 1 records, overall adapted RoB is `high` for 21 and `some_concerns` for 12, with no `low`;
- Tier 1 evidence types: 14 simulation-only, 13 lab prototype, 3 field deployment, 2 greenhouse/plot experiment, 1 mixed. 21 of 33 report no comparator at all. This, not retrieval coverage, is why the three claim-level certainty ratings stay at very low/provisional;
- S03 was reviewed from the arXiv preprint version, not the published IFAC version, and S05 from a doctoral thesis; both are recorded in their locators.

These counts describe the audited corpus, not field-wide study quality.

Caution: metadata verification and PNCE classification confidence are not study-quality judgements. Do not claim that all 64 sources have complete 12-variable full-text PNCE extraction. Rebuild in this order if required:

```bash
python3 bib_audit/build_rob_grade_audit.py
python3 bib_audit/apply_fulltext_rob_reviews.py
python3 bib_audit/import_remaining_fulltext_audits.py
python3 bib_audit/apply_pass2_fulltext_reviews.py
python3 bib_audit/apply_pass3_fulltext_reviews.py
python3 bib_audit/pnce_recode/build_recode.py
python3 bib_audit/pnce_recode/apply_overrides.py
python3 bib_audit/build_two_tier_corpus.py
python3 bib_audit/regen_ch3_tier1.py
python3 bib_audit/regen_ch3_figures_tier1.py
```
