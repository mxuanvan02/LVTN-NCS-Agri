# NCS-Agri: PRISMA Audit & Simulation Code

Mã nguồn và dữ liệu nền (source data) đi kèm luận văn về **Hệ thống điều khiển qua mạng (Networked Control Systems – NCS) trong nông nghiệp thông minh**, kết hợp tổng quan có hệ thống theo chuẩn PRISMA 2020 với kiểm chứng mô phỏng.

Repo này chứa **code + source data** để tái lập, không chứa bản thảo (`.tex`), hình biên tập hay file kết quả đã render trong luận văn.

## Cấu trúc

```
prisma/
  tools/prisma_rebuild_audit.py   # Pipeline tái chạy PRISMA: truy vấn, gộp lặp, sàng lọc, ghi vết
  bib_audit/                      # Toàn bộ vết kiểm chứng PRISMA (CSV/JSON) + danh mục nguồn
simulation/
  src/models.py                  # Mô hình plant + kênh mạng (NCS)
  experiments/                   # Script chạy benchmark, ablation, đánh giá
  data/                          # Dữ liệu thời tiết (Mekong VN, Tokyo) + trace mạng
  results/                       # Kết quả benchmark dạng CSV
  tests/                         # Kiểm thử mô hình
```

## Quy trình PRISMA

Pipeline tái chạy 10 chuỗi truy vấn theo nhóm PNCE (Plant–Network–Control–Evaluation) trên OpenAlex (2015–2025), hợp nhất với vết nguồn cũ, sau đó gộp lặp và sàng lọc:

`627 bản ghi thô → 424 nguồn duy nhất → 187 nguồn sau sàng lọc → 64 công trình lõi`

Toàn bộ con số trong sơ đồ PRISMA của luận văn truy được về các tệp trong `prisma/bib_audit/`.

## Mô phỏng

Benchmark nền kiểm tra đánh đổi giữa chất lượng điều khiển, truyền tin và năng lượng trên 3 kịch bản:
- **Mekong-Trace** — kịch bản Việt Nam (dữ liệu thời tiết ĐBSCL).
- **Tokyo-Bernoulli / Tokyo-Burst** — đối chứng với hai mô hình mất gói.

### Chạy

```bash
cd simulation
pip install -r requirements.txt
python experiments/run_q1_benchmark.py
```

## Trích dẫn

Nếu sử dụng mã nguồn hoặc dữ liệu này, vui lòng trích dẫn luận văn tương ứng (xem thông tin trong hồ sơ luận văn).

## Giấy phép

Mã nguồn phát hành theo giấy phép MIT (xem `LICENSE`).
