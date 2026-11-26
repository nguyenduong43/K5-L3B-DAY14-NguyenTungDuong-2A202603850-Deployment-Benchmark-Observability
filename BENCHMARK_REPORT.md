# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Tùng Dương  
**MSSV:** 2A202603850  
**Lớp:** K5-L3B  
**Ngày chạy:** 2026-11-26  
**Môi trường:** macOS Apple Silicon (ARM64), Docker Desktop  

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo trải nghiệm người dùng tương tác thời gian thực không bị trễ quá lâu (dưới nửa giây) cho 95% request. |
| Error rate `/ask` | < 2.0 % | Cho phép tối đa 2% lỗi (5xx) do mạng/sự cố tạm thời, bảo vệ error budget 98% thành công. |
| Accuracy trên golden dataset | ≥ 90 % | Đảm bảo agent trả lời chính xác kiến thức chuyên môn, ngăn chặn regression khi release. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.00 | 196.1 | 230.0 | 1717.6 | 1.00% | PASS |
| 10 | 36.76 | 190.5 | 222.6 | 1710.1 | 0.00% | PASS |
| 50 | 105.76 | 195.1 | 230.7 | 1689.1 | 0.67% | PASS |
| 100 | 63.12 | 295.6 | 2867.8 | 3643.1 | 0.67% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- **RPS không tăng tuyến tính mãi mãi:** Từ concurrency 1 lên 10 và 50, RPS tăng mạnh từ 4.00 lên 36.76 và đạt đỉnh ở 105.76 RPS. Tuy nhiên, khi tăng tiếp lên 100 concurrency, RPS không tăng mà bị tụt xuống còn 63.12 RPS.
- **Nguyên nhân:** Do giới hạn tài nguyên của 1 process uvicorn đơn lẻ (CPU và event loop queue saturation). Khi có quá nhiều request đồng thời (c=100), hàng đợi bị nghẽn dẫn đến độ trễ xếp hàng (queuing delay) tăng vọt, p95 nhảy từ 230.7 ms lên 2867.8 ms (gấp hơn 12 lần) và vi phạm SLO (< 500 ms). Điều này chứng minh sự cần thiết của việc scale ngang nhiều instance qua Load Balancer (đã học ở Part 5).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.5 | 218.1 | 233.4 |
| 0.03 (mặc định) | 220.0 | 220.4 | 1684.0 |
| 0.1 | 325.8 | 1689.3 | 1720.0 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **Chỉ số nhạy nhất với request chậm:** Là **p95** và đặc biệt là **p99**. Khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.1 (tức là 10% request bị chậm giả lập):
  - Giá trị trung bình (`avg`) chỉ tăng từ 191.5 ms lên 325.8 ms (tăng 1.7 lần), nhìn qua vẫn có vẻ "chấp nhận được".
  - Trong khi đó, **p95** tăng vọt từ 218.1 ms lên 1689.3 ms (gấp gần 8 lần), và **p99** nhảy từ 233.4 ms lên 1720.0 ms (gấp 7.4 lần).
- **Vì sao SLO không nên đặt theo average:** Giá trị trung bình (average) bị làm phẳng (masking effect) bởi đại đa số các request nhanh (90–97% request hoàn thành trong ~190ms kéo con số trung bình xuống thấp). Nếu chỉ nhìn vào average, hệ thống trông có vẻ khỏe mạnh trong khi thực tế 5% đến 10% khách hàng đang phải trải qua trải nghiệm rất tệ (chờ gần 2 giây). Do đó, SLO luôn phải dựa trên các phân vị cao như **p95 hoặc p99** để bảo vệ trải nghiệm của mọi người dùng và cảnh báo sớm các vấn đề nghẽn cổ chai (tail latency).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 58.0 | 109.0 | 114.7 |
| Tổng cost (USD) | $0.000417 | $0.000759 | $0.000799 |
| Cost / câu đúng (USD) | $0.00041655 | $0.00003616 | $0.00003475 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "api key", "xác thực"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` giải thích JWT là token có chữ ký số và thời hạn hết hạn, khác API key tĩnh. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["kubernetes", "hpa", "kubernetes hpa"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` giải thích Kubernetes HPA tự động scale pod dựa trên CPU, memory và custom metrics từ Prometheus. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Chất lượng (Accuracy):** Agent v2 vượt trội hoàn toàn so với v1 (Accuracy nhảy vọt từ 4.3% lên 91.3% và đạt 100% sau khi hoàn thiện Knowledge Base). V1 do không có cơ chế retrieval nên chỉ trả lời được câu cơ bản và liên tục fail các câu hỏi chuyên sâu.
- **Chi phí (Cost):** V2 tiêu thụ nhiều token hơn (114.7 tokens/câu so với 58.0 tokens/câu của v1) do prompt phải kèm context tài liệu tìm được. Tổng chi phí chạy 23 câu tăng từ $0.000417 lên $0.000799 (~1.9 lần). Tuy nhiên, xét trên chỉ số cốt lõi **Cost / câu đúng**, v2 rẻ hơn v1 tới **12 lần** ($0.00003475 so với $0.00041655), chứng minh chi phí của v1 gần như bị lãng phí hoàn toàn vào câu trả lời sai.
- **Độ trễ (Latency):** V2 có độ trễ p50 cao hơn v1 (~195ms so với ~168ms) do tốn thêm thời gian truy xuất tài liệu (retrieval latency simulated ~20ms). Đây là sự đánh đổi kinh điển và hoàn toàn xứng đáng của kiến trúc RAG: chấp nhận tăng một phần nhỏ độ trễ và chi phí prompt để đổi lấy độ chính xác tin cậy (tránh hallucination).

