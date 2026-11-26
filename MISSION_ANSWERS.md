# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Phát hiện anti-patterns

Sau khi đọc `01-localhost-vs-production/develop/app.py`, tôi xác định các vấn đề sau:

| STT | Anti-pattern | Vị trí trong `develop/app.py` | Giải thích |
|---|---|---|---|
| 1 | Hardcode API key | Dòng 17 | Đưa khóa vào mã nguồn có nguy cơ làm lộ khóa khi chia sẻ hoặc đẩy repository lên GitHub. |
| 2 | Hardcode thông tin kết nối database | Dòng 18 | Chuỗi kết nối chứa tài khoản và mật khẩu; khi triển khai ở môi trường khác cũng khó thay đổi an toàn. |
| 3 | Cấu hình cố định trong code | Dòng 21–22 | `DEBUG` và `MAX_TOKENS` được gán trực tiếp, khiến cấu hình giữa dev và production khó quản lý. |
| 4 | Ghi secret vào log | Dòng 33–38, đặc biệt dòng 34 | `print()` ghi cả API key ra terminal. Người truy cập log có thể nhìn thấy dữ liệu nhạy cảm. |
| 5 | Không có health check | Không khai báo `/health`; ghi chú ở dòng 42–43 | Hệ thống giám sát hoặc nền tảng triển khai thiếu endpoint riêng để kiểm tra ứng dụng còn hoạt động. |
| 6 | Bind vào localhost | Dòng 51 | Chỉ lắng nghe trên loopback, không phù hợp khi cần nhận kết nối qua mạng của container. |
| 7 | Port bị cố định | Dòng 52 | Dùng cứng cổng `8000`, không đọc giá trị `PORT` do nền tảng cloud cấp. |
| 8 | Bật reload cố định | Dòng 53 | `reload=True` phù hợp cho phát triển nhưng không nên bật khi triển khai production. |
| 9 | Không có logic shutdown/cleanup ở cấp ứng dụng | File không khai báo lifespan hoặc xử lý dọn tài nguyên khi dừng | Nếu ứng dụng dùng tài nguyên như kết nối database, cần cơ chế đóng và thu hồi tài nguyên có kiểm soát. |

**Nhận xét:** Bản develop có thể xử lý request nhưng chưa đủ điều kiện triển khai production, chủ yếu do cấu hình và secret đặt trong source, logging thiếu an toàn, và thiếu cơ chế kiểm tra tình trạng hoạt động.

### Exercise 1.2: Chạy basic/develop version

**Môi trường:** Ubuntu trên WSL2, dùng Python trong virtual environment `day14`.

Khởi động ứng dụng tại `01-localhost-vs-production/develop/`:

```bash
python app.py
```

Gửi request kiểm tra:

```bash
curl -i -X POST "http://localhost:8000/ask?question=Hello"
```

**Kết quả đã quan sát:**

```text
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Server ghi log nhận câu hỏi và phản hồi; đồng thời in API key giả được hardcode ra log. Điều này minh họa trực tiếp anti-pattern tại dòng 34. Phản hồi đến từ **mock LLM**, không phải bằng chứng về một lần gọi OpenAI API thật.

**Kết luận:** Bản develop chạy thành công trên localhost nhưng khả năng chạy được không đồng nghĩa với việc an toàn và sẵn sàng cho production.

### Exercise 1.3: So sánh develop với production

| Tiêu chí | Develop (`develop/app.py`) | Production (`production/app.py`, `config.py`) | Tại sao quan trọng? |
|---|---|---|---|
| Quản lý cấu hình | Giá trị được gán trực tiếp trong code | Đọc qua `os.getenv()` trong `config.py` (dòng 17–35) | Có thể cấu hình riêng cho dev/staging/production mà không sửa source. |
| Quản lý secret | API key và database URL hardcode (dòng 17–18) | Đọc API key từ environment (dòng 27, 32 của `config.py`) | Hạn chế nguy cơ lộ secret khi chia sẻ repository. |
| Host và port | `localhost:8000` cố định (dòng 51–52) | Dùng `settings.host` và `settings.port` (dòng 196–197); mặc định host `0.0.0.0` | Cho phép nhận kết nối từ bên ngoài container và dùng cổng do nền tảng cung cấp. |
| Chế độ debug | `reload=True` cố định (dòng 53) | `reload=settings.debug` (dòng 198) | Tắt reload ở production để tránh tác động không cần thiết. |
| Logging | Dùng `print()`, có in API key (dòng 33–38) | Dùng `logging`, log thông tin sự kiện, độ dài câu hỏi/câu trả lời thay vì secret (dòng 27–32, 110–122) | Hữu ích khi theo dõi, tìm lỗi, đồng thời tránh đưa secret vào log. |
| Health check | Không có | `GET /health` (dòng 135–149) | Giúp kiểm tra tiến trình ứng dụng còn phản hồi. |
| Readiness check | Không có | `GET /ready` (dòng 152–161) | Giúp xác định ứng dụng có sẵn sàng nhận traffic hay chưa. |
| Shutdown | Không có logic lifecycle riêng | Có `lifespan` với bước startup/shutdown (dòng 39–67) và handler SIGTERM (dòng 180–189) | Tạo vị trí thực hiện cleanup và quản lý vòng đời ứng dụng. |
| Dữ liệu đầu vào | `question` nhận từ query parameter | `question` nhận từ JSON request body (dòng 102–108) | Hình thức API được xác định rõ và có kiểm tra trường bắt buộc. |

**Kiểm tra thực tế bản production:**

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
curl -i -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```

