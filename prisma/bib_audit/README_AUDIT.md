# PRISMA audit package

This folder contains the verification package for the thesis systematic review on Networked Control Systems in smart agriculture.

## Purpose

The audit package allows a reviewer to trace every reported PRISMA number back to machine-readable files. The canonical flow used in the thesis is:

`627 raw records -> 424 unique sources -> 187 sources after title/abstract screening -> 64 included core works`

The tools and AI-assisted steps were used only for search support, metadata normalization, duplicate detection, extraction of traceable evidence, table generation, and consistency checks. They were not used as scientific evidence and did not replace the author's final academic judgement.

## How to verify the numbers

| Thesis number | File to inspect | Verification method |
| --- | --- | --- |
| 627 raw records | `prisma_raw_all_sources_rebuilt.csv` | Count rows excluding the header; inspect `raw_id`, source channel, query id, title, year, DOI/URL if available. |
| 424 unique sources | `prisma_unique_screening_rebuilt.csv` | Count unique rows after deduplication; compare with `prisma_deduplication_evidence.csv`. |
| 203 duplicate/fragment records | `prisma_deduplication_evidence.csv` | Count duplicate rows and inspect the retained record and matching rule. |
| 237 excluded at title/abstract screening | `prisma_screening_decisions_evidence.csv` | Filter `decision=exclude` or the equivalent exclude status/reason fields. |
| 187 sources entering eligibility | `prisma_fulltext_eligibility_queue.csv` | Count rows; the `status` column separates `included_core` (64) from `candidate_core` (123, requiring further full-text verification before reuse). |
| 64 included core works | `lvtn_68_clean_corpus_FINAL.csv` and `core68_source_audit_trail.csv` | Count unique rows (S-id may contain gaps after duplicate DOI/title resolution; see note below). |

## Main files

- `prisma_rebuilt_query_log.json`: query log and search counts.
- `prisma_raw_all_sources_rebuilt.csv`: all raw records before deduplication.
- `prisma_deduplication_evidence.csv`: duplicate/fragment evidence and retained record IDs.
- `prisma_unique_screening_rebuilt.csv`: unique source list with screening status.
- `prisma_screening_decisions_evidence.csv`: title/abstract screening decisions and reason codes.
- `prisma_fulltext_eligibility_queue.csv`: the 187 sources entering eligibility, with `included_core` (64) separated from `candidate_core` (123).
- `prisma_step_evidence_map.csv`: mapping from PRISMA steps to evidence files (canonical flow).
- `lvtn_68_clean_corpus_FINAL.csv` / `lvtn_68_clean_corpus_FINAL.bib`: the 64 verified core works (filename retains the `68` prefix from earlier seed audits; current row count is 64).
- `core68_source_audit_trail.csv`: prior verified core set audit trail; four duplicate DOI/title pairs were resolved, leaving 64 unique core sources. S-id gaps (S33, S53, S54, S68) honestly reflect the removed duplicates.
- `lvtn_68_coding_per_paper.csv`: PNCE coding for the 64 core works.

## Search strategy summary

The search used adaptive query expansion around the PNCE framework:

- P -- Plant/application: irrigation, greenhouse, fertigation, hydroponic, soil moisture.
- N -- Network: LoRaWAN, ZigBee, WiFi, NB-IoT, wireless sensor network, cloud, edge.
- C -- Control: event-triggered control, self-triggered control, model predictive control, fuzzy control, PID, reinforcement learning.
- E -- Evaluation: experiment, simulation, field test, energy saving, water saving, RMSE, IAE, packet loss, delay.

The principal academic metadata sources were OpenAlex, Crossref, Unpaywall, DOI landing pages, and locally curated thesis source lists. Query strings and counts are recorded in `prisma_rebuilt_query_log.json` and in the thesis appendix.

## Tool accountability

| Stage | Tool support | Human responsibility |
| --- | --- | --- |
| Search query design | Keyword expansion and metadata APIs | Define scope, timeframe, PNCE criteria, and final query families. |
| Metadata collection | OpenAlex/Crossref/Unpaywall/DOI landing pages | Check whether records are relevant and academically traceable. |
| Deduplication | Python scripts | Review matching rules and ambiguous duplicates. |
| Screening | Python scripts and PNCE reason codes | Interpret inclusion/exclusion criteria and accept final decisions. |
| Eligibility | Full-text/metadata retrieval scripts | Apply the conservative rule when evidence is insufficient. |
| Writing and tables | LaTeX, Python, AI-assisted consistency checks | Author the thesis, interpret findings, and take responsibility for claims. |

## Conservative rule

If a source did not provide enough accessible full text, abstract, DOI landing page, or metadata evidence to verify the PNCE criteria, it was excluded at eligibility rather than being counted as included. This rule is intentionally conservative to reduce the risk of over-claiming.
