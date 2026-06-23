# LVTN 68-Study Metadata Audit Report

## Purpose

This audit verifies the 68 core works listed in `LVTN/Chapter/phuluc.tex` using non-LLM bibliographic metadata sources. The goal is to prevent hallucinated BibTeX and identify which records need manual verification before thesis/paper submission.

## Method

A helper script queried:

1. Crossref title search.
2. OpenAlex title search as fallback/competitor.
3. DOI content negotiation for BibTeX when a DOI candidate was available.

Script:

`LVTN/tools/verify_68_metadata.py`

Outputs:

- `LVTN/bib_audit/lvtn_68_metadata_audit.csv`
- `LVTN/bib_audit/lvtn_68_metadata_summary.json`
- `LVTN/bib_audit/lvtn_68_verified_candidates.bib`

These outputs were also copied to:

`Paper_LaTeX/Supplementary/bib_audit/`

## Summary

- Total appendix seed records: 68
- High-confidence matches: 44
- Medium-confidence matches: 9
- Low-confidence matches: 15
- Not found: 0
- BibTeX candidates fetched via DOI: 50

## Interpretation

- High-confidence records can be used as metadata candidates, but should still be spot-checked against the publisher page.
- Medium-confidence records require manual title/author/year verification before use.
- Low-confidence records should not be imported into `references.bib` without manual verification.
- Several appendix entries contain corrupted year values such as `(1155)`, `(1154)`, `(1152)`, `(1151)`, `(1150)`, and `(168)`. These should be corrected from DOI/publisher metadata, not guessed.

## Anti-hallucination BibTeX rule

Do not generate BibTeX from an LLM. Use DOI/publisher metadata whenever possible:

```bash
curl -LH "Accept: application/x-bibtex" https://doi.org/<DOI>
```

or use:

```bash
python LVTN/tools/fetch_bibtex.py --doi <DOI>
python LVTN/tools/fetch_bibtex.py --title "Exact paper title"
```

## Next actions

1. Manually inspect the 15 low-confidence records.
2. Verify the 9 medium-confidence records.
3. Replace corrupted appendix years using verified metadata.
4. Merge only verified BibTeX into `LVTN/references.bib` and `Paper_LaTeX/refs.bib`.
5. Complete full-text PNCE coding after bibliographic identity is verified.

## Final verification pass — 2026-05-01

A stricter acceptance filter was applied:

- accepted: DOI present and either high-confidence metadata match, or match score >= 0.86;
- manual review: low-confidence, weak medium-confidence, or missing DOI/BibTeX uncertainty.

Final outputs:

- `lvtn_68_final_verified_ACCEPTED.csv`
- `lvtn_68_final_verified_ACCEPTED.bib`
- `lvtn_68_final_manual_review_REQUIRED.csv`
- `FINAL_MANUAL_REVIEW_REQUIRED.md`
- `Chapter/phuluc_candidate_verified.tex`

Summary:

- Accepted metadata candidates: 47/68
- Manual review required: 21/68
- Accepted BibTeX blocks: 45

The candidate appendix is not automatically substituted for `Chapter/phuluc.tex` because 21 records still require manual verification.
