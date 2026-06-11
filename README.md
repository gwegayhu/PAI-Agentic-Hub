# PragMind Agentic Hub — LangGraph Backend

Five specialised AI agents orchestrated in a single LangGraph hub graph,
served via FastAPI. Built for PragMind AI · Dubai.

---

## Architecture

```
POST /hub/run
      │
      ▼
 router_node          ← Classifies input, selects 1 of 5 agents
      │
      ▼ (conditional edge)
 ┌────┴─────────────────────────────────┐
 │  axiom_node  │ sage_node │ atlas_node │
 │  pulse_node  │ forge_node             │
 └────┬─────────────────────────────────┘
      │
      ▼
 escalation_node      ← Scans response for trigger phrases
      │
      ▼
     END
```

All 5 agents run on `claude-sonnet-4-20250514`. Forge uses a larger
context window (8192 tokens). No persistence — state is in-memory per request.

---

## Project Structure

```
pragmind_hub/
├── main.py                   ← Entry point (uvicorn)
├── requirements.txt
├── .env.example
├── config/
│   └── settings.py           ← Env vars, escalation phrases
├── models/
│   └── schemas.py            ← Pydantic request/response models
├── agents/
│   ├── prompts.py            ← All 5 system prompts + router prompt (verbatim from spec)
│   └── escalation.py        ← Escalation phrase detector
├── graphs/
│   ├── state.py              ← HubState TypedDict
│   └── hub_graph.py         ← LangGraph graph assembly
└── api/
    └── app.py                ← FastAPI endpoints
```

---

## Setup

**1. Clone and install**
```bash
cd pragmind_hub
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

**3. Run**
```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**4. Open API docs**
```
http://localhost:8000/docs
```

---

## Endpoints

### `GET /health`
Returns service status.

```json
{"status": "ok", "service": "PragMind Agentic Hub", "model": "claude-sonnet-4-20250514"}
```

---

### `GET /agents`
Returns metadata for all 5 agents (name, role, icon, accent colour, input hint).

---

### `POST /agents/run`
Run a **specific agent directly** — no routing step.
Use this when your caller already knows which agent to invoke.

**Request:**
```json
{
  "agent": "axiom",
  "message": "Client: 150-person UAE logistics firm. Uses Excel for all data...",
  "history": []
}
```

**Response:**
```json
{
  "agent": "axiom",
  "response": "### AI READINESS ASSESSMENT — ...",
  "escalation": {
    "triggered": false,
    "phrase": null,
    "type": null
  }
}
```

**Multi-turn example** (pass prior turns in `history`):
```json
{
  "agent": "atlas",
  "message": "Can you add a compliance section for the finance sector?",
  "history": [
    {"role": "user", "content": "Run Atlas for a Dubai insurance company..."},
    {"role": "assistant", "content": "[DRAFT — REQUIRES PRAGMIND REVIEW]..."}
  ]
}
```

---

### `POST /hub/run`
Send a message to the **hub router**. Claude classifies the intent and
dispatches to the correct agent automatically.

**Request:**
```json
{
  "message": "Design a multi-agent credit risk system for a Dubai bank",
  "history": []
}
```

**Response:**
```json
{
  "routed_to": "forge",
  "routing_reason": "Request asks for multi-agent system design — Forge's domain.",
  "response": "[ARCHITECTURAL SPECIFICATION — REQUIRES PRAGMIND DELIVERY TEAM REVIEW]...",
  "escalation": {
    "triggered": false,
    "phrase": null,
    "type": null
  }
}
```

---

## Escalation Flags

When an agent response contains a trigger phrase, the `escalation` object
is populated. Your frontend should render these as alert banners.

| `type`          | Trigger phrase                          | UI treatment                        |
|-----------------|-----------------------------------------|-------------------------------------|
| `escalation`    | `ESCALATION REQUIRED`                   | ⚠️ Amber — requires human review     |
| `clarification` | `CLARIFICATION REQUIRED`                | 📋 Blue — more input needed          |
| `anomaly`       | `ANOMALY ALERT`                         | 🚨 Red — unusual data movement       |
| `draft`         | `DRAFT — REQUIRES PRAGMIND REVIEW`      | 📝 Yellow — do not send to client    |

---

## Connecting to Base44

In your Base44 app, replace direct Anthropic API calls with calls to this backend:

**Direct agent call:**
```javascript
const res = await fetch("https://your-backend-url/agents/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    agent: "axiom",
    message: userInput,
    history: conversationHistory
  })
});
const data = await res.json();
// data.response — the agent's reply
// data.escalation.triggered — whether to show an alert banner
```

**Hub auto-routing:**
```javascript
const res = await fetch("https://your-backend-url/hub/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userInput, history: [] })
});
const data = await res.json();
// data.routed_to — which agent handled it
// data.response — the agent's reply
```

---

## Deployment

The backend is stateless (in-memory only). Deploy to any platform:

| Platform  | Command                                              |
|-----------|------------------------------------------------------|
| Render    | Set `ANTHROPIC_API_KEY` env var, start cmd: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Railway   | Same as above                                        |
| Docker    | `docker build -t pragmind-hub . && docker run -p 8000:8000 pragmind-hub` |

**CORS:** The app currently allows `*` origins. Before production, update
`allow_origins` in `api/app.py` to your Base44 domain.

---

## Agent Quick Reference

| Agent  | Endpoint `agent` value | Best for                                |
|--------|------------------------|-----------------------------------------|
| Axiom  | `axiom`                | AI readiness scoring, maturity reports  |
| Sage   | `sage`                 | PragMind internal knowledge questions   |
| Atlas  | `atlas`                | Proposal generation from discovery notes|
| Pulse  | `pulse`                | Weekly data briefs for executives       |
| Forge  | `forge`                | Multi-agent system architecture         |
