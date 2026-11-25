# Day 14 Lab — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Các vấn đề trong bản develop

1. `develop/app.py:17–18` đặt API key mẫu và chuỗi kết nối cơ sở dữ liệu trực tiếp trong mã. Nếu dùng thông tin thật, thông tin có thể lộ qua repo và lịch sử Git.
2. `develop/app.py:34` in API key ra log. Người có quyền xem log có thể đọc được giá trị đó.
3. `develop/app.py:41–42` thiếu endpoint `/health`, nên hạ tầng không có endpoint chuyên dụng để kiểm tra ứng dụng còn hoạt động.
4. `develop/app.py:51` bind vào `localhost`, giới hạn kết nối trong cùng máy hoặc container.
5. `develop/app.py:52` cố định cổng `8000`, nên không thể đổi cổng qua biến môi trường.
6. `develop/app.py:53` luôn bật `reload`, khiến server có thể khởi động lại khi mã nguồn thay đổi.

### Exercise 1.2 — Kết quả chạy bản develop

```powershell
curl.exe -i -X POST "http://localhost:8000/ask?question=Hello"
curl.exe -i "http://localhost:8000/health"
```

- `POST /ask?question=Hello` trả `HTTP/1.1 200 OK` và JSON có trường `answer` do mock LLM tạo.
- `GET /health` trả `HTTP/1.1 404 Not Found` với `{"detail":"Not Found"}`.

### Exercise 1.3 — So sánh với bản production

| Tiêu chí | Develop | Production | Vì sao quan trọng? |
|---|---|---|---|
| Cấu hình | Host và port cố định trong mã | Đọc `HOST`, `PORT` và `DEBUG` từ biến môi trường. Bản thử chạy trên cổng `8001`. | Có thể đổi cấu hình theo môi trường triển khai mà không sửa mã. |
| Health check | `/health` trả 404, thiếu `/ready`. | `/health` và `/ready` đều trả 200 khi ứng dụng sẵn sàng. | Hạ tầng có thể kiểm tra ứng dụng còn hoạt động và đã sẵn sàng nhận request. |
| Logging | Dùng `print()`, có dòng in giá trị key. | Dùng `logging` và ghi thông tin có cấu trúc về request và response. | Dễ lọc sự kiện trong log và tránh ghi API key. |
| Shutdown | Thiếu hook dọn tài nguyên của ứng dụng. | Hook `lifespan` đặt lại cờ sẵn sàng và ghi log khi shutdown. | Hook cung cấp chỗ để đóng kết nối và dọn tài nguyên khi ứng dụng dừng. |

Kết quả kiểm tra bản production trên `localhost:8001`:

- `GET /health` trả `HTTP/1.1 200 OK` với `"status":"ok"`.
- `GET /ready` trả `HTTP/1.1 200 OK` với `{"ready":true}`.
- `POST /ask` với JSON `{"question":"Hello"}` trả `HTTP/1.1 200 OK`. Phản hồi chứa câu hỏi, câu trả lời từ mock LLM và tên mô hình theo cấu hình.

Phần shutdown trong bảng dựa trên mã nguồn. Chưa ghi nhận log shutdown từ lần chạy thử.

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

1. Base image là `python:3.11`.
2. Thư mục làm việc trong container là `/app`.
3. Dockerfile sao chép `requirements.txt` và cài dependencies trước khi sao chép mã ứng dụng. Khi chỉ sửa mã, Docker có thể dùng lại layer cài dependencies.
4. `ENTRYPOINT` xác định chương trình chính. `CMD` đặt lệnh mặc định khi không có `ENTRYPOINT`, hoặc cung cấp đối số mặc định khi có `ENTRYPOINT`. Dockerfile này dùng `CMD ["python", "app.py"]`.

### Exercise 2.2 — Build và chạy bản develop

```powershell
curl.exe -i -X POST "http://localhost:8002/ask?question=What%20is%20Docker%3F"
docker images my-agent:develop
```

