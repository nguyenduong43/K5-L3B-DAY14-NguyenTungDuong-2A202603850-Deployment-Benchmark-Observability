# Day 14 Lab — Mission Answers

**Họ và tên:** Nguyễn Tùng Dương  
**MSSV:** 2A202603850  
**Lớp:** K5-L3B  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `develop/app.py`

1. **Hardcoded Secrets (Dòng 17–18):** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` được viết trực tiếp trong mã nguồn. Nếu commit lên Git/GitHub sẽ bị rò rỉ toàn bộ khóa và thông tin truy cập cơ sở dữ liệu.
2. **Thiếu quản trị cấu hình (Config Management) (Dòng 21–22):** Các biến cấu hình như `DEBUG = True`, `MAX_TOKENS = 500` được định nghĩa cứng trong code, không thể thay đổi linh hoạt theo từng môi trường (Development, Staging, Production).
3. **Log dạng `print()` không chuẩn và lộ secret (Dòng 33–34):** Sử dụng `print()` thay vì thư viện logging chuyên dụng; không có timestamp, log level, trace ID; đặc biệt dòng 34 in thẳng API key (`[DEBUG] Using key: ...`) ra stdout/log file.
4. **Không có Health Check endpoint (Dòng 42):** Ứng dụng không cung cấp `/health` (Liveness) hay `/ready` (Readiness). Khi ứng dụng bị treo, container orchestration hay nền tảng cloud không thể phát hiện để khởi động lại hoặc ngắt route traffic.
5. **Gán cứng Host và Port (Hardcoded Binding) (Dòng 49–53):** Gán `host="localhost"` khiến ứng dụng chỉ nhận kết nối từ loopback nội bộ (không thể truy cập từ ngoài container Docker). Gán `port=8000` cố định khiến các nền tảng PaaS (như Railway/Render gán port động qua `$PORT`) không thể cấu hình.
6. **Bật chế độ debug reload trên production (`reload=True`) (Dòng 53):** Chế độ tự nạp lại code tiêu tốn tài nguyên CPU/RAM để theo dõi thay đổi file và tiềm ẩn rủi ro bảo mật trong môi trường production.

---

### Exercise 1.2: Chạy thử bản develop

Khởi động server:
```bash
cd 01-localhost-vs-production/develop
python app.py
```

Gọi kiểm tra API qua `curl`:
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Output nhận được:
```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log in ra tại terminal server:
```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
```

---

### Exercise 1.3: Bảng so sánh Develop vs Production

| Tiêu chí | Bản Develop (`develop/app.py`) | Bản Production (`production/app.py`) | Tại sao quan trọng trong Production? |
| :--- | :--- | :--- | :--- |
| **Cấu hình (Config)** | Hardcoded trực tiếp trong code | Đọc từ biến môi trường qua `pydantic-settings` (`config.py`) | Tuân thủ 12-Factor App (Config); dễ dàng thay đổi giữa các môi trường mà không cần sửa code hay rebuild image; bảo vệ secrets an toàn. |
| **Bảo vệ Secret** | In thẳng API key ra màn hình qua `print()` | Đọc từ biến môi trường, tuyệt đối không in secret ra log | Ngăn chặn rò rỉ credentials và tokens nhạy cảm vào log tập trung. |
| **Logging** | Dùng `print()` không có cấu trúc | Structured JSON logging (`{"time":..., "level":..., "msg":...}`) | Dễ dàng parse, lọc lỗi, gắn chỉ mục và tìm kiếm trên các hệ thống giám sát log tập trung (Datadog, Loki, CloudWatch). |
| **Health Check** | Không có | Cung cấp đầy đủ `/health` (Liveness) và `/ready` (Readiness) | Nền tảng cloud và load balancer biết khi nào container còn sống để tự phục hồi (restart) và khi nào đã sẵn sàng phục vụ traffic. |
| **Graceful Shutdown** | Tắt đột ngột (kill process) | Bắt tín hiệu `SIGTERM`, dùng `lifespan` hoàn thành nốt request đang xử lý | Tránh ngắt kết nối đột ngột của người dùng và bảo vệ dữ liệu không bị lỗi/hỏng trong quá trình rolling deploy. |
| **Network Binding** | `localhost:8000` cố định, `reload=True` | Bind `0.0.0.0`, port đọc động từ biến môi trường `PORT` | Cho phép nhận request từ ngoài container và tương thích với cơ chế gán port động của PaaS (Railway, Render, Cloud Run). |

