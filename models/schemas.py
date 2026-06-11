"""Pydantic schemas for API requests/responses and internal data structures."""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class AgentName(str, Enum):
    """The five specialised agents in the PragMind hub."""
    AXIOM = "axiom"
    SAGE = "sage"
    ATLAS = "atlas"
    PULSE = "pulse"
    FORGE = "forge"


class ChatMessage(BaseModel):
    """A single message in a conversation (user or assistant)."""
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class EscalationFlag(BaseModel):
    """Escalation detection result."""
    triggered: bool = Field(default=False, description="True if escalation phrase detected")
    phrase: Optional[str] = Field(default=None, description="The escalation phrase if triggered")
    type: Optional[str] = Field(default=None, description="Type of escalation (e.g., 'urgent', 'technical')")


class RunAgentRequest(BaseModel):
    """Request to run a specific agent directly."""
    agent: AgentName = Field(..., description="Which agent to run")
    message: str = Field(..., description="The user's message")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation history for context"
    )


class RunAgentResponse(BaseModel):
    """Response from a direct agent run."""
    agent: AgentName = Field(..., description="The agent that processed the request")
    response: str = Field(..., description="The agent's response text")
    escalation: EscalationFlag = Field(..., description="Escalation detection result")


class HubRouteRequest(BaseModel):
    """Request to send a message through the hub router."""
    message: str = Field(..., description="The user's message")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation history for context"
    )


class HubRouteResponse(BaseModel):
    """Response from the hub router."""
    routed_to: AgentName = Field(..., description="Which agent the router selected")
    routing_reason: str = Field(..., description="Why the router chose this agent")
    response: str = Field(..., description="The agent's response text")
    escalation: EscalationFlag = Field(..., description="Escalation detection result")