Các kết quả đã ghi nhận:

```text
GET /health  -> HTTP/1.1 200 OK
  status: ok
  uptime_seconds: 17.0 (ở thời điểm kiểm tra)

GET /ready   -> HTTP/1.1 200 OK
  {"ready":true}

POST /ask    -> HTTP/1.1 200 OK
  {"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

**Đánh giá:** Phiên bản production mẫu khắc phục nhiều hạn chế của bản develop, đặc biệt là cấu hình từ environment, health/readiness check và không in secret trong log. Tuy nhiên, mã nguồn này vẫn mang tính minh họa: định dạng log được ghép thủ công nên chưa bảo đảm mọi bản ghi là JSON hợp lệ; phần shutdown sử dụng `sleep()` giả lập và chưa được kiểm thử khả năng hoàn thành request đang xử lý. Do đó, không nên coi bản mẫu là một hệ thống production-ready hoàn chỉnh.

### Tổng kết Part 1

Từ hai phiên bản, tôi rút ra rằng một Agent chạy được trên máy cá nhân chưa đủ để đưa lên production. Ứng dụng cần tách cấu hình khỏi mã nguồn, bảo vệ thông tin nhạy cảm, cung cấp health/readiness check, có logging phù hợp và quản lý vòng đời khi khởi động hoặc dừng. Các yếu tố này giúp việc triển khai, giám sát và vận hành ổn định hơn.

---

## Part 2: Docker Containerization

### Exercise 2.1: Đọc Dockerfile cơ bản

Mã nguồn tham khảo: `02-docker/develop/Dockerfile`.

**1. Base image là gì?**  
Base image là image nền cung cấp môi trường để xây dựng image mới. Dockerfile develop dùng `FROM python:3.11`, tức image Python 3.11 bản đầy đủ. Nó chứa Python runtime cùng các thành phần hệ thống cần thiết, nhưng thường có dung lượng lớn hơn bản `slim`.

**2. Working directory là gì?**  
`WORKDIR /app` đặt `/app` làm thư mục làm việc mặc định bên trong container. Những lệnh tương đối phía sau như `COPY ... .` và lệnh khởi chạy sẽ được thực thi theo ngữ cảnh thư mục này.

**3. Tại sao copy `requirements.txt` trước khi copy source code?**  
Docker lưu cache theo từng bước build. Khi copy file requirements trước rồi `RUN pip install`, nếu mã nguồn thay đổi nhưng requirements không đổi thì Docker có thể dùng lại layer cài dependencies, tránh cài lại thư viện không cần thiết. `pip install --no-cache-dir` chỉ tắt cache của pip, không tắt Docker layer cache.

**4. `CMD` và `ENTRYPOINT` khác nhau thế nào?**  
`CMD` cung cấp lệnh hoặc đối số mặc định của container; có thể thay bằng đối số đặt sau tên image trong `docker run`. `ENTRYPOINT` xác định chương trình chính; các đối số khi chạy thường được nối vào lệnh này. `ENTRYPOINT` vẫn có thể bị thay thế bằng tùy chọn `--entrypoint`. Trong Dockerfile develop, `CMD ["python", "app.py"]` là lệnh chạy Agent mặc định.

### Exercise 2.2: Build và chạy basic container

Thực hiện từ thư mục gốc repository trên Windows PowerShell, sử dụng Docker Desktop với Linux containers:

```powershell
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker images my-agent:develop
docker run --rm -d --name k5-day14-basic -p 8000:8000 my-agent:develop
curl.exe -i http://localhost:8000/health
curl.exe -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"
docker logs k5-day14-basic
docker stop k5-day14-basic
```

**Kết quả quan sát từ terminal:**

| Thông tin | Kết quả |
|---|---|
| Docker build | `FINISHED (12/12)`, 76,6 giây |
| Image | `my-agent:develop` (ID rút gọn `82af015681e2`) |
| `docker images` — Content Size | 426 MB |
| `docker image inspect` — Size | 406,57 MiB |
| Docker Desktop — Disk Usage | 1,67 GB (chỉ số hiển thị riêng của Docker Desktop) |
| Container | `k5-day14-basic`, chạy ở `0.0.0.0:8000->8000/tcp` |
| `GET /health` | HTTP `200 OK` |
| `POST /ask?question=What%20is%20Docker%3F` | HTTP `200 OK` |

Phản hồi thực tế:

```text
GET /health -> HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":9.2,"container":true}

