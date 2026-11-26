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


## Part 4: API Security

**Môi trường:** Ubuntu WSL2, Python 3.12 trong venv `day14`. Đây là các ứng dụng minh họa dùng mock LLM; các phép thử được chạy trên `localhost:8000` ngày 26/11/2026. Các key và tài khoản được dùng là dữ liệu demo của bài lab.

### Exercise 4.1: API Key Authentication

**Vị trí kiểm tra:** `04-api-gateway/develop/app.py` khai báo `APIKeyHeader(name="X-API-Key", auto_error=False)`; dependency `verify_api_key()` được gắn vào endpoint `/ask` qua `Depends(verify_api_key)`.

- **Thiếu key:** trả HTTP `401 Unauthorized`.
- **Key không khớp:** trả HTTP `403 Forbidden` theo cách xử lý của ứng dụng mẫu.
- **Key hợp lệ:** tiếp tục xử lý request và trả HTTP `200 OK`.
- **Rotate key:** tạo key mới có độ ngẫu nhiên cao, cấu hình lại `AGENT_API_KEY` qua secret/environment trên nền tảng, cập nhật các client và khởi động lại/redeploy ứng dụng để nạp key mới. Bản mẫu chỉ hỗ trợ một key đang hoạt động; để chuyển đổi không gián đoạn trong production cần hỗ trợ song song key cũ/mới trong giai đoạn chuyển tiếp. Không hardcode hay ghi secret vào log.

Khởi động mẫu (không phải khóa dùng thật):

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=secret-key-123 python app.py
```

**Kết quả `curl -i` thực tế:**

```text
POST /ask (không gửi X-API-Key)
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

POST /ask (X-API-Key: wrong-key)
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

POST /ask (X-API-Key: secret-key-123)
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

**Kết luận:** Xác thực API key đã từ chối request không có/sai key và chấp nhận key đúng theo thiết kế ứng dụng mẫu.

### Exercise 4.2: JWT Authentication

**Mã nguồn:** `04-api-gateway/production/auth.py` tạo JWT bằng `HS256` với payload chứa `sub` (username), `role`, `iat`, `exp`; thời hạn token là 60 phút. `verify_token()` đọc header `Authorization: Bearer <token>`, xác minh chữ ký và hạn dùng. Demo user `student` có role `user`, `teacher` có role `admin`.

**Luồng xác thực:** Client gửi username/password đến `POST /auth/token` → server xác thực và trả JWT → client gửi JWT trong header Bearer khi gọi `POST /ask` → server xác minh JWT trước khi thực hiện xử lý và rate limit.

Đã dùng tài khoản demo `student/demo123` để lấy token; token được lưu trong biến shell `TOKEN` và không đưa giá trị thật vào báo cáo.

**Kết quả kiểm thử thực tế:**

```text
POST /auth/token (student/demo123)
HTTP/1.1 200 OK
{"access_token":"[REDACTED]","token_type":"bearer","expires_in_minutes":60,...}

POST /ask (không có Authorization)
HTTP/1.1 401 Unauthorized
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

POST /ask (Bearer invalid-token)
HTTP/1.1 403 Forbidden
{"detail":"Invalid token."}

POST /ask (Bearer token hợp lệ, question="Explain JWT")
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**Lưu ý:** Giá trị `budget_remaining_usd` trong phản hồi `/ask` trên thực tế là **tổng chi phí đã dùng** do `app.py` trả `usage.total_cost_usd` vào trường có tên này. Không dùng trường đó làm số dư ngân sách; số dư thật được kiểm tra qua `/me/usage`.

### Exercise 4.3: Rate Limiting

**Thuật toán:** `04-api-gateway/production/rate_limiter.py` dùng một `deque` timestamp theo từng user. Mỗi lần kiểm tra, loại timestamp nằm ngoài 60 giây, đếm request đang nằm trong cửa sổ và trả HTTP 429 nếu đạt giới hạn. Xét cách cài đặt, đây là **sliding window dựa trên timestamp** (không phải token bucket). Dữ liệu đang lưu **in-memory**, nên chưa chia sẻ được giữa nhiều worker/instance.

**Giới hạn:**

| Role | Giới hạn | Cách xử lý |
|---|---|---|
| `user` | 10 request / 60 giây | `rate_limiter_user` |
| `admin` | 100 request / 60 giây | `rate_limiter_admin` |

Admin không được bỏ qua giới hạn hoàn toàn; ứng dụng dùng ngưỡng riêng cao hơn cho role `admin`. Muốn miễn giới hạn cho một nhóm cụ thể phải thiết kế chính sách riêng thay vì chỉ tăng role giả mạo trong request.

**Lệnh đã chạy:**

```bash
for i in $(seq 1 20); do
  printf "Request %02d: " "$i"
  curl -sS -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"question\":\"Test $i\"}"
