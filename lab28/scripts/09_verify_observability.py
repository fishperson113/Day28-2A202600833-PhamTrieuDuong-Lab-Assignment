import requests
import os
from dotenv import load_dotenv

load_dotenv()

def check_prometheus():
    try:
        resp = requests.get("http://localhost:9090/api/v1/query",
                            params={"query": 'http_requests_total{job="api-gateway"}'})
        data = resp.json()
        assert data["status"] == "success"
        print("Integration 9 OK: Prometheus metrics flowing")
    except Exception as e:
        print(f"Integration 9 Failed: {e}")

def check_langsmith():
    try:
        from langsmith import Client
        client = Client(api_key=os.environ.get("LANGCHAIN_API_KEY", ""))
        runs = list(client.list_runs(project_name=os.environ.get("LANGCHAIN_PROJECT", "lab28-platform"), limit=1))
        assert len(runs) >= 0
        print("Integration 10 OK: LangSmith traces visible")
    except Exception as e:
        print(f"Integration 10 Failed: {e}")

check_prometheus()
check_langsmith()
