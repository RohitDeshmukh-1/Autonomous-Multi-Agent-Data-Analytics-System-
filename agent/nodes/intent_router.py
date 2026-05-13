"""
agent/nodes/intent_router.py
Classifies user query into: sql | pandas | insight | unsupported
"""

import json
from agent.state import AgentState
from llm import get_groq_client

SYSTEM = """You are an intent classifier for a data analyst agent.
Classify the user query into exactly one of these intents:
- sql       : needs SQL query against a relational database
- pandas    : needs Python/Pandas data manipulation (uploaded CSV, complex transforms)
- insight   : general analytical question answerable from prior context, no new query needed
- unsupported : out of scope (weather, news, code help unrelated to data, etc.)

Respond ONLY with a JSON object: {"intent": "<intent>", "reasoning": "<one sentence>"}"""


def intent_router(state: AgentState) -> AgentState:
    client = get_groq_client()
    raw = client.complete_system(
        system=SYSTEM,
        user=f"Query: {state['user_query']}\nConnector type: {state['connector_id'].split(':')[0]}",
        model=client.reason_model,
        max_tokens=128,
    )
    try:
        result = json.loads(raw)
        intent = result.get("intent", "sql")
    except json.JSONDecodeError:
        intent = "sql"

    return {**state, "intent": intent}