done
```

**Kết quả thực tế:** request 01–09 trả HTTP `200`, request 10–20 trả HTTP `429`. Nguyên nhân request 10 trong vòng lặp đã bị chặn là có một request `/ask` hợp lệ được thực hiện ngay trước đó trong cùng cửa sổ 60 giây, nâng tổng số request thành công lên 10.

```text
Request 01–09: 200 (9 request)
Request 10–20: 429 (11 request)
```

**Kiểm tra usage sau vòng lặp:**

```text
GET /me/usage
HTTP/1.1 200 OK
{"user_id":"student","date":"2026-11-26","requests":10,"input_tokens":40,"output_tokens":288,"cost_usd":0.000179,"budget_usd":1.0,"budget_remaining_usd":0.999821,"budget_used_pct":0.0}
```

**Kiểm tra bổ sung HTTP 429 bằng `curl -i` (ngày 26/11/2026):** Sau khi gửi thêm 11 request để chạm giới hạn, tôi thực hiện một request mới với JWT hợp lệ. Server trả về đầy đủ status, headers và body như sau (không đưa JWT vào báo cáo):

```text
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795684305
retry-after: 50
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":50}}
```

Kết quả xác nhận giới hạn **10 request/60 giây** được áp dụng; `x-ratelimit-remaining: 0` cho biết không còn lượt trong cửa sổ hiện tại và `retry-after: 50` hướng dẫn client thử lại sau 50 giây tại thời điểm kiểm tra. Đây là kết quả thực tế, không phải response giả định. Các output 401/200 đã ghi ở Exercise 4.1 và 4.2.

### Exercise 4.4: Cost Guard

**Phân tích mã nguồn mẫu (`04-api-gateway/production/cost_guard.py`):**

- Budget mỗi user mặc định là **$1/ngày**, toàn hệ thống **$10/ngày**; đây **không phải** bài toán $10/user/tháng trong `CODE_LAB.md`.
- `CostGuard.check_budget()` kiểm tra ngân sách đã sử dụng: khi user vượt/ngang ngưỡng trả **HTTP 402**; khi global budget hết trả **HTTP 503**. Ngưỡng cảnh báo là 80%.
- `record_usage()` cộng input/output tokens và tính chi phí mô phỏng sau khi gọi LLM.
- Bản mẫu lưu số liệu **in-memory** nên có thể mất khi restart hoặc sai lệch khi nhiều worker/instance đồng thời; nó không chặn trước chi phí ước tính của request mới (chỉ so số đã dùng).
- Ở lần kiểm thử này, budget còn `$0.999821`, chưa chạm ngưỡng; **chưa quan sát trực tiếp phản hồi HTTP 402**. Không kết luận rằng nhánh 402 đã được kiểm thử.

**Thiết kế bài toán được yêu cầu: $10/user/tháng, lưu Redis, reset đầu tháng.** Đề xuất hàm `check_budget(user_id, estimated_cost) -> bool` như sau:

1. Xác định tháng theo UTC (`YYYY-MM`), tạo khóa Redis dạng `budget:<user_id>:<YYYY-MM>` để cô lập chi tiêu từng user/tháng.
2. Biểu diễn số tiền bằng đơn vị nguyên nhỏ (ví dụ micro-USD) để tránh sai lệch số thực; lấy số đã dùng của tháng.
3. Trong **một thao tác nguyên tử Redis** (Lua script/transaction), kiểm tra `current + estimated_cost <= 10 USD`. Nếu vượt giới hạn, trả `False` và không tăng bộ đếm; nếu còn đủ, cập nhật số tiền đã dành và trả `True`.
4. Đặt hạn sử dụng khóa tại **00:00 UTC ngày đầu tháng kế tiếp** (hoặc dùng key của tháng mới) để việc tính budget tháng mới không phụ thuộc vào thời điểm request đầu tiên.
5. Endpoint `/ask` trả HTTP `402 Payment Required` khi `check_budget()` là `False`; sau khi gọi LLM, đối soát chi phí thực tế (nếu khác estimate) và xử lý sai lệch phù hợp. Cần quy định trường hợp LLM thất bại để hoàn lại phần ngân sách đã giữ.

**Phác thảo thuật toán (chưa tích hợp và chưa chạy):**

```python
# Nguyên tắc: check + update trong Redis phải ATOMIC
# Redis key: budget:<user_id>:<YYYY-MM>, value: integer micro-USD

