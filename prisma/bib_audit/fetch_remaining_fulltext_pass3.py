#!/usr/bin/env python3
"""Pass-3 lawful full-text retrieval for records still at E1.

Pass 2 only exercised the arXiv route for a single record. This pass runs the
arXiv author-manuscript route properly for every pending record, adds DOAJ
article full-text links, and adds targeted institutional-repository patterns
for records whose author affiliations have a known open repository.

Only lawful publisher/repository/preprint sources are used. Retrieval success is
recorded as availability; it never by itself upgrades an evidence tier.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
CACHE = AUDIT / "fulltext_cache"
CACHE.mkdir(exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# Targeted lawful repository / static-host patterns keyed by record id.
TARGETED: dict[str, list[tuple[str, str]]] = {
    "S05": [
        ("wur_fulltext", "https://library.wur.nl/WebQuery/wurpubs/fulltext/205106"),
        ("wur_edepot", "https://edepot.wur.nl/205106"),
    ],
    "S13": [
        ("mdpi_static", "https://mdpi-res.com/d_attachment/applsci/applsci-12-04235/article_deploy/applsci-12-04235.pdf"),
        ("mdpi_static", "https://mdpi-res.com/d_attachment/applsci/applsci-12-04235/article_deploy/applsci-12-04235-v2.pdf"),
    ],
    "S21": [
        ("diva_kth", "https://www.diva-portal.org/smash/get/diva2:586202/FULLTEXT01"),
        ("diva_kth", "http://kth.diva-portal.org/smash/get/diva2:586202/FULLTEXT01.pdf"),
    ],
    "S50": [
        ("dergipark", "https://dergipark.org.tr/tr/download/article-file/587896"),
        ("dergipark", "https://dergipark.org.tr/en/download/article-file/587896"),
    ],
}

# DSpace / discovery search endpoints (query-by-title) for known affiliations.
DSPACE = {
    "S17": ("eth_research_collection",
            "https://www.research-collection.ethz.ch/server/api/discover/search/objects?query="),
    "S29": ("uned_espacio",
            "https://e-spacio.uned.es/server/api/discover/search/objects?query="),
    "S39": ("ual_repositorio",
            "https://repositorio.ual.es/server/api/discover/search/objects?query="),
    "S49": ("uth_repository",
            "https://ir.lib.uth.gr/server/api/discover/search/objects?query="),
}


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fetch(url: str, timeout: int = 30) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/pdf,text/html,application/json,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, b"", ""
    except Exception:
        return -1, b"", ""


def save_pdf(rid: str, blob: bytes) -> tuple[bool, int]:
    """Persist a candidate PDF only if it is a real PDF with extractable text."""
    if not blob.startswith(b"%PDF"):
        return False, 0
    pdf = CACHE / f"{rid}.pdf"
    pdf.write_bytes(blob)
    txt = CACHE / f"{rid}.txt"
    try:
        subprocess.run(["pdftotext", str(pdf), str(txt)], check=True,
                       capture_output=True, timeout=120)
    except Exception:
        pdf.unlink(missing_ok=True)
        return False, 0
    chars = len(txt.read_text(encoding="utf-8", errors="ignore").strip()) if txt.exists() else 0
    if chars < 4000:            # scanned/stub PDFs are not auditable full text
        pdf.unlink(missing_ok=True)
        txt.unlink(missing_ok=True)
        return False, chars
    return True, chars


def arxiv_candidates(title: str) -> list[str]:
    q = urllib.parse.quote(f'ti:"{title[:120]}"')
    url = f"http://export.arxiv.org/api/query?search_query={q}&max_results=8"
    code, body, _ = fetch(url, timeout=40)
    if code != 200 or not body:
        return []
    text = body.decode("utf-8", errors="ignore")
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", text, flags=re.S):
        t = re.search(r"<title>(.*?)</title>", entry, flags=re.S)
        pid = re.search(r"<id>(.*?)</id>", entry, flags=re.S)
        if not (t and pid):
            continue
        ratio = difflib.SequenceMatcher(None, norm(t.group(1)), norm(title)).ratio()
        if ratio >= 0.85:
            abs_url = pid.group(1).strip()
            out.append(abs_url.replace("/abs/", "/pdf/"))
    return out


def doaj_candidates(doi: str) -> list[str]:
    if not doi:
        return []
    url = "https://doaj.org/api/search/articles/doi:" + urllib.parse.quote(doi, safe="")
    code, body, _ = fetch(url, timeout=30)
    if code != 200 or not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    urls = []
    for res in data.get("results", []):
        for link in (res.get("bibjson", {}) or {}).get("link", []) or []:
            if link.get("type") in {"fulltext", "pdf"} and link.get("url"):
                urls.append(link["url"])
    return urls


def dspace_candidates(rid: str, title: str) -> list[str]:
    if rid not in DSPACE:
        return []
    _, base = DSPACE[rid]
    code, body, _ = fetch(base + urllib.parse.quote(title[:90]), timeout=30)
    if code != 200 or not body:
        return []
    # Collect any bitstream/download links advertised by the DSpace REST payload.
    text = body.decode("utf-8", errors="ignore")
    return list(dict.fromkeys(re.findall(r"https?://[^\"\\ ]+?/bitstreams/[^\"\\ ]+?/content", text)))[:3]


corpus = {r["id"]: r for r in read_csv(AUDIT / "lvtn_68_clean_corpus_FINAL.csv")}
rob = read_csv(AUDIT / "rob_grade_audit_log.csv")
pending = [r["record_id"] for r in rob if r["evidence_tier"].startswith("E1")]

log_rows: list[dict] = []
retrieved: list[tuple[str, str, str, int]] = []

for i, rid in enumerate(pending, 1):
    rec = corpus[rid]
    title = rec["title"]
    doi = (rec.get("doi") or "").strip()
    print(f"[{i}/{len(pending)}] {rid}", flush=True)

    candidates: list[tuple[str, str]] = list(TARGETED.get(rid, []))
    candidates += [("arxiv_title", u) for u in arxiv_candidates(title)]
    candidates += [("doaj_fulltext", u) for u in doaj_candidates(doi)]
    candidates += [("dspace_repository", u) for u in dspace_candidates(rid, title)]

    if not candidates:
        log_rows.append({"record_id": rid, "route": "pass3", "url": "",
                         "outcome": "NO_NEW_CANDIDATE",
                         "detail": "arXiv/DOAJ/repository routes returned no new lawful candidate"})
        continue

    got = False
    for route, url in candidates:
        code, blob, ctype = fetch(url)
        if code != 200 or not blob:
            log_rows.append({"record_id": rid, "route": route, "url": url,
                             "outcome": f"HTTP_{code}", "detail": ctype})
            continue
        ok, chars = save_pdf(rid, blob)
        if ok:
            log_rows.append({"record_id": rid, "route": route, "url": url,
                             "outcome": "OK_PDF", "detail": f"{chars} chars extracted"})
            retrieved.append((rid, route, url, chars))
            print(f"  RETRIEVED {rid} via {route}: {chars} chars", flush=True)
            got = True
            break
        log_rows.append({"record_id": rid, "route": route, "url": url,
                         "outcome": "NOT_PDF" if not blob.startswith(b"%PDF") else "PDF_NO_TEXT",
                         "detail": f"{ctype}; extracted {chars} chars"})
    if not got:
        pass

log_path = AUDIT / "fulltext_retrieval_log.csv"
existing = read_csv(log_path)
with log_path.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["record_id", "route", "url", "outcome", "detail"])
    w.writeheader()
    w.writerows(existing)
    w.writerows(log_rows)

print("\nPass 3 newly retrieved:", len(retrieved))
for rid, route, url, chars in retrieved:
    print(" ", rid, route, chars, url[:90])
