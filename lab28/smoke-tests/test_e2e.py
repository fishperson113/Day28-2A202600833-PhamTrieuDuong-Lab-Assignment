import pytest, requests, time, os

BASE_URL = "http://localhost:8000"
VLLM_URL = os.environ.get("VLLM_NGROK_URL", "")

class TestHappyPath:
    def test_full_inference_returns_200(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={
            "query": "What is platform engineering?",
            "embedding": [0.1] * 384
        }, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 10
        assert data["latency_ms"] < 2000

    def test_health_check_passes(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

class TestDataIngestion:
    def test_kafka_ingest_and_qdrant_store(self):
        from kafka import KafkaProducer
        import json

        producer = KafkaProducer(
            bootstrap_servers="localhost:9092",
            value_serializer=lambda v: json.dumps(v).encode()
        )
        producer.send("data.raw", {"id": "smoke_001", "text": "smoke test document"})
        producer.flush()

        time.sleep(10)

        resp = requests.get("http://localhost:6333/collections/documents")
        assert resp.status_code == 200
        count = resp.json()["result"]["points_count"]
        assert count > 0

class TestObservability:
    def test_prometheus_scrapes_api_gateway(self):
        resp = requests.get("http://localhost:9090/api/v1/query",
                            params={"query": "up{job='api-gateway'}"})
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]
        assert len(result) > 0
        assert result[0]["value"][1] == "1"

    def test_grafana_dashboard_accessible(self):
        resp = requests.get("http://localhost:3000/api/health",
                            auth=("admin", "admin"))
        assert resp.status_code == 200

class TestFailurePath:
    def test_invalid_request_returns_422(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={})
        assert resp.status_code in [400, 422]

    def test_timeout_handled_gracefully(self):
        try:
            resp = requests.post(f"{BASE_URL}/api/v1/chat",
                                 json={"query": "test", "embedding": [0.1] * 384},
                                 timeout=0.001)
        except requests.exceptions.Timeout:
            pass

        health = requests.get(f"{BASE_URL}/health", timeout=5)
        assert health.status_code == 200

class TestFeatureStore:
    def test_feast_redis_has_features(self):
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        keys = r.keys("feature:*")
        assert len(keys) > 0, "No features found in Feast store"
