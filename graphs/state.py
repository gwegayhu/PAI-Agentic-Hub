"""LangGraph state definition for the PragMind Hub."""

from typing import TypedDict
from langchain_core.messages import BaseMessage


class HubState(TypedDict, total=False):
    """
    The state shared across all nodes in the PragMind Hub graph.
    
    Fields:
        messages: List of LangChain message objects (HumanMessage, AIMessage, etc.)
        routed_agent: The agent name selected by the router
        routing_reason: Why the router selected this agent
        response: The final response text from the selected agent
        escalation_triggered: Boolean flag for escalation detection
        escalation_phrase: The escalation phrase that was detected (if any)
        escalation_type: The category of escalation (if triggered)
    """
    messages: list[BaseMessage]
    routed_agent: str
    routing_reason: str
    response: str
    escalation_triggered: bool
    escalation_phrase: str | None
    escalation_type: str | None