POST /ask?question=What%20is%20Docker%3F -> HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

`docker logs` ghi nhận Uvicorn lắng nghe trên `0.0.0.0:8000`, cả hai request đều trả `200 OK`. Endpoint develop nhận `question` qua **query parameter** theo mã nguồn; không dùng JSON body như ví dụ chưa được cập nhật trong `CODE_LAB.md`. Container đã được dừng bằng `docker stop` sau khi kiểm thử.

### Exercise 2.3: Multi-stage build và so sánh image

Mã nguồn tham khảo: `02-docker/production/Dockerfile`.

**Stage 1 — `builder`:** Dùng `python:3.11-slim`, cài công cụ build như `gcc`, `libpq-dev`, sau đó cài Python dependencies vào `/root/.local` bằng `pip install --user`.

**Stage 2 — `runtime`:** Bắt đầu từ image `python:3.11-slim` sạch, copy phần dependencies đã cài từ builder và copy mã nguồn Agent. Tạo người dùng `appuser`, chuyển sang chạy bằng `USER appuser`, cấu hình `PATH`, `PYTHONPATH`, health check và lệnh Uvicorn. Công cụ build của stage đầu không nằm trong image runtime cuối cùng.

Lệnh đã thực hiện:

```powershell
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent

$devBytes = [double](docker image inspect my-agent:develop --format '{{.Size}}')
$prodBytes = [double](docker image inspect my-agent:advanced --format '{{.Size}}')
"Develop: {0:N2} MiB" -f ($devBytes / 1MB)
"Production: {0:N2} MiB" -f ($prodBytes / 1MB)
"Reduction: {0:N2}%" -f ((1 - $prodBytes / $devBytes) * 100)
```

**Kết quả đo thực tế:**

| Chỉ số | Develop (single-stage) | Production (multi-stage) |
|---|---:|---:|
| Base image | `python:3.11` | `python:3.11-slim` (builder và runtime) |
| Build time | 76,6 giây | 74,1 giây |
| Docker CLI — Content Size | 426 MB | 57,4 MB |
| `docker image inspect` — Size | **406,57 MiB** | **54,75 MiB** |
| Docker Desktop — Disk Usage | 1,67 GB | 240 MB |
| Health check | HTTP 200 | HTTP 200 |
| Agent endpoint | HTTP 200 | HTTP 200 |

Tính tỷ lệ giảm từ **cùng chỉ số `docker image inspect .Size`**, không trộn với Disk Usage:

```text
Reduction = (406.57 - 54.75) / 406.57 * 100 = 86.53%
```

