#!/usr/bin/env python3
"""Apply the pass-2 locator-backed full-text reviews (S03, S06, S18, S40, S63).

These five records had full text retrieved in the second lawful open-access
retrieval sweep (see fetch_remaining_fulltext.py and
fetch_remaining_fulltext_pass2.py). Only records with a real locator are
upgraded to E2/E3; the reviewed judgements replace the previous
"retrieval attempted / not assessable" state.

S03 was retrieved as an arXiv preprint rather than the published
IFAC-PapersOnLine version. That distinction is recorded explicitly in the
evidence basis, the locator, and the RoB basis so the log never implies that
the published record was audited.

Text is kept in English to stay consistent with the rest of the audit log.
"""
from __future__ import annotations
import csv
from pathlib import Path

AUDIT = Path(__file__).resolve().parent

DOMAIN = ["selection", "performance", "detection", "attrition", "reporting", "information_leakage"]

REVIEWS = {
    "S03": {
        "evidence_tier": "E2",
        "evidence_basis": "full_text_preprint",
        "fulltext_url": "https://arxiv.org/pdf/2506.13278v1",
        "locator": (
            "arXiv:2506.13278v1 (16 Jun 2025) PREPRINT VERSION, not the published "
            "IFAC-PapersOnLine record; Sections 2.1-2.2 and Tables 1-3; Section 3 and "
            "Table 4; Sections 5-6 and Figures 1-2."
        ),
        "D": [
            ("some_concerns", "Two numerical scenarios (deterministic and parametric-uncertainty) both use a single 40-day Venlow Greenhouse weather series (30 Jan - 11 Mar 2014) with fixed initial conditions; the stochastic case draws 30 parameter realizations (Sections 2.1-2.2; Section 6.2)."),
            ("some_concerns", "RL-Guided MPC is compared with standalone MPC and SAC under a common objective (Sections 2.2, 3, 4, 6; Figures 1-2), but matched tuning and computational budgets are not established; SAC required gamma=0.95 because gamma=1 destabilized training (Section 3; Table 4)."),
            ("some_concerns", "The Economic Profit Indicator is defined with units and a 40-day horizon (Section 2.2; Tables 1-3; Eq. 3), but comparative results are presented graphically (Figures 1-2) without numerical tables, and the deterministic case reports no uncertainty."),
            ("some_concerns", "Thirty parameter realizations and averaging are reported (Section 6.2), but random seeds, repeated deterministic runs, solver failures, and exclusion rules are not stated."),
            ("high", "Equations, constraints, price factors, and some hyperparameters are reported (Sections 2-5; Tables 2-5) and CasADi/IPOPT are named (Section 4), but model parameter values are deferred to another paper and no code, trained policy, weather data, seeds, or numerical result tables are supplied."),
            ("high", "The simulation assumes weather is deterministic and known at each step (Section 2.1) and assumes crop dry weight is always observed although the paper states growers cannot access it directly (Sections 2.1 and 3). These information assumptions are not shown to hold at decision time."),
        ],
        "rob_overall": "high",
        "applicability_note": "Agricultural application evidence, but simulation-only and at preprint level: economic climate control of a lettuce greenhouse over a 40-day weather series, with no physical greenhouse deployment.",
        "pnce": "Retain greenhouse_microclimate and the hybrid RL-MPC strategy, but classify the evidence as numerical simulation rather than deployed control. The full text supports no networked/IoT deployment claim. Note that the reviewed copy is the arXiv preprint, not the IFAC version listed in the reference set.",
    },
    "S06": {
        "evidence_tier": "E3",
        "evidence_basis": "full_text",
        "fulltext_url": "https://link.springer.com/content/pdf/10.1007/s13593-021-00705-z.pdf",
        "locator": (
            "Agronomy for Sustainable Development 41:43 (2021), pp. 3-8: Section 2.1 and "
            "Table 1 (design); Sections 2.2.1-2.2.3 (measurement/analysis); Sections "
            "3.1-3.3 and Tables 2-4 (water, energy, yield); Section 4 (limitations/data)."
        ),
        "D": [
            ("some_concerns", "The trial covers 147 on-farm plots in Can Tho, Tra Vinh, and An Giang: 94 IoT-AWD, 28 continuously flooded, and 25 manual-AWD, with one treatment per farmer (Section 2.1; Table 1). Allocation/randomization is not reported and group sizes are unequal."),
            ("some_concerns", "Concurrent comparators (continuous flooding and manual AWD) are specified with plot counts (Section 2.1; Table 1), but infrastructure, field levelling, soil, irrigation autonomy, and AWD adherence differ materially across sites (Sections 2.1 and 3.1-3.2), so co-intervention balance is incomplete."),
            ("low", "Farmer crop diaries were validated periodically; yield came from five randomly selected 5 m2 cuts per plot standardized to 14% moisture (Section 2.2.1). Water volume came from pump capacity/duration or IoT irrigation history (Section 3.1). Tables 2-4 report outcomes with units: IoT-AWD saved 13-20% water versus manual AWD, energy savings in Can Tho were 24-25%, and yield differences ranged from -12% to 11%."),
            ("some_concerns", "The paper states transparently that experimental-trial results were dropped from the on-farm outcome analysis while retained for the water comparison (Section 3), but it does not quantify missing diaries, withdrawn plots, device failures, or excluded observations among the 147 plots."),
            ("some_concerns", "Intervention, sensors, survey, measurement procedures, and statistical analysis are described (Sections 2.1-2.2; Figure 2) and data are available from the corresponding author on request (Section 4), but no plot-level raw data, analysis code, or reproducible device/cloud configuration is included."),
            ("low", "The IoT tube measured actual field water level every five minutes and transmitted in real time; users monitored remotely and triggered individual pumps (Sections 2.1.1 and 2.2.1). The evaluated intervention relies on contemporaneous monitoring, not future information."),
        ],
        "rob_overall": "some_concerns",
        "applicability_note": "Direct agricultural application evidence: multi-site on-farm rice trials in the Mekong Delta. Highly relevant to IoT-assisted AWD irrigation, but unreported allocation, site-level co-interventions, and missing-data accounting limit causal certainty and generalizability.",
        "pnce": "Retain irrigation_outdoor. Replace the 'unspecified' control label with IoT-assisted AWD: solar-powered water-level sensing, LoRa transmission, app/cloud monitoring, and remotely triggered irrigation (Section 2.1.1; Figure 2). The full text establishes comparators (manual AWD and continuous flooding) and outcomes for water (m3/ha/crop), irrigation energy cost, and rice yield (t/ha at 14% moisture) (Tables 2-4).",
    },
    "S18": {
        "evidence_tier": "E3",
        "evidence_basis": "full_text",
        "fulltext_url": "https://d-nb.info/1372381732/34",
        "locator": (
            "IEEE Access 12 (2024), pp. 153243-153252: Sections II-IV, Eqs. (1)-(29), "
            "Algorithms 1-2; Section V.A with Figures 1-5 and Tables 1-2; Section V.B "
            "with Figures 6-7; Section VI."
        ),
        "D": [
            ("high", "The evaluation covers only an academic two-state nonlinear oscillator and a simulated VTOL aircraft model (Sections V.A-V.B; Eqs. 30-33). No agricultural system, field setting, or communication deployment is evaluated."),
            ("some_concerns", "Approximate and exact self-triggered implementations are compared, and self-triggered MPC is compared with fixed-sampling MPC at stated intervals and noise levels (Sections V.A.1-V.A.3; Figure 4; Table 2), but fixed-sampling choices and sensitivity weights are author-selected and no broad benchmark set is reported."),
            ("some_concerns", "Metrics, settings, and units are defined, including sampling time in seconds, total cost, sample counts, and CPU time (Sections III-V; Figures 1-5; Table 2). The academic example reports mean sampling time about 0.33 s, RMSE 5e-5 s, and maximum deviation 1e-3 s (Section V.A.1), and the noise study uses 50 runs per scenario (Section V.A.2). Several principal comparisons remain graphical."),
            ("some_concerns", "Fifty runs per noise scenario and box plots are reported (Section V.A.2; Figure 4), but random seeds, failed optimizations, infeasibility handling, and exclusion rules are not stated."),
            ("some_concerns", "The MPC formulation, algorithms, bounds, and example parameters are reported (Sections II-V; Algorithms 1-2; Eqs. 30-33) and GRAMPC is named as the solver (Section V.A.1), but no code, input files, seeds, or raw outputs are supplied."),
            ("low", "At each sampling instant the optimization uses the current state x_k and derives the next sampling time from the MPC solution and current cost sensitivity (Sections II.A and III; Algorithm 1). No future measured outcomes or non-causal data are used."),
        ],
        "rob_overall": "high",
        "applicability_note": "Technical-support (indirect) evidence only. It establishes simulation properties of sensitivity-based self-triggered nonlinear MPC on an academic oscillator and a VTOL model, not agricultural control or an agricultural NCS deployment.",
        "pnce": "Reclassify from ncs_iot_platform to generic self-triggered nonlinear MPC technical-support evidence. The full text contains no agricultural plant and no IoT-platform deployment; networked-system references are motivational (Introduction) while the evaluated systems are the academic oscillator and VTOL model (Section V).",
    },
    "S40": {
        "evidence_tier": "E2",
        "evidence_basis": "full_text",
        "fulltext_url": "https://inria.hal.science/hal-01420287/file/978-3-319-19620-6_76_Chapter.pdf",
        "locator": (
            "Full text (HAL deposit inria hal-01420287), Sections 1-4; in particular "
            "Section 2.3 (coordinator design), Section 3 with Figs. 9-12 (control "
            "logic/software), and Section 4 (Results and Conclusion)."
        ),
        "D": [
            ("high", "The reported evaluation is a single four-node star network (one coordinator and three end nodes) about 70 m apart; no greenhouse site, crop, operating duration, or replication is reported (Section 4)."),
            ("not_assessable", "No concurrent comparator system, baseline, or alternative control/network configuration is evaluated; Section 4 reports functionality of the implemented network only."),
            ("high", "Section 4 reports qualitative functional observations (node addresses, LCD showing 0 after an end node is removed, temperature/humidity display restored on rejoin) without defining any numerical metric, unit, measurement window, or quantitative monitoring/control result."),
            ("some_concerns", "Node removal and rejoin behaviour is described (Section 4), but no repetitions, packet/run denominators, failed runs, missing observations, or missing-data rule are reported."),
            ("high", "Hardware and logic are described (Sections 1-3; Figs. 1-12), but no source code, raw temperature/humidity series, threshold values, complete test protocol, or reproducible experimental artifact is supplied."),
            ("not_assessable", "The system is described as real-time threshold-based relay control (Sections 2.3 and 3; Fig. 9), not a predictive-model evaluation, so no temporal validation protocol applies."),
        ],
        "rob_overall": "high",
        "applicability_note": "Agricultural application evidence: a greenhouse ZigBee prototype for temperature/humidity monitoring and threshold relay control. It is engineering feasibility evidence only, with limited reported deployment context and no quantitative or comparative agricultural-effectiveness outcome.",
        "pnce": "The full text confirms P=greenhouse temperature/humidity context, N=ZigBee star network, and C=automatic threshold-triggered relays for humidifiers, fans, sprayers, and heating (Sections 1-3). Reclassify E as qualitative prototype/functionality evidence rather than a quantified performance, water-use, or yield evaluation; the supported tier is E2, not E3.",
    },
    "S63": {
        "evidence_tier": "E3",
        "evidence_basis": "full_text",
        "fulltext_url": "https://link.springer.com/content/pdf/10.1007/s42452-019-0227-8.pdf",
        "locator": (
            "Full text, Sections 3-5; Fig. 1 (architecture), Tables 1-3 (Wi-Fi allocation "
            "and simulation parameters), Sections 4.2-4.3 (three scenarios and metrics), "
            "Sections 5.1-5.2 with Figs. 6-8 and Tables 4-6 (Riverbed results), and "
            "Section 6 with Table 7 (CTMC case study)."
        ),
        "D": [
            ("high", "The two-greenhouse configuration is a Riverbed Modeler simulation: two modelled 200 m x 40 m greenhouses, each divided into five cells (Section 4.1; Fig. 2). No measured greenhouse deployment, crop-specific operation, or multi-site installation is reported."),
            ("some_concerns", "Fault-free operation is compared with two controller-failure scenarios (Section 4.2; Tables 4-6), but the architecture is not compared with an external implementation, an alternative channel-allocation scheme, or a matched non-fault-tolerant design."),
            ("some_concerns", "Packet loss and end-to-end delay are defined (Section 4.3) and reported over 33 seeds of 1800 s at 95% confidence (Section 5). However, the zero-packet-loss and no-over-delayed-packet results are Riverbed simulation outputs, not deployment measurements. Maximum total delay is reported in milliseconds in Tables 4-6, including 5.63-6.02 ms and 5.56-5.94 ms in the fault-free scenario."),
            ("some_concerns", "Section 5 states 33 seeds of 1800 s and analysis of maximum delay and packet loss, but does not state whether any runs failed, were discarded or rerun, nor give a failed-run rule."),
            ("high", "Extensive simulated topology and traffic parameters (Tables 1-3) and numeric results (Tables 4-7) are provided, but no Riverbed model/project file, seed list, simulation scripts, per-seed raw output, or executable configuration is supplied."),
            ("not_assessable", "This is a network/control-architecture simulation, not a predictive or learned-decision evaluation. Although Layer 2 is described as processing sensor readings and issuing actuator commands (Section 3.2), no temporal validation protocol is evaluated."),
        ],
        "rob_overall": "high",
        "applicability_note": "Within agricultural scope because the architecture, sensors, actuators, and two-greenhouse scenarios are greenhouse-specific. Its evidentiary role is nevertheless technical-support/indirect: all packet-loss and delay claims, including zero packet loss and no over-delayed packets, are Riverbed simulation outputs rather than measured deployment results.",
        "pnce": "The full text confirms P=two modelled greenhouses, N=Wi-Fi/Ethernet IoT network with a cloud backend, C=local/remote actuation with controller-failure takeover, and E=auditable simulation evaluation. Retain E3 because comparator conditions, metrics with units, and numeric results are present, but record E specifically as network-simulation performance/reliability evidence, not field-measured agricultural or yield evidence.",
    },
}


