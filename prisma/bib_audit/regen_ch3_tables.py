#!/usr/bin/env python3
"""Sinh lại các số đếm và danh mục \cite của Chương 3 trực tiếp từ dữ liệu mã hóa.

Nguồn dữ liệu (không nhập tay):
  - bib_audit/lvtn_68_coding_per_paper.csv : nhãn mã hóa 63 nghiên cứu sơ cấp (S22 là nguồn bối cảnh)
  - bib_audit/lvtn_68_clean_corpus_FINAL.csv : năm công bố + tiêu đề (n=64)
  - references.bib : ánh xạ tiêu đề -> cite key

Chạy:  uv run python bib_audit/regen_ch3_tables.py
Xuất:  bib_audit/ch3_table_regen.json  (số đếm + danh sách cite key theo nhóm)
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "references.bib"
CODING = ROOT / "bib_audit" / "lvtn_68_coding_per_paper.csv"
CORPUS = ROOT / "bib_audit" / "lvtn_68_clean_corpus_FINAL.csv"
OUT = ROOT / "bib_audit" / "ch3_table_regen.json"


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
        depth = 0
        end = k
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


def main() -> None:
    bibmap = {}
    for key, body in bib_entries(BIB.read_text(encoding="utf-8")):
        t = norm(field(body, "title"))
        if t:
            bibmap.setdefault(t, key)

    corpus = list(csv.DictReader(CORPUS.open(encoding="utf-8-sig")))
    coding = list(csv.DictReader(CODING.open(encoding="utf-8-sig")))
    coding = [r for r in coding if r["id"] != "S22"]
    corpus = [r for r in corpus if r["id"] != "S22"]
    assert len(corpus) == len(coding) == 63, (len(corpus), len(coding))

    id2key, id2year = {}, {}
    for r in corpus:
        t = norm(r["title"])
        key = bibmap.get(t)
        if not key:
            cand = [bk for bt, bk in bibmap.items() if bt[:50] == t[:50]]
            key = cand[0] if len(cand) == 1 else None
        if not key:
            raise SystemExit(f"Không ánh xạ được cite key cho {r['id']}: {r['title'][:60]}")
        id2key[r["id"]] = key
        id2year[r["id"]] = int(r["year"])

    def tally(field_name):
        d = {}
        for r in coding:
            d.setdefault(r[field_name], []).append(r["id"])
        return d

    proto, ctrl, app = tally("protocol_class"), tally("control_strategy"), tally("application_class")
    years = {"pre2015": [], "2015_2023": [], "2024_2025": []}
    for sid, y in id2year.items():
        bucket = "pre2015" if y < 2015 else ("2024_2025" if y >= 2024 else "2015_2023")
        years[bucket].append(sid)

    def keys(ids):
        return [id2key[i] for i in sorted(ids)]

    groups = {
        "mpc": keys(ctrl.get("MPC", [])),
        "etc_stc": keys(ctrl.get("ETC_event_triggered", [])),
        "hybrid": keys(ctrl.get("hybrid", [])),
        "fuzzy_ml_review": keys(
            ctrl.get("Fuzzy_PID", []) + ctrl.get("ML_RL", []) + ctrl.get("none_review", [])
        ),
        "unspecified_strategy": keys(ctrl.get("unspecified", [])),
        "recent_2024_2025": keys(years["2024_2025"]),
        "lorawan_lpwan": keys(proto.get("LoRaWAN_LPWAN", [])),
    }

    result = {
        "n": len(coding),
        "counts": {
            "protocol": {k: len(v) for k, v in sorted(proto.items(), key=lambda x: -len(x[1]))},
            "control_strategy": {k: len(v) for k, v in sorted(ctrl.items(), key=lambda x: -len(x[1]))},
            "application": {k: len(v) for k, v in sorted(app.items(), key=lambda x: -len(x[1]))},
            "year": {k: len(v) for k, v in years.items()},
            "year_reference_group": len(years["pre2015"]) + len(years["2015_2023"]),
        },
        "pre2015_detail": sorted((id2year[i], i, id2key[i]) for i in years["pre2015"]),
        "groups": groups,
        "id2key": id2key,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    def pct(n):
        return f"{100.0 * n / len(coding):.1f}"

    print(f"n = {result['n']}")
    for cat in ("year", "protocol", "control_strategy", "application"):
        print(f"\n## {cat}")
        for k, v in result["counts"][cat].items():
            print(f"  {v:3d} ({pct(v):>4}%)  {k}")
    print(f"\nnhóm tham chiếu (trước 2015 + 2015-2023) = {result['counts']['year_reference_group']}"
          f" ({pct(result['counts']['year_reference_group'])}%)")
    print("\ncông trình trước 2015:", result["pre2015_detail"])
    print("\n--- danh mục cite theo nhóm ---")
    for g, ks in groups.items():
        print(f"\n[{g}] n={len(ks)}\n\\cite{{{', '.join(ks)}}}")
    print(f"\nĐã ghi {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
