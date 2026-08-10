#!/usr/bin/env python3
"""Re-fetch full text for reviewed records whose local cache copy is missing.

Seventeen records were reviewed by subagents that downloaded the article inside
their own session, so no local text remained for PNCE re-coding. This script
re-retrieves them from the lawful URL already recorded in
fulltext_availability_inventory.csv, preferring PDF and falling back to the
Europe PMC / PMC full-text route for PMC-hosted articles.

Only successful retrievals are written to bib_audit/fulltext_cache/.
"""
from __future__ import annotations

import csv
import html
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
CACHE = AUDIT / "fulltext_cache"
CACHE.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

TARGETS = [
    "S02", "S07", "S08", "S10", "S16", "S36", "S38", "S44",
    "S45", "S46", "S52", "S57", "S59", "S60", "S61", "S66", "S67",
]


def get(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/pdf,text/html,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except Exception as exc:  # noqa: BLE001 - retrieval outcome is data here
        return -1, f"error:{type(exc).__name__}", b""


def pdf_to_text(raw: bytes, rid: str) -> str | None:
    pdf_path = CACHE / f"{rid}.pdf"
    pdf_path.write_bytes(raw)
    try:
        out = subprocess.run(
            ["pdftotext", "-q", str(pdf_path), "-"],
            capture_output=True, timeout=180,
        )
    except Exception:
        return None
    text = out.stdout.decode("utf-8", "replace")
    return text if len(text.strip()) > 3000 else None


def html_to_text(raw: bytes) -> str | None:
    doc = raw.decode("utf-8", "replace")
    doc = re.sub(r"(?is)<(script|style|nav|header|footer)\b.*?</\1>", " ", doc)
    doc = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</h\d>", "\n", doc)
    doc = re.sub(r"(?s)<[^>]+>", " ", doc)
    doc = html.unescape(doc)
    doc = re.sub(r"[ \t\xa0]+", " ", doc)
    doc = re.sub(r"\n\s*\n\s*\n+", "\n\n", doc)
    return doc if len(doc.strip()) > 3000 else None


def pmcid_of(url: str) -> str | None:
    m = re.search(r"(PMC\d+)", url)
    return m.group(1) if m else None


def routes_for(rid: str, url: str):
    """Yield (label, url) candidates, best first."""
    pmcid = pmcid_of(url)
    if pmcid:
        yield "europepmc_xml", f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        yield "europepmc_html", f"https://europepmc.org/article/PMC/{pmcid}"
        yield "pmc_html", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        return
    yield "recorded_url", url
    if "mdpi.com" in url:
        m = re.search(r"mdpi\.com/(\d{4}-\d{3}[\dxX])/(\d+)/(\d+)/(\d+)", url)
        if m:
            issn, vol, iss, art = m.groups()
            yield "mdpi_static", (
                f"https://mdpi-res.com/d_attachment/{issn}/{issn}-{vol}-{iss}-{art}"
                f"/article_deploy/{issn}-{vol}-{iss}-{art}.pdf"
            )
    if url.startswith("https://doi.org/10.3390/"):
        yield "mdpi_landing", url


def main() -> int:
    inv = {
        r["record_id"]: r
        for r in csv.DictReader(open(AUDIT / "fulltext_availability_inventory.csv", encoding="utf-8-sig"))
    }
    log_rows = []
    got = []

    for rid in TARGETS:
        txt_path = CACHE / f"{rid}.txt"
        if txt_path.exists() and len(txt_path.read_text(encoding="utf-8", errors="replace").strip()) > 3000:
            print(f"{rid}: already cached")
            continue

        url = (inv[rid].get("pdf_url") or "").strip()
        if not url:
            log_rows.append((rid, "none", "", "NO_URL", ""))
            print(f"{rid}: no recorded URL")
            continue

        success = False
        for label, cand in routes_for(rid, url):
            status, ctype, raw = get(cand)
            outcome = f"HTTP_{status}"
            text = None
            if status == 200 and raw:
                head = raw[:5]
                if head.startswith(b"%PDF") or "pdf" in ctype.lower():
                    text = pdf_to_text(raw, rid)
                    outcome = "OK_PDF" if text else "PDF_TOO_SHORT"
                else:
                    text = html_to_text(raw)
                    outcome = "OK_TEXT" if text else "NOT_FULLTEXT"
            log_rows.append((rid, label, cand, outcome, ctype[:60]))
            if text:
                txt_path.write_text(text, encoding="utf-8")
                got.append((rid, label, len(text)))
                print(f"  RETRIEVED {rid} via {label}: {len(text)} chars")
                success = True
                break
        if not success:
            print(f"{rid}: not retrieved")

    log_path = AUDIT / "fulltext_refetch_log.csv"
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "route", "url", "outcome", "content_type"])
        w.writerows(log_rows)

    print(f"\nRe-fetched {len(got)} of {len(TARGETS)} targets")
    for rid, label, n in got:
        print(f"  {rid} {label} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