Image production nhỏ hơn khoảng **351,82 MiB (86,53%)** so với develop. Kết quả đến từ việc sử dụng base image `slim` và tách dependencies/build tools khỏi runtime bằng multi-stage. Hai thời gian build trên không đủ để kết luận multi-stage luôn build nhanh hơn, vì còn phụ thuộc cache và mạng.

**Kiểm thử production container:**

```powershell
docker run --rm -d --name k5-day14-advanced -p 8000:8000 -e ENVIRONMENT=production my-agent:advanced
curl.exe -i http://localhost:8000/health
'{"question":"What is Docker?"}' | Set-Content -Encoding ascii request.json
curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" --data-binary "@request.json"
Remove-Item request.json
docker stop k5-day14-advanced
```

Kết quả `GET /health`: HTTP `200 OK`, trả `status=ok`, `version=2.0.0`, `uptime_seconds=10.8`. Kết quả `POST /ask` với JSON hợp lệ: HTTP `200 OK`, trả lời đúng phản hồi mock về Docker giống phần develop.

Trong hai lần thử đầu, cách escape JSON trực tiếp với `curl.exe` trong PowerShell làm request bị sai và nhận HTTP 500, kèm lỗi phân tích đối số của curl. Khi chuyển sang gửi dữ liệu bằng file `request.json`, API trả 200. Đây là lỗi truyền request trong quá trình thử, không phải bằng chứng production Agent hoạt động đúng với JSON lỗi. Container đã được dừng sau khi kiểm thử.

### Exercise 2.4: Docker Compose stack

Đọc `02-docker/production/docker-compose.yml` và `02-docker/production/nginx/nginx.conf`. Stack dùng bốn service trong cùng Docker bridge network `internal`.

**Sơ đồ kiến trúc (logical deployment):**

```text
                   Client (localhost)
                          |
                   HTTP port 80
                          |
                     +---------+
                     |  Nginx  |
                     +---------+
                          |
                 proxy_pass agent:8000
                          |
                     +---------+
                     |  Agent  |  FastAPI / Uvicorn
                     +---------+
                      /       \
          REDIS_URL  /         \  QDRANT_URL
                    v           v
             +-----------+  +-----------+
             |   Redis   |  |  Qdrant   |
             |   :6379   |  |   :6333   |
             +-----------+  +-----------+
              redis_data     qdrant_data
                 (named Docker volumes)
```

**Vai trò và đường kết nối:**

| Service | Vai trò / kết nối |
|---|---|
| `nginx` | Reverse proxy, nhận request từ host cổng 80 và chuyển đến upstream `agent:8000`. File cấu hình còn khai báo rate limiting theo IP. |
| `agent` | FastAPI chạy tại cổng nội bộ 8000; chỉ truy cập từ host qua Nginx, không public trực tiếp cổng 8000 của Compose stack. |
| `redis` | Dịch vụ cache/session, lắng nghe nội bộ ở `redis:6379`, gắn volume `redis_data`. |
| `qdrant` | Vector database phục vụ RAG, lắng nghe nội bộ ở `qdrant:6333`, gắn volume `qdrant_data`. |

Docker Compose đặt `REDIS_URL=redis://redis:6379/0` và `QDRANT_URL=http://qdrant:6333` cho Agent, đồng thời dùng `depends_on` với điều kiện `service_healthy`. **Trong ví dụ này, `main.py` chỉ trả lời bằng mock LLM và chưa thực hiện truy vấn Redis/Qdrant**; sơ đồ thể hiện khả năng kết nối theo cấu hình, không phải bằng chứng về luồng dữ liệu RAG thực tế. Nginx cũng publish cổng 443 nhưng chưa có cấu hình chứng chỉ TLS trong file Nginx được cung cấp, nên không kết luận HTTPS đã sẵn sàng.

**Lệnh đã chạy trên PowerShell từ gốc repository:**

```powershell
# Tạo file env rỗng theo hướng dẫn K5 (được .gitignore bỏ qua)
New-Item -ItemType File -Path "02-docker/production/.env.local"

docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml config --services
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml up -d --build
docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml ps
curl.exe -i http://localhost/health
'{"question":"Explain microservices"}' | Set-Content -Encoding ascii request.json
curl.exe -i -X POST http://localhost/ask -H "Content-Type: application/json" --data-binary "@request.json"
Remove-Item request.json
```

