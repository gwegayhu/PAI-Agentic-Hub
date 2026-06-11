"""Escalation detection logic for agent responses."""

ESCALATION_PHRASES = {
    "urgent": [
        "escalate", "urgent", "immediate attention", "critical issue",
        "urgent assistance", "right away", "asap", "priority"
    ],
    "technical": [
        "technical support", "system error", "crash", "bug", "fatal",
        "system failure", "outage"
    ],
    "handoff": [
        "transfer", "handoff", "specialist", "expert needed", "beyond scope",
        "human intervention required"
    ],
}


def detect_escalation(response: str) -> tuple[bool, str | None, str | None]:
    """
    Scan a response text for escalation trigger phrases.
    
    Returns:
        (triggered, phrase, escalation_type)
        - triggered: bool indicating if any escalation phrase was found
        - phrase: the exact phrase that triggered escalation (if any)
        - escalation_type: the category of escalation (if triggered)
    """
    response_lower = response.lower()
    
    for esc_type, phrases in ESCALATION_PHRASES.items():
        for phrase in phrases:
            if phrase in response_lower:
                return True, phrase, esc_type
    
    return False, None, None
