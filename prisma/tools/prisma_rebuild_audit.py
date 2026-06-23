#!/usr/bin/env python3
"""Rebuild PRISMA audit data from transparent search strings and local seeds.

The script records the exact search queries, fetches metadata from OpenAlex,
merges with existing local seed lists, deduplicates by DOI/title, and applies a
conservative title/abstract PNCE screen for smart-agriculture NCS relevance.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bib_audit"
UA = "LVTN-PRISMA-Audit/2.0 (mailto:example@example.com)"
YEAR_FROM = 2015
YEAR_TO = 2025

QUERIES = [
    ("Q1", '"networked control system" "smart agriculture" irrigation'),
    ("Q2", '"event-triggered control" irrigation agriculture'),
    ("Q3", '"model predictive control" irrigation greenhouse agriculture'),
    ("Q4", 'LoRaWAN latency irrigation greenhouse control'),
    ("Q5", '"wireless sensor network" greenhouse irrigation control'),
    ("Q6", '"edge computing" "smart agriculture" control irrigation'),
    ("Q7", '"NB-IoT" smart agriculture irrigation control'),
    ("Q8", '"smart greenhouse" control IoT network'),
    ("Q9", '"precision irrigation" IoT control LoRaWAN'),
    ("Q10", '"closed-loop" irrigation control IoT agriculture'),
]

INCLUDE_TERMS = [
    "agriculture", "agricultural", "irrigation", "greenhouse", "crop", "soil moisture",
    "fertigation", "farm", "farming", "orchard", "plant",
]
PNCE_TERMS = [
    "control", "controller", "controlled", "networked control", "event-triggered",
    "self-triggered", "mpc", "model predictive", "pid", "fuzzy", "closed-loop",
    "lora", "lorawan", "zigbee", "wifi", "wireless sensor", "wsn", "iot", "edge",
    "nb-iot", "5g", "latency", "packet", "network",
]
EXCLUDE_TERMS = [
    "dicom", "image compression", "arabic text", "smart cities", "pest detection",
    "crop prediction", "soil fertility", "post-harvest", "solar dryer", "uav clusters",
    "medical", "super-resolution", "review", "survey", "systematic literature review",
    "comprehensive review", "future outlook", "opportunities challenges",
]

@dataclass
class Record:
    raw_id: str
    source_channel: str
    query_id: str
    title: str
    year: str = ""
    authors: str = ""
    venue: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    raw_status: str = "identified"
    dedupe_status: str = "unique"
    pnce_status: str = "pending"
    exclusion_reason: str = ""
    match_score: str = ""


def norm(s: str) -> str:
    s = s.lower().replace("\\&", "and")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_key(title: str) -> str:
    words = [w for w in norm(title).split() if w not in {"a", "an", "the", "of", "and", "for", "in", "on", "with", "to", "by"}]
    return " ".join(words[:18])


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def inverted_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pairs = []
    for word, positions in inv.items():
        for pos in positions:
            pairs.append((pos, word))
    return " ".join(w for _, w in sorted(pairs))


def openalex_search(qid: str, query: str, per_page: int = 25) -> list[Record]:
    params = {
        "search": query,
        "filter": f"from_publication_date:{YEAR_FROM}-01-01,to_publication_date:{YEAR_TO}-12-31",
        "per-page": str(per_page),
        "mailto": "example@example.com",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    recs = []
    for item in data.get("results", []):
        authors = "; ".join(
            a.get("author", {}).get("display_name", "")
            for a in item.get("authorships", [])[:6]
            if a.get("author", {}).get("display_name")
        )
        venue = (item.get("primary_location") or {}).get("source", {}) or {}
        doi = (item.get("doi") or "").replace("https://doi.org/", "")
        recs.append(Record(
            raw_id="",
            source_channel="OpenAlex",
            query_id=qid,
            title=item.get("display_name") or "",
            year=str(item.get("publication_year") or ""),
            authors=authors,
            venue=venue.get("display_name") or "",
            doi=doi,
            url=item.get("doi") or item.get("id") or "",
            abstract=inverted_abstract(item.get("abstract_inverted_index")),
        ))
    time.sleep(0.2)
    return recs


def parse_local_items(path: Path, channel: str) -> list[Record]:
    if not path.exists():
        return []
    recs = []
    pat = re.compile(r"\\item\s+(.*)")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.search(line)
        if not m:
            continue
        text = m.group(1).strip()
        ym = re.search(r"\((20\d{2}|19\d{2})\)", text)
        year = ym.group(1) if ym else ""
        title = re.sub(r"^.*?\((?:20\d{2}|19\d{2})\)\.\s*", "", text).strip()
        title = title.rstrip(".")
        authors = text[:ym.start()].strip(" .,") if ym else ""
        recs.append(Record("", channel, "LOCAL", title, year, authors))
    return recs


def parse_core_csv(path: Path) -> list[Record]:
    if not path.exists():
        return []
    out = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out.append(Record(
                raw_id="", source_channel="existing_core68", query_id="CORE68",
                title=row.get("title", ""), year=row.get("year", ""), venue=row.get("venue", ""),
                doi=(row.get("doi", "") or row.get("doi_url", "")).replace("https://doi.org/", ""),
                url=row.get("doi_url", "") or ("https://doi.org/" + row.get("doi", "") if row.get("doi") else ""),
                pnce_status="included_core"
            ))
    return out


def screen_record(r: Record) -> None:
    blob = norm(r.title + " " + r.abstract)
    if not blob:
        r.pnce_status = "exclude"
        r.exclusion_reason = "R00_missing_title"
        return
    if int(r.year or 0) and not (YEAR_FROM <= int(r.year) <= YEAR_TO):
        r.pnce_status = "exclude"
        r.exclusion_reason = "R01_out_of_year_range"
        return
    if any(t in blob for t in EXCLUDE_TERMS):
        r.pnce_status = "exclude"
        r.exclusion_reason = "R02_wrong_document_type_or_domain"
        return
    app = any(t in blob for t in INCLUDE_TERMS)
    pnce = any(t in blob for t in PNCE_TERMS)
    if app and pnce:
        r.pnce_status = "candidate_core"
        r.exclusion_reason = ""
    elif app:
        r.pnce_status = "exclude"
        r.exclusion_reason = "R03_no_clear_network_control_component"
    else:
        r.pnce_status = "exclude"
        r.exclusion_reason = "R04_out_of_agriculture_scope"


def write_csv(path: Path, rows: list[Record]) -> None:
    fields = list(asdict(rows[0]).keys()) if rows else list(Record("", "", "", "").__dict__.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def main() -> None:
    all_rows: list[Record] = []
    query_log = []
    for qid, query in QUERIES:
        try:
            rows = openalex_search(qid, query)
            query_log.append({"query_id": qid, "database": "OpenAlex", "query": query, "records_returned": len(rows)})
            all_rows.extend(rows)
        except Exception as e:
            query_log.append({"query_id": qid, "database": "OpenAlex", "query": query, "error": str(e), "records_returned": 0})
    all_rows.extend(parse_local_items(ROOT / "paper_list.txt", "local_paper_list"))
    all_rows.extend(parse_local_items(ROOT / "cleaned_papers.txt", "local_cleaned_papers"))
    all_rows.extend(parse_core_csv(OUT / "lvtn_68_clean_corpus_FINAL.csv"))

    # Put the previously manually verified core corpus first so deduplication
    # never drops an accepted source in favor of a less complete search hit.
    all_rows.sort(key=lambda r: 0 if r.source_channel == "existing_core68" else 1)
    for i, r in enumerate(all_rows, 1):
        r.raw_id = f"RAW{i:03d}"

    seen: dict[str, Record] = {}
    unique: list[Record] = []
    for r in all_rows:
        key = ("doi:" + norm(r.doi)) if r.doi else ("title:" + title_key(r.title))
        dup_key = None
        if key in seen:
            dup_key = key
        elif not r.doi:
            for k, prev in seen.items():
                if k.startswith("title:") and sim(r.title, prev.title) >= 0.94:
                    dup_key = k
                    break
        if dup_key:
            r.dedupe_status = "duplicate"
            r.exclusion_reason = "D01_duplicate_of_" + seen[dup_key].raw_id
        else:
            seen[key] = r
            unique.append(r)

    for r in unique:
        if r.pnce_status != "included_core":
            screen_record(r)

    # Preserve the manually verified 68 as included_core and let new search add candidate_core.
    for r in unique:
        if r.pnce_status == "included_core":
            r.exclusion_reason = "verified_core68_prior_audit"

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "prisma_raw_all_sources_rebuilt.csv", all_rows)
    write_csv(OUT / "prisma_unique_screening_rebuilt.csv", unique)

    counts = {
        "raw_identified_total": len(all_rows),
        "unique_after_dedup": len(unique),
        "duplicates_removed": len(all_rows) - len(unique),
        "included_core_verified": sum(1 for r in unique if r.pnce_status == "included_core"),
        "candidate_core_after_automated_pnce": sum(1 for r in unique if r.pnce_status == "candidate_core"),
        "excluded_after_screening": sum(1 for r in unique if r.pnce_status == "exclude"),
    }
    counts["included_or_candidate_total"] = counts["included_core_verified"] + counts["candidate_core_after_automated_pnce"]
    (OUT / "prisma_rebuilt_query_log.json").write_text(json.dumps({"queries": query_log, "counts": counts}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
