#!/usr/bin/env python3
"""Build reproducible evidence-access, RoB, and claim-level GRADE audit logs.

The script deliberately separates bibliographic/metadata verification from
full-text review. It never upgrades a record merely because an OA URL exists.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"
CORPUS = AUDIT / "lvtn_68_clean_corpus_FINAL.csv"
CODING = AUDIT / "lvtn_68_coding_per_paper.csv"
TRAIL = AUDIT / "core68_source_audit_trail.csv"


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_doi(value: str) -> str:
    value = (value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    return value.strip()


def openalex_by_doi(doi: str):
    if not doi:
        return {}
    url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "LVTN-evidence-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}


corpus = read_csv(CORPUS)
coding = {r["id"]: r for r in read_csv(CODING)}
trail = {r["id"]: r for r in read_csv(TRAIL)}
assert len(corpus) == 64

availability_rows = []
rob_rows = []
for idx, row in enumerate(corpus, 1):
    rid = row["id"]
    code = coding[rid]
    tr = trail[rid]
    doi = norm_doi(row.get("doi"))
    oa = openalex_by_doi(doi) if doi else {}
    best = oa.get("best_oa_location") or {}
    primary = oa.get("primary_location") or {}
    oa_info = oa.get("open_access") or {}
    pdf_url = best.get("pdf_url") or primary.get("pdf_url") or ""
    landing = best.get("landing_page_url") or primary.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else "")
    oa_status = oa_info.get("oa_status", "unknown" if not oa else "closed")
    fulltext_status = "oa_pdf_identified_not_reviewed" if pdf_url else "no_oa_pdf_identified"
    if oa.get("_error"):
        fulltext_status = "lookup_error"
    role = "context_secondary" if rid == "S22" else (
        "technical_support_primary" if code["application_class"] == "ncs_iot_platform" else "analytical_primary"
    )
    availability_rows.append({
        "record_id": rid,
        "doi": doi,
        "openalex_id": oa.get("id", ""),
        "oa_status": oa_status,
        "pdf_url": pdf_url,
        "landing_url": landing,
        "fulltext_status": fulltext_status,
        "lookup_note": oa.get("_error", "OA URL availability is not equivalent to full-text verification"),
    })
    evidence_basis = "verified_metadata"
    evidence_tier = "E1-context" if rid == "S22" else "E1"
    default_judgement = "not_assessable" if rid == "S22" else "unclear"
    support = "No locator-backed full-text RoB extraction is stored; metadata confidence is not study quality."
    rob_rows.append({
        "record_id": rid,
        "record_role": role,
        "title": row["title"],
        "year": row["year"],
        "doi": doi,
        "metadata_status": tr.get("metadata_status", ""),
        "evidence_tier": evidence_tier,
        "evidence_basis": evidence_basis,
        "fulltext_status": fulltext_status,
        "fulltext_locator": "",
        "application_class": code["application_class"],
        "application_confidence": code["application_conf"],
        "protocol_class": code["protocol_class"],
        "protocol_confidence": code["protocol_conf"],
        "control_strategy": code["control_strategy"],
        "control_confidence": code["control_conf"],
        "pnce_evidence_note": code["evidence_note"],
        "D1_selection_judgement": default_judgement,
        "D1_selection_support": support,
        "D2_performance_judgement": default_judgement,
        "D2_performance_support": support,
        "D3_detection_judgement": default_judgement,
        "D3_detection_support": support,
        "D4_attrition_judgement": default_judgement,
        "D4_attrition_support": support,
        "D5_reporting_judgement": default_judgement,
        "D5_reporting_support": support,
        "D6_information_leakage_judgement": default_judgement,
        "D6_information_leakage_support": support,
        "rob_overall": "not_assessable",
        "rob_basis": "Provisional metadata-level audit; requires full-text review with page/section/table locators.",
        "applicability_note": "Context source excluded from analytical RoB/GRADE." if rid == "S22" else (
            "Generic NCS/technical-support evidence; indirect for agricultural implementation." if role == "technical_support_primary" else "Application-domain record; directness still requires full-text verification."
        ),
        "audit_status": "awaiting_fulltext_review",
        "reviewer_id": "metadata_migration_2026",
        "audit_date": "2026-08-09",
    })
    if idx < len(corpus):
        time.sleep(0.08)

for path, rows in [
    (AUDIT / "fulltext_availability_inventory.csv", availability_rows),
    (AUDIT / "rob_grade_audit_log.csv", rob_rows),
]:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

claims = [
    {
        "claim_id": "C1_ETC_STC_RESOURCE_TRADEOFF",
        "claim_text": "Trong một số điều kiện báo cáo, ETC/STC giảm tải truyền thông nhưng lợi ích năng lượng và chất lượng điều khiển không đồng nhất.",
        "outcome": "communication_load; energy; control_quality",
        "included_record_ids": "S16;S17;S21;S23;S28;S29;S30;S39",
        "starting_certainty": "low",
        "risk_of_bias_downgrade": "1",
        "inconsistency_downgrade": "1",
        "indirectness_downgrade": "1",
        "imprecision_downgrade": "1",
        "publication_bias_downgrade": "1",
        "final_certainty": "very_low_provisional",
        "certainty_rationale": "Most contributing records are currently E1 and lack locator-backed full-text RoB; outcomes and comparators are heterogeneous.",
        "scope_conditions": "Descriptive synthesis only; thesis simulation verifies fixed-threshold ETC, not STC.",
    },
    {
        "claim_id": "C2_LORAWAN_IRRIGATION",
        "claim_text": "LoRaWAN là lựa chọn tiềm năng cho tưới diện rộng khi vùng phủ và năng lượng quan trọng, nhưng tính phù hợp phụ thuộc điều kiện hiện trường.",
        "outcome": "network_reliability; energy; implementation",
        "included_record_ids": "S38;S45;S48;S52",
        "starting_certainty": "low",
        "risk_of_bias_downgrade": "1",
        "inconsistency_downgrade": "0",
        "indirectness_downgrade": "1",
        "imprecision_downgrade": "1",
        "publication_bias_downgrade": "1",
        "final_certainty": "very_low_provisional",
        "certainty_rationale": "Protocol identification is available, but field reliability, comparator fairness, and uncertainty are not uniformly audited from full text.",
        "scope_conditions": "Not a universal deployment recommendation; requires site-specific RSSI/SNR/PDR and burst-loss measurements.",
    },
    {
        "claim_id": "C3_MPC_DELAY_LOSS",
        "claim_text": "MPC and predictive/event-triggered variants may mitigate delay or packet-loss effects under modeled conditions.",
        "outcome": "control_quality; stability; network_reliability",
        "included_record_ids": "S04;S18;S19;S20;S25;S27;S61;S65;S66",
        "starting_certainty": "low",
        "risk_of_bias_downgrade": "1",
        "inconsistency_downgrade": "1",
        "indirectness_downgrade": "1",
        "imprecision_downgrade": "1",
        "publication_bias_downgrade": "1",
        "final_certainty": "very_low_provisional",
        "certainty_rationale": "Evidence mixes generic NCS theory and application studies; tuning, plant models, and network assumptions are heterogeneous and not fully audited.",
        "scope_conditions": "Under reported model/simulation conditions; no universal stability or field-performance claim.",
    },
]
with (AUDIT / "grade_claim_audit.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(claims[0]))
    w.writeheader(); w.writerows(claims)

print(f"Wrote {len(rob_rows)} record audit rows and {len(claims)} claim audit rows")
print("OA PDFs identified:", sum(bool(r["pdf_url"]) for r in availability_rows))
