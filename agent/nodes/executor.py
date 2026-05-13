"""
agent/nodes/executor.py
Executes validated SQL or Pandas code.
Caches results in Upstash Redis (TTL 1 hour).
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from agent.state import AgentState
from connectors.base import get_connector
from sandbox.python_sandbox import run_pandas
from upstash_redis import Redis


def _get_redis() -> Redis:
    return Redis(
        url=os.environ["UPSTASH_REDIS_REST_URL"],
        token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
    )


def _cache_key(connector_id: str, code: str, code_type: str) -> str:
    raw = f"{connector_id}:{code_type}:{code}"
    return "exec:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def executor(state: AgentState) -> AgentState:
    # Skip if safety block was triggered
    if (state.get("execution_error") or "").startswith("SAFETY_BLOCK"):
        return state

    code = state["generated_code"]
    code_type = state["code_type"]
    connector_id = state["connector_id"]

    # ── Cache lookup ──────────────────────────────────────────────────────────
    redis = _get_redis()
    cache_key = _cache_key(connector_id, code, code_type)
    try:
        cached = redis.get(cache_key)
        if cached:
            result = json.loads(cached)
            return {**state, "execution_result": result, "from_cache": True, "execution_error": None}
    except Exception:
        pass  # Cache miss or Redis error — proceed to execution

    # ── Execute ───────────────────────────────────────────────────────────────
    start = time.time()
    connector = get_connector(connector_id)

    try:
        if code_type == "sql":
            rows = connector.execute_sql(code)
            result = rows[:500]  # hard cap
        else:
            # Pandas: load dataframe from connector then run sandboxed code
            df = connector.load_dataframe()
            result_df = run_pandas(code, df)
            result = json.loads(result_df.to_json(orient="records", date_format="iso"))

        latency_ms = int((time.time() - start) * 1000)

        # ── Write to cache ────────────────────────────────────────────────────
        try:
            redis.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass  # Non-fatal cache write failure

        return {
            **state,
            "execution_result": result,
            "execution_error": None,
            "from_cache": False,
            "latency_ms": latency_ms,
        }

    except Exception as exc:
        return {
            **state,
            "execution_result": None,
            "execution_error": str(exc),
            "from_cache": False,
        }
