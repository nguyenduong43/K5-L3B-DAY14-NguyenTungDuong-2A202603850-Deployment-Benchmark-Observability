import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# Structured logging: đảm bảo mọi dòng log do app in ra là JSON hợp lệ
class JsonFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if msg.startswith("{") and msg.endswith("}"):
            try:
                # Đã là json object
                json.loads(msg)
                return msg
            except Exception:
                pass
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "msg": msg,
            "name": record.name,
        }
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lifecycle: startup và graceful shutdown
    logger.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "lvl": "INFO", "event": "startup"}))
    yield
    logger.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "lvl": "INFO", "event": "shutdown"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def json_logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": "INFO",
        "event": "request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": duration_ms,
    }))
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health_check():
    """Liveness probe: Luôn trả 200 khi process đang chạy, kể cả khi Redis chưa kết nối."""
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    """Readiness probe: 200 khi sẵn sàng, 503 khi Redis không kết nối được."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis connection failed")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Protected endpoint cho AI Agent."""
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(10, len(body.question.split()) * 2)
    output_tokens = max(10, len(answer.split()) * 2)
    record_cost(input_tokens, output_tokens)

    return {"question": body.question, "answer": answer}