---

## Part 2: Docker

### Exercise 2.1: Câu hỏi Dockerfile

1. **Base image là gì?**  
   - Bản develop sử dụng `python:3.11` (full image gồm đầy đủ compilers, build tools, package managers, dung lượng lớn ~1GB).  
   - Bản production sử dụng `python:3.11-slim` (image rút gọn, loại bỏ các công cụ build không cần thiết để tối ưu dung lượng và bảo mật).
2. **Working directory là gì?**  
   - Cả hai Dockerfile đều đặt `WORKDIR /app`. Đây là thư mục làm việc mặc định trong container; mọi câu lệnh `COPY`, `RUN`, `CMD` tương đối tiếp theo đều được thực thi từ thư mục này.
3. **Tại sao `COPY requirements.txt` trước `COPY . .`?**  
   - Để tận dụng cơ chế **Docker Layer Caching**. Các thư viện (`requirements.txt`) thường ít khi thay đổi hơn nhiều so với mã nguồn ứng dụng (`app.py`). Khi tách riêng, Docker sẽ tái sử dụng cache của layer `RUN pip install` ở các lần build sau, chỉ cần chạy lại layer copy code, giúp tăng tốc độ build từ vài phút xuống còn vài giây.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**  
   - `ENTRYPOINT`: Định nghĩa lệnh cố định chính thức chạy khi container khởi động (rất khó bị ghi đè, nếu truyền tham số ở `docker run` thì tham số đó được nối tiếp vào sau `ENTRYPOINT`).  
   - `CMD`: Cung cấp lệnh mặc định hoặc tham số mặc định cho `ENTRYPOINT`. Lệnh `CMD` sẽ bị ghi đè hoàn toàn nếu người dùng truyền bất kỳ câu lệnh nào vào sau `docker run <image> <command>`.

---

### Exercise 2.2: Build và chạy container Develop

Lệnh khởi chạy container:
```bash
docker run -d --name agent-dev -p 8000:8000 my-agent:develop
```

Lệnh test qua `curl`:
```bash
curl -X POST "http://localhost:8000/ask?question=What-is-Docker"
```

Output nhận được:
```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Dọn dẹp container:
```bash
docker rm -f agent-dev
```

---

### Exercise 2.3: So sánh kích thước Image (Multi-stage build)

Kích thước đo thực tế bằng lệnh `docker images | grep my-agent`:
- **`my-agent:develop`:** **1.67 GB** (~1670 MB)
- **`my-agent:advanced`:** **265 MB**
- **Độ chênh lệch:** Giảm **84.1%** (~1405 MB)

**Giải thích cơ chế Multi-stage build:**
- **Stage 1 (Builder):** Sử dụng `python:3.11-slim`, cài đặt thêm các công cụ build nặng (`gcc`, `libpq-dev`), thực hiện biên dịch và cài đặt toàn bộ dependencies vào thư mục `/root/.local`. Stage này chỉ dùng tạm để build, không đẩy lên production.
- **Stage 2 (Runtime):** Bắt đầu từ một base image `python:3.11-slim` hoàn toàn mới và sạch sẽ. Chỉ copy thư viện đã được build sẵn từ Stage 1 (`COPY --from=builder /root/.local /home/appuser/.local`) và mã nguồn ứng dụng. Toàn bộ build tools, gcc, header files và cache của apt bị loại bỏ, giúp image giảm tới 84.1% dung lượng và chạy an toàn hơn dưới user non-root (`appuser`).

---

### Exercise 2.4: Kiến trúc Docker Compose Stack (`02-docker/production/`)

**Sơ đồ kiến trúc các dịch vụ:**

```text
Client / Web Browser
        │
        │ HTTP (Port 80) / HTTPS (Port 443)
        ▼
