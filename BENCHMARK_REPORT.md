# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Văn Hùng
**Ngày chạy:** 26/11/2026
**Môi trường:** Ubuntu (WSL), Python virtual environment `day14`; Agent v1 `localhost:8001`, Agent v2 `localhost:8002`. Cấu hình CPU/RAM: chưa ghi nhận.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`; dùng p95 để giám sát phần lớn request và phát hiện giảm hiệu năng. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`; đo tỷ lệ phản hồi khác HTTP 200, bao gồm lỗi upstream mô phỏng. |
| Accuracy trên golden dataset | ≥ 85% (CI) | Ngưỡng Quality Gate trong Exercise 7.3. Riêng lần eval sau sửa KB dùng `--min-accuracy 1.0` để xác nhận 23/23 (100%). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.64 | 190.9 | 224.5 | 1695.5 | 1.33% | PASS |
| 10 | 39.98 | 192.6 | 223.8 | 1708.6 | 0.33% | PASS |
| 50 | 94.77 | 226.6 | 528.4 | 1739.2 | 1.00% | FAIL (p95) |
| 100 | 58.26 | 498.3 | 3477.4 | 3784.4 | 1.00% | FAIL (p95) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. RPS tăng từ 4.64 (concurrency 1) lên 39.98 (10) và đạt 94.77 req/s (50), sau đó **giảm còn 58.26 req/s** (100). Ở concurrency 50, p95 đạt 528.4 ms, vừa vượt ngưỡng 500 ms; tại 100, p95 lên tới 3477.4 ms. Dù tỷ lệ lỗi đều dưới 2%, SLO độ trễ không đạt ở hai mức tải cao. Điều này gợi ý hiện tượng xếp hàng/tắc nghẽn tài nguyên khi tăng đồng thời, nhưng chỉ một lượt đo chưa đủ xác định chính xác nút thắt. Để kiểm chứng cần lặp lại benchmark và quan sát CPU, RAM, connection pool và queueing.

Các bài dùng **300 request/mức concurrency**, Agent v2 local. Bài load test mặc định mô phỏng `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Latency percentile trong script tính trên request HTTP 200; RPS và error rate tính trên toàn bộ request.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 193.0 | 223.5 | 241.3 |
| 0.03 (mặc định) | 229.8 | 227.3 | 1694.7 |
| 0.1 | 346.6 | 1702.6 | 1727.1 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

**p99** nhạy hơn khi tỷ lệ request chậm chỉ 3%: p99 tăng từ 241.3 lên 1694.7 ms (khoảng 7 lần), trong khi p95 gần như không đổi (223.5 → 227.3 ms). Khi tăng slow rate lên 10%, p95 cũng tăng mạnh lên 1702.6 ms, khiến SLO FAIL. Average chỉ tăng từ 193.0 lên 346.6 ms, có thể che lấp một nhóm người dùng phải chờ hơn 1.7 giây. Vì vậy, nên giám sát p95 theo SLO và bổ sung p99 để phát hiện tail latency sớm.

Mỗi cấu hình chạy **300 request, concurrency 20**; lần lượt đặt `MOCK_SLOW_RATE=0`, `0.03` và `0.1`. RPS tương ứng là 100.13; 63.32; 45.99 req/s. Tỷ lệ lỗi tương ứng 1.00%; 0.67%; 1.00%; cả ba đều đạt giới hạn lỗi 2%.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0% (23/23)** |
| Avg tokens / câu | 57.4 | 108.8 | 117.7 |
| Tổng cost (USD) | 0.000409 | 0.000758 | 0.000825 |
| Cost / câu đúng (USD) | 0.00040875 | 0.00003607 | 0.00003589 |
| Quality gate | FAIL (80%) | PASS (80%, 0 regression) | **PASS (100%, 0 regression)** |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung entry `jwt`/`json web token` vào `develop/utils/mock_llm.py`, giải thích JWT là token có chữ ký số và thời điểm hết hạn, đối chiếu với API key. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung entry `kubernetes hpa`/`hpa`/`horizontal pod autoscaler`, giải thích HPA scale replica dựa trên CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v1 (không retrieval) có p95 eval thấp hơn (191.6 ms), ít token hơn (57.4 token/câu), nhưng chỉ đúng **1/23 câu (4.3%)**. Agent v2 ban đầu có retrieval, đạt 21/23 (91.3%), p95 219.2 ms và 108.8 token/câu. Sau khi bổ sung **2 entry Knowledge Base**, v2 đạt **23/23 (100%)**, p95 223.5 ms, 117.7 token/câu và không regression so với v2 trước sửa.

So với v1, phiên bản v2 cuối tiêu thụ nhiều token và có tổng chi phí mô phỏng cao hơn (0.000825 so với 0.000409 USD), nhưng **cost/câu đúng** thấp hơn (0.00003589 so với 0.00040875 USD). Đây là trade-off hợp lý trong benchmark này: tăng retrieval context làm tăng latency/cost theo request nhưng cải thiện chất lượng đủ lớn để giảm chi phí trên mỗi câu đúng. Giá token là **mô phỏng** trong `mock_llm.py`, không phải chi phí API LLM thực tế.

Eval sử dụng **23 câu golden dataset**, `MOCK_ERROR_RATE=0`, `MOCK_SLOW_RATE=0`; hai lần đo v1/v2 sử dụng ngưỡng mặc định 80%, còn lần kiểm tra v2 sau sửa dùng `--min-accuracy 1.0` và baseline `eval_v2.json`. CI Exercise 7.3 yêu cầu ngưỡng riêng 85%; job CI được cung cấp trong `.github/workflows/eval.yml`.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
