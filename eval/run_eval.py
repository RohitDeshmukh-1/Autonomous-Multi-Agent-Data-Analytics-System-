#!/usr/bin/env python3
"""
eval/run_eval.py
Runs the agent against eval/datasets/queries.json and prints a results table.
Usage: python eval/run_eval.py
"""

import json
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import get_graph

DATASET = Path(__file__).parent / "datasets" / "queries.json"
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


def run_eval():
    cases = json.loads(DATASET.read_text())
    graph = get_graph()
    results = []

    print(f"\nRunning {len(cases)} eval cases…\n")

    for case in cases:
        state = {
            "session_id": str(uuid.uuid4()),
            "user_id": "eval",
            "user_query": case["query"],
            "connector_id": case["connector_id"],
            "intent": "",
            "query_plan": {},
            "relevant_tables": [],
            "schema_context": "",
            "memory_context": "",
            "conversation_history": [],
            "generated_code": "",
            "code_type": "sql",
            "sql_dialect": "postgres",
            "execution_result": None,
            "execution_error": None,
            "from_cache": False,
            "error_class": None,
            "correction_attempts": 0,
            "max_corrections": 3,
            "insight_text": "",
            "chart_spec": None,
            "anomalies": [],
            "history_id": None,
            "latency_ms": None,
            "stream_tokens": [],
        }

        t0 = time.time()
        try:
            result = graph.invoke(state)
            elapsed = int((time.time() - t0) * 1000)

            intent_ok = result.get("intent") == case["expected_intent"]
            has_result = bool(result.get("execution_result")) or result.get("intent") == "unsupported"
            no_error = not result.get("execution_error")

            insight = result.get("insight_text", "")
            contains_ok = all(
                kw.lower() in insight.lower() or kw.lower() in result.get("generated_code", "").lower()
                for kw in case.get("expected_contains", [])
            )

            passed = intent_ok and (has_result or case["expected_intent"] == "unsupported") and no_error and contains_ok
            status = PASS if passed else FAIL

            results.append({
                "id": case["id"],
                "query": case["query"][:55],
                "intent": result.get("intent"),
                "expected_intent": case["expected_intent"],
                "corrections": result.get("correction_attempts", 0),
                "anomalies": len(result.get("anomalies", [])),
                "latency_ms": elapsed,
                "passed": passed,
                "status": status,
            })

        except Exception as exc:
            results.append({
                "id": case["id"],
                "query": case["query"][:55],
                "intent": "ERROR",
                "expected_intent": case["expected_intent"],
                "corrections": 0,
                "anomalies": 0,
                "latency_ms": int((time.time() - t0) * 1000),
                "passed": False,
                "status": FAIL,
                "error": str(exc),
            })

    # Print table
    print(f"{'ID':<5} {'Status':<4} {'Intent':<12} {'Fixes':<6} {'Warns':<6} {'ms':<7} Query")
    print("─" * 90)
    for r in results:
        print(
            f"{r['id']:<5} {r['status']:<4} {r['intent']:<12} {r['corrections']:<6} "
            f"{r.get('anomalies', 0):<6} {r['latency_ms']:<7} {r['query']}"
        )

    passed = sum(1 for r in results if r["passed"])
    avg_lat = sum(r["latency_ms"] for r in results) // len(results)
    print(f"\n{'─' * 90}")
    print(f"Passed: {passed}/{len(results)} ({100 * passed // len(results)}%) | Avg Latency: {avg_lat}ms")
    return passed == len(results)



if __name__ == "__main__":
    ok = run_eval()
    sys.exit(0 if ok else 1)
