from datetime import datetime, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cost_key = f"budget:daily:{today}"
    try:
        current_cost = float(r.get(cost_key) or 0.0)
        if current_cost >= settings.daily_budget_usd:
            raise HTTPException(
                status_code=402,
                detail=f"Budget exceeded. Current: ${current_cost:.6f}, Limit: ${settings.daily_budget_usd:.6f}",
            )
    except HTTPException:
        raise
    except Exception:
        pass


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cost_key = f"budget:daily:{today}"
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    try:
        r.incrbyfloat(cost_key, cost)
        r.expire(cost_key, 86400 * 3)
    except Exception:
        pass
    return cost
