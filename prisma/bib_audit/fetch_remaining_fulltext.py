#!/usr/bin/env python3
"""Exhaustive lawful open-access retrieval for records still at E1.

Routes tried per record, in order:
  1. OpenAlex `locations[]` (every OA location, not just best_oa_location)
  2. Unpaywall `oa_locations[]`
  3. Europe PMC full text (PDF / supplementaryFiles / fullTextXML)
  4. NCBI ID converter -> PMC OA PDF
  5. Semantic Scholar `openAccessPdf`
  6. DOAJ article fulltext links
  7. OpenAIRE / CORE discovery
  8. Publisher static mirrors (mdpi-res.com, DergiPark, HAL, DiVA, arXiv)

Nothing behind a paywall is bypassed. Every attempt and its HTTP outcome is
logged to bib_audit/fulltext_retrieval_log.csv so the audit stays traceable.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "bib_audit"
CACHE = AUDIT / "fulltext_cache"
CACHE.mkdir(exist_ok=True)
UA = "LVTN-evidence-audit/2.0 (mailto:mxuanvan02@example.edu)"
EMAIL = "mxuanvan02@example.edu"


def get(url: str, timeout: int = 45, accept: str | None = None) -> tuple[int, bytes, str]:
    """Return (status, body, final_url). Never raises on HTTP error."""
    headers = {
        "User-Agent": UA,
        "Accept": accept or "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:  # noqa: PERF203
        return e.code, b"", url
    except Exception as e:
        return -1, str(e).encode(), url


def get_json(url: str, timeout: int = 40):
    st, body, _ = get(url, timeout=timeout, accept="application/json")
    if st == 200 and body:
        try:
            return json.loads(body)
        except Exception:
            return None
    return None


def is_pdf(body: bytes) -> bool:
    return body[:5] == b"%PDF-"


def pdf_pages(path: Path) -> int:
    try:
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=60)
        m = re.search(r"Pages:\s+(\d+)", out.stdout)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def extract_text(pdf: Path, txt: Path) -> int:
    try:
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], capture_output=True, timeout=180)
        return len(txt.read_text(encoding="utf-8", errors="ignore")) if txt.exists() else 0
    except Exception:
        return 0


def save_pdf(rid: str, body: bytes, url: str, log: list, route: str) -> dict | None:
    pdf = CACHE / f"{rid}.pdf"
    pdf.write_bytes(body)
    pages = pdf_pages(pdf)
    txt = CACHE / f"{rid}.txt"
    chars = extract_text(pdf, txt)
    if pages >= 3 and chars >= 4000:
        log.append((rid, route, url, "OK_PDF", f"{pages}p/{chars}chars"))
        return {"kind": "pdf", "url": url, "route": route, "pages": pages, "chars": chars}
    log.append((rid, route, url, "PDF_TOO_THIN", f"{pages}p/{chars}chars"))
    pdf.unlink(missing_ok=True)
    txt.unlink(missing_ok=True)
    return None


def save_text(rid: str, text: str, url: str, log: list, route: str) -> dict | None:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    if len(text) < 8000:
        log.append((rid, route, url, "TEXT_TOO_THIN", str(len(text))))
        return None
    (CACHE / f"{rid}.txt").write_text(text, encoding="utf-8")
    log.append((rid, route, url, "OK_TEXT", f"{len(text)}chars"))
    return {"kind": "text", "url": url, "route": route, "pages": 0, "chars": len(text)}


def try_url(rid: str, url: str, log: list, route: str) -> dict | None:
    if not url:
        return None
    st, body, final = get(url)
    if st != 200 or not body:
        log.append((rid, route, url, f"HTTP_{st}", ""))
        return None
    if is_pdf(body):
        return save_pdf(rid, body, final, log, route)
    log.append((rid, route, url, "NOT_PDF", f"{len(body)}bytes"))
    return None


def openalex_locations(doi: str) -> tuple[list[str], str]:
    if not doi:
        return [], ""
    data = get_json("https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe=""))
    if not data:
        return [], ""
    urls = []
    for loc in (data.get("locations") or []):
        for key in ("pdf_url", "landing_page_url"):
            u = loc.get(key)
            if u and u not in urls:
                urls.append(u)
    return urls, (data.get("ids", {}) or {}).get("pmid", "") or ""


def unpaywall_locations(doi: str) -> list[str]:
    if not doi:
        return []
    data = get_json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='')}?email={EMAIL}")
    if not data:
        return []
    urls = []
    for loc in (data.get("oa_locations") or []):
        for key in ("url_for_pdf", "url_for_landing_page", "url"):
            u = loc.get(key)
            if u and u not in urls:
                urls.append(u)
    return urls


def europepmc(rid: str, doi: str, log: list) -> dict | None:
    if not doi:
        return None
    q = get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22"
                 + urllib.parse.quote(doi) + "%22&resultType=core&format=json")
    hits = ((q or {}).get("resultList") or {}).get("result") or []
    if not hits:
        return None
    h = hits[0]
    pmcid = h.get("pmcid") or ""
    for u in [x.get("url") for tl in (h.get("fullTextUrlList") or {}).get("fullTextUrl", [])
              for x in [tl] if tl.get("documentStyle") in ("pdf", "html")]:
        r = try_url(rid, u, log, "europepmc_fulltexturl")
        if r:
            return r
    if pmcid:
        for u in (f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
                  f"https://europepmc.org/api/fulltextRepo?pprId={pmcid}&type=FILE&fileName=EMS.pdf"):
            st, body, final = get(u)
            if st == 200 and body:
                if is_pdf(body):
                    r = save_pdf(rid, body, final, log, "europepmc_pdf")
                    if r:
                        return r
                else:
                    r = save_text(rid, body.decode("utf-8", "ignore"), final, log, "europepmc_xml")
                    if r:
                        return r
            else:
                log.append((rid, "europepmc_xml", u, f"HTTP_{st}", ""))
    return None


def pmc_route(rid: str, doi: str, log: list) -> dict | None:
    if not doi:
        return None
    conv = get_json("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?format=json&ids="
                    + urllib.parse.quote(doi))
    recs = (conv or {}).get("records") or []
    pmcid = next((r.get("pmcid") for r in recs if r.get("pmcid")), None)
    if not pmcid:
        return None
    for u in (f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
              f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"):
        st, body, final = get(u)
        if st == 200 and body:
            if is_pdf(body):
                r = save_pdf(rid, body, final, log, "pmc_pdf")
                if r:
                    return r
            else:
                r = save_text(rid, body.decode("utf-8", "ignore"), final, log, "pmc_html")
                if r:
                    return r
        else:
            log.append((rid, "pmc", u, f"HTTP_{st}", ""))
    return None


def semantic_scholar(rid: str, doi: str, log: list) -> dict | None:
    if not doi:
        return None
    data = get_json("https://api.semanticscholar.org/graph/v1/paper/DOI:"
                    + urllib.parse.quote(doi) + "?fields=openAccessPdf,externalIds")
    url = ((data or {}).get("openAccessPdf") or {}).get("url")
    if url:
        return try_url(rid, url, log, "semantic_scholar")
    arxiv = ((data or {}).get("externalIds") or {}).get("ArXiv")
    if arxiv:
        return try_url(rid, f"https://arxiv.org/pdf/{arxiv}", log, "arxiv")
    return None


def doaj_route(rid: str, doi: str, log: list) -> dict | None:
    if not doi:
        return None
    data = get_json("https://doaj.org/api/search/articles/doi:" + urllib.parse.quote(doi))
    for res in ((data or {}).get("results") or []):
        for link in ((res.get("bibjson") or {}).get("link") or []):
            if link.get("url"):
                r = try_url(rid, link["url"], log, "doaj")
                if r:
                    return r
    return None


def openaire_route(rid: str, doi: str, log: list) -> dict | None:
    if not doi:
        return None
    st, body, _ = get("https://api.openaire.eu/search/publications?doi="
                      + urllib.parse.quote(doi) + "&format=json", accept="application/json")
    if st != 200 or not body:
        return None
    for u in sorted(set(re.findall(r'https?://[^"\s<>]+?\.pdf', body.decode("utf-8", "ignore")))):
        r = try_url(rid, u, log, "openaire")
        if r:
            return r
    return None


def publisher_mirrors(rid: str, doi: str, log: list) -> dict | None:
    doi = (doi or "").lower()
    cands: list[str] = []
    if doi.startswith("10.3390/"):
        tail = doi.split("/", 1)[1]
        m = re.match(r"([a-z]+)(\d+)", tail)
        if m:
            journal, num = m.group(1), m.group(2)
            cands += [f"https://mdpi-res.com/d_attachment/{journal}/{journal}-{num}/article_deploy/{journal}-{num}.pdf",
                      f"https://www.mdpi.com/{tail}/pdf?version=1"]
    if doi.startswith("10.1007/"):
        cands.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    if doi.startswith("10.21923/"):
        cands.append("https://dergipark.org.tr/tr/download/article-file/587896")
    for u in cands:
        r = try_url(rid, u, log, "publisher_mirror")
        if r:
            return r
    return None


def main() -> None:
    rob = list(csv.DictReader((AUDIT / "rob_grade_audit_log.csv").open(encoding="utf-8-sig")))
    pending = [r for r in rob if r["evidence_tier"].startswith("E1")]
    log: list[tuple] = []
    results: dict[str, dict] = {}
    for i, row in enumerate(pending, 1):
        rid, doi = row["record_id"], (row["doi"] or "").strip()
        if (CACHE / f"{rid}.txt").exists():
            log.append((rid, "cache", "", "ALREADY_CACHED", ""))
            continue
        oa_urls, _ = openalex_locations(doi)
        got = None
        for u in oa_urls:
            got = try_url(rid, u, log, "openalex_location")
            if got:
                break
        for fn in (europepmc, pmc_route, semantic_scholar, doaj_route, openaire_route, publisher_mirrors):
            if got:
                break
            got = fn(rid, doi, log)
        if not got:
            for u in unpaywall_locations(doi):
                got = try_url(rid, u, log, "unpaywall_location")
                if got:
                    break
        if got:
            results[rid] = got
        print(f"[{i}/{len(pending)}] {rid}: {'RETRIEVED ' + got['route'] if got else 'no lawful full text'}", flush=True)
        time.sleep(0.2)

    with (AUDIT / "fulltext_retrieval_log.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "route", "url", "outcome", "detail"])
        w.writerows(log)
    (AUDIT / "fulltext_retrieval_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nNewly retrieved:", len(results), "of", len(pending), "pending")
    for rid, meta in sorted(results.items()):
        print(" ", rid, meta["route"], meta["kind"], meta["pages"], meta["chars"])


if __name__ == "__main__":
    main()