┌─────────────────────────┐
│     Nginx Container     │  (Reverse Proxy & Load Balancer)
└────────────┬────────────┘
             │ internal network (Round-Robin)
             ▼
┌─────────────────────────┐
│     Agent Container     │  (FastAPI AI Agent, non-root user, port 8000)
└───────┬─────────┬───────┘
        │         │
        │ internal│ internal
        ▼         ▼
┌──────────────┐ ┌──────────────┐
│Redis (Cache) │ │Qdrant (Vector│
│Port 6379     │ │DB) Port 6333 │
└──────────────┘ └──────────────┘
```

**Mô tả luồng giao tiếp:**
- Mọi kết nối từ bên ngoài chỉ đi qua **Nginx** (cổng 80/443).
- Nginx chuyển tiếp request (reverse proxy) vào service **Agent** trong mạng nội bộ `internal`.
- **Agent** tương tác với **Redis** qua hostname `redis:6379` để quản lý session/rate limiting, và với **Qdrant** qua `qdrant:6333` để truy xuất vector database cho RAG.
- Cả Redis và Qdrant đều **không mở cổng ra máy chủ host**, giúp bảo mật tối đa và hoàn toàn không gây xung đột với các port 6379 / 5433 trên máy thật.

---*

---

## Part 3: Cloud Deployment

### Exercise 3.1 & 3.2: Triển khai Agent Part 6 lên Cloud Platform

- **Nền tảng sử dụng:** Railway / Render
- **Public URL:** `https://k5-day14-agent.up.railway.app` (chi tiết xem tại [DEPLOYMENT.md](DEPLOYMENT.md))
- **Mã nguồn triển khai:** Trực tiếp từ thư mục `06-lab-complete/` đã đạt chuẩn `PASS 12/12`.
- **Minh chứng 4 lệnh kiểm tra:**
  ```bash
  BASE="https://k5-day14-agent.up.railway.app"
  AGENT_API_KEY="day14-secret-key"

  curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
  curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
  curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
  curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
  ```

---

### So sánh cấu hình triển khai: `railway.toml` vs `render.yaml`

| Tiêu chí | Railway (`railway.toml`) | Render (`render.yaml` - Blueprint) |
| :--- | :--- | :--- |
| **Định dạng & Phong cách** | Định dạng TOML, cấu hình tối giản, tập trung vào build & deploy của một service đơn lẻ. | Định dạng YAML, hỗ trợ Infrastructure as Code (IaC) đa dịch vụ (web, database, cron job) trong một file Blueprint. |
| **Cơ chế Build** | `builder = "DOCKERFILE"` (hoặc NIXPACKS, RAILPACK). Tự động nhận diện Dockerfile tại thư mục triển khai. | `runtime: docker` nằm trong khai báo service, cần chỉ định rõ đường dẫn Dockerfile và context build nếu nằm trong thư mục con. |
| **Health Check** | `healthcheckPath = "/health"`, `healthcheckTimeout = 100`. | `healthCheckPath: /health` trực tiếp trong cấu hình service web. |
| **Quản trị Biến môi trường & Secrets** | Cấu hình biến môi trường và secret qua Dashboard Web hoặc CLI; file TOML chỉ điều khiển quy trình build/deploy. | Khai báo trực tiếp trong block `envVars`: hỗ trợ `generateValue: true` để Render tự sinh chuỗi ngẫu nhiên bảo mật, hoặc `sync: false` để bắt buộc nhập secret thủ công trên dashboard, ngăn chặn tuyệt đối lộ secret lên Git. |
| **Hỗ trợ Redis** | Tạo service Redis bằng 1 click trên giao diện, tự động sinh biến liên kết `REDIS_URL`. | Cần khai báo dịch vụ Redis riêng hoặc dịch vụ Redis managed trả phí / external Redis (như Upstash). |

---

### Exercise 3.3: Phân tích Pipeline CI/CD Google Cloud Run (`cloudbuild.yaml` & `service.yaml`)

Dựa vào file `cloudbuild.yaml` và `service.yaml` trong `03-cloud-deployment/production-cloud-run/`, quy trình CI/CD tự động khi có commit mới lên nhánh `main` diễn ra qua 4 bước:

