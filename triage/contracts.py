"""Local contracts and strict parsing of the documented Decisions answer types."""
from dataclasses import dataclass, asdict
import math

ROUTES = ("technical", "billing", "scheduling", "information", "review")
LEVEL_LABELS = ("Routine", "Soon", "Today", "Critical")


@dataclass(frozen=True)
class Email:
    subject: str
    body: str

    def __post_init__(self):
        if not isinstance(self.subject, str) or not isinstance(self.body, str):
            raise ValueError("Subject and body must be strings.")
        if not self.body.strip() or len(self.subject) > 300 or len(self.body) > 12000:
            raise ValueError("Use a nonempty body up to 12,000 characters and a subject up to 300.")

    def evidence(self):
        # JSON encoding gives data boundaries; it is not a prompt-injection guarantee.
        import json
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass(frozen=True)
class Decision:
    action_probability: float
    route: str
    route_confidence: float
    route_probabilities: dict
    urgency: float
    urgency_confidence: float
    urgency_probabilities: dict


class ContractError(ValueError):
    """Malformed, missing, or unexpected model output; always escalate."""


class DecisionRefused(ContractError):
    """At least one question was refused; do not use partial answers."""


def number(value, low=0.0, high=1.0):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ContractError("Invalid numeric answer.")
    return float(value)


def distribution(items, expected):
    if not isinstance(items, list) or len(items) != len(expected):
        raise ContractError("Incomplete probability distribution.")
    values = {}
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("Invalid probability entry.")
        key = item.get("value")
        # bool is an int subclass in Python, but is not a valid level index.
        if type(key) not in (str, int) or key not in expected or key in values:
            raise ContractError("Invalid or duplicate option.")
        values[key] = number(item.get("probability"))
    if abs(sum(values.values()) - 1) > 0.01:
        raise ContractError("Probabilities must sum to one.")
    return values


def parse_decision(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        raise ContractError("Missing answers array.")
    answers = payload["answers"]
    if any(isinstance(a, dict) and a.get("type") == "refusal" for a in answers):
        raise DecisionRefused("The model refused at least one question.")
    expected = {"action_required": "predicate", "workflow": "choice", "urgency": "score"}
    if len(answers) != len(expected):
        raise ContractError("Incorrect answer count.")
    named = {}
    for answer in answers:
        if not isinstance(answer, dict):
            raise ContractError("Invalid answer.")
        name = answer.get("name")
        if not isinstance(name, str) or name not in expected or name in named:
            raise ContractError("Unexpected or duplicate answer name.")
        if answer.get("type") != expected[name]:
            raise ContractError("Unexpected answer type.")
        named[name] = answer
    route = named["workflow"]
    if route.get("choice") not in ROUTES:
        raise ContractError("Unknown workflow.")
    route_probs = distribution(route.get("probabilities"), ROUTES)
    urgency = named["urgency"]
    urgency_probs = distribution(urgency.get("probabilities"), range(4))
    score = number(urgency.get("score"), 0, 3)
    # The API score is a weighted average, never an invented integer severity.
    if abs(score - sum(k * p for k, p in urgency_probs.items())) > 0.02:
        raise ContractError("Score does not match its probability distribution.")
    return Decision(
        number(named["action_required"].get("probability")), route["choice"],
        number(route.get("confidence")), route_probs, score,
        number(urgency.get("confidence")), urgency_probs,
    )
