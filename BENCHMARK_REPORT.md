# Benchmark & Observability Report — Day 14

- **Họ tên** Nguyễn Tuấn Hiếu
- **Ngày chạy** 25/11/2026 (GMT+7)
- **Môi trường** Windows, Python 3.11, Docker Desktop. Load test chạy qua loopback. Các lượt eval đặt `MOCK_ERROR_RATE=0` để đo chất lượng câu trả lời.

## 1. SLO của agent

| SLI | Ngưỡng | Mục đích |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Giới hạn độ trễ của phần lớn request. |
| Error rate `/ask` | ≤ 2% | Giới hạn tỷ lệ request thất bại trong load test local. |
| Accuracy | ≥ 85% cho CI, 100% cho lần kiểm tra v2 sau khi sửa | Chặn giảm chất lượng trước khi merge. |

## 2. Benchmark hiệu năng

### Metrics của agent

Đã gọi `/ask` trên v2 và kiểm tra `/metrics`. `http_requests_total` là counter, `agent_in_flight_requests` là gauge và `http_request_duration_seconds` là histogram. Đã thêm histogram `agent_question_length_chars` và xác nhận một request tạo đúng một observation với giá trị bằng số ký tự của câu hỏi. Các lượt load test ở dưới được đo trước khi bổ sung histogram này.

Label `route` dùng mẫu đường dẫn và gom URL không khớp vào `unmatched`. Dùng từng URL thật cho label sẽ tạo nhiều chuỗi thời gian khi có URL động hoặc lượt quét URL, làm tăng bộ nhớ và chi phí truy vấn Prometheus.

### 2.1 Concurrency

Mỗi lượt gửi 300 request với cùng ngưỡng SLO. Dữ liệu gốc nằm trong [reports](reports/).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.64 | 218.2 | 358.4 | 1724.2 | 1.00% | PASS |
| 10 | 27.68 | 257.9 | 559.8 | 1759.4 | 1.00% | FAIL |
| 50 | 14.27 | 2031.1 | 8593.7 | 13993.3 | 1.33% | FAIL |
| 100 | 28.33 | 1814.4 | 7639.1 | 9568.6 | 0.67% | FAIL |

RPS không tăng tuyến tính. Chỉ concurrency 1 đạt cả hai ngưỡng. Ở concurrency 50 và 100, p95 vượt 7 giây dù tỷ lệ lỗi vẫn dưới ngưỡng. Client và server chạy cùng máy, trong lúc Docker tải image và chuẩn bị stack. Kết quả mô tả lần đo này và chưa đủ để quy mức chậm cho riêng ứng dụng.

### 2.2 Tail latency

Giữ 300 request và concurrency 20 cho ba lượt.

| MOCK_SLOW_RATE | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 278.4 | 417.9 | 465.1 |
| 0.03 | 288.7 | 366.4 | 1691.1 |
| 0.1 | 492.4 | 1816.6 | 1954.9 |

Ở mức 0.03, avg chỉ tăng từ 278.4 lên 288.7 ms, trong khi p99 tăng lên 1691.1 ms. Khi mức chậm tăng lên 0.1, p95 cũng tăng mạnh. p95 và p99 giúp thấy tác động lên nhóm request chậm mà trung bình có thể che khuất.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 | v2 sau khi sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Avg tokens / câu | 57.5 | 109.0 | 113.7 |
| Tổng cost (USD) | 0.000410 | 0.000760 | 0.000791 |
| Cost / câu đúng (USD) | 0.00040995 | 0.00003619 | 0.00003438 |
| Latency p95 (ms) | 1671.2 | 240.4 | 268.8 |
| Quality gate | FAIL | PASS | PASS |

| ID | Từ khóa thiếu | Cách sửa |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Bổ sung đoạn giải thích JWT và API key. |
| scaling-03 | cpu, memory, custom metrics | Bổ sung đoạn giải thích các chỉ số Kubernetes HPA sử dụng. |

V2 dùng nhiều token hơn nhưng chi phí trên mỗi câu đúng giảm vì trả lời đúng nhiều hơn. Lần chạy cuối đạt 23/23 với 0 regression. Độ trễ p95 của mỗi lần eval còn chịu ảnh hưởng của latency giả lập và cỡ mẫu 23 câu.

Trong CI, khởi động v2 rồi chạy `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.85 --baseline reports/eval_v2.json`. Đặt job làm kiểm tra bắt buộc để chặn merge khi script trả exit code 1 do accuracy dưới ngưỡng hoặc regression.

## 4. Observability stack

### 4.1 Dashboard Grafana

Locust gửi request qua Nginx, Prometheus scrape `/metrics` trên các instance agent trong mạng Compose, và Grafana truy vấn Prometheus. Agent gửi span qua OTLP tới Jaeger. Trong [ảnh Grafana khi có tải](screenshots/grafana-dashboard.png), dashboard hiển thị bốn tín hiệu cho `POST /ask`: traffic 25,0 req/s, error rate 0,52%, latency p95 623,73 ms và saturation 18 request đang xử lý. Đây là ảnh chụp tại một thời điểm, còn CSV Locust tóm tắt toàn bộ thời gian chạy.

