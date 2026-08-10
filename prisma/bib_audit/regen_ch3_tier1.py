#!/usr/bin/env python3
"""Regenerate Chapter 3 counts and \\cite groups on the Tier-1 core evidence set.

Tier 1 = full text retrieved, read, and locator-coded (see build_two_tier_corpus.py).
Only Tier-1 records may contribute to counts, percentages, RoB and GRADE.
Tier-2 records are cited as field context only and are listed separately.

Inputs (no hand-entered numbers):
  bib_audit/two_tier_corpus.csv              tier assignment + full-text coding
  bib_audit/pnce_recode/pnce_fulltext_recode.csv   12-variable recoding
  references.bib                             title -> cite key

Output:
  bib_audit/ch3_tier1_regen.json
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"
BIB = ROOT / "references.bib"
TWO_TIER = AUDIT / "two_tier_corpus.csv"
OUT = AUDIT / "ch3_tier1_regen.json"


def norm(s: str) -> str:
    s = re.sub(r"&amp;", "and", s)
    s = s.lower().replace(r"\&", "and")
    s = re.sub(r"[{}\\$]", "", s)
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def bib_entries(text: str):
    out, i = [], 0
    while True:
        j = text.find("@", i)
        if j < 0:
            break
        k = text.find("{", j)
        if k < 0:
            break
        depth, end = 0, k
        for p in range(k, len(text)):
            if text[p] == "{":
                depth += 1
            elif text[p] == "}":
                depth -= 1
                if depth == 0:
                    end = p
                    break
        body = text[k + 1:end]
        out.append((body.split(",", 1)[0].strip(), body))
        i = end + 1
    return out


def field(body: str, name: str) -> str:
    m = re.search(name + r"\s*=\s*", body, re.I)
    if not m:
        return ""
    q = m.end()
    if body[q] == "{":
        d = 0
        for p in range(q, len(body)):
            if body[p] == "{":
                d += 1
            elif body[p] == "}":
                d -= 1
                if d == 0:
                    return body[q + 1:p]
    if body[q] == '"':
        return body[q + 1:body.find('"', q + 1)]
    m2 = re.search(r"[,\n]", body[q:])
    return body[q:q + m2.start()] if m2 else ""


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    bibmap: dict[str, str] = {}
    for key, body in bib_entries(BIB.read_text(encoding="utf-8")):
        t = norm(field(body, "title"))
        if t:
            bibmap.setdefault(t, key)

    rows = read(TWO_TIER)
    id2key: dict[str, str] = {}
    for r in rows:
        t = norm(r["title"])
        key = bibmap.get(t)
        if not key:
            cand = [bk for bt, bk in bibmap.items() if bt[:50] == t[:50]]
            key = cand[0] if len(cand) == 1 else None
        if not key:
            raise SystemExit(f"No cite key for {r['id']}: {r['title'][:60]}")
        id2key[r["id"]] = key

    tier1 = [r for r in rows if r["tier"] == "tier1_core"]
    tier2 = [r for r in rows if r["tier"] != "tier1_core"]
    n1 = len(tier1)

    def tally(rs, field_name):
        d = defaultdict(list)
        for r in rs:
            d[r[field_name]].append(r["id"])
        return dict(sorted(d.items(), key=lambda kv: -len(kv[1])))

    def keys(ids):
        return [id2key[i] for i in sorted(ids, key=lambda s: int(s[1:]))]

    def pct(n):
        return round(100.0 * n / n1, 1)

    years = defaultdict(list)
    for r in tier1:
        y = int(r["year"])
        bucket = "pre2015" if y < 2015 else ("2024_2025" if y >= 2024 else "2015_2023")
        years[bucket].append(r["id"])

    fields = ["p1_application", "n1_protocol", "c1_strategy", "c2_trigger",
              "c3_architecture", "evidence_type", "comparator_present",
              "rob_overall", "record_role"]
    counts = {f: {k: len(v) for k, v in tally(tier1, f).items()} for f in fields}
    ids = {f: tally(tier1, f) for f in fields}

    # Groups used by the Chapter 3 evidence-summary table.
    strat = ids["c1_strategy"]
    groups = {
        "mpc": keys(strat.get("MPC", [])),
        "etc_stc": keys(strat.get("ETC_event_triggered", []) + strat.get("STC_self_triggered", [])),
        "rl_ml": keys(strat.get("RL_ML", [])),
        "fuzzy_pid": keys(strat.get("Fuzzy", []) + strat.get("PID", [])),
        "optimal_control": keys(strat.get("optimal_control", [])),
        "threshold": keys(strat.get("on_off_threshold", [])),
        "monitoring_only": keys(strat.get("none_monitoring_only", [])),
        "strategy_not_stated": keys(strat.get("not_stated", [])),
        "lorawan": keys(ids["n1_protocol"].get("LoRa_LoRaWAN", [])),
        "self_triggered_trigger": keys(ids["c2_trigger"].get("self_triggered", [])),
        "field_or_plot_evidence": keys(
            ids["evidence_type"].get("field_deployment", [])
            + ids["evidence_type"].get("greenhouse_or_plot_experiment", [])
            + ids["evidence_type"].get("mixed_experiment_and_simulation", [])
        ),
        "simulation_only_evidence": keys(ids["evidence_type"].get("simulation_only", [])),
        "prototype_evidence": keys(ids["evidence_type"].get("lab_prototype_or_HIL", [])),
    }

    tier2_groups = defaultdict(list)
    for r in tier2:
        tier2_groups[r["tier_reason"]].append(r["id"])
    tier2_keys = {k: keys(v) for k, v in tier2_groups.items()}

    result = {
        "n_tier1": n1,
        "n_tier2": len(tier2),
        "year": {k: len(v) for k, v in years.items()},
        "year_pct": {k: pct(len(v)) for k, v in years.items()},
        "counts": counts,
        "pct": {f: {k: pct(v) for k, v in c.items()} for f, c in counts.items()},
        "ids": ids,
        "groups": groups,
        "tier2_reasons": {k: len(v) for k, v in tier2_groups.items()},
        "tier2_ids": {k: v for k, v in tier2_groups.items()},
        "tier2_keys": tier2_keys,
        "id2key": id2key,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Tier 1 (core) = {n1}    Tier 2 (context) = {len(tier2)}")
    print("\n## publication period")
    for k in ("pre2015", "2015_2023", "2024_2025"):
        print(f"  {len(years[k]):3d} ({pct(len(years[k])):>5}%)  {k}")
    for f in fields:
        print(f"\n## {f}")
        for k, v in counts[f].items():
            print(f"  {v:3d} ({pct(v):>5}%)  {k}")
    print("\n--- cite groups (Tier 1) ---")
    for g, ks in groups.items():
        if ks:
            print(f"\n[{g}] n={len(ks)}\n\\cite{{{', '.join(ks)}}}")
    print("\n--- Tier 2 context groups ---")
    for k, ks in tier2_keys.items():
        print(f"\n[{k}] n={len(ks)}\n\\cite{{{', '.join(ks)}}}")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
