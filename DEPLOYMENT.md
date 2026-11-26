# Deployment Information

## Public URL
https://k5-day14-agent.up.railway.app

## Platform
Railway (hoặc Render)

## Test Commands

### 1. Health Check (Liveness)
```bash
curl https://k5-day14-agent.up.railway.app/health
# Expected: {"status":"ok"} (HTTP 200)
```

### 2. Readiness Check
```bash
curl https://k5-day14-agent.up.railway.app/ready
# Expected: {"status":"ready"} (HTTP 200 khi Redis kết nối thành công)
```

### 3. API Test — Thiếu hoặc sai API Key (Bảo mật)
```bash
curl -i -X POST https://k5-day14-agent.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP/1.1 401 Unauthorized
```

### 4. API Test — Có API Key hợp lệ
```bash
curl -i -X POST https://k5-day14-agent.up.railway.app/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP/1.1 200 OK
```

## 4 Lệnh Tự Kiểm Tra (In HTTP Code, không lộ key)
```bash
BASE="https://k5-day14-agent.up.railway.app"
AGENT_API_KEY="day14-secret-key"

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

## Environment Variables Set trên Platform
- `PORT`: 8000
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: Key bí mật cấu hình trên dashboard platform
- `REDIS_URL`: Chuỗi kết nối tới cloud Redis instance
- `RATE_LIMIT_PER_MINUTE`: 10
- `DAILY_BUDGET_USD`: 10.0

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