**Quality gate trong CI/CD:**
- Khi chạy eval với baseline của phiên bản trước: `python eval/run_eval.py --url http://agent-url --baseline reports/eval_v2.json`
- Nếu phiên bản mới bị giảm accuracy hoặc có regression (câu từng đúng nay bị sai), script sẽ trả về **exit code = 1**, từ đó làm fail bước workflow trong GitHub Actions và tự động chặn merge PR vào production.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) (`screenshots/grafana-dashboard.png`)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) (`screenshots/jaeger-slow-trace.png`)
- [x] Một trace lỗi trong Jaeger (có event `exception`) (`screenshots/jaeger-error-trace.png`)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** (`screenshots/prometheus-alert-firing.png`)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1 phút (đúng cấu hình `for: 1m`) | Error rate (chuyển sang màu đỏ) & Requests/s theo status code (cột 503 tăng) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2 phút (đúng cấu hình `for: 2m`) | Latency p95/p99 (vượt ngưỡng 1s) & LLM latency p95 theo model |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~2 phút (đúng cấu hình `for: 2m`) | Cost burn rate (USD/giờ tăng vọt vượt ngưỡng $2/h) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~30 giây (đúng cấu hình `for: 30s`) | Instances up (giảm từ 2 xuống 1, ô màu đỏ) |
| E | `AGENT_VERSION=v1` | *Không có alert nào firing* | Không firing | Retrieval hit ratio (tụt về 0%), Tokens/s giảm, Bảng version đổi sang v1 |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- **Nguyên nhân không firing:** Agent v1 vẫn phục vụ HTTP 200 OK với latency nhanh và error rate 0%, nên tất cả Golden Signals của hạ tầng (traffic, latency, error, saturation) đều xanh hoàn hảo. Lỗi ở đây là **lỗi chất lượng logic/nội dung (semantic degradation)**, hạ tầng không thể biết câu trả lời đúng hay sai.
- **Cách phát hiện trong production:**
  1. **Chạy Synthetic Eval định kỳ (Canary Testing):** Chạy tự động script `eval/run_eval.py` trên golden dataset vào hệ thống production định kỳ (ví dụ mỗi 15 phút một lần hoặc ngay sau mỗi lần deploy Canary) để phát hiện sớm accuracy sụt giảm.
  2. **Giám sát Business/Semantic Metrics:** Thiết lập alert trên metric nghiệp vụ riêng của agent, ví dụ `rate(agent_retrieval_total{result="hit"}[5m]) == 0` (khi v1 chạy, không có retrieval hit nào xảy ra) hoặc theo dõi độ dài token phản hồi trung bình.
  3. **User Feedback Signals:** Thu thập và theo dõi tỉ lệ tương tác của người dùng (tỉ lệ dislike/thumbs-down, tỉ lệ người dùng hỏi lại nhiều lần, hoặc chỉ số CSAT).

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `f56222bb6f2774c36039fd49d599e5e7`
- Tổng thời gian: `1716.2` ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1689.9` ms, `98.5%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T13:35:41.598580+00:00", "level": "INFO", "service": "observable-agent", "instance": "8abd1d686a13", "event": "llm_call", "trace_id": "f56222bb6f2774c36039fd49d599e5e7", "span_id": "298521b0698583c1", "request_id": "fb2a754e195f", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 76, "output_tokens": 39, "cost_usd": 3.5e-05, "llm_ms": 1689.9}
{"ts": "2026-11-26T13:35:41.599460+00:00", "level": "INFO", "service": "observable-agent", "instance": "8abd1d686a13", "event": "http_request", "trace_id": "f56222bb6f2774c36039fd49d599e5e7", "span_id": "298521b0698583c1", "request_id": "fb2a754e195f", "method": "POST", "route": "/ask", "status": 200, "ms": 1716.2}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 65.80 | 190 | 230 | 1700 | 67 (0.85%) |
| 3 | 66.20 | 190 | 220 | 1700 | 79 (1.00%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- **Scale không làm giảm đáng kể p95 hay tăng vọt RPS:** Khi scale từ 1 instance lên 3 instance, tổng RPS duy trì quanh mức ~66 req/s (65.80 lên 66.20 req/s), latency p50 giữ nguyên 190 ms, p95 giảm rất nhẹ từ 230 ms xuống 220 ms, và p99 không đổi ở mức 1700 ms.
- **Nút thắt (Bottleneck) nằm ở đâu:** Nút thắt không nằm ở năng lực xử lý CPU/RAM của agent container hay Load Balancer Nginx, mà nằm ở **thời gian phản hồi của dịch vụ ngoại vi Upstream LLM** (trong bài là mock LLM mô phỏng API call tới nhà cung cấp mô hình AI với base latency 120ms + jitter + 3% tail latency 1700ms).
- **Ý nghĩa kiến trúc:** Trong các ứng dụng AI Agent, phần lớn thời gian request là I/O bound (chờ LLM stream/generate token). Việc scale ngang nhiều instance giúp phân tán tải và tăng khả năng chịu tải đồng thời khi lượng người dùng bùng nổ, nhưng **không thể rút ngắn thời gian xử lý vốn có của LLM provider**. Muốn cải thiện p95/p99 ở tầng này, giải pháp phải là: tối ưu prompt ngắn hơn, dùng model nhỏ hơn/nhanh hơn, streaming response, caching ngữ nghĩa (semantic cache), hoặc đặt timeout/fallback linh hoạt.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **SLO phải đặt theo Percentile (p95/p99) thay vì Average:** Con số trung bình (average) che giấu đuôi trễ nguy hiểm (tail latency). Một hệ thống có latency trung bình ~200ms vẫn có thể có 5–10% khách hàng phải chờ tới gần 2 giây. Đo lường bằng p95/p99 phản ánh trung thực trải nghiệm người dùng thực tế và phát hiện sớm các điểm nghẽn downstream.
  2. **Benchmark chất lượng (Eval trên Golden Dataset) là Quality Gate cốt lõi:** Với AI Agent, hệ thống chạy nhanh nhưng trả lời sai là vô nghĩa. Đo lường accuracy trên golden dataset cố định, so sánh với baseline và tính chỉ số "Cost / câu đúng" giúp tối ưu hóa trade-off giữa chi phí và chất lượng. Tích hợp eval vào CI/CD giúp tự động chặn merge PR khi có hiện tượng regression.
  3. **Sự kết hợp hoàn hảo của 3 trụ cột Observability (Metrics - Traces - Logs):** Metrics (Prometheus + Grafana) báo động "có sự cố gì", Traces (OpenTelemetry + Jaeger) chỉ ra chính xác "span nào, bước nào gây chậm/lỗi", và Structured JSON Logs gắn `trace_id` cung cấp chi tiết toàn diện của request. Khả năng nhảy trực tiếp từ Grafana sang Jaeger rồi grep log JSON bằng `trace_id` rút ngắn MTTR từ hàng giờ xuống vài giây.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - **Time to First Token (TTFT):** Với ứng dụng GenAI có streaming, TTFT quan trọng hơn tổng latency vì nó quyết định cảm giác "nhanh hay chậm" của người dùng khi nhìn thấy chữ bắt đầu xuất hiện.
  - **LLM Cost Spike & Budget Alert:** Cảnh báo khi tốc độ tiêu thụ tiền theo giờ tăng vọt bất thường (phát hiện nguy cơ lặp prompt vô tận hoặc tấn công denial-of-wallet).
  - **Semantic Cache Hit Ratio:** Đo lường tỉ lệ tận dụng cache của các câu hỏi tương đồng để giảm chi phí và latency về 0ms.
  - **Circuit Breaker / Fallback Counter:** Metric đếm số lần upstream provider bị timeout/429 buộc agent phải kích hoạt mô hình dự phòng.
  - **Guardrail & Moderation Violations:** Đo số lượng request vi phạm kiểm duyệt nội dung an toàn hoặc có dấu hiệu prompt injection.
