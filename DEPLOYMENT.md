# Deployment Information — Day 14 (CP6)

**Ngày kiểm thử:** 26/11/2026  
**Môi trường:** production  
**Nền tảng:** Railway (triển khai Part 6 — Production-ready AI Agent)

## Public URL

- **URL:** https://k5-l3b-day14-nguyenvanhung-2a202603816-deploymen-production.up.railway.app
- **Source GitHub:** https://github.com/nguyenhung1901/K5-L3B-DAY14-NguyenVanHung-2A202603816-Deployment-Benchmark-Observability
- **Branch:** `main`
- **Railway project:** `gracious-insight`, environment `production`
- **Root Directory:** `/06-lab-complete`
- **Dockerfile:** `/06-lab-complete/Dockerfile`
- **Build:** Dockerfile multi-stage, Python 3.11 slim, non-root
- **Public Domain Target Port:** `8080` (khớp log Uvicorn trên Railway)
- **Healthcheck Path:** `/health`

## Kiến trúc triển khai

```text
Client (HTTPS)
      |
      v
Railway Public Domain --Target Port 8080--> Agent (FastAPI, Uvicorn; 2 workers)
                                                   |
                                                   | REDIS_URL (private network)
                                                   v
                                              Railway Redis
```

| Thành phần | Bằng chứng đã quan sát |
|---|---|
| Agent | Service Online; deployment `ACTIVE` và `Deployment successful` |
| Redis | Service Online; nằm trong cùng project; `/ready` của Agent trả `200` và `{"ready":true}` |
| API | Public HTTPS trả đúng các mã `200 / 200 / 401 / 200` |

Agent dùng **mock LLM**, không kết nối OpenAI/Anthropic thật trong bài này.

## Environment Variables

Các biến đã được cấu hình tại Railway → Agent → Variables. Không ghi giá trị bí mật thật vào Git hoặc báo cáo.

| Biến | Cách đặt | Ghi chú |
|---|---|---|
| `AGENT_API_KEY` | Secret đặt trên Railway | Không đưa giá trị vào ảnh/log/repository |
| `REDIS_URL` | Variable reference đến Redis: `${{Redis.REDIS_URL}}` | Kết nối Redis qua mạng riêng |
| `ENVIRONMENT` | `production` | Đã xác nhận trong phản hồi `/health` |
| `RATE_LIMIT_PER_MINUTE` | `10` | Thiết lập cho môi trường cloud |
| `DAILY_BUDGET_USD` | `1.0` | Ngân sách minh họa theo mã nguồn Part 6 |
| `PORT` | Railway cấp khi chạy; log xác nhận `8080` | Không lấy giá trị mặc định local `8000` làm cổng cloud |

## Lệnh kiểm thử Public URL

Chạy trên Ubuntu WSL2; nhập key bí mật qua prompt ẩn, không in ra terminal:

```bash
BASE="https://k5-l3b-day14-nguyenvanhung-2a202603816-deploymen-production.up.railway.app"
read -rsp "AGENT_API_KEY: " AGENT_API_KEY
echo

curl -sS -o /dev/null -w "Health: %{http_code}\n" "$BASE/health"
curl -sS -o /dev/null -w "Ready: %{http_code}\n" "$BASE/ready"
curl -sS -o /dev/null -w "No API Key: %{http_code}\n" \
  -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
curl -sS -o /dev/null -w "Valid API Key: %{http_code}\n" \
  -X POST "$BASE/ask" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

### Kết quả thực tế (26/11/2026)

```text
Health: 200
Ready: 200
No API Key: 401
Valid API Key: 200
```

| Kiểm tra | HTTP mong đợi | HTTP quan sát | Đánh giá |
|---|---:|---:|---|
| `GET /health` | 200 | 200 | PASS |
| `GET /ready` | 200 | 200 | PASS |
| `POST /ask` không key | 401 | 401 | PASS |
| `POST /ask` có key hợp lệ | 200 | 200 | PASS |

Response chi tiết đã quan sát khi kiểm tra public URL:

```text
GET /health -> HTTP/2 200
{"status":"ok","uptime_seconds":1058.44,"environment":"production"}

GET /ready -> HTTP/2 200
{"ready":true}
```

## Sự cố khi triển khai và cách xử lý

- Lần đầu gửi request bằng URL thiếu `https://`, Railway phản hồi `301` do chuyển hướng HTTP sang HTTPS; khắc phục bằng khai báo URL HTTPS đầy đủ.
- Khi dùng URL HTTPS, `/health` trả `502 Application failed to respond`. Đối chiếu Deploy Logs cho thấy Uvicorn lắng nghe trên `0.0.0.0:8080`, còn domain được tạo ban đầu trỏ sai cổng.
- Sửa **Target Port của Railway Public Domain sang `8080`**, không chỉnh code. Sau đó `/health` và `/ready` đều trả HTTP 200; các test xác thực cũng đạt như bảng trên.

## Screenshots — bằng chứng từ hệ thống thật

- [Railway Project Canvas: Agent + Redis Online](screenshots/dashboard.png)
- [Railway deployment ACTIVE, successful và public URL](screenshots/running.png)
- [Terminal public API: 200 / 200 / 401 / 200](screenshots/test.png)

## Đối chiếu bài chấm Part 6

Lệnh local `python check_production_ready.py --redis-url redis://127.0.0.1:6379/0` đã đạt **PASS 12/12 — 41/41 checks**. Kết quả local và kiểm thử URL public là **hai nhóm bằng chứng riêng**, không thay thế nhau.

**Giới hạn:** Trạng thái Online và phản hồi `/ready` cho thấy Redis khả dụng ở thời điểm kiểm tra; chưa phải phép thử đo độ bền dài hạn hoặc khả năng tự phục hồi khi dịch vụ Redis mất kết nối trên cloud.