- `POST /ask` trả `HTTP/1.1 200 OK` với phản hồi `{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}`.
- Image `my-agent:develop` (ID `1943526f01ce`) có `DISK USAGE` **1.67 GB** và `CONTENT SIZE` **426 MB**, theo kết quả đo trong terminal.

### Exercise 2.3 — Multi-stage build

- Stage `builder` dùng `python:3.11-slim`, cài công cụ build như `gcc` và `libpq-dev`, rồi cài các package Python.
- Stage `runtime` dùng `python:3.11-slim`, sao chép các package đã cài và mã ứng dụng, rồi chạy Uvicorn bằng user `appuser`.
- Image cuối nhỏ hơn nhờ base image slim và chỉ mang theo các package cần khi chạy. Công cụ build nằm ở stage đầu.

Kết quả đo bằng `docker images my-agent`:

| Image | Disk Usage | Content Size |
|---|---:|---:|
| `my-agent:develop` | 1.67 GB | 426 MB |
| `my-agent:advanced` | 240 MB | 57.4 MB |

Theo cột Content Size, bản advanced giảm **86.53%** so với bản develop: `(426 - 57.4) / 426 × 100`.

### Exercise 2.4 — Docker Compose và Nginx

```text
PowerShell → localhost:80 → nginx → agent:8000
                                     ├─ Redis:6379  (cache)
                                     └─ Qdrant:6333 (vector database)
```

Nginx nhận request từ máy host và chuyển tiếp đến `agent:8000` qua mạng bridge của Compose. Compose cấu hình địa chỉ Redis và Qdrant cho agent qua tên service, đồng thời đợi cả hai service qua health check trước khi chạy agent.

- `docker compose ps` hiển thị Redis và Qdrant ở trạng thái `healthy`.
- `GET http://localhost/health` trả `HTTP/1.1 200 OK`, header `Server: nginx` và JSON có `"status":"ok"`, `"version":"2.0.0"`.
- `POST http://localhost/ask` với JSON `{"question":"Explain microservices"}` trả `HTTP/1.1 200 OK`, header `Server: nginx` và trường `answer` từ mock LLM.

## Part 3 — Cloud Deployment

Agent dùng cấu hình [Railway của Part 6](06-lab-complete/railway.toml). Còn chờ URL public và kết quả kiểm tra `/health`, `/ready` và `/ask` để điền vào `DEPLOYMENT.md`.

## Part 4 — API Security

### Exercise 4.1 — API key

`POST /ask` trên `localhost:8003` với JSON `{"question":"Hello"}`:

