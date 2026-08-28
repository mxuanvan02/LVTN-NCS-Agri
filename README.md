# LVTN-NCS-Agri — Code and reproducibility companion repository

Kho lưu trữ này chứa **mã nguồn, dữ liệu tổng hợp/kiểm toán và đầu ra phục vụ tái lập** cho luận văn về *hệ thống điều khiển qua mạng (Networked Control Systems — NCS) trong nông nghiệp thông minh*.

> **Phạm vi của repository:** code và reproducibility. Repository này **không phải bản nguồn LaTeX của luận văn**, không chứa PDF toàn văn của luận văn, và không chứa bản sao toàn văn các tài liệu tham khảo. Bộ nguồn LaTeX tối thiểu được phát hành riêng dưới dạng gói ZIP.

## Nội dung và giới hạn sử dụng

Repository gồm hai nhánh liên quan:

1. **PRISMA/evidence audit:** pipeline xây dựng, đối chiếu và phân tầng corpus; bảng mã hóa PNCE; nhật ký truy xuất; đánh giá RoB/GRADE và các thống kê dùng trong luận văn.
2. **Network-control simulation:** mô hình plant–network–control và các benchmark phần mềm, gồm benchmark v2 cho nhà kính và tưới.

Các kết quả mô phỏng là kết quả trong **mô hình chuẩn hóa với tham số và trace đã khai báo**. Năng lượng là năng lượng mô hình hóa, không phải số đo phần cứng. Trace LoRa được tạo theo heuristic có điều kiện thời tiết, không phải log đo mạng thực địa. Vì vậy, repository **không chứng minh hiệu quả triển khai, an toàn sinh học, hay hiệu năng phần cứng ngoài hiện trường**.

## Trạng thái bằng chứng của luận văn

Luồng audit tại thời điểm chốt luận văn:

```text
627 bản ghi thô
  → 424 nguồn duy nhất
  → 187 sau sàng lọc
  → 123 ứng viên bổ sung được thẩm định
  → 64 nguồn trong tập tham chiếu
  → 34 nguồn được truy xuất và đọc toàn văn
  → 33 nguồn Tier 1 được mã hóa làm bằng chứng sơ cấp
```

- **Tier 1 (n = 33):** toàn văn đã được truy xuất hợp pháp, đọc và mã hóa PNCE kèm locator; dùng cho thống kê nội dung, RoB và GRADE.
- **Tier 2 (n = 31):** nguồn bối cảnh hoặc chưa có toàn văn được truy xuất trong quy trình; không dùng làm mẫu số cho thống kê bằng chứng lõi.
- Trong Tier 1, RoB tổng thể gồm 21 nguồn mức cao và 12 nguồn có một số quan ngại; mức chắc chắn của các luận điểm chính được đánh giá là rất thấp, tạm thời.

Các con số trên mô tả trạng thái audit của luận văn; chúng không phải kết quả của một phép đo thực địa.

## Cấu trúc repository

```text
prisma/
  tools/                 # Công cụ dựng lại audit PRISMA
  bib_audit/             # Corpus, PNCE, truy xuất, RoB/GRADE và script audit
    test_*.py            # Kiểm thử hồi quy cho quy tắc phân tầng bằng chứng
simulation/
  src/                   # Plant, controller, trigger, network và energy models
  experiments/           # Benchmark, ablation và các script đánh giá
  data/                  # Weather data và trace tổng hợp
  results/               # CSV, manifest, provenance và summary đã sinh
  tests/                 # Kiểm thử mô hình và artifact
README.md               # Phạm vi, giới hạn và hướng dẫn tái lập
```

## Môi trường và cài đặt

Yêu cầu tối thiểu: Python 3.9+.

