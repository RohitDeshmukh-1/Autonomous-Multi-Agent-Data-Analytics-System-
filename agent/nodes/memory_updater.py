"""
agent/nodes/memory_updater.py
Persists successful query + insight into Neon pgvector for future retrieval.
Also writes to query_history table.
Uses connection pool for performance.
"""

import json
import uuid
from agent.state import AgentState
from db.pool import pooled_connection
from llm import get_embedder


def memory_updater(state: AgentState) -> AgentState:
    if not state.get("execution_result") or not state.get("insight_text"):
        return state

    with pooled_connection() as conn:
        embedder = get_embedder()
        combined_text = f"{state['user_query']} {state['insight_text']}"
        embedding = embedder.embed(combined_text)

        table_names = [t["table"] for t in state.get("relevant_tables", [])]
        history_id = str(uuid.uuid4())
        latency_ms = state.get("latency_ms", 0)

        with conn.cursor() as cur:
            # Write to query_history
            cur.execute(
                """
                INSERT INTO query_history
                  (id, session_id, user_query, generated_code, code_type,
                   insight_text, chart_spec, result_preview, retry_count, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    history_id,
                    state["session_id"],
                    state["user_query"],
                    state["generated_code"],
                    state["code_type"],
                    state["insight_text"],
                    json.dumps(state.get("chart_spec")),
                    json.dumps(state.get("execution_result", [])[:20]),
                    state.get("correction_attempts", 0),
                    latency_ms,
                ),
            )

            # Write to memory_embeddings
            cur.execute(
                """
                INSERT INTO memory_embeddings
                  (id, session_id, query, insight, table_names, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                (
                    str(uuid.uuid4()),
                    state["session_id"],
                    state["user_query"],
                    state["insight_text"],
                    table_names,
                    embedding,
                ),
            )
            conn.commit()

    return {**state, "history_id": history_id}