```text
Thiếu header X-API-Key → HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

Sai API key → HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

Đúng API key → HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

`verify_api_key()` đọc header `X-API-Key` và so sánh với giá trị cấu hình khi ứng dụng khởi động. Để đổi key, cập nhật biến `AGENT_API_KEY`, khởi động lại ứng dụng và cập nhật key ở client.

### Exercise 4.2 — JWT authentication

Đăng nhập bằng tài khoản mẫu `student` qua `POST /auth/token`. Server kiểm tra thông tin đăng nhập rồi trả `access_token`. Client gửi token trong header `Authorization: Bearer <token>` để server xác thực trước khi xử lý `/ask`.

Kết quả gọi `POST /ask` trên `localhost:8003` với câu hỏi `Explain JWT`: `HTTP/1.1 200 OK`, có câu trả lời từ mock LLM và `usage.requests_remaining: 9`.

### Exercise 4.3 — Rate limiting

Limiter dùng cửa sổ trượt 60 giây. Mỗi tài khoản có một hàng đợi timestamp trong bộ nhớ. Trước khi xét request mới, limiter loại các timestamp đã ra khỏi cửa sổ và đếm các request còn lại.

Role `user` có giới hạn 10 request/phút. Role `admin` được áp dụng limiter riêng với giới hạn 100 request/phút.

Trong vòng lặp 20 lần gọi `POST /ask` bằng JWT của `student`, request số 9 trả 200 với `requests_remaining: 0`. Request số 10 là lần đầu trả 429 vì lần gọi thành công ở Exercise 4.2 vẫn nằm trong cửa sổ 60 giây.

Trích phản hồi của request số 10:

```text
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 7

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":7}}
```

### Exercise 4.4 — Cost guard

Hàm `check_budget(user_id, estimated_cost)` trong `04-api-gateway/production/cost_guard.py` lưu chi phí theo khóa Redis `budget:<user_id>:<YYYY-MM>` với tháng tính theo UTC. Tháng mới dùng khóa riêng. Hàm trả `False` nếu tổng dự kiến vượt 10 USD. Nếu đủ ngân sách, hàm giữ trước chi phí và trả `True`.

Hàm dùng số thập phân cho tiền và giao dịch Redis `WATCH/MULTI/EXEC` để kiểm tra lại khi một request khác cập nhật cùng khóa. Rate limiter giới hạn số lượt gọi trong một khoảng thời gian. Cost guard giới hạn tổng chi phí, kể cả khi số lượt gọi còn trong giới hạn.

Kết quả gọi hàm trên Redis local với cùng một người dùng thử mới:

```text
9.90 USD -> True
0.10 USD -> True
0.01 USD -> False
```

Phép thử gọi trực tiếp hàm ngân sách tháng. Endpoint `/ask` của bản mẫu vẫn dùng bộ theo dõi ngân sách ngày có sẵn.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Health checks

Kết quả kiểm tra bản develop trên `localhost:8004`:

- `GET /health` trả `HTTP/1.1 200 OK` với `status: ok`, uptime 9,1 giây và mức dùng RAM 81,3%. Đây là liveness probe để kiểm tra ứng dụng còn hoạt động.
- `GET /ready` trả `HTTP/1.1 200 OK` với `{"ready":true,"in_flight_requests":1}`. Middleware đếm cả request `/ready` đang xử lý. Load balancer dùng readiness để quyết định có chuyển request vào instance hay không. Mã nguồn trả 503 khi cờ sẵn sàng tắt.

### Exercise 5.2 — Graceful shutdown

Chạy bản develop trong container Python Linux, xác nhận `os.name` là `posix`. Gửi `POST /ask?question=Long%20task` rồi gửi `SIGTERM` cho tiến trình Uvicorn sau 0,5 giây.

Log hiện `Shutting down`, sau đó request vẫn trả `HTTP/1.1 200 OK` cùng phản hồi từ mock LLM. Tiếp theo, ứng dụng ghi `Shutdown complete` và tiến trình kết thúc. Phép thử xác nhận request đang xử lý được hoàn thành trước khi server tắt.

### Exercise 5.3 — Stateless design

Mỗi instance có bộ nhớ riêng. Nếu lưu lịch sử hội thoại trong RAM, request tiếp theo có thể được Nginx chuyển sang một instance khác và instance đó không có lịch sử trước đó.

Bản production lưu session dưới khóa Redis `session:<session_id>` với TTL mặc định 3.600 giây. `save_session()` ghi nội dung đã tuần tự hóa, còn `load_session()` đọc lại bằng cùng khóa. Các instance dùng chung Redis có thể tiếp tục cùng một hội thoại. Bản mẫu có chế độ dự phòng lưu trong RAM, nên cần kiểm tra `storage: redis` khi chạy thử nhiều instance.

### Exercise 5.4 — Load balancing

Stack chạy với `docker compose -p k5-day14-scaling up -d --build --scale agent=3`. Gọi `GET http://localhost:8080/health` qua Nginx trả `HTTP/1.1 200 OK`, có header `X-Served-By: 172.19.0.3:8000` và JSON báo `storage: redis`, `redis_connected: true`.

Năm request của script lần lượt được xử lý bởi `instance-d9f71f`, `instance-7544ea`, `instance-1dec09`, `instance-d9f71f` và `instance-7544ea`. Kết quả xác nhận Nginx phân phối request qua cả ba instance.

