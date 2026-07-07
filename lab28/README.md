# Lab #28: Full Platform Integration Sprint

## Hướng dẫn Setup và Chạy hệ thống

### 1. Chuẩn bị môi trường (Kaggle)
1. Mở Kaggle, tạo notebook mới, bật GPU T4 x2.
2. Chạy lần lượt các bước để cài đặt dependencies, cấu hình ngrok, và chạy vLLM (Port 8001) cùng Embedding (Port 8002).
3. Lấy URL public từ ngrok/cloudflared.

### 2. Cấu hình môi trường (Local)
Mở file `.env` và cập nhật các thông tin sau:
```bash
VLLM_NGROK_URL=<URL_từ_Kaggle_cho_vLLM>
EMBED_NGROK_URL=<URL_từ_Kaggle_cho_Embedding>
LANGCHAIN_API_KEY=<LangSmith_API_Key_của_bạn>
LANGCHAIN_PROJECT=lab28-platform
```

### 3. Khởi động Platform
Mở terminal tại thư mục `lab28/` và chạy:
```bash
docker compose up -d
```
Đợi các container chuyển trạng thái `Up` (kiểm tra bằng `docker compose ps`).

### 4. Deploy và Chạy Flow, Ingest Data
1. Deploy Prefect flow:
```bash
cd prefect/flows
pip install -r requirements.txt
python kafka_to_delta.py
cd ../..
```
2. Đẩy dữ liệu vào Kafka:
```bash
python scripts/01_ingest_to_kafka.py
```
3. Chạy luồng dữ liệu (Delta -> Feast, Embed -> Qdrant):
```bash
python scripts/03_delta_to_feast.py
python scripts/05_embed_to_qdrant.py
```

### 5. Kiểm thử hệ thống
1. Chạy Smoke Tests:
```bash
pytest smoke-tests/ -v
```
2. Chạy Production Readiness Check:
```bash
python scripts/production_readiness_check.py
```

### 6. Truy cập Dashboards
- Prefect UI: http://localhost:4200
- API Gateway (Docs): http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)
- Qdrant UI: http://localhost:6333/dashboard

---

## Trả lời 5 câu hỏi Submission

**1. Phân tích các trade-offs trong thiết kế kiến trúc AI platform của bạn. Bạn đã cân bằng giữa performance, reliability, và maintainability như thế nào?**
- **Performance:** Đẩy workload nặng (vLLM inference) lên Kaggle GPU giúp tăng tốc độ generate, trong khi local chỉ cần handle lightweight processes (API Gateway, orchestration). Trade-off là latency mạng giữa local và Kaggle.
- **Reliability:** Sử dụng Kafka để decouple data ingestion, cho phép retry/replay khi pipeline hỏng. Trade-off là cấu trúc hạ tầng phức tạp hơn.
- **Maintainability:** Triển khai bằng Docker Compose giúp quản lý các microservices nhất quán, dễ dàng deploy và share.

**2. Trong kiến trúc hybrid (Local + Kaggle), bạn xử lý ngắt kết nối giữa local và Kaggle như thế nào? Có cơ chế fallback không?**
- Trong setup hiện tại, ngắt kết nối sẽ gây timeout tại API Gateway khi gọi vLLM.
- Hướng giải quyết (fallback): Thiết lập timeout hợp lý (trong API Gateway đã có `timeout=30`), khi catch timeout sẽ trả về lỗi rõ ràng hoặc gọi fallback model nhỏ nhẹ hơn chạy ở local (nếu cấu hình thêm).

**3. Giải thích cách event-driven architecture với Kafka giúp decouple các components trong AI platform của bạn.**
- Producer (như `01_ingest_to_kafka.py`) đẩy raw data vào broker và không cần chờ consumer xử lý xong.
- Consumer (như `prefect worker`) có thể đọc batch khi sẵn sàng.
- Khi một component (như DB) bị sập, dữ liệu vẫn được lưu trữ an toàn trong Kafka queue thay vì bị rớt (loss) như trong kiến trúc API đồng bộ.

**4. Bạn đã implement observability như thế nào? Logs, metrics, và traces được thu thập và visualized ra sao?**
- **Metrics:** Sử dụng `prometheus-fastapi-instrumentator` trong FastAPI để tự động expose metrics `/metrics`. Prometheus pull metrics này và Grafana query từ Prometheus để hiển thị.
- **Traces:** Sử dụng `LangSmith` để ghi nhận các trace từ LLM requests (nếu wrap bằng LangChain) hoặc track request context.
- **Logs:** Docker thu thập logs của toàn bộ service thông qua stdout/stderr và có thể được quản lý qua `docker compose logs`.

**5. Nếu một service trong stack (ví dụ: Qdrant hoặc Kafka) bị crash, hệ thống của bạn sẽ xử lý như thế nào? Có graceful degradation không?**
- Trong cấu hình `docker-compose.yml`, các service `depends_on` được thiết lập. API Gateway có thể healthcheck liên tục. Nếu Qdrant chết, phần gọi Vector Search sẽ bị exception. Tốt nhất là thêm exception handling tại API Gateway, để nếu Qdrant chết, request search sẽ bypass và trực tiếp để LLM generate dựa trên system prompt (graceful degradation) thay vì throw error 500 toàn bộ flow.
