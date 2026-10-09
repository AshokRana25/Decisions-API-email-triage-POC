"""Deterministic review policy. This module has no email or workflow side effects."""
from dataclasses import dataclass
import re

ACTION_LOW, ACTION_HIGH = 0.20, 0.80
CONFIDENCE_MIN = 0.75
CHOICE_PROBABILITY_MIN = 0.65
POLICY_VERSION = "review-only-v1"

# Demonstration defense in depth, not a complete injection or fraud detector.
SUSPICIOUS = re.compile(
    r"ignore (?:all |the |any )?(?:previous|prior|system) instructions|"
    r"system prompt|developer message|override (?:the )?(?:policy|rubric)|"
    r"execute (?:this |the )?(?:command|shell)|send (?:me |us )?(?:the )?api key",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Recommendation:
    action_required: bool | None
    proposed_queue: str
    abstained: bool
    reasons: tuple[str, ...]
    human_review_required: bool = True
    execution_allowed: bool = False
    simulation_only: bool = True


def apply_policy(email, decision=None, error=None):
    if error or decision is None:
        return Recommendation(None, "manual-review", True, (error or "missing_decision",))
    p = decision.action_probability
    action = True if p >= ACTION_HIGH else False if p <= ACTION_LOW else None
    reasons = []
    if SUSPICIOUS.search(email.subject + "\n" + email.body):
        reasons.append("suspicious_instruction_pattern")
    if action is None:
        reasons.append("uncertain_action_required")
    if decision.route == "review":
        reasons.append("fallback_workflow")
    if decision.route_confidence < CONFIDENCE_MIN:
        reasons.append("low_workflow_confidence")
    if decision.route_probabilities[decision.route] < CHOICE_PROBABILITY_MIN:
        reasons.append("diffuse_workflow_distribution")
    if decision.urgency_confidence < CONFIDENCE_MIN:
        reasons.append("low_urgency_confidence")
    if action is False and decision.route != "information":
        reasons.append("contradictory_no_action_route")
    if action is True and decision.route == "information":
        reasons.append("contradictory_action_information_route")
    if action is False and decision.urgency >= 2:
        reasons.append("contradictory_no_action_urgency")
    if reasons:
        return Recommendation(action, "manual-review", True, tuple(reasons))
    queue = {
        "technical": "technical-review", "billing": "billing-review",
        "scheduling": "calendar-review", "information": "fyi-review",
    }[decision.route]
    # This is a display label only. Even high-confidence results cannot execute actions.
    return Recommendation(action, queue, False, ("review_before_any_action",))
