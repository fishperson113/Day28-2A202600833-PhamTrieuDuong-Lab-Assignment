# Lab #28 — Full Platform Integration Sprint

AI platform với kiến trúc hybrid (Local + Kaggle GPU) sử dụng Prefect, Kafka, Qdrant, Prometheus, Grafana.

## Kiến trúc

```
Local (Docker Compose):
  Kafka → Prefect → Delta Lake → Feast (Redis)
  ↓                ↓
  Qdrant         API Gateway (FastAPI)
  ↓                ↓
  Prometheus ← Grafana
  ↓
  LangSmith tracing

Kaggle (GPU T4/P100):
  vLLM serving
  Embedding service
  MLflow tracking
```

## Yêu cầu

- Docker Desktop đang chạy
- Python 3.10+
- Tài khoản Kaggle với GPU đã bật
- **Tunnel service** (chọn 1 trong 2):
  - `ngrok` đã cài và token configured
  - HOẶC `cloudflared` đã cài (`brew install cloudflare/cloudflare/cloudflared`)

## Quick Start

### 1. Khởi động Local Stack

```bash
cd lab28
docker compose up -d
docker compose ps  # Kiểm tra tất cả services Up
```

**Services:**

- Prefect UI: http://localhost:4200
- Grafana: http://localhost:3000 (admin/admin)
- Qdrant: http://localhost:6333/dashboard
- Prometheus: http://localhost:9090
- API Gateway: http://localhost:8000

### 2. Setup Kaggle GPU

Tạo Kaggle Notebook với GPU T4 x2, chọn 1 trong 2 option:

**Option A: Single GPU (đơn giản - dùng 1 GPU)**

```python
# Cell 1: Install dependencies
!pip install -q vllm fastapi uvicorn pyngrok mlflow sentence-transformers

# Nếu cài vLLM bị lỗi, dùng fallback:
# !pip install transformers==4.46.3 --quiet
# !pip install vllm==0.7.3 --quiet

# Cell 2: Setup ngrok
from pyngrok import ngrok
ngrok.set_auth_token("YOUR_NGROK_TOKEN")  # lấy tại ngrok.com

# Cell 3: Start vLLM server (single GPU)
import subprocess, threading, time

def run_vllm():
    subprocess.run([
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
        "--port", "8001",
        "--max-model-len", "4096",
        "--gpu-memory-utilization", "0.5"
    ])

thread = threading.Thread(target=run_vllm, daemon=True)
thread.start()
time.sleep(60)
print("vLLM server started")

# Cell 4: Create ngrok tunnel
tunnel = ngrok.connect(8001, "http")
print(f"vLLM URL: {tunnel.public_url}")
```

**Option B: Multi-GPU (nâng cao - dùng 2 GPUs)**

```python
# Cell 1: Install dependencies
!pip install -q vllm fastapi uvicorn pyngrok mlflow sentence-transformers

# Nếu cài vLLM bị lỗi, dùng fallback:
# !pip install transformers==4.46.3 --quiet
# !pip install vllm==0.7.3 --quiet

# Cell 2: Setup ngrok
from pyngrok import ngrok
ngrok.set_auth_token("YOUR_NGROK_TOKEN")  # lấy tại ngrok.com

# Cell 3: Start vLLM server (multi-GPU)
import subprocess
import os
import time
import requests
import threading

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"

def start_server(gpu_id, port):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    proc = subprocess.Popen(
        [
            "vllm", "serve", MODEL_NAME,
            "--dtype", "float16",
            "--max-model-len", "8192",
            "--host", "0.0.0.0",
            "--port", str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )

    def stream_logs():
        for line in proc.stdout:
            print(f"[GPU {gpu_id}] {line.decode()}", end="")

    threading.Thread(target=stream_logs, daemon=True).start()

    return proc

print("Starting Server on GPU 0 (Port 8000)")
proc1 = start_server(0, 8000)

print("Starting Server on GPU 1 (Port 8001)")
proc2 = start_server(1, 8001)

def wait_for_server(port):
    print(f" Waiting for server on port {port}...")
    for _ in range(60):
        try:
            r = requests.get(f"http://localhost:{port}/health")
            if r.status_code == 200:
                print(f"Server on port {port} is ready!")
                return
        except:
            time.sleep(5)
    raise RuntimeError(f"Server on port {port} failed to start.")

wait_for_server(8000)
wait_for_server(8001)

# Cell 4: Create ngrok tunnel
print("Creating ngrok tunnels...")
tunnel1 = ngrok.connect(8000, "http")
tunnel2 = ngrok.connect(8001, "http")

print(f"GPU 0 URL: {tunnel1.public_url}")
print(f"GPU 1 URL: {tunnel2.public_url}")
# Có thể dùng 1 trong 2 hoặc cả 2 cho load balancing
```

**Option C: Dùng cloudflared (Single GPU)**

