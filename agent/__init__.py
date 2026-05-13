# Lazy imports — use `from agent.graph import get_graph` directly in application code
# to avoid pulling in heavy optional deps (weasyprint, etc.) during testing.
from .state import AgentState