def check_budget(user_id: str, estimated_cost: float) -> bool:
    key = f"budget:{user_id}:{current_utc_month()}"
    amount = to_integer_micro_usd(estimated_cost)
    limit = 10_000_000  # $10 = 10 triệu micro-USD
    return redis_atomic_check_add(
        key=key,
        amount=amount,
        limit=limit,
        expires_at=first_day_of_next_month_utc(),
    )
```

Đoạn trên là **pseudocode thiết kế**, không phải hàm chạy được ngay; `current_utc_month`, `to_integer_micro_usd`, `redis_atomic_check_add` và `first_day_of_next_month_utc` cần được hiện thực trong ứng dụng thật.

**Tại sao phải có cả Rate Limit và Cost Guard?** Rate limiting hạn chế tốc độ/số request trong khoảng ngắn; cost guard hạn chế tổng mức chi tiêu tích lũy. Một user có thể gửi request rất chậm nhưng mỗi request tiêu nhiều token, khi đó vẫn có thể vượt ngân sách dù chưa hề chạm giới hạn request/phút.

### Tổng kết Part 4

Đã kiểm thử API Key Authentication (`401/403/200`), JWT Authentication (`401/403/200`) và rate limiting (9 request `200`, 11 request `429` trong vòng lặp 20 lần). `GET /me/usage` trả thông tin chi phí mô phỏng và số dư daily budget. Phần Cost Guard được **phân tích và thiết kế** theo yêu cầu Redis $10/tháng, **chưa triển khai Redis thật** và **chưa chạy thử trường hợp vượt budget 402**. Điểm này cần phân biệt với các bài test đã PASS.

---

## AI log

| Phần | Mục đích sử dụng AI | Nội dung hỗ trợ | Cách tự kiểm tra |
|---|---|---|---|
| Part 1 — Exercise 1.1–1.3 | Nhờ ChatGPT hướng dẫn đọc phát hiện anti-pattern và trình bày phần so sánh develop/production | Gợi ý giải thích lý do các cấu hình chưa phù hợp production và hỗ trợ sửa `MISSION_ANSWERS.md` | Đọc `develop/app.py`, `production/app.py`, `config.py`; tự chạy hai phiên bản trên Ubuntu WSL2; gửi các request đến `/ask`, `/health`, `/ready` và kiểm tra HTTP status/log thực tế. |
| Part 2 — Exercise 2.1–2.4 | Nhờ ChatGPT giải thích Dockerfile, multi-stage build, lỗi Docker Hub 429, lỗi cú pháp JSON trong PowerShell và hỗ trợ viết báo cáo | Hướng dẫn lệnh build/run, so sánh kích thước, đọc Docker Compose, diễn giải kiến trúc và tổng hợp số liệu | Tự build hai image, chạy và kiểm thử container; dùng `docker image inspect` tính mức giảm 86,53%; tự đăng nhập Docker Hub, pull image, chạy bốn service và kiểm tra API qua Nginx. Đối chiếu log đầu ra trước khi đưa số liệu vào báo cáo. |
| Part 4 — Exercise 4.1–4.4 | Nhờ ChatGPT hướng dẫn kiểm thử API key/JWT, rate limiting, đề xuất thiết kế cost guard | Giải thích 401/403/200/429, thống kê usage, phân biệt ngân sách mẫu in-memory với bài toán Redis $10/tháng, phát hiện trường phản hồi `/ask` đặt sai tên | Tự chạy các curl, vòng lặp 20 request và kiểm tra response `curl -i` HTTP 429 trên WSL2; xem HTTP status, headers và `/me/usage`; đối chiếu `app.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`; chưa tuyên bố đã test HTTP 402 hoặc chạy Redis budget. |

> Các mục Part 3, Part 5, kết quả Part 6 và AI log tương ứng sẽ được bổ sung sau khi hoàn thành từng checkpoint.
