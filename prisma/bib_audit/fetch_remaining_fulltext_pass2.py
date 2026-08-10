#!/usr/bin/env python3
"""Second lawful-retrieval pass for records with no OA location in pass 1.

Targets preprint/repository routes that the OA-location pass cannot see:
arXiv title search, institutional repositories named in metadata (WUR e-depot,
KTH DiVA, HAL), and Semantic Scholar / CORE / OpenAIRE by DOI *and* by title.

Only lawful open locations are requested. Every attempt is appended to the
existing retrieval log so the audit trail stays complete.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"
CACHE = AUDIT / "fulltext_cache"
CACHE.mkdir(exist_ok=True)
LOG = AUDIT / "fulltext_retrieval_log.csv"
UA = "LVTN-thesis-audit/1.0 (academic systematic review; contact via thesis repository)"

# Records still lacking reviewable full text after pass 1.
PENDING = """S01 S03 S04 S05 S09 S11 S12 S13 S14 S15 S17 S19 S21 S22 S23 S24 S25
S26 S27 S28 S29 S31 S32 S37 S39 S47 S49 S50 S51 S56 S62 S64 S65""".split()


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm_doi(value: str) -> str:
    value = (value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    return value.strip()


def get_json(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def get_text(url: str, timeout: int = 25) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def try_pdf(rid: str, url: str, route: str, log: list) -> bool:
    """Download url; keep it only when it is a real, text-bearing PDF."""
    dest = CACHE / f"{rid}.pdf"
    tmp = CACHE / f"{rid}.tmp.pdf"
    cmd = ["curl", "-sSL", "--max-time", "70", "-A", UA,
           "-H", "Accept: application/pdf,*/*", "-o", str(tmp),
           "-w", "%{http_code}", url]
    try:
        code = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout.strip()
    except Exception as exc:
        log.append({"record_id": rid, "route": route, "url": url,
                    "outcome": "ERROR", "detail": type(exc).__name__})
        tmp.unlink(missing_ok=True)
        return False
    if code != "200" or not tmp.exists() or tmp.stat().st_size < 20000:
        log.append({"record_id": rid, "route": route, "url": url,
                    "outcome": f"HTTP_{code}", "detail": f"size={tmp.stat().st_size if tmp.exists() else 0}"})
        tmp.unlink(missing_ok=True)
        return False
    if tmp.read_bytes()[:5] != b"%PDF-":
        log.append({"record_id": rid, "route": route, "url": url,
                    "outcome": "NOT_PDF", "detail": "response body is not a PDF"})
        tmp.unlink(missing_ok=True)
        return False
    txt = CACHE / f"{rid}.txt"
    subprocess.run(["pdftotext", str(tmp), str(txt)], capture_output=True, timeout=180)
    chars = len(txt.read_text(encoding="utf-8", errors="replace")) if txt.exists() else 0
    if chars < 4000:
        log.append({"record_id": rid, "route": route, "url": url,
                    "outcome": "PDF_NO_TEXT", "detail": f"chars={chars}"})
        tmp.unlink(missing_ok=True)
        txt.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    pages = subprocess.run(["pdfinfo", str(dest)], capture_output=True, text=True).stdout
    npages = next((l.split(":")[1].strip() for l in pages.splitlines() if l.startswith("Pages")), "?")
    log.append({"record_id": rid, "route": route, "url": url,
                "outcome": "OK_PDF", "detail": f"pages={npages} chars={chars}"})
    print(f"  RETRIEVED {rid} via {route}: {npages} pages, {chars} chars")
    return True


def arxiv_candidates(title: str) -> list[str]:
    """Search arXiv by exact-ish title; return PDF URLs for close title matches."""
    q = urllib.parse.quote(f'ti:"{title[:180]}"')
    url = f"http://export.arxiv.org/api/query?search_query={q}&max_results=5"
    body = get_text(url, timeout=30)
    if not body:
        return []
    out = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    want = norm(title)
    for entry in root.findall("a:entry", ns):
        got = norm(entry.findtext("a:title", default="", namespaces=ns))
        if not got:
            continue
        # require strong overlap to avoid pulling an unrelated preprint
        if got == want or want in got or got in want:
            for link in entry.findall("a:link", ns):
                if link.get("title") == "pdf" and link.get("href"):
                    out.append(link.get("href"))
    return out


def s2_and_core(doi: str, title: str) -> list[tuple[str, str]]:
    cands: list[tuple[str, str]] = []
    if doi:
        s2 = get_json(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields=openAccessPdf,externalIds")
        if s2 and (s2.get("openAccessPdf") or {}).get("url"):
            cands.append(("semanticscholar_doi", s2["openAccessPdf"]["url"]))
        if s2 and (s2.get("externalIds") or {}).get("ArXiv"):
            cands.append(("arxiv_id", f"https://arxiv.org/pdf/{s2['externalIds']['ArXiv']}"))
    if title:
        q = urllib.parse.quote(title[:200])
        s2t = get_json(f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}&limit=3&fields=title,openAccessPdf,externalIds")
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
        for p in (s2t or {}).get("data", []):
            if norm(p.get("title")) != norm(title):
                continue
            if (p.get("openAccessPdf") or {}).get("url"):
                cands.append(("semanticscholar_title", p["openAccessPdf"]["url"]))
            if (p.get("externalIds") or {}).get("ArXiv"):
                cands.append(("arxiv_id_title", f"https://arxiv.org/pdf/{p['externalIds']['ArXiv']}"))
    return cands


# Repository leads that earlier audit batches identified by name but could not fetch.
MANUAL_LEADS = {
    "S05": [("wur_edepot_search", None)],           # resolved dynamically below
    "S21": [("kth_diva", "https://kth.diva-portal.org/smash/get/diva2:586202/FULLTEXT01")],
    "S29": [("uned_eprints", "https://e-spacio.uned.es/fez/eserv/bibliuned:DptoISIA-ETSI-Articulos-Earanda-0001/Aranda_Escolastico_Ernesto_stability.pdf")],
}


def wur_edepot_lead(title: str) -> list[tuple[str, str]]:
    """Resolve the WUR research portal record to its e-depot PDF, if openly posted."""
    api = ("https://research.wur.nl/en/publications/?search=" + urllib.parse.quote(title[:120]))
    body = get_text(api, timeout=30)
    leads: list[tuple[str, str]] = []
    if body:
        for m in re.finditer(r"https://edepot\.wur\.nl/\d+", body):
            leads.append(("wur_edepot", m.group(0)))
    # OpenAIRE also indexes WUR theses
    return leads


def main() -> None:
    corpus = {r["id"]: r for r in read_csv(AUDIT / "lvtn_68_clean_corpus_FINAL.csv")}
    trail = {r["id"]: r for r in read_csv(AUDIT / "core68_source_audit_trail.csv")}
    audit = {r["id"]: r for r in read_csv(AUDIT / "lvtn_all_metadata_audit.csv")} if (AUDIT / "lvtn_all_metadata_audit.csv").exists() else {}
    log: list[dict] = []
    got: list[str] = []

    for i, rid in enumerate(PENDING, 1):
        row = corpus[rid]
        title = row["title"]
        doi = norm_doi(row.get("doi") or trail.get(rid, {}).get("doi_url", ""))
        # Recover DOIs that are blank in the corpus CSV but present in the metadata audit.
        if not doi:
            key = "S%03d" % int(rid[1:])
            doi = norm_doi((audit.get(key) or {}).get("verified_doi", ""))
        print(f"[{i}/{len(PENDING)}] {rid} {doi or '(no doi)'}")

        cands: list[tuple[str, str]] = []
        cands += s2_and_core(doi, title)
        for url in arxiv_candidates(title):
            cands.append(("arxiv_title", url))
        for route, url in MANUAL_LEADS.get(rid, []):
            if url:
                cands.append((route, url))
        if rid == "S05":
            cands += wur_edepot_lead(title)

        seen: set[str] = set()
        for route, url in cands:
            if not url or url in seen:
                continue
            seen.add(url)
            if try_pdf(rid, url, route, log):
                got.append(rid)
                break
        else:
            if not cands:
                log.append({"record_id": rid, "route": "discovery", "url": "",
                            "outcome": "NO_OA_CANDIDATE",
                            "detail": "arXiv/Semantic Scholar/repository discovery returned no lawful open PDF"})
        time.sleep(0.2)

    # Append to the existing retrieval log rather than overwriting it.
    existing = read_csv(LOG) if LOG.exists() else []
    fields = ["record_id", "route", "url", "outcome", "detail"]
    with LOG.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(existing + log)

    print(f"\nPass 2 newly retrieved: {len(got)} -> {got}")


if __name__ == "__main__":
    main()
