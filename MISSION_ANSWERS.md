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

## AI log

| Phần | Mục đích sử dụng AI | Nội dung hỗ trợ | Cách tự kiểm tra |
|---|---|---|---|
| Part 1 — Exercise 1.1–1.3 | Nhờ ChatGPT hướng dẫn đọc phát hiện anti-pattern và trình bày phần so sánh develop/production | Gợi ý giải thích lý do các cấu hình chưa phù hợp production và hỗ trợ sửa `MISSION_ANSWERS.md` | Đọc `develop/app.py`, `production/app.py`, `config.py`; tự chạy hai phiên bản trên Ubuntu WSL2; gửi các request đến `/ask`, `/health`, `/ready` và kiểm tra HTTP status/log thực tế. |

> Các mục Part 2–5, kết quả Part 6 và AI log tương ứng sẽ được bổ sung sau khi hoàn thành từng checkpoint.
