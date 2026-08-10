#!/usr/bin/env python3
"""Doi nhan 53 ban ghi "cho xac minh" trong bang 627 ban ghi cua phu luc audit.

Ly do: 53 ban ghi nay co final_decision=include trong
prisma_fulltext_final_decisions.csv (dat PNCE o muc tom tat/sieu du lieu) nhung
truoc day bi ghi la "Loai" trong Chapter/phuluc_audit.tex. Nhan dung phai la
"Cho" (buoc 4b: chua dat nguong bang chung toan van de ma hoa PNCE).

Chay:  uv run python relabel_onhold_appendix.py [--apply]
Khong co --apply thi chi bao cao, khong ghi file.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANUSCRIPT = HERE.parent
DECISIONS = HERE / "prisma_fulltext_final_decisions.csv"
CORPUS = HERE / "lvtn_68_clean_corpus_FINAL.csv"
APPENDIX = MANUSCRIPT / "Chapter" / "phuluc_audit.tex"

NEW_LABEL = r"\revcell{Chờ}"
NEW_STEP = r"\revcell{Xác minh bằng chứng (bước 4b)}"
NEW_REASON = r"\revcell{Đạt PNCE mức tóm tắt, chưa đủ toàn văn để mã hóa}"


def clean_title(raw: str) -> str:
    """Bo escape HTML long nhieu lop va the <i>/<sub> con sot trong metadata."""
    prev = raw or ""
    for _ in range(4):
        cur = html.unescape(prev)
        if cur == prev:
            break
        prev = cur
    return re.sub(r"<[^>]+>", " ", prev)


def norm(raw: str) -> str:
    """Chuan hoa tieu de: chu thuong, bo dau cau, rut gon khoang trang."""
    text = clean_title(raw).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def prefix_match(a: str, b: str, floor: int = 40) -> bool:
    """Khop khi mot tieu de la tien to cua tieu de kia (metadata bi cat cut)."""
    if not a or not b:
        return False
    n = min(len(a), len(b))
    return n >= floor and a[:n] == b[:n]


def load_on_hold() -> list[dict]:
    """56 ung vien include, tru 3 ban ghi da co trong tap loi -> 53 ban ghi cho."""
    with DECISIONS.open(encoding="utf-8-sig") as fh:
        includes = [r for r in csv.DictReader(fh) if r["final_decision"].strip() == "include"]
    with CORPUS.open(encoding="utf-8-sig") as fh:
        core = [(r["id"], norm(r["title"])) for r in csv.DictReader(fh)]

    on_hold, promoted = [], []
    for row in includes:
        cand = norm(row["title"])
        hit = next(
            (sid for sid, ctitle in core if cand == ctitle or prefix_match(cand, ctitle)),
            None,
        )
        (promoted if hit else on_hold).append(row)
    if len(includes) != 56 or len(promoted) != 3 or len(on_hold) != 53:
        sys.exit(f"Số liệu lệch: include={len(includes)} lõi={len(promoted)} chờ={len(on_hold)}")
    return on_hold


ROW_RE = re.compile(
    r"^(?P<stt>\d+)\s*&(?P<year>[^&]*)&(?P<title>.*?)&(?P<label>[^&]*)&(?P<step>[^&]*)&(?P<reason>[^&]*)\\\\\s*$"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ghi thay doi vao file .tex")
    args = ap.parse_args()

    on_hold = load_on_hold()
    lines = APPENDIX.read_text(encoding="utf-8").splitlines(keepends=True)

    # Chi so hoa cac dong bang 627 ban ghi theo tieu de chuan hoa.
    rows: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        m = ROW_RE.match(line.strip())
        if m:
            rows.append((idx, norm(m.group("title"))))

    targets: dict[int, str] = {}
    unmatched: list[str] = []
    for row in on_hold:
        cand = norm(row["title"])
        hit = next(
            (
                idx
                for idx, rtitle in rows
                if idx not in targets and (cand == rtitle or prefix_match(cand, rtitle))
            ),
            None,
        )
        if hit is None:
            unmatched.append(row["candidate_id"])
        else:
            targets[hit] = row["candidate_id"]

    if unmatched:
        sys.exit(f"Không tìm được dòng phụ lục cho: {', '.join(unmatched)}")

    changed = 0
    for idx, cand_id in sorted(targets.items()):
        m = ROW_RE.match(lines[idx].strip())
        assert m is not None
        if m.group("label").strip() != "Loại":
            continue
        lines[idx] = (
            f"{m.group('stt')} &{m.group('year')}&{m.group('title')}"
            f"& {NEW_LABEL} & {NEW_STEP} & {NEW_REASON} \\\\\n"
        )
        changed += 1

    print(f"Bản ghi chờ: {len(on_hold)} | dòng phụ lục khớp: {len(targets)} | đổi nhãn: {changed}")
    if args.apply:
        APPENDIX.write_text("".join(lines), encoding="utf-8")
        print(f"Đã ghi {APPENDIX.relative_to(MANUSCRIPT)}")
    else:
        print("Chạy lại với --apply để ghi thay đổi.")


if __name__ == "__main__":
    main()