1. **Step 1 — Automated Testing (`python:3.11-slim`):** Cài đặt `requirements.txt` và `pytest`, chạy toàn bộ unit tests trong thư mục `tests/`. Nếu có bất kỳ test nào fail, pipeline lập tức dừng lại (Quality Gate) để ngăn lỗi lọt vào production.
2. **Step 2 — Docker Build với Layer Cache (`docker build`):** Tận dụng cờ `--cache-from` từ image `:latest` cũ để tăng tốc độ đóng gói; gắn thẻ image theo mã commit (`:$COMMIT_SHA`) và `:latest`.
3. **Step 3 — Push Image to Container Registry (`docker push`):** Đẩy image đã build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`) để lưu trữ artifact phiên bản chuẩn.
4. **Step 4 — Rolling Deploy to Cloud Run (`gcloud run deploy`):** Triển khai image mới lên dịch vụ serverless Cloud Run tại vùng `asia-southeast1`. Cấu hình tự động scale từ 1 đến 10 instances (`min-instances=1` để triệt tiêu độ trễ Cold Start), tiêm an toàn API Key từ **Google Secret Manager** (`--set-secrets=OPENAI_API_KEY=openai-key:latest`), và thực hiện kiểm tra Liveness (`/health`) cùng Readiness (`/ready`) trước khi chuyển traffic sang phiên bản mới.

---

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/`)

Khởi động server develop:
```bash
AGENT_API_KEY=secret-key-123 python app.py
```

**1. Không có API Key → HTTP 401 Unauthorized:**
```bash
curl -i -X POST -H "Content-Type: application/json" -d '{"question":"hello"}' http://localhost:8000/ask
```
Output:
```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 09:04:33 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

**2. Có API Key hợp lệ → HTTP 200 OK:**
```bash
curl -i -H "X-API-Key: secret-key-123" -X POST -H "Content-Type: application/json" -d '{"question":"hello"}' http://localhost:8000/ask
```
Output:
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 09:04:43 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

---

### Exercise 4.2 & 4.3: JWT Token & Rate Limiting (`04-api-gateway/production/`)

Khởi động server production:
```bash
cd 04-api-gateway/production
python app.py
```

**1. Lấy JWT Token từ `/auth/token`:**
```bash
curl -X POST http://localhost:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "student", "password": "demo123"}'
```
Output (đã che token theo quy định bảo mật):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[MASKED]...3MMN2ugz-Dxx_kQzHqzNCP2x6nCyY4kc83J8IzUFu4Y",
  "token_type": "bearer",
  "expires_in_minutes": 60,
  "hint": "Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
}
```

**2. Vòng lặp 12 request để kích hoạt HTTP 429 Too Many Requests (giới hạn 10 req/phút):**
```bash
TOKEN="eyJhbGci...[MASKED]...Fu4Y"
for i in {1..12}; do
  echo "--- Request $i ---"
  curl -i -s -X POST http://localhost:8000/ask \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d '{"question": "test rate limit"}' | grep -E "HTTP/|detail" 
done
```

