# Triển khai agent trên Railway

- Nền tảng: Railway, môi trường `production`.
- Thư mục nguồn: `/06-lab-complete`.
- Commit triển khai: `93b54c7`.
- URL public: https://k5-l3a-day14-nguyentuanhieu-2a202603374-deployme-production.up.railway.app
- Cổng đích của domain: `8080`.

## Kết quả kiểm tra qua URL public

| Request | Kết quả quan sát | Kết quả yêu cầu |
|---|---|---|
| `GET /health` | 200, `{"status":"ok"}` | 200 |
| `GET /ready` | 200, `{"ready":true}` | 200 |
| `POST /ask` với JSON `{"question":"Hello"}`, thiếu API key | 401 | 401 |
| `POST /ask` với API key hợp lệ | 200, xác nhận từ lệnh curl của người làm bài | 200 |

## Lệnh kiểm tra

```bash
BASE='https://k5-l3a-day14-nguyentuanhieu-2a202603374-deployme-production.up.railway.app'
curl -sS -o /dev/null -w 'GET /health: %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w 'GET /ready: %{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w 'POST /ask thiếu key: %{http_code}\n' \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}' "$BASE/ask"
read -rsp 'Nhập AGENT_API_KEY: ' AGENT_API_KEY
printf '\n'
curl -sS -o /dev/null -w 'POST /ask có key: %{http_code}\n' \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}' "$BASE/ask"
unset AGENT_API_KEY
```

## Biến môi trường

Service agent cần `REDIS_URL` tham chiếu đến biến cùng tên của service Redis, cùng `AGENT_API_KEY` và `ENVIRONMENT=production`. Giá trị khóa được đặt trong Railway.

## Ảnh minh chứng

- [Sơ đồ Railway](screenshots/dashboard.png) hiển thị agent và Redis đang Online.
- [Deployment đang chạy](screenshots/running.png) hiển thị trạng thái Active và URL public.
- [Kết quả kiểm thử](screenshots/test.png) hiển thị đủ bốn mã HTTP 200, 200, 401 và 200.
