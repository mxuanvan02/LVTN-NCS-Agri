#!/usr/bin/env python3
"""Apply locator-backed full-text RoB decisions to the metadata audit log.

This file is deliberately separate from build_rob_grade_audit.py so rerunning
metadata/OA discovery cannot silently overwrite human full-text judgements.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "rob_grade_audit_log.csv"
INV = ROOT / "fulltext_availability_inventory.csv"
DATE = "2026-08-09"

# tier, locator, D1..D6 pairs, overall, applicability
R = {
"S20": ("E3", "Full text pp.1--7; Section V p.6; Figs.2--6 pp.6--7.",
 [("high","One simulated three-robot case only (Section V, p.6)."),("high","No concurrent comparator in Section V/Figs.2--6, pp.6--7."),("some_concerns","Plots cover 0--20 steps; graphical outcomes only (Figs.2--5, p.7)."),("unclear","No repetitions, seeds, failed runs or exclusions reported (Section V, p.6)."),("some_concerns","Parameters reported, but no code/solver artifact located (Section V, p.6)."),("unclear","Temporal-information protocol not described (Section V, p.6).")], "high", "Single theoretical simulation; mechanism evidence, indirect for agriculture."),
"S30": ("E3", "Full text pp.1--12; Table I/Section IV p.9; Figs.4--12 pp.9--11.",
 [("some_concerns","Two simulated settings, no physical deployment (Section IV, pp.9--11)."),("some_concerns","Comparators used, but matched tuning/budgets not established (Section IV, pp.9--11)."),("some_concerns","Scenario-specific updates/power and 300-step episodes; limited uncertainty (pp.10--11)."),("some_concerns","Five training processes/50 tests stated; seeds and failed-run accounting absent (pp.9--11)."),("high","No code, trained policy, seeds or complete hyperparameter artifact located (Section IV)."),("unclear","Tuning/final-test separation not documented (Sections III--IV).")], "some_concerns", "Comparative simulation evidence only; not deployed ICPS evidence."),
"S34": ("E3", "Full text pp.278--290; Sections A--B pp.285--288; Figs.14--17; Table 2.",
 [("high","Single greenhouse prototype with three-day observations (Section B, pp.286--288)."),("high","No concurrent external comparator (Section A, pp.285--286)."),("some_concerns","Relevant device measures, but only three-day horizon and no yield outcome (Section B)."),("some_concerns","Errors acknowledged; replicates/missing-data/failed-run rules absent (p.287)."),("some_concerns","Prototype parameters reported; no code/raw series located (pp.285--288)."),("unclear","Evapotranspiration prediction timing/source insufficiently specified (p.287).")], "high", "Three-day engineering demonstration; not comparative agronomic evidence."),
"S35": ("E3", "Full text pp.1--46; Section 3.6 pp.30--37; Sections 4--5 pp.38--42.",
 [("not_assessable","System description without scenario-based performance evaluation (Sections 3.6--5)."),("not_assessable","No comparator experiment (Figs.27--38, pp.33--37)."),("not_assessable","No defined numerical crop/system performance outcomes (Sections 4--5)."),("not_assessable","No evaluative run set or failure accounting (Sections 3.6--5)."),("high","No source code, raw data or complete control configuration (pp.29--37)."),("unclear","Recommendation inputs lack temporal-separation specification (Section 3.6).")], "high", "Architecture/interface description only; not effectiveness evidence."),
"S41": ("E3", "Full text pp.15--20; Sections 2.1--2.7 pp.15--18; Tables 3--9 pp.19--20.",
 [("some_concerns","Two-year 80-ha field study at one rice farm, three blocks/treatment (p.15)."),("some_concerns","Control and RCBD stated; allocation/co-intervention balance incompletely described (p.15)."),("low","Two seasons with defined irrigation, yield, nitrogen, accuracy and stability outcomes (pp.15,18--20)."),("some_concerns","Failures reported, but missingness and exclusions not quantified (pp.16,20)."),("some_concerns","Methods detailed; no code/raw field data/model artifact (pp.15--18)."),("some_concerns","70/15/15 split not stated chronological; interpolation/LSTM may use future information (pp.16--17).")], "some_concerns", "Two-season single-farm comparative field evidence; limited external validity."),
"S42": ("E2", "Full text; system design Figs.1--7/Tables 2--3; results PDF pp.17--25; S1--S3 Tables p.25.",
 [("some_concerns","Indoor prototype with short subsystem tests; limited sites/crops/conditions (pp.17--25)."),("not_assessable","No concurrent irrigation comparator (pp.17--25)."),("some_concerns","Short hardware horizons; no long-term plant/water outcome (p.25)."),("some_concerns","No missing-run/exclusion protocol (p.25)."),("some_concerns","Architecture/specifications supplied; no code/raw dataset (Figs.1,5--7; Tables 2--3)."),("not_assessable","Real-time prototype, no predictive validation protocol.")], "some_concerns", "Indoor implementation evidence; not comparative field effectiveness."),
"S43": ("E2", "Full text pp.59--68; Section IV pp.63--64; Section V pp.66--67; Fig.18.",
 [("high","Only a short generic-node test; no seasonal/site/crop deployment results (p.67)."),("not_assessable","No concurrent comparator (Sections IV--V)."),("high","Short acquisition trend only; no water/fertilizer/crop horizon (p.67)."),("some_concerns","Retries described but failures/packets/exclusions not quantified (pp.63--67)."),("high","No agronomic model/code/configuration/raw data (Sections IV--V)."),("unclear","Forecast source and temporal availability unspecified (Abstract; Section IV).")], "high", "WSN/fertigation architecture feasibility only."),
"S48": ("E2", "Full text pp.1--20; Sections 5.1--5.3 pp.13--17; Table 1; Figs.9--13.",
 [("high","Range test around a university, not diverse agricultural environments (p.15)."),("not_assessable","No comparator irrigation/communication system (pp.13--17)."),("some_concerns","Link/power measures reported; no irrigation/water/crop outcome horizon (pp.15--17)."),("some_concerns","Signal loss reported, but packet attempts/PDR/actions/exclusions absent (p.15)."),("high","No code/raw experiment/cloud configuration (pp.9--15)."),("unclear","No timestamped decision or temporal-separation protocol (pp.7--13).")], "high", "Prototype communications evidence; not irrigation-effectiveness evidence."),
"S55": ("E2", "Full text pp.1--6; Methods pp.2--4; Table 1/Fig.5 p.5.",
 [("high","Point-to-point line-of-sight 100--1000 m trials only (pp.2--4)."),("not_assessable","No concurrent comparator (pp.2--5)."),("some_concerns","RSSI/SNR reported; PDR, duration and greenhouse outcome absent (pp.3,5)."),("high","Collisions acknowledged but not quantified; missing/excluded runs absent (pp.3,5)."),("high","No code, exact transmission config or raw observations (pp.3--5)."),("not_assessable","Monitoring/link study; no predictive validation.")], "high", "LoRaWAN link/monitoring evidence only."),
"S58": ("E3", "Full text pp.1--7; Methods pp.2--3; Tables 1--3/Fig.2 pp.3--6.",
 [("low","Five greenhouse configurations, 45 points, ten days/configuration (pp.1--3)."),("some_concerns","Randomized design stated; order/weather balance/contemporaneous control unclear (p.3)."),("low","30-s readings for ten days/configuration with defined tests (p.3)."),("some_concerns","Fan failure noted; handling of anomalous/missing data unclear (p.6)."),("some_concerns","Sensors/layout/cadence/tests specified; no raw data/scripts (pp.2--3)."),("not_assessable","Physical monitoring study, no predictive validation.")], "some_concerns", "Controlled greenhouse microclimate monitoring; not control/yield evidence."),
}

with LOG.open(encoding="utf-8-sig", newline="") as f:
    rows=list(csv.DictReader(f)); fields=list(rows[0])
for row in rows:
    rid=row["record_id"]
    if rid not in R: continue
    tier, locator, domains, overall, applicability=R[rid]
    row.update({"evidence_tier":tier,"evidence_basis":"full_text","fulltext_status":"fulltext_reviewed","fulltext_locator":locator,"rob_overall":overall,"rob_basis":"Locator-backed full-text audit using adapted D1--D6 engineering RoB framework.","applicability_note":applicability,"audit_status":"fulltext_review_complete","reviewer_id":"independent_fulltext_review_2026","audit_date":DATE})
    for i,(jud,support) in enumerate(domains,1):
        name={1:"selection",2:"performance",3:"detection",4:"attrition",5:"reporting",6:"information_leakage"}[i]
        row[f"D{i}_{name}_judgement"]=jud; row[f"D{i}_{name}_support"]=support
with LOG.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

with INV.open(encoding="utf-8-sig",newline="") as f:
    inv=list(csv.DictReader(f)); ifields=list(inv[0])
for row in inv:
    if row["record_id"] in R:
        row["fulltext_status"]="fulltext_reviewed"
        row["lookup_note"]="Downloaded full text retained in bib_audit/fulltext_cache and audited with locators."
with INV.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=ifields); w.writeheader(); w.writerows(inv)
print("Applied",len(R),"full-text reviews")
