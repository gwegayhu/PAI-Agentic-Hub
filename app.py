"""
PragMind Agentic Hub — FastAPI Application
==========================================
Endpoints:

  POST /agents/run          — Run a specific agent directly (bypass router)
  POST /hub/run             — Send a message to the hub; router selects the agent
  GET  /agents              — List all 5 agents with metadata
  GET  /health              — Health check
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from models.schemas import (
    AgentName,
    ChatMessage,
    RunAgentRequest,
    RunAgentResponse,
    HubRouteRequest,
    HubRouteResponse,
    EscalationFlag,
)
from agents.prompts import AGENT_PROMPTS
from agents.escalation import detect_escalation
from graphs.hub_graph import hub_graph
from config.settings import MODEL_NAME, MAX_TOKENS, FORGE_MAX_TOKENS

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage as LCSystemMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PragMind Agentic Hub starting up...")
    logger.info(f"Model: {MODEL_NAME}")
    yield
    logger.info("PragMind Agentic Hub shutting down.")


app = FastAPI(
    title="PragMind Agentic Hub",
    description=(
        "Five specialised AI agents for PragMind AI — Dubai. "
        "Powered by LangGraph + Claude Sonnet 4."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten to your Base44 domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Agent metadata (for the /agents list endpoint)
# ---------------------------------------------------------------------------

AGENT_METADATA = {
    "axiom": {
        "name": "Axiom",
        "role": "AI Readiness Assessment Agent",
        "icon": "🧭",
        "accent": "#4A9EDB",
        "mission": (
            "Conducts structured AI Readiness Assessments. Scores maturity across "
            "5 dimensions, produces a prioritised adoption roadmap, and maps findings "
            "to PragMind's service portfolio."
        ),
        "tags": ["AI Strategy", "Consulting", "Discovery"],
        "input_hint": (
            "Provide: client industry, company size, current tech stack, "
            "top 3 business goals, data infrastructure description, "
            "any AI initiatives attempted, and budget signal (high/medium/low)."
        ),
    },
    "sage": {
        "name": "Sage",
        "role": "RAG Knowledge Agent",
        "icon": "🧠",
        "accent": "#2EC67A",
        "mission": (
            "PragMind's institutional memory. Answers questions using retrieval-augmented "
            "generation over PragMind's internal knowledge base with full source citations."
        ),
        "tags": ["RAG / LLM", "Internal Knowledge", "LangChain"],
        "input_hint": (
            "Ask any question about PragMind's services, past work, frameworks, or SOPs. "
            "Optionally specify: audience type (internal team / client-facing)."
        ),
    },
    "atlas": {
        "name": "Atlas",
        "role": "Proposal Generator",
        "icon": "📐",
        "accent": "#E0A835",
        "mission": (
            "Converts discovery call notes into fully scoped, technically credible "
            "PragMind proposals. Produces same-day proposals at consistent quality."
        ),
        "tags": ["AI Consulting", "Proposals", "Pydantic AI"],
        "input_hint": (
            "Provide: discovery call notes, client industry, stated goals, "
            "tech environment, budget signal (high/medium/low), "
            "proposal audience (technical / executive / mixed)."
        ),
    },
    "pulse": {
        "name": "Pulse",
        "role": "Data Insight Narrator",
        "icon": "📊",
        "accent": "#9B8FF8",
        "mission": (
            "Transforms data exports into weekly executive insight briefs. "
            "Translates numbers into business language that non-technical stakeholders "
            "can act on."
        ),
        "tags": ["Data Analytics", "Power BI / Tableau", "Retainer Service"],
        "input_hint": (
            "Provide: weekly data export or paste metrics directly, client business "
            "context (industry, revenue scale, strategic priority), prior week's values "
            "for comparison, and any anomaly thresholds if defined."
        ),
    },
    "forge": {
        "name": "Forge",
        "role": "Agentic Workflow Architect",
        "icon": "⚙️",
        "accent": "#D17DF5",
        "mission": (
            "Designs complete multi-agent systems — technical architecture, "
            "individual agent specs with production-ready prompts, inter-agent "
            "communication protocols, and deployment blueprints."
        ),
        "tags": ["Agentic Workflows", "LangGraph / CrewAI", "Prompt Engineering"],
        "input_hint": (
            "Provide: client business process description, pain points, "
            "existing tools/systems, team technical level, volume/scale requirements, "
            "and what systems the solution must integrate with."
        ),
    },
}


# ---------------------------------------------------------------------------
# Helper: convert API ChatMessage list → LangChain message objects
# ---------------------------------------------------------------------------

def _to_lc_messages(history: list[ChatMessage]):
    lc_msgs = []
    for m in history:
        if m.role == "user":
            lc_msgs.append(HumanMessage(content=m.content))
        else:
            lc_msgs.append(AIMessage(content=m.content))
    return lc_msgs


def _build_escalation_flag(triggered: bool, phrase: str | None, esc_type: str | None) -> EscalationFlag:
    return EscalationFlag(triggered=triggered, phrase=phrase, type=esc_type)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "PragMind Agentic Hub", "model": MODEL_NAME}


@app.get("/agents")
async def list_agents():
    """Return metadata for all 5 agents."""
    return {"agents": AGENT_METADATA}


@app.post("/agents/run", response_model=RunAgentResponse)
async def run_agent(request: RunAgentRequest):
    """
    Run a specific agent directly — no routing.
    Useful when the caller already knows which agent to use.
    Pass full conversation history in `history` for multi-turn context.
    """
    agent_name = request.agent.value
    system_prompt = AGENT_PROMPTS.get(agent_name)
    if not system_prompt:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    # Build message list: system prompt + history + new user message
    lc_history = _to_lc_messages(request.history)
    lc_history.append(HumanMessage(content=request.message))

    # Select LLM (Forge gets larger context window)
    max_tok = FORGE_MAX_TOKENS if agent_name == "forge" else MAX_TOKENS
    llm = ChatAnthropic(model=MODEL_NAME, max_tokens=max_tok)

    messages = [LCSystemMessage(content=system_prompt)] + lc_history

    try:
        result = llm.invoke(messages)
        response_text = result.content
    except Exception as e:
        logger.error(f"[/agents/run] {agent_name} LLM call failed: {e}")
        raise HTTPException(status_code=502, detail=f"Agent call failed: {str(e)}")

    triggered, phrase, esc_type = detect_escalation(response_text)

    return RunAgentResponse(
        agent=request.agent,
        response=response_text,
        escalation=_build_escalation_flag(triggered, phrase, esc_type),
    )


@app.post("/hub/run", response_model=HubRouteResponse)
async def hub_run(request: HubRouteRequest):
    """
    Send a message to the hub. The router node classifies it and dispatches
    to the appropriate agent automatically.
    """
    # Build initial state
    lc_history = _to_lc_messages(request.history)
    lc_history.append(HumanMessage(content=request.message))

    initial_state: dict = {
        "messages": lc_history,
        "routed_agent": None,
        "routing_reason": None,
        "response": None,
        "escalation_triggered": False,
        "escalation_phrase": None,
        "escalation_type": None,
    }

    try:
        final_state = hub_graph.invoke(initial_state)
    except Exception as e:
        logger.error(f"[/hub/run] Graph execution failed: {e}")
        raise HTTPException(status_code=502, detail=f"Hub graph failed: {str(e)}")

    routed_agent = final_state.get("routed_agent", "axiom")
    routing_reason = final_state.get("routing_reason", "")
    response_text = final_state.get("response", "")
    triggered = final_state.get("escalation_triggered", False)
    phrase = final_state.get("escalation_phrase")
    esc_type = final_state.get("escalation_type")

    return HubRouteResponse(
        routed_to=AgentName(routed_agent),
        routing_reason=routing_reason,
        response=response_text,
        escalation=_build_escalation_flag(triggered, phrase, esc_type),
    )
