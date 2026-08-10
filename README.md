# NCS-Agri: PRISMA Audit & Simulation Code

Mã nguồn và dữ liệu kiểm toán đi kèm luận văn về **Hệ thống điều khiển qua mạng (Networked Control Systems -- NCS) trong nông nghiệp thông minh**, kết hợp quy trình audit theo logic PRISMA 2020 với bộ kiểm thử mô phỏng có thể tái lập.

Repo chứa **code + dữ liệu kiểm toán/tổng hợp**; không chứa bản thảo LaTeX, PDF toàn văn của nguồn tham khảo hoặc cache trích xuất cục bộ.

## Trạng thái bằng chứng tại thời điểm chốt luận văn

Luồng kiểm toán hiện hành:

`627 bản ghi thô -> 424 nguồn duy nhất -> 187 sau sàng lọc -> 123 ứng viên mới được thẩm định -> tập tham chiếu 64 nguồn -> 34 toàn văn đã đọc -> 33 nguồn Tier 1`

Tập tham chiếu 64 nguồn được tách theo PRISMA 2020:

- **Tier 1 -- bằng chứng lõi (n = 33):** toàn văn đã được truy xuất hợp pháp, đọc và mã hóa PNCE kèm locator. Chỉ Tier 1 tham gia thống kê nội dung, RoB và GRADE.
- **Tier 2 -- nguồn bối cảnh (n = 31):** 29 nguồn chưa truy xuất được toàn văn, khảo sát nền tảng S22 và bài tổng quan thứ cấp S46. Tier 2 không tham gia các số đếm bằng chứng.

Trong 34 nguồn đã đọc toàn văn, S46 bị loại khỏi bằng chứng sơ cấp vì nhà xuất bản phân loại là bài `Review`. RoB của 33 nguồn Tier 1 gồm 21 `high` và 12 `some_concerns`; các luận điểm GRADE chính vẫn ở mức `very_low_provisional`.

## Cấu trúc

```text
prisma/
  tools/prisma_rebuild_audit.py   # Pipeline nhận diện, gộp lặp và sàng lọc
  bib_audit/                      # Corpus, PNCE, truy xuất, RoB/GRADE và script tái tạo
    pnce_recode/                  # Mã hóa toàn văn 12 biến kèm locator
    two_tier_corpus.csv           # Phân tầng từng nguồn: Tier 1/Tier 2
    ch3_counts_tier1.json         # Thống kê Chương 3 với mẫu số 33
simulation/
  src/models.py                   # Mô hình plant + kênh mạng
  experiments/                    # Benchmark, ablation và đánh giá
  data/                           # Dữ liệu thời tiết + trace tổng hợp
  results/                        # Kết quả benchmark CSV
  tests/                          # Kiểm thử mô hình
```

## Tái tạo phân tầng và thống kê

Từ thư mục gốc repo:

```bash
python3 prisma/bib_audit/build_two_tier_corpus.py
python3 prisma/bib_audit/enforce_two_tier_consistency.py
python3 prisma/bib_audit/build_two_tier_corpus.py
python3 prisma/bib_audit/regen_ch3_tier1.py
```

Các script sinh hình Chương 3/4 được giữ để truy vết mã, nhưng cần cây thư mục `figures/` của bản thảo làm đích xuất và vì vậy không nằm trong lệnh tái tạo tối thiểu của repo đồng hành.

Xem thêm:

- [`prisma/bib_audit/README.md`](prisma/bib_audit/README.md): trạng thái corpus và thứ tự pipeline.
- [`prisma/bib_audit/README_AUDIT.md`](prisma/bib_audit/README_AUDIT.md): cách kiểm tra từng số PRISMA.
- [`prisma/bib_audit/pnce_recode/SCHEMA.md`](prisma/bib_audit/pnce_recode/SCHEMA.md): định nghĩa 12 biến PNCE và quy tắc locator.

## Mô phỏng

Benchmark kiểm tra đánh đổi giữa chất lượng điều khiển, truyền tin và năng lượng mô hình hóa trên ba kịch bản:

- **Mekong-Trace:** trace mất gói tổng hợp được điều kiện hóa theo thời tiết Mekong; không phải log mạng đo thực địa.
- **Tokyo-Bernoulli:** đối chứng mất gói Bernoulli.
- **Tokyo-Burst:** đối chứng mất gói tương quan theo thời gian.

Mô hình plant là một trừu tượng nhiệt độ nhà kính vô hướng chuẩn hóa. Kết quả không phải xác nhận phần cứng, an toàn sinh học hay hiệu quả triển khai thực địa.

### Chạy kiểm thử và benchmark

```bash
cd simulation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python experiments/run_q1_benchmark.py
```

Hoặc chạy toàn bộ quy trình mô phỏng:

```bash
cd simulation
./run_all.sh
```

## Quy tắc công khai dữ liệu

Repo chỉ lưu metadata, bảng mã hóa có locator/trích đoạn ngắn cần cho kiểm toán, nhật ký tuyến truy xuất, mã nguồn và kết quả tổng hợp. Các tệp PDF/toàn văn, văn bản trích xuất toàn bài và cache ứng viên cục bộ bị loại bằng `.gitignore`; người dùng phải tự truy xuất nguồn qua DOI, kho OA hoặc thư viện hợp pháp.

## Trích dẫn

Nếu sử dụng mã nguồn hoặc dữ liệu này, vui lòng trích dẫn luận văn tương ứng (xem thông tin trong hồ sơ luận văn).

## Giấy phép

Mã nguồn phát hành theo giấy phép MIT (xem [`LICENSE`](LICENSE)). Quyền đối với các công trình được trích dẫn vẫn thuộc tác giả/nhà xuất bản tương ứng.