### Exercise 5.5 — Kiểm tra session qua nhiều instance

Chạy `python test_stateless.py`. Script gửi 5 câu hỏi qua `POST /chat` với cùng một `session_id`, rồi đọc lại lịch sử. Output báo `Total requests: 5`, 3 instance và `Total messages: 10` gồm 5 câu hỏi và 5 câu trả lời. Các instance dùng chung Redis nên lịch sử vẫn đầy đủ dù request được chuyển qua nhiều instance.

Phép thử này xác nhận chia sẻ session giữa các instance đang chạy. Script của repo không dừng instance trong quá trình chạy.

## Part 6 — Production readiness

### Checklist Deliverable từ lần chạy trên Ubuntu WSL2

Người làm bài chạy `python check_production_ready.py` trong `06-lab-complete` bằng Python 3.11 trên Ubuntu WSL2, với Docker Engine 29.9.3 và Redis tạm do script tạo.

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 41/41 checks passed
🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Docker build trong 28 giây. Image đo được 273 MB và container trả 200 ở `/health`. Khi nhận SIGTERM, request đang xử lý vẫn trả 200 và tiến trình thoát với exit code 0. Phép thử `docker stop` hoàn tất trong 0,7 giây với exit code 0. Mục Public URL ready xác nhận cấu hình Railway và biến `PORT`.

## AI log

- Hỏi AI cách làm Part 1 trên PowerShell.
- AI đối chiếu đề với mã nguồn, giải thích bản develop nhận `question` qua query string và bản production nhận JSON, rồi soạn phần trả lời dựa trên ảnh kết quả.
- Người làm bài tự chạy hai phiên bản và gọi các endpoint trên `localhost:8000` và `localhost:8001`.
- Part 2: AI hướng dẫn build và chạy Docker trên PowerShell, giải thích Dockerfile và ghi lại kết quả. Người làm bài tự gọi API của container trên cổng `8002` và kiểm tra kích thước image bằng `docker images`.
- Người làm bài tự build image advanced, chạy Compose và kiểm tra hai endpoint qua Nginx. AI tính phần trăm giảm từ số đo và ghi lại kết quả trong ảnh terminal.
- Exercise 4.1: AI hướng dẫn thử ba trường hợp xác thực. Người làm bài tự chạy và xác nhận các mã 401, 403 và 200 trong terminal.
- Exercise 4.2: AI đối chiếu đường dẫn đăng nhập với mã nguồn. Người làm bài tự lấy JWT, lưu vào biến PowerShell và xác nhận `/ask` trả 200 khi dùng token.
- Exercise 4.3: AI hướng dẫn vòng lặp PowerShell và đối chiếu thuật toán trong mã nguồn. Người làm bài tự gọi API và ghi nhận phản hồi 429 trong terminal.
- Exercise 4.4: Người làm bài khởi động Redis và xác nhận `PONG`. AI triển khai hàm ngân sách tháng và chạy phép thử ba lần gọi trên Redis local.
- Exercise 5.1: AI hướng dẫn chạy bản develop và phân biệt liveness với readiness. Người làm bài tự gọi hai endpoint và xác nhận cả hai trả 200.
- Exercise 5.2: AI hướng dẫn cách thử SIGTERM trong container Linux. Người làm bài tự chạy và xác nhận mã 200 cùng log shutdown.
- Exercise 5.3–5.5: AI đối chiếu cách lưu session và hướng dẫn chạy Compose. Người làm bài tự chạy stack, gọi health check và chạy script kiểm tra lịch sử qua ba instance.
- Part 6: AI bổ sung cấu hình, health/readiness, log JSON, xác thực, rate limiting và cost guard dùng Redis, lifespan shutdown, Dockerfile, Compose và cấu hình Railway. AI chạy các phép thử trên workspace và hướng dẫn thiết lập Python 3.11 cùng quyền Docker trong Ubuntu WSL2. Người làm bài tự chạy script đầy đủ và xác nhận `PASS 12/12`.
