#!/usr/bin/env python3
"""Apply the pass-3 locator-backed full-text reviews (S05, S13).

Both records were retrieved in the third lawful OA sweep:
  S05 -> Wageningen e-depot copy of the 1994 doctoral thesis (edepot.wur.nl/205106)
  S13 -> MDPI static article mirror (mdpi-res.com)

Every quantitative statement below was verified verbatim against the cached
full text in bib_audit/fulltext_cache/. One reviewer claim was rejected during
verification: the reviewer attributed S13's meteorological inputs to "NASA
POWER", but that string does not occur in the article. The article states only
that hourly climatological data were recorded in a computational database from
1 July to 29 August. The support text below records what the article actually
says.
"""
from __future__ import annotations
import csv
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
DOMAIN = ["selection", "performance", "detection", "attrition", "reporting", "information_leakage"]

REVIEWS = {
    "S05": {
        "evidence_tier": "E3",
        "evidence_basis": "full_text_thesis",
        "fulltext_url": "https://edepot.wur.nl/205106",
        "locator": (
            "Doctoral thesis (Wageningen, 1994), Wageningen e-depot copy: Chapter 3 Sec. 3.2.1 "
            "(experimental greenhouse, floor area approx. 300 m2); Chapter 7 Sec. 7.2.2-7.2.3 "
            "(grower vs optimal control comparison), Fig. 7.1 and Table 7.1 (CO2, energy, "
            "ventilation outcomes); Sec. 7.4.2 (sub-optimal feedback/feedforward runs); "
            "Sec. 7.5.2 (50 of 57 days simulated, VAX workspace limit); Chapters 8-9 "
            "(conclusions and the statement that full-scale comparative experiments remain needed)."
        ),
        "D": [
            ("high",
             "Control-performance evidence rests on simulations tied to one experimental 4-span "
             "Venlo-type greenhouse with a floor area of approximately 300 m2 and the single 1992 "
             "lettuce experiment (Chapter 3 Sec. 3.2.1; Chapter 7 Sec. 7.2.2). The thesis itself "
             "states that full-scale comparative experiments are still necessary (Chapter 9), so "
             "the evaluation is a single illustrative case rather than a sampled or replicated trial."),
            ("high",
             "Optimal control is compared against the grower's recorded operation under the same "
             "measured 1992 outside climate, but both arms are produced through the model and the "
             "optimal trajectories were, in the thesis's own words, calculated after the greenhouse "
             "experiment had ended using complete knowledge about the outside climatic conditions as "
             "well as the auction price (Chapter 7 Sec. 7.2.3). The comparator therefore has a "
             "structural information advantage and is not a concurrent physical control arm."),
            ("some_concerns",
             "Comparator outcomes are auditable with units: CO2 consumption, energy consumption, and "
             "ventilation per unit area for the grower and simulation runs, plus relative harvest "
             "weight and net return (Chapter 7 Fig. 7.1 and Table 7.1). However, these are "
             "model-derived quantities without replicate-level uncertainty, and crop quality, fungal "
             "disease, and physiological damage are explicitly left out of the criterion (Chapter 7)."),
            ("some_concerns",
             "The thesis discloses that although the second greenhouse experiment lasted 57 days, only "
             "50 days were simulated because of limitations in the available workspace on the VAX "
             "mainframe (Chapter 7 Sec. 7.5.2), and it reports the integration method and stopping "
             "criterion. It does not account for failed optimisation runs, numerical breakdowns, or "
             "excluded runs, and the deterministic simulations report no replicates."),
            ("some_concerns",
             "Model equations, parameters, constraints, units, Runge-Kutta integration, and the "
             "steepest-ascent optimisation with its stopping rule are reported in detail (Chapter 6 "
             "Table 6.1; Chapter 7 Sec. 7.2.2 and 7.5.2), but no code, executable, or raw dataset is "
             "supplied. The source is a doctoral thesis examined at Wageningen rather than a "
             "peer-reviewed journal article, so it lacks external journal peer-review assurance."),
            ("high",
             "The principal grower comparison uses trajectories computed with complete knowledge of "
             "future weather and auction price (Chapter 7 Sec. 7.2.3). The sub-optimal "
             "feedback/feedforward evaluation additionally sets the one-step-ahead prediction equal to "
             "the next measurement in the 1992 data (Chapter 7 Sec. 7.4.2). Both are information "
             "assumptions unavailable at prospective decision time."),
        ],
        "rob_overall": "high",
        "applicability_note": (
            "Two physical lettuce greenhouse experiments support model calibration and validation, but "
            "the optimal-control performance comparisons are retrospective simulations driven by "
            "measured greenhouse and weather inputs, not physical deployments of optimal control. "
            "Numeric comparator outcomes justify E3, yet they do not establish prospective greenhouse "
            "effectiveness. The source is a 1994 doctoral thesis, not a peer-reviewed article."
        ),
        "pnce": (
            "Plant is greenhouse lettuce with coupled climate, growth, CO2, heating, ventilation, and "
            "humidity models. Network is ABSENT: full-text search finds no packet, protocol, wireless, "
            "LoRa, ZigBee, networked-control, or communication-delay content, and the 'distribution "
            "network' wording in Chapter 3 refers to physical CO2 hoses rather than a data network. "
            "Control is centralised economic optimal control with time-scale decomposition, open-loop "
            "and feedback/feedforward variants, and a proposed receding-horizon implementation. "
            "Evaluation combines experimental model validation with retrospective control simulation. "
            "Correct the control label from 'unspecified' to centralised optimal control, and record "
            "explicitly that this source carries no networked-control evidence."
        ),
    },
    "S13": {
        "evidence_tier": "E3",
        "evidence_basis": "full_text",
        "fulltext_url": "https://mdpi-res.com/d_attachment/applsci/applsci-12-04235/article_deploy/applsci-12-04235.pdf",
        "locator": (
            "Applied Sciences 2022, 12, 4235: Sec. 3.1-3.2 (irrigation scheduling and microgrid EMS "
            "formulation); Sec. 4.1 (case study, plot of 1173 m2 in Cotopaxi, Ecuador); Sec. 4.2-4.5 "
            "(traditional, technified, and proposed irrigation plus EMS scenarios); Table 5 "
            "(technified irrigation schedule); Table 7 (comparative crop time, irrigation hours, "
            "gallons, and cost); Figs. 4-7 (soil-moisture trajectories and one-day EMS dispatch); "
            "Data Availability Statement (declared 'Not applicable')."
        ),
        "D": [
            ("high",
             "The evaluation is a deterministic 60-day software simulation for one modelled 1173 m2 "
             "alfalfa plot in Cotopaxi, Ecuador, over a single 1 July to 29 August record (Sec. 4.1; "
             "Sec. 4). No physical deployment, hardware-in-the-loop test, replication, or site "
             "sampling is reported."),
            ("some_concerns",
             "Traditional, technified, and proposed irrigation are compared numerically over the same "
             "stated 60-day crop period (Table 7), but the three schedules are constructed by "
             "different procedures and matched optimisation constraints or equivalent operating "
             "policies are not established; the second scenario is applied only to the proposed EMS "
             "(Sec. 4.2 and 4.4)."),
            ("some_concerns",
             "Modelled outcomes are auditable with units: traditional 60 h and USD 57, technified 83 h "
             "and USD 78.85, proposed 37 h and USD 35.15 over 60 days, with gallons per technique "
             "(Table 7), plus simulated soil-moisture trajectories in mm (Figs. 4-6). However, no "
             "measured field water use, crop growth, yield, or hardware energy outcome is reported, "
             "and no uncertainty estimates accompany the point values."),
            ("high",
             "No repeated runs, seeds, missing-data rule, solver-failure accounting, excluded periods, "
             "or sensitivity analysis is reported for the 60-day simulation; results are presented as "
             "one deterministic trajectory plus a single one-day EMS dispatch profile (Sec. 4.2-4.5; "
             "Fig. 7)."),
            ("high",
             "Equations, component ratings, and schedules are reported (Tables 1-6), and the solver "
             "environment is named, but no code, complete input series, or reusable output artifact is "
             "supplied, and the Data Availability Statement declares 'Not applicable', which removes "
             "any route to independent verification of the reported savings."),
            ("high",
             "Irrigation decisions use one-day-ahead precipitation and meteorological predictions and "
             "the EMS uses a 24-sample irradiance prediction horizon (Sec. 3.1), while the evaluation "
             "inputs are described only as hourly climatological data recorded in a computational "
             "database from 1 July through 29 August (Sec. 4). No forecast issue times, archived "
             "forecast products, or hindcast protocol are reported, so forecast availability at each "
             "decision instant is not demonstrated."),
        ],
        "rob_overall": "high",
        "applicability_note": (
            "Comparative engineering evidence from a deterministic software simulation driven by "
            "historical hourly climatological records. The article does not demonstrate field "
            "deployment or hardware-in-the-loop evaluation, so the reported water, diesel, and cost "
            "savings are modelled rather than measured outcomes."
        ),
        "pnce": (
            "Plant is modelled alfalfa on a nominal 1173 m2 Ecuadorian plot over 60 days, not a "
            "measured crop deployment. Network is ABSENT: no communication protocol, delay, packet "
            "loss, or link performance is evaluated, so the existing 'unspecified' protocol label is "
            "correct and must not be upgraded. Control is rule-based daily water-balance irrigation "
            "scheduling combined with MPC-style microgrid energy optimisation for pump timing plus "
            "battery, photovoltaic, and diesel dispatch. Evaluation is software simulation with "
            "numeric comparisons in Tables 5-7 and Figs. 4-7. Retain MPC for the energy-management "
            "stage but record that the irrigation-scheduling stage is rule-based water balance, and "
            "that no networked-control evidence is present."
        ),
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
        "Locator-backed full-text adapted RoB audit (pass-3 lawful OA retrieval); "
        "every quantitative claim was verified verbatim against the cached full text."
        + (" Reviewed source is a doctoral thesis, not a peer-reviewed article." if rid == "S05" else "")
    )
    row["applicability_note"] = rv["applicability_note"]
    # Appending unconditionally would stack another copy of the same audit
    # note on every rerun, so the marker is added only once.
    _pass3_note = " | Full-text audit (pass 3): " + rv["pnce"]
    if _pass3_note not in row["pnce_evidence_note"]:
        row["pnce_evidence_note"] += _pass3_note
    row["audit_status"] = "fulltext_review_complete"
    row["reviewer_id"] = "pass3_fulltext_audit_2026"
    row["audit_date"] = "2026-08-10"

    ar = avail_by[rid]
    ar["fulltext_status"] = "fulltext_reviewed"
    ar["pdf_url"] = rv["fulltext_url"]
    ar["lookup_note"] = (
        "Pass-3 lawful OA retrieval succeeded and full text was reviewed with locators."
        + (" Retrieved copy is the Wageningen e-depot thesis." if rid == "S05" else
           " Retrieved copy is the MDPI static article mirror.")
    )

write_csv(rob_path, rob)
write_csv(avail_path, avail)
print("Applied", len(REVIEWS), "pass-3 full-text reviews")
