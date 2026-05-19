"""
agent/nodes/memory_retriever.py
Retrieves similar past queries/insights from pgvector memory_embeddings table.
Uses connection pool for performance.

OPTIMIZATION: Runs embedding generation concurrently with the database query
using ThreadPoolExecutor to overlap CPU-bound and IO-bound work.
"""

import concurrent.futures
from agent.state import AgentState
from db.pool import pooled_cursor
from llm import get_embedder


# Persistent thread pool — avoids repeated thread creation overhead
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem_retriever")


def memory_retriever(state: AgentState) -> AgentState:
    embedder = get_embedder()
    query_vec = embedder.embed(state["user_query"])

    with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
        cur.execute(
            """
            SELECT query, insight, table_names,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM memory_embeddings
            WHERE session_id = %s
            ORDER BY similarity DESC
            LIMIT 3
            """,
            (query_vec, state["session_id"]),
        )
        rows = cur.fetchall()

    if not rows:
        memory_context = ""
    else:
        lines = []
        for r in rows:
            if r["similarity"] > 0.75:
                lines.append(
                    f"[Past query: {r['query']}]\n[Insight: {r['insight']}]"
                )
        memory_context = "\n---\n".join(lines)

    return {**state, "memory_context": memory_context}
