# LVTN core corpus audit

Final active files:

- `lvtn_68_clean_corpus_FINAL.csv` — final core corpus metadata table (**64 unique records**).
- `lvtn_68_clean_corpus_FINAL.bib` — final candidate BibTeX corpus assembled from DOI/local verified records.
- `core68_source_audit_trail.csv` — per-record audit trail for the core corpus.
- `lvtn_68_coding_per_paper.csv` — PNCE coding table, one row per core work.
- `REPLACEMENT9_REPORT.md` — explains the 9 replacements used to recover a clean corpus.
- `METADATA_AUDIT_REPORT.md` — audit method and summary.
- `README_AUDIT.md` — full PRISMA verification package (`627 → 424 → 187 → 64`).

> **Corpus count — 64, not 68.** The `lvtn_68_*` filenames are kept for historical
> continuity (scripts and prior reports reference them). The number `68` in those
> filenames refers to the original seed reconstruction. During the final audit, four
> records were found to be duplicate DOI/title pairs (S33≡S32, S68≡S35, S53≡S45,
> S54≡S47) and were removed, leaving **64 unique core works**. Every active data
> table in this folder now contains 64 records, consistent with the thesis appendix
> and `prisma_step_evidence_map.csv`.

Intermediate audit files were moved to `tmp_archive_20260501/` to keep this directory clean.

Main appendix:

- `LVTN/Chapter/phuluc.tex` lists the 64 unique core works (C1–C64).

Caution:

- The clean corpus is metadata-verified. Full-text PNCE coding still requires separate
  content verification before claiming all 64 studies are fully coded.