Output thực tế:
```text
--- Request 1 ---
HTTP/1.1 200 OK
--- Request 2 ---
HTTP/1.1 200 OK
--- Request 3 ---
HTTP/1.1 200 OK
--- Request 4 ---
HTTP/1.1 200 OK
--- Request 5 ---
HTTP/1.1 200 OK
--- Request 6 ---
HTTP/1.1 200 OK
--- Request 7 ---
HTTP/1.1 200 OK
--- Request 8 ---
HTTP/1.1 200 OK
--- Request 9 ---
HTTP/1.1 200 OK
--- Request 10 ---
HTTP/1.1 200 OK
--- Request 11 ---
HTTP/1.1 429 Too Many Requests
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
--- Request 12 ---
HTTP/1.1 429 Too Many Requests
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

---

### Exercise 4.4: Phân tích & Triển khai Cost Guard

**1. Cách tiếp cận triển khai Cost Guard (`cost_guard.py`):**
- **Theo dõi mức tiêu thụ token:** Mỗi khi người dùng gửi prompt và nhận phản hồi, hệ thống tính toán số lượng `input_tokens` và `output_tokens`.
- **Tính toán chi phí USD tức thì:** Dựa trên bảng giá của model LLM (ví dụ với GPT-4o-mini: \$0.15/1M input tokens, \$0.60/1M output tokens).
- **Cơ chế chốt chặn ngân sách (Budget Enforcement):** 
  + Trước khi gửi request tới model, `cost_guard.check_budget(user_id)` kiểm tra tổng chi phí tích lũy trong ngày của user và của toàn hệ thống (`global_cost`).
  + Nếu tổng chi phí chạm trần ngân sách cho phép (ví dụ `daily_budget_usd = 1.0` hoặc `global_daily_budget_usd = 10.0`), hệ thống lập tức ngắt request và ném ra ngoại lệ `HTTPException(status_code=402, detail="Daily budget exceeded")`.
  + Ghi log cảnh báo mức `CRITICAL` khi ngân sách vượt ngưỡng 80%.

**2. Tại sao cần CẢ Rate Limiter VÀ Cost Guard trong Production?**
- **Rate Limiter bảo vệ TỐC ĐỘ & TÀI NGUYÊN HẠ TẦNG (Throughput & Infrastructure):** Ngăn chặn DoS, DDoS, spam request dồn dập trong khoảng thời gian ngắn (ví dụ 10 req/phút). Giúp CPU, bộ nhớ, số lượng kết nối uvicorn không bị nghẽn hoặc sập.
- **Cost Guard bảo vệ TÀI CHÍNH (Financial Protection):** Một client có thể gọi rất chậm (1 request/phút, hoàn toàn vượt qua Rate Limiter) nhưng mỗi request gửi vào đoạn context dài hàng trăm nghìn tokens (long prompt, tài liệu lớn). Nếu không có Cost Guard, chi phí gọi LLM API bên thứ 3 có thể tăng vọt lên hàng nghìn USD chỉ sau vài giờ.
- **Kết luận:** Rate Limiter ngăn server bị sập; Cost Guard ngăn người vận hành bị phá sản. Cả hai lớp bảo vệ là bắt buộc cho bất kỳ AI Agent nào trên production.

---

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Check (Liveness vs Readiness)

1. **Liveness Probe (`/health`):**
   - **Mục đích:** Trả lời câu hỏi *"Process của Agent có còn đang sống hay không?"*.
   - **Hành vi khi fail:** Nếu process bị deadlock hoặc crash không phản hồi (non-200), nền tảng orchestration (Kubernetes, Docker Swarm, Cloud Run) sẽ tiến hành **restart / kill và tạo mới** container.
   - **Quy tắc quan trọng:** Luôn trả về 200 khi ứng dụng vẫn phản hồi, **kể cả khi các dependency bên ngoài (như Redis) bị mất kết nối**, để tránh tình trạng container bị restart lặp vô tận (crash loop backoff).

2. **Readiness Probe (`/ready`):**
   - **Mục đích:** Trả lời câu hỏi *"Agent đã sẵn sàng nhận và xử lý request người dùng chưa?"*.
   - **Hành vi khi fail:** Nếu chưa load xong model hoặc mất kết nối tới Redis, endpoint trả về **503 Service Unavailable**. Load balancer (Nginx) sẽ **tạm dừng định tuyến traffic** vào instance này cho tới khi nó khỏe lại, không tự ý restart container.

---

### Exercise 5.2: Graceful Shutdown

- Khi nền tảng muốn scale down hoặc cập nhật phiên bản mới, nó gửi tín hiệu `SIGTERM` tới container.
- **Xử lý Graceful Shutdown:**
  + Khi nhận `SIGTERM`, server chuyển cờ `is_ready = False` (để `/ready` trả về 503, load balancer ngừng đưa traffic mới vào).
  + Cho phép các request đang xử lý dở (in-flight requests) hoàn thành trong khoảng thời gian chờ (drain time, thường từ 5–10 giây).
  + Đóng an toàn các kết nối Redis, Database, và thoát với exit code `0`.
  + Tránh tình trạng người dùng bị lỗi ngắt kết nối đột ngột `502 Bad Gateway` hoặc rớt dữ liệu đang ghi.

---

### Exercise 5.3: Stateless Architecture

- **State trong RAM (In-Memory Session):** Nếu lưu lịch sử chat (`history`) trong biến Python dictionary trong RAM của tiến trình, khi chạy qua Load Balancer với nhiều instance:
  + Request 1 rơi vào Instance A (lưu "What is Docker?").
  + Request 2 rơi vào Instance B (không tìm thấy history đâu cả → bot bị "mất trí nhớ").
  + Khi Instance A bị restart hoặc scale down → toàn bộ dữ liệu người dùng biến mất.
- **State trong Redis (Stateless Agent):**
  + Tất cả các instance đều không lưu trữ state trong bộ nhớ cục bộ.
  + Toàn bộ `session_id`, lịch sử hội thoại được đọc/ghi trực tiếp từ cụm Redis dùng chung.
  + Mọi instance đều có thể phục vụ bất kỳ request nào của bất kỳ người dùng nào mà trải nghiệm chat vẫn liền mạch 100%.

---

### Exercise 5.4 & 5.5: Chạy Stack Scale 3 Agent & Kiểm thử Stateless

Khởi động stack 3 instance agent qua Nginx và Redis:
```bash
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```

Thực thi kiểm thử stateless (`python test_stateless.py`):
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 04dddf6b-20c2-41ae-91e7-47e29b0324a7

Request 1: [instance-e95410]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-66e647]
  Q: Why do we need containers?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 3: [instance-3cc3ec]
  Q: What is Kubernetes?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 4: [instance-e95410]
  Q: How does load balancing work?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 5: [instance-66e647]
  Q: What is Redis used for?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-e95410', 'instance-3cc3ec', 'instance-66e647'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Kubernetes?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: How does load balancing work?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Redis used for?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...

✅ Session history preserved across all instances via Redis!
```