```python
# Cell 1: Install dependencies
!pip install -q vllm fastapi uvicorn cloudflared mlflow sentence-transformers

# Nếu cài vLLM bị lỗi, dùng fallback:
# !pip install transformers==4.46.3 --quiet
# !pip install vllm==0.7.3 --quiet

# Cell 2: Start vLLM server (single GPU)
import subprocess, threading, time

def run_vllm():
    subprocess.run([
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
        "--port", "8001",
        "--max-model-len", "4096",
        "--gpu-memory-utilization", "0.5"
    ])

thread = threading.Thread(target=run_vllm, daemon=True)
thread.start()
time.sleep(60)
print("vLLM server started")

# Cell 3: Create cloudflare tunnel
import subprocess
tunnel = subprocess.run(["cloudflared", "tunnel", "--url", "http://localhost:8001"], capture_output=True, text=True)
print(tunnel.stdout)  # URL sẽ hiển thị
```

**Option D: Dùng cloudflared (Multi-GPU)**

```python
# Cell 1: Install dependencies
!pip install -q vllm fastapi uvicorn cloudflared mlflow sentence-transformers

# Nếu cài vLLM bị lỗi, dùng fallback:
# !pip install transformers==4.46.3 --quiet
# !pip install vllm==0.7.3 --quiet

# Cell 2: Start vLLM server (multi-GPU)
import subprocess
import os
import time
import requests
import threading

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"

def start_server(gpu_id, port):
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    proc = subprocess.Popen(
        [
            "vllm", "serve", MODEL_NAME,
            "--dtype", "float16",
            "--max-model-len", "8192",
            "--host", "0.0.0.0",
            "--port", str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )

    def stream_logs():
        for line in proc.stdout:
            print(f"[GPU {gpu_id}] {line.decode()}", end="")

    threading.Thread(target=stream_logs, daemon=True).start()

    return proc

print("Starting Server on GPU 0 (Port 8000)")
proc1 = start_server(0, 8000)

print("Starting Server on GPU 1 (Port 8001)")
proc2 = start_server(1, 8001)

def wait_for_server(port):
    print(f" Waiting for server on port {port}...")
    for _ in range(60):
        try:
            r = requests.get(f"http://localhost:{port}/health")
            if r.status_code == 200:
                print(f"Server on port {port} is ready!")
                return
        except:
            time.sleep(5)
    raise RuntimeError(f"Server on port {port} failed to start.")

wait_for_server(8000)
wait_for_server(8001)

# Cell 3: Create cloudflare tunnel
import subprocess
print("Creating cloudflare tunnels...")
tunnel1 = subprocess.run(["cloudflared", "tunnel", "--url", "http://localhost:8000"], capture_output=True, text=True)
tunnel2 = subprocess.run(["cloudflared", "tunnel", "--url", "http://localhost:8001"], capture_output=True, text=True)
print(f"GPU 0 URL (copy from output):")
print(tunnel1.stdout)
print(f"GPU 1 URL (copy from output):")
print(tunnel2.stdout)
# Có thể dùng 1 trong 2 hoặc cả 2 cho load balancing
```

### 3. Cập nhật Environment Variables

```bash
# Copy và chỉnh sửa file .env
cp .env.example .env
# Thay VLLM_NGROK_URL với URL từ Kaggle (ngrok hoặc cloudflared)
# Thay EMBED_NGROK_URL nếu có embedding service
# Thay LANGCHAIN_API_KEY với key của bạn
```

### 4. Deploy Prefect Flows

```bash
cd prefect/flows
pip install -r requirements.txt
python kafka_to_delta.py
```

### 5. Ingest Data vào Kafka

```bash
cd ../..
python scripts/01_ingest_to_kafka.py
```

### 6. Chạy Smoke Tests

```bash
pytest smoke-tests/ -v
```

Kỳ vọng: 5/5 tests passing

### 7. Production Readiness Check

```bash
python scripts/production_readiness_check.py
```

Kỳ vọng: Score >80%

## Scripts

| Script                                    | Mô tả                                                  |
| ----------------------------------------- | -------------------------------------------------------- |
| `scripts/01_ingest_to_kafka.py`         | Ingest sample data vào Kafka                            |
| `scripts/03_delta_to_feast.py`          | Load từ Delta Lake và push features vào Feast (Redis) |
| `scripts/05_embed_to_qdrant.py`         | Embed data và lưu vectors vào Qdrant                  |
| `scripts/09_verify_observability.py`    | Kiểm tra Prometheus metrics và LangSmith traces        |
| `scripts/production_readiness_check.py` | Production readiness checklist                           |

## API Gateway

**Health Check:**

```bash
curl http://localhost:8000/health
```

**Chat Endpoint:**

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is platform engineering?",
    "embedding": [0.1, 0.2, ...]
  }'
