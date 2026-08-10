#!/usr/bin/env python3
"""Generate the per-source tier listing table for the audit appendix.

Without this table a reader cannot check which of the 64 reference sources
entered the Tier-1 core evidence set and which stayed in the Tier-2 context
layer. The table is generated from two_tier_corpus.csv so it cannot drift
away from the data.

Output: Chapter/generated/tier_listing_table.tex, input-ed by phuluc_audit.tex.
"""
from __future__ import annotations

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "bib_audit" / "two_tier_corpus.csv"
OUT = ROOT / "Chapter" / "generated" / "tier_listing_table.tex"

TIER = {"tier1_core": "Lõi", "tier2_context": "Bối cảnh"}
REASON = {
    "fulltext_read_and_coded": "đã đọc toàn văn và mã hóa",
    "fulltext_not_retrieved": "không truy xuất được toàn văn",
    "methodological_context_source": "khảo sát nền tảng (bối cảnh)",
    "retrieved_but_secondary_review": "toàn văn đã đọc nhưng là tổng quan thứ cấp",
}
# Short form for the in-table reason column.
REASON_SHORT = {
    "fulltext_read_and_coded": "đã đọc và mã hóa",
    "fulltext_not_retrieved": "không truy xuất được",
    "methodological_context_source": "nguồn bối cảnh",
    "retrieved_but_secondary_review": "tổng quan thứ cấp",
}
ROLE = {
    "analytical_primary": "phân tích",
    "technical_support_primary": "hỗ trợ kỹ thuật",
    "context_secondary": "bối cảnh",
}
ROB = {
    "high": "High",
    "some_concerns": "Some concerns",
    "not_assessable": "Not assessable",
}
APP = {
    "irrigation_outdoor": "Tưới ngoài trời",
    "greenhouse_microclimate": "Vi khí hậu nhà kính",
    "hydroponic_cea": "Thủy canh/CEA",
    "ncs_generic_nonagricultural": "NCS tổng quát",
    "not_stated": "Không nêu rõ",
    "": "--",
}


def esc(s: str) -> str:
    # Some upstream titles arrive with HTML entities still encoded.
    s = html.unescape(s)
    for a, b in (("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#")):
        s = s.replace(a, b)
    return s


def short(title: str, n: int = 40) -> str:
    title = " ".join(html.unescape(title).split())
    # Use "..." rather than U+2026: the thesis font lacks a reliable glyph.
    return esc(title) if len(title) <= n else esc(title[: n - 3].rstrip()) + r"\ldots"


def main() -> None:
    rows = list(csv.DictReader(SRC.open(encoding="utf-8-sig")))
    rows.sort(key=lambda r: int(r["id"][1:]))
    OUT.parent.mkdir(parents=True, exist_ok=True)

    out = []
    out.append(r"% Sinh tự động bởi bib_audit/gen_tier_table_tex.py -- không sửa tay.")
    out.append(r"\footnotesize")
    # longtable captions default to 4in, which overflows the text block.
    out.append(r"\setlength{\LTcapwidth}{\textwidth}")
    # Column widths sum to ~14.2cm, leaving room for the six inter-column gaps
    # inside a 15.5cm text block. Ragged-right avoids overfull lines from long
    # unbreakable tokens in the title column.
    out.append(
        r"\begin{longtable}{@{}p{0.8cm} p{0.75cm} "
        r">{\raggedright\arraybackslash}p{3.8cm} "
        r">{\raggedright\arraybackslash}p{1.15cm} "
        r">{\raggedright\arraybackslash}p{2.5cm} "
        r">{\raggedright\arraybackslash}p{1.6cm} "
        r">{\raggedright\arraybackslash}p{1.9cm}@{}}"
    )
    out.append(
        r"\caption{Phân tầng bằng chứng của từng nguồn trong tập tham chiếu 64 nguồn. "
        r"Cột \textit{Tầng} quyết định nguồn có tham gia thống kê, RoB và GRADE hay không}"
        r"\label{tab:per_source_tier}\\"
    )
    head = (
        r"\toprule" "\n"
        r"\textbf{Mã} & \textbf{Năm} & \textbf{Tiêu đề (rút gọn)} & "
        r"\textbf{Tầng} & \textbf{Lý do} & \textbf{Vai trò} & \textbf{RoB} \\" "\n"
        r"\midrule"
    )
    out.append(head + r"\endfirsthead")
    out.append(
        r"\multicolumn{7}{@{}l}{\small\itshape Bảng~\ref{tab:per_source_tier} "
        r"(tiếp trang trước)}\\" "\n" + head + r"\endhead"
    )
    out.append(r"\midrule \multicolumn{7}{r@{}}{\small\itshape (tiếp trang sau)}\\ \endfoot")
    out.append(r"\bottomrule \endlastfoot")

    for r in rows:
        tier = TIER.get(r["tier"], r["tier"])
        cell_tier = tier if r["tier"] == "tier1_core" else r"\textit{" + tier + "}"
        out.append(
            " & ".join(
                [
                    esc(r["id"]),
                    esc(r["year"]),
                    short(r["title"]),
                    cell_tier,
                    REASON_SHORT.get(r["tier_reason"], r["tier_reason"]),
                    ROLE.get(r["record_role"], r["record_role"]),
                    ROB.get(r["rob_overall"], r["rob_overall"]),
                ]
            )
            + r" \\"
        )
    out.append(r"\end{longtable}")
    out.append(r"\normalsize")

    # Reason summary so the appendix explains why each Tier-2 record is there.
    from collections import Counter

    reasons = Counter(r["tier_reason"] for r in rows)
    out.append("")
    out.append(r"\noindent\textbf{Lý do phân tầng.} ")
    parts = []
    for k, v in reasons.most_common():
        parts.append(f"{v} nguồn {REASON.get(k, k)}")
    out.append("; ".join(parts) + ".")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    t1 = sum(1 for r in rows if r["tier"] == "tier1_core")
    print(f"wrote {OUT.relative_to(ROOT)}  rows={len(rows)}  tier1={t1}  tier2={len(rows)-t1}")
    print("reasons:", dict(reasons))


if __name__ == "__main__":
    main()
