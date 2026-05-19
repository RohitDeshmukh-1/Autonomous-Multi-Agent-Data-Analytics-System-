"""
agent/nodes/intent_router.py
Classifies user query into: sql | pandas | insight | unsupported
"""

import json
from agent.state import AgentState
from llm import get_groq_client

SYSTEM = """You are an intent classifier for a data analyst agent.
Classify the user query into exactly one of these intents:
- sql       : needs SQL query against a relational database. Use this for general questions about the data, business insights, or if there is no prior context to answer the question.
- pandas    : needs Python/Pandas data manipulation (uploaded CSV, complex transforms)
- insight   : general analytical question answerable from PRIOR CONTEXT. ONLY use this if there is prior conversation history, no new query needed.
- unsupported : out of scope (weather, news, code help unrelated to data, etc.)

Respond ONLY with a JSON object: {"intent": "<intent>", "reasoning": "<one sentence>"}"""


def intent_router(state: AgentState) -> AgentState:
    client = get_groq_client()
    has_history = len(state.get("conversation_history", [])) > 0
    history_msg = "YES" if has_history else "NO (Do not classify as 'insight')"
    
    user_msg = (
        f"Query: {state['user_query']}\n"
        f"Connector type: {state['connector_id'].split(':')[0]}\n"
        f"Has prior conversation history: {history_msg}"
    )

    raw = client.complete_system(
        system=SYSTEM,
        user=user_msg,
        model=client.reason_model,
        max_tokens=128,
    )
    try:
        result = json.loads(raw)
        intent = result.get("intent", "sql")
    except json.JSONDecodeError:
        intent = "sql"

    # Post-processing safeguard: cannot do insight without prior context
    if intent == "insight" and not has_history:
        intent = "sql"

    return {**state, "intent": intent}