```

## Monitoring

- **Grafana Dashboard:** http://localhost:3000
- **Prometheus:** http://localhost:9090
- **Prefect UI:** http://localhost:4200

## Troubleshooting

**Services không start:**

```bash
docker compose logs <service_name>
docker compose down -v
docker compose up -d
```

**Prefect worker không connect:**

```bash
# Check Prefect UI: http://localhost:4200
# Đảm bảo worker đang chạy:
docker compose logs prefect-worker
```

**Kafka consumer lag:**

```bash
# Kiểm tra topic
docker exec lab28-kafka-1 kafka-topics --list --bootstrap-server localhost:9092
```

## Nộp Bài
Xem `SUBMISSION.md` ở thư mục gốc project.

---

## Trả Lời 5 Câu Hỏi Lý Thuyết (Lab #28)

**1. Phân tích các trade-offs trong thiết kế kiến trúc AI platform của bạn. Bạn đã cân bằng giữa performance, reliability, và maintainability như thế nào?**
- **Performance:** Bằng cách tách riêng phần nặng nhất (LLM Inference và Embedding) chạy trên GPU Kaggle thay vì local, hệ thống đảm bảo thời gian tính toán nhanh nhất có thể. Trade-off là latency đường truyền qua mạng Internet (Cloudflare/Ngrok).
- **Reliability:** Dùng Kafka làm bộ đệm (Message Queue) giúp hệ thống không bị mất dữ liệu khi lưu lượng tăng đột biến. Dùng Docker giúp môi trường luôn nhất quán và ít lỗi vặt.
- **Maintainability:** Việc tách rời các module (Decoupling) bằng Microservices (vLLM, Prefect, FastAPI) giúp dễ dàng cập nhật/bảo trì từng phần riêng biệt mà không làm sập toàn bộ hệ thống.

**2. Trong kiến trúc hybrid (Local + Kaggle), bạn xử lý ngắt kết nối giữa local và Kaggle như thế nào? Có cơ chế fallback không?**
- Do đặc thù Kaggle session bị giới hạn thời gian (12 tiếng) hoặc dễ bị ngắt kết nối (Idle), các liên kết Ngrok/Cloudflare sẽ chết.
- **Xử lý:** Mọi thao tác kết nối tới Kaggle (FastAPI gọi LLM/Embedding) đều được cấu hình timeout để tránh treo hệ thống (`timeout=30` trong `httpx`).
- **Cơ chế Fallback:** Khi API request bị thất bại do timeout hoặc ngắt kết nối, API Gateway sẽ bắt lỗi thông qua Try/Catch hoặc trả về HTTP Status code rõ ràng thay vì crash server, đồng thời cảnh báo (Alert) để người vận hành cập nhật lại biến môi trường URL.

**3. Giải thích cách event-driven architecture với Kafka giúp decouple các components trong AI platform của bạn.**
- Nếu không có Kafka, hệ thống nguồn (Ví dụ: Web app) phải gọi API trực tiếp tới luồng xử lý Data (Prefect/Delta Lake), tạo ra điểm nghẽn cổ chai (Bottleneck) khi dữ liệu quá tải.
- Nhờ Kafka, hệ thống nguồn chỉ cần quăng dữ liệu vào Topic (`data.raw`) và lập tức trả về phản hồi "Thành công" cho người dùng. Phía sau, luồng Prefect (Consumer) có thể từ từ hút dữ liệu theo lịch trình (`schedule`) và lưu vào Delta Lake mà không phụ thuộc lẫn nhau. Hai hệ thống hoạt động hoàn toàn độc lập (Decoupled).

**4. Bạn đã implement observability như thế nào? Logs, metrics, và traces được thu thập và visualized ra sao?**
- **Metrics:** Sử dụng thư viện `prometheus-fastapi-instrumentator` để tự động thu thập các chỉ số về HTTP requests (thời gian phản hồi, số lượng request, mã lỗi...) của API Gateway. Prometheus sẽ cào (scrape) các thông số này mỗi 15s.
- **Visualization:** Các metrics từ Prometheus được đổ lên Grafana (cổng 3000) để vẽ biểu đồ Dashboard trực quan.
- **Traces:** Sử dụng nền tảng LangSmith để trace toàn bộ hành trình của dòng dữ liệu từ lúc User nhập câu hỏi (Prompt) cho tới lúc LLM trên Kaggle trả về kết quả, giúp dễ dàng debug.

**5. Nếu một service trong stack (ví dụ: Qdrant hoặc Kafka) bị crash, hệ thống của bạn sẽ xử lý như thế nào? Có graceful degradation không?**
- Nếu service bị crash, Docker Compose đã được cấu hình với cơ chế tự khởi động lại hoặc ta có thể phục hồi nó dễ dàng do dữ liệu được lưu trữ thông qua persistent volumes (ví dụ: `qdrant_data`).
- **Graceful degradation (Xuống cấp ôn hòa):** Tại API Gateway, nếu gọi tới Qdrant (Vector Database) thất bại, ứng dụng vẫn có thể chặn lỗi và trả về câu trả lời mặc định từ LLM (không có context) thay vì crash toàn bộ hệ thống API. Tương tự, nếu Kafka sập, dữ liệu chưa kịp gửi sẽ được nhà phát hành (Producer) retry hoặc lưu tạm vào log thay vì báo lỗi trực tiếp cho end-user.