**Kết quả quan sát:**

| Kiểm tra | Kết quả |
|---|---|
| `config --services` | Liệt kê đủ `qdrant`, `redis`, `agent`, `nginx` |
| Docker build stack | `FINISHED (20/20)` khi build lại, dùng cache |
| Containers | Bốn service được tạo và chạy (`Up`) |
| Redis | `Up ... (healthy)` |
| Qdrant | `Up ... (healthy)` |
| Agent | `Up ... (health: starting)` lúc gọi `ps`, chưa có log `healthy` sau đó trong bằng chứng đã gửi |
| Nginx | `Up`, publish cổng 80 và 443 |
| `GET http://localhost/health` | HTTP `200 OK`, `Server: nginx` |
| `POST http://localhost/ask` | HTTP `200 OK`, `Server: nginx` |

Output API đã quan sát:

```text
GET http://localhost/health -> HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":7.1,"version":"2.0.0","timestamp":"2026-11-26T08:39:38.383835"}

POST http://localhost/ask -> HTTP/1.1 200 OK
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Lần đầu chạy Compose bị Docker Hub trả **HTTP 429 Too Many Requests** khi resolve `nginx:alpine`, sau đó `qdrant/qdrant:v1.9.0`. Tôi đăng nhập Docker Hub và tải lần lượt `nginx:alpine`, `redis:7-alpine`, `qdrant/qdrant:v1.9.0`; sau đó `docker compose up -d --build` chạy thành công. Compose còn cảnh báo `version` obsolete vì file có `version: "3.9"`, nhưng cảnh báo này không ảnh hưởng việc khởi chạy.

**Đánh giá:** Stack Docker Compose đã khởi chạy đủ bốn service và định tuyến request qua Nginx đến Agent thành công. Ở thời điểm `docker compose ps`, Agent vẫn đang trong giai đoạn health check khởi tạo, tuy nhiên `/health` sau đó đã phản hồi 200; chưa có bằng chứng kiểm tra trạng thái `healthy` ổn định sau khi chờ. Kết quả hiện tại đáp ứng mục tiêu kiểm thử API qua Nginx của Exercise 2.4.

### Tổng kết Part 2

Tôi đã thực hành build image single-stage và multi-stage, khởi chạy container, dùng `docker logs` để kiểm tra request, đo kích thước image và chạy stack nhiều dịch vụ bằng Docker Compose. Image production giảm 86,53% theo kết quả đo thực tế; stack `agent + redis + qdrant + nginx` phản hồi thành công qua reverse proxy. Việc ứng dụng mock trả HTTP 200 chưa đồng nghĩa với việc các chức năng cache, RAG, TLS hay vận hành production đầy đủ đã được kiểm thử.

---

## AI log

| Phần | Mục đích sử dụng AI | Nội dung hỗ trợ | Cách tự kiểm tra |
|---|---|---|---|
| Part 1 — Exercise 1.1–1.3 | Nhờ ChatGPT hướng dẫn đọc phát hiện anti-pattern và trình bày phần so sánh develop/production | Gợi ý giải thích lý do các cấu hình chưa phù hợp production và hỗ trợ sửa `MISSION_ANSWERS.md` | Đọc `develop/app.py`, `production/app.py`, `config.py`; tự chạy hai phiên bản trên Ubuntu WSL2; gửi các request đến `/ask`, `/health`, `/ready` và kiểm tra HTTP status/log thực tế. |
| Part 2 — Exercise 2.1–2.4 | Nhờ ChatGPT giải thích Dockerfile, multi-stage build, lỗi Docker Hub 429, lỗi cú pháp JSON trong PowerShell và hỗ trợ viết báo cáo | Hướng dẫn lệnh build/run, so sánh kích thước, đọc Docker Compose, diễn giải kiến trúc và tổng hợp số liệu | Tự build hai image, chạy và kiểm thử container; dùng `docker image inspect` tính mức giảm 86,53%; tự đăng nhập Docker Hub, pull image, chạy bốn service và kiểm tra API qua Nginx. Đối chiếu log đầu ra trước khi đưa số liệu vào báo cáo. |

> Các mục Part 3–5, kết quả Part 6 và AI log tương ứng sẽ được bổ sung sau khi hoàn thành từng checkpoint.
