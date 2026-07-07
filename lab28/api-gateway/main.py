from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
import httpx, os, time, langsmith

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)  # Integration 9: Prometheus

VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8001")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")

@app.post("/api/v1/chat")
async def chat(request: Request):
    body = await request.json()
    query = body.get("query", "")
    start = time.time()

    # 1. Vector search
    async with httpx.AsyncClient() as client:
        search_resp = await client.post(f"{QDRANT_URL}/collections/documents/points/search", json={
            "vector": body.get("embedding", [0.0] * 384),
            "limit": 3
        })
        context_data = search_resp.json().get("result", [])
        context = [pt.get("payload", {}).get("text", "") for pt in context_data]

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {query}"
    async with httpx.AsyncClient(timeout=30) as client:
        llm_resp = await client.post(f"{VLLM_URL}/v1/chat/completions", json={
            "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
            "messages": [{"role": "user", "content": prompt}]
        })

    latency = (time.time() - start) * 1000
    
    if llm_resp.status_code == 200:
        result = llm_resp.json()
        return {
            "answer": result["choices"][0]["message"]["content"],
            "latency_ms": round(latency, 2),
            "model": result.get("model", "unknown")
        }
    else:
        return {
            "error": "Failed to call LLM",
            "status_code": llm_resp.status_code,
            "details": llm_resp.text
        }

@app.get("/health")
def health():
    return {"status": "ok"}