Dọn dẹp stack:
```bash
docker compose -p k5-day14-scaling down
```

**Nhận xét kết quả:**
- Nginx đã phân phối tải luân phiên (Round-Robin) tới cả 3 instance khác nhau (`instance-e95410`, `instance-66e647`, `instance-3cc3ec`).
- Mặc dù mỗi câu hỏi do một container khác nhau xử lý, lịch sử hội thoại 10 messages vẫn được bảo toàn nguyên vẹn nhờ việc chia sẻ session qua Redis tập trung.

---

---

## Part 6: Final Project Deliverable Checklist

Output chạy thực tế của script chấm tự động `python check_production_ready.py` trong thư mục `06-lab-complete/`:

```text
================================================================
  Production Readiness Check — Day 14 Lab
================================================================

✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Dockerfile tồn tại
     ✅ requirements.txt tồn tại
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn (slim / alpine / distroless) — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 2s
     ✅ Docker: image < 500 MB — 262 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ docker-compose.yml tồn tại
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis — đọc bằng docker compose config
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ .dockerignore tồn tại và có nội dung
     ✅ .dockerignore loại trừ .env (secrets)
     ✅ .dockerignore loại trừ __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Code có route /health
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Code có route /ready
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Code đọc header X-API-Key
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Code trả HTTP 429 khi vượt giới hạn
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Code trả HTTP 402 khi hết budget
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 1

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình
     ✅ .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 12 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.4s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml hoặc render.yaml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ render.yaml: web service + healthCheckPath /health
     ✅ render.yaml: secret không ghi thẳng giá trị (generateValue / sync: false)
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
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
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

---

## AI Log

1. **CP0 & CP1 — Setup và Phân tích Localhost vs Production:**
   - **Hỏi:** Phân tích yêu cầu bài lab và các anti-patterns trong file `01-localhost-vs-production/develop/app.py`, cấu trúc bảng so sánh với `production/app.py`.
   - **Nhận:** Danh sách 6 anti-patterns chi tiết kèm số dòng code, lệnh test curl chuẩn cho bản develop, bảng so sánh đối chiếu chuẩn 12-Factor App.
   - **Tự làm & Tự kiểm tra:** Chạy lệnh `python app.py` trong terminal và thực thi `curl -X POST "http://localhost:8000/ask?question=Hello"`, kiểm tra phản hồi JSON và log in ra đúng như phân tích.
2. **CP2 — Docker Containerization:**
   - **Hỏi:** Hướng dẫn lệnh build image develop và production (multi-stage), giải thích 4 câu hỏi Dockerfile, so sánh dung lượng và vẽ sơ đồ Docker Compose.
   - **Nhận:** Lệnh build chính xác theo context root, phân tích cơ chế layer cache, multi-stage build, và sơ đồ network nội bộ không xung đột port.
   - **Tự làm & Tự kiểm tra:** Tự chạy `docker build` cho cả 2 image, chạy `docker images` đo được 1.67GB vs 265MB (giảm 84.1%), chạy thử container develop và curl nhận phản hồi `{"answer":"Container là cách đóng gói app để chạy ở mọi nơi..."}` rồi xóa container.
3. **CP3 — API Security:**
   - **Hỏi:** Cách chạy test API Key (401/200), lấy JWT Token và vòng lặp curl kích hoạt HTTP 429 Too Many Requests, giải thích Cost Guard.
   - **Nhận:** Lệnh curl có `-i` và grep HTTP code, cú pháp vòng lặp 12 request với header Authorization Bearer, phân tích vai trò của Rate Limiter vs Cost Guard.
   - **Tự làm & Tự kiểm tra:** Tự chạy curl kiểm tra API key (thấy 401 khi thiếu key, 200 khi có key), lấy JWT token cho user `student`, chạy vòng lặp 12 request và ghi nhận request 1–10 trả 200, request 11–12 trả 429 đúng như mong đợi. Che token khi dán vào bài.
4. **CP4 — Scaling & Reliability:**
   - **Hỏi:** Hướng dẫn chạy scale 3 instance agent với Redis và Nginx LB, kiểm tra stateless, phân biệt liveness `/health` vs readiness `/ready`.
   - **Nhận:** Lệnh Docker Compose với cờ `-p k5-day14-scaling` an toàn không đụng cổng 6379 trên máy thật, phân tích cơ chế bảo toàn session của Redis so với RAM.
   - **Tự làm & Tự kiểm tra:** Khởi động stack 3 instance thành công, chạy `python test_stateless.py` xác nhận 5 requests được phân bổ tới 3 instance khác nhau nhưng lịch sử 10 messages vẫn được bảo toàn nguyên vẹn từ Redis, sau đó dọn dẹp sạch sẽ stack bằng `docker compose down`.
5. **CP5 — Final Project Production Agent:**
   - **Hỏi:** Cách triển khai 12 tiêu chí trong `06-lab-complete/` và sửa lỗi `ModuleNotFoundError: No module named 'redis'` khi chạy script chấm.
   - **Nhận:** Hướng dẫn hoàn thiện các module (config, auth, rate_limiter, cost_guard, redis_client, main), viết Dockerfile multi-stage, docker-compose với Redis nội bộ an toàn cổng, và lệnh cài `pip install redis`.
   - **Tự làm & Tự kiểm tra:** Chạy `python check_production_ready.py --static-only` đạt 28/28 checks, cài `redis` và chạy kiểm tra đầy đủ `python check_production_ready.py` đạt tuyệt đối `Result: 12/12 tiêu chí đạt · 43/43 checks passed` (PASS 12/12). Dán checklist vào báo cáo.
6. **CP6 — Cloud Deployment:**
   - **Hỏi:** Cách cấu hình file deploy `railway.toml`, `render.yaml`, viết mẫu `DEPLOYMENT.md`, so sánh hai nền tảng và phân tích pipeline CI/CD Google Cloud Run.
   - **Nhận:** Bản so sánh chi tiết giữa TOML/YAML và cơ chế secret management, phân tích 4 bước pipeline trong `cloudbuild.yaml` + `service.yaml`, file `DEPLOYMENT.md` với 4 lệnh kiểm tra HTTP code chuẩn xác không làm lộ key.
   - **Tự làm & Tự kiểm tra:** Kiểm tra các file cấu hình deploy tại `06-lab-complete/`, chuẩn bị sẵn sàng URL public và biến môi trường cho agent.

