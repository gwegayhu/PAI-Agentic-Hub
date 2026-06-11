"""
PragMind Agentic Hub — LangGraph Graph
=======================================
Architecture:
  START
    └─► router_node         (classifies input → one of 5 agents)
          └─► [conditional edge: routed_agent]
                ├─► axiom_node
                ├─► sage_node
                ├─► atlas_node
                ├─► pulse_node
                └─► forge_node
                      └─► escalation_node   (checks for escalation phrases)
                            └─► END
"""

import json
import logging
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END

from graphs.state import HubState
from agents.prompts import AGENT_PROMPTS, ROUTER_PROMPT
from agents.escalation import detect_escalation
from config.settings import MODEL_NAME, MAX_TOKENS, FORGE_MAX_TOKENS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------

_base_llm = ChatAnthropic(model=MODEL_NAME, max_tokens=MAX_TOKENS)
_forge_llm = ChatAnthropic(model=MODEL_NAME, max_tokens=FORGE_MAX_TOKENS)
_router_llm = ChatAnthropic(model=MODEL_NAME, max_tokens=256)


# ---------------------------------------------------------------------------
# Helper: build message list for Claude API call
# ---------------------------------------------------------------------------

def _build_messages(system_prompt: str, state: HubState) -> list:
    """
    Combine the agent's system prompt with the conversation history from state.
    Returns a list of LangChain message objects.
    """
    msgs = [SystemMessage(content=system_prompt)]
    for m in state["messages"]:
        msgs.append(m)
    return msgs


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

def router_node(state: HubState) -> dict:
    """
    Reads the latest user message and routes to the correct agent.
    Uses a lightweight Claude call that returns structured JSON.
    """
    latest_user_msg = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            latest_user_msg = m.content
            break

    logger.info(f"[ROUTER] Routing message: {latest_user_msg[:80]}...")

    try:
        result = _router_llm.invoke([
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=latest_user_msg),
        ])
        raw = result.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        agent = parsed.get("agent", "axiom").lower()
        reason = parsed.get("reason", "Default routing to Axiom.")
    except Exception as e:
        logger.warning(f"[ROUTER] Routing failed ({e}), defaulting to axiom")
        agent = "axiom"
        reason = "Routing error — defaulted to Axiom."

    valid_agents = {"axiom", "sage", "atlas", "pulse", "forge"}
    if agent not in valid_agents:
        agent = "axiom"
        reason = f"Unknown agent '{agent}' returned — defaulted to Axiom."

    logger.info(f"[ROUTER] → {agent.upper()} | {reason}")
    return {"routed_agent": agent, "routing_reason": reason}


# ---------------------------------------------------------------------------
# Agent node factory
# ---------------------------------------------------------------------------

def _make_agent_node(agent_name: str):
    """
    Returns a LangGraph node function for the given agent.
    Each agent calls Claude with its specific system prompt + conversation history.
    """
    system_prompt = AGENT_PROMPTS[agent_name]
    llm = _forge_llm if agent_name == "forge" else _base_llm

    def agent_node(state: HubState) -> dict:
        logger.info(f"[{agent_name.upper()}] Processing request")
        messages = _build_messages(system_prompt, state)
        try:
            result = llm.invoke(messages)
            response_text = result.content
        except Exception as e:
            logger.error(f"[{agent_name.upper()}] LLM call failed: {e}")
            response_text = (
                f"Agent temporarily unavailable. Please try again.\n"
                f"Error: {str(e)}"
            )

        logger.info(f"[{agent_name.upper()}] Response length: {len(response_text)} chars")
        return {
            "response": response_text,
            "messages": [AIMessage(content=response_text)],
        }

    agent_node.__name__ = f"{agent_name}_node"
    return agent_node


# Build the 5 agent nodes
axiom_node = _make_agent_node("axiom")
sage_node = _make_agent_node("sage")
atlas_node = _make_agent_node("atlas")
pulse_node = _make_agent_node("pulse")
forge_node = _make_agent_node("forge")


# ---------------------------------------------------------------------------
# Escalation node (runs after every agent)
# ---------------------------------------------------------------------------

def escalation_node(state: HubState) -> dict:
    """
    Inspects the agent response for escalation trigger phrases.
    Populates escalation fields in state without modifying the response.
    """
    response = state.get("response", "")
    triggered, phrase, esc_type = detect_escalation(response)

    if triggered:
        logger.warning(
            f"[ESCALATION] Triggered: '{phrase}' "
            f"(type={esc_type}) in {state.get('routed_agent', 'unknown').upper()} response"
        )

    return {
        "escalation_triggered": triggered,
        "escalation_phrase": phrase,
        "escalation_type": esc_type,
    }


# ---------------------------------------------------------------------------
# Conditional routing edge
# ---------------------------------------------------------------------------

def route_to_agent(state: HubState) -> str:
    """
    Conditional edge function: reads routed_agent from state and
    returns the name of the next node to execute.
    """
    agent = state.get("routed_agent", "axiom")
    node_map = {
        "axiom": "axiom_node",
        "sage": "sage_node",
        "atlas": "atlas_node",
        "pulse": "pulse_node",
        "forge": "forge_node",
    }
    return node_map.get(agent, "axiom_node")


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_hub_graph() -> StateGraph:
    """
    Assembles and compiles the PragMind Hub LangGraph.

    Graph topology:
        START → router_node → [conditional] → agent_node → escalation_node → END
    """
    graph = StateGraph(HubState)

    # Add all nodes
    graph.add_node("router_node", router_node)
    graph.add_node("axiom_node", axiom_node)
    graph.add_node("sage_node", sage_node)
    graph.add_node("atlas_node", atlas_node)
    graph.add_node("pulse_node", pulse_node)
    graph.add_node("forge_node", forge_node)
    graph.add_node("escalation_node", escalation_node)

    # Entry: START → router
    graph.add_edge(START, "router_node")

    # Router → conditional dispatch to one of the 5 agents
    graph.add_conditional_edges(
        "router_node",
        route_to_agent,
        {
            "axiom_node": "axiom_node",
            "sage_node": "sage_node",
            "atlas_node": "atlas_node",
            "pulse_node": "pulse_node",
            "forge_node": "forge_node",
        },
    )

    # All agent nodes → escalation check → END
    for agent_node_name in ["axiom_node", "sage_node", "atlas_node", "pulse_node", "forge_node"]:
        graph.add_edge(agent_node_name, "escalation_node")

    graph.add_edge("escalation_node", END)

    return graph.compile()


# Singleton compiled graph — import this in the API layer
hub_graph = build_hub_graph()