```bash
cd simulation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Để tái lập chặt hơn, có thể dùng `requirements-lock.txt` trong cùng thư mục.

## Chạy kiểm thử và benchmark v2

Từ thư mục `simulation/`:

```bash
python -m pytest -q
python experiments/run_v2_primary.py --dry-run
python experiments/run_v2_primary.py --seeds 50
python experiments/run_v2_hil_loopback.py
python experiments/summarize_v2.py
python experiments/plot_v2.py
```

Benchmark v2 gồm hai plant (greenhouse và irrigation), bốn chính sách (TT-MPC, ET-MPC, TT-PI và ET-PI), sáu cấu hình mạng (`N0_ideal`–`N5_full_stress`) và 50 seed. Các schema JSONL/UDP trong loopback chỉ là **software-in-the-loop/HIL-ready interface**; không được hiểu là HIL vật lý.

Để chạy workflow legacy đầy đủ:

```bash
./run_all.sh
```

Workflow legacy tự chuẩn bị dữ liệu thời tiết, tạo trace tổng hợp, chạy kiểm thử và sinh các kết quả trong `simulation/results/`. Không nên gọi trace này là trace LoRa đo thực địa nếu chưa bổ sung log đo thật.

## Tái lập audit PRISMA

Từ thư mục gốc repository:

```bash
python3 prisma/bib_audit/build_two_tier_corpus.py
python3 prisma/bib_audit/enforce_two_tier_consistency.py
python3 prisma/bib_audit/build_two_tier_corpus.py
python3 prisma/bib_audit/regen_ch3_tier1.py
```

Bước `enforce_two_tier_consistency.py` áp quy tắc hai tầng lên nhật ký audit: nó
giới hạn `included_record_ids` của mỗi nhận định GRADE trong Tier 1, chuyển các
bản ghi Tier 2 sang cột `tier2_context_record_ids`, gỡ phán đoán RoB phân tích
khỏi bản ghi Tier 2 và ghi ô PRISMA tương ứng vào cột `prisma_disposition`.
Script được thiết kế idempotent: chạy lại nhiều lần cho cùng một kết quả, nên
trình tự trên có thể lặp mà không làm mất dấu vết nguồn bối cảnh.

Để kiểm tra tính chất đó trước khi tin vào số liệu:

```bash
python3 -m unittest discover -s prisma/bib_audit -p 'test_*.py' -v
```

Bộ kiểm thử xác nhận năm điều kiện: chạy lặp không làm đổi nhật ký; ID Tier 2
không bị xóa ở lần chạy thứ hai; `included_record_ids` chỉ chứa bản ghi Tier 1;
phần mở đầu của `certainty_rationale` không bị nối thêm bản sao; và không bản ghi
nào xuất hiện đồng thời ở hai cột. Bộ kiểm thử cũng đối chiếu lý do hạ tầng theo
`tier_reason`, nhằm tránh gán nhãn *secondary review* cho bản ghi thực chất chỉ
thiếu toàn văn.

Sau khi chạy lại pipeline, `prisma/bib_audit/two_tier_corpus.csv` có thể hiện ra
ở `git status` như đã thay đổi. Nguyên nhân là ký tự kết thúc dòng: trình ghi CSV
của Python sinh CRLF, trong khi một phần tệp trong repository được lưu ở dạng LF.
Nội dung các ô không đổi. Khi cần khẳng định kết quả tái lập, nên đối chiếu
checksum của `rob_grade_audit_log.csv` và `grade_claim_audit.csv`, hoặc so sánh
theo từng ô sau khi chuẩn hóa ký tự kết thúc dòng, thay vì so sánh byte trực tiếp.

Tài liệu chi tiết:

- [`prisma/bib_audit/README.md`](prisma/bib_audit/README.md): trạng thái corpus và thứ tự pipeline.
- [`prisma/bib_audit/README_AUDIT.md`](prisma/bib_audit/README_AUDIT.md): kiểm tra từng bước PRISMA.
- [`prisma/bib_audit/pnce_recode/SCHEMA.md`](prisma/bib_audit/pnce_recode/SCHEMA.md): 12 biến PNCE và quy tắc locator.
- [`simulation/README.md`](simulation/README.md): mô tả kỹ thuật các mô hình và benchmark.

## Dữ liệu, provenance và giấy phép sử dụng

Repository chỉ phát hành metadata, bảng mã hóa có locator/trích đoạn ngắn cần cho audit, nhật ký provenance, mã nguồn và kết quả tổng hợp. PDF/toàn văn nguồn, văn bản trích xuất toàn bài và cache cục bộ không được phát hành; người dùng phải tự truy xuất qua DOI, kho open-access hoặc thư viện hợp pháp.

Các tệp `SOURCE_PROVENANCE.txt`, manifest và checksum trong `simulation/` mô tả nguồn dữ liệu, cấu hình và artifact tương ứng. Khi tái lập, cần ghi lại phiên bản Python, dependency, cấu hình và seed.

Mã nguồn được phát hành theo [MIT License](LICENSE). Quyền đối với các công trình được trích dẫn thuộc về tác giả/nhà xuất bản tương ứng.

## Trích dẫn

Nếu sử dụng code, dữ liệu tổng hợp hoặc quy trình audit, vui lòng trích dẫn luận văn tương ứng và ghi rõ commit/release của repository đã sử dụng. Repository này là companion code/reproducibility archive, không thay thế cho bản luận văn chính thức.
