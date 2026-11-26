"""Production AI Agent: API security, Redis accounting and health checks."""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost, release_budget
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }, ensure_ascii=False)


logger = logging.getLogger("day14.agent")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("startup")
    yield
    logger.info("shutdown")  # Uvicorn drains requests on SIGTERM.


app = FastAPI(title="Production AI Agent", lifespan=lifespan)
started_at = time.monotonic()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} {response.status_code} {round((time.monotonic()-start)*1000, 2)}ms")
    return response


@app.get("/health")
def health():
    # Liveness must not depend on Redis availability.
    return {"status": "ok", "uptime_seconds": round(time.monotonic() - started_at, 2),
            "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    budget_key, reserved = check_budget(api_key, body.question)
    try:
        answer = llm_ask(body.question)
    except Exception:
        release_budget(budget_key, reserved)
        raise
    input_tokens = max(1, (len(body.question) + 3) // 4)
    output_tokens = max(1, (len(answer) + 3) // 4)
    cost_usd = record_cost(budget_key, input_tokens, output_tokens, reserved)
    return {"question": body.question, "answer": answer,
            "usage": {"input_tokens": input_tokens,
                      "output_tokens": output_tokens, "cost_usd": cost_usd}}