Trong cửa sổ 1 phút kết thúc lúc 17:46:50 (GMT+7) của lượt 3 replica, Prometheus báo avg 240,65 ms và p95 294,94 ms. Nginx chia tương đối đều, với 20,56, 20,36 và 20,75 req/s trên ba instance. Input đạt khoảng 4497,49 token/s và output đạt 2390,07 token/s. Prompt v2 mang thêm ngữ cảnh retrieval nên input dài hơn. Gọi `/metrics` qua Nginx trả 404 vì endpoint chỉ phục vụ scrape nội bộ.

### 4.2 Phân tích trace

- [Trace chậm](screenshots/jaeger-slow-trace.png), ID `20c269e588172fafb6a20db6ec9825c6`. Request mất 1703,603 ms. Span nghiệp vụ chậm nhất là `chat mock-llm-small`, 1684,133 ms, khoảng 98,9% tổng thời gian. Bước retrieval mất 17,496 ms.
- [Trace lỗi](screenshots/jaeger-error-trace.png), ID `0fb484085cbaf29b17c6652cc693ee85`. Request trả 503 sau 106,264 ms. Span gọi LLM mất 79,137 ms và ghi event `exception` với loại `utils.mock_llm.LLMError`.

Log từ các request tương ứng:

```jsonl
{"ts": "2026-11-25T10:44:05.028902+00:00", "level": "INFO", "service": "observable-agent", "instance": "6c006ce422e5", "event": "llm_call", "trace_id": "20c269e588172fafb6a20db6ec9825c6", "span_id": "e27ceb6cf517ac0f", "request_id": "ad925dbc2de7", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 4e-05, "llm_ms": 1683.0}
{"ts": "2026-11-25T10:44:04.564997+00:00", "level": "INFO", "service": "observable-agent", "instance": "6c006ce422e5", "event": "llm_error", "trace_id": "0fb484085cbaf29b17c6652cc693ee85", "span_id": "70b46c23cc99ce73", "request_id": "d5879b3a818d", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

### 4.3 Phát hiện giảm chất lượng

Nếu đổi từ v2 sang v1, request vẫn có thể trả HTTP 200 với latency thấp dù thiếu kiến thức cần thiết. Dùng eval định kỳ và trước mỗi lần deploy, so từng câu với baseline. Có thể theo dõi thêm tỷ lệ retrieval hit và đưa các câu hỏi canary vào kiểm tra để phát hiện giảm chất lượng sau deploy.

### 4.4 Kiểm tra alert

`promtool test rules /p/alert_rules_test.yml` báo `SUCCESS`. Sau hai lượt benchmark, đặt đồng thời `MOCK_ERROR_RATE=0.2` và `MOCK_SLOW_RATE=0.3` trên stack local, tạo tải bằng Locust với 30 user và kiểm tra trạng thái alert mỗi 5 giây. Thời gian dưới đây tính từ lúc bắt đầu áp dụng cấu hình đến lần quan sát đầu tiên thấy `firing`.

| Thay đổi | Alert | Thời gian | Chỉ số lúc phát hiện |
|---|---|---:|---:|
| `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 104 giây | 20,77% error rate |
| `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 157 giây | p95 1,893 giây |

Hai cảnh báo cùng xuất hiện trong [ảnh Alerts của Prometheus](screenshots/prometheus-alert-firing.png). Thời gian đo gồm khởi động lại agent, tích lũy dữ liệu scrape, khoảng `for` của từng rule và độ trễ lấy mẫu. Ảnh còn hiện cảnh báo chi phí, song phép thử này chỉ đo thời gian phát hiện của hai cảnh báo trong bảng.

## 5. Benchmark scaling

Locust chạy headless qua Nginx với 100 user, ramp-up 10 user/giây, thời lượng 2 phút. Dùng `docker compose run --no-deps` để lượt Locust giữ đúng số replica đã cấu hình. Bảng lấy dòng `POST /ask` từ [CSV 1 replica](benchmark-results/scale_1_stats.csv) và [CSV 3 replica](benchmark-results/scale_3_stats.csv).

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 1 | 59.41 | 200 | 380 | 1700 | 83 |
| 3 | 59.95 | 190 | 260 | 1700 | 85 |

Ba replica giảm p95 khoảng 31,6%, trong khi RPS tăng dưới 1%. Locust giữ nguyên 100 user và thời gian nghỉ giữa các request. Lượt chạy này cho thấy p95 được cải thiện dưới cùng một cấu hình tải. Cả hai lượt có p99 là 1700 ms, phù hợp với trace chậm cho thấy phần lớn thời gian nằm trong bước gọi mock LLM.

## 6. Kết luận

1. Đối chiếu throughput với p95, p99 và tỷ lệ lỗi để đánh giá tác động đến người dùng ở mỗi mức tải.
2. Dùng accuracy và chi phí trên mỗi câu đúng để đánh giá hiệu quả của retrieval.
3. Dùng cùng `trace_id` trong Jaeger và log JSON để lần từ request lỗi hoặc chậm đến span nghiệp vụ.

Khi triển khai thật, nên theo dõi thêm tỷ lệ timeout của upstream và độ trễ retrieval, đồng thời chạy eval canary để phát hiện giảm chất lượng sau deploy.