def read_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p, rows):
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


rob_path = AUDIT / "rob_grade_audit_log.csv"
avail_path = AUDIT / "fulltext_availability_inventory.csv"
rob = read_csv(rob_path)
avail = read_csv(avail_path)
rob_by = {r["record_id"]: r for r in rob}
avail_by = {r["record_id"]: r for r in avail}

for rid, rv in REVIEWS.items():
    row = rob_by[rid]
    row["evidence_tier"] = rv["evidence_tier"]
    row["evidence_basis"] = rv["evidence_basis"]
    row["fulltext_status"] = "fulltext_reviewed"
    row["fulltext_locator"] = rv["locator"]
    for i, (judg, support) in enumerate(rv["D"]):
        row[f"D{i+1}_{DOMAIN[i]}_judgement"] = judg
        row[f"D{i+1}_{DOMAIN[i]}_support"] = support
    row["rob_overall"] = rv["rob_overall"]
    row["rob_basis"] = (
        "Locator-backed full-text adapted RoB audit (pass-2 lawful OA retrieval)."
        + (" Reviewed version is the arXiv preprint, not the published record." if rid == "S03" else "")
    )
    row["applicability_note"] = rv["applicability_note"]
    row["pnce_evidence_note"] += " | Full-text audit (pass 2): " + rv["pnce"]
    row["audit_status"] = "fulltext_review_complete"
    row["reviewer_id"] = "pass2_fulltext_audit_2026"
    row["audit_date"] = "2026-08-10"

    ar = avail_by[rid]
    ar["fulltext_status"] = "fulltext_reviewed"
    ar["pdf_url"] = rv["fulltext_url"]
    ar["lookup_note"] = (
        "Pass-2 lawful OA retrieval succeeded and full text was reviewed with locators."
        + (" Retrieved copy is the arXiv preprint version." if rid == "S03" else "")
    )

write_csv(rob_path, rob)
write_csv(avail_path, avail)

# Refresh claim-level rationales to reflect the new full-text coverage.
claims_path = AUDIT / "grade_claim_audit.csv"
claims = read_csv(claims_path)
for c in claims:
    if c["claim_id"] == "C3_MPC_DELAY_LOSS":
        c["certainty_rationale"] = (
            "Full-text RoB is now available for S18, S20, S61, and S66; S04, S19, S25, S27, and S65 remain E1. "
            "Reviewed contributors are simulation or academic-model studies with heterogeneous plant and network "
            "assumptions, and S18 is generic (non-agricultural) technical evidence."
        )
write_csv(claims_path, claims)

print(f"Applied {len(REVIEWS)} pass-2 full-text reviews")
