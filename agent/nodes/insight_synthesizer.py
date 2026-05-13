"""
agent/nodes/insight_synthesizer.py
Generates 2-3 sentence analytical insight from query results.
"""

import json
from agent.state import AgentState
from llm import get_groq_client

SYSTEM = """You are a senior data analyst. Given a user question and query results,
write 2-3 concise analytical sentences that directly answer the question.
Focus on the most important numbers, trends, and business implications.
Do not describe how the query works — just state what the data shows."""


def insight_synthesizer(state: AgentState) -> AgentState:
    result = state.get("execution_result")
    if not result:
        return {**state, "insight_text": "No results were returned for this query."}

    # Truncate result preview for prompt (first 20 rows)
    preview = json.dumps(result[:20], default=str)

    client = get_groq_client()
    insight = client.complete_system(
        system=SYSTEM,
        user=f"Question: {state['user_query']}\n\nResults (first 20 rows):\n{preview}",
        model=client.reason_model,
        max_tokens=256,
        temperature=0.2,
    )

    return {**state, "insight_text": insight}
