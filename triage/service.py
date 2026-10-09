"""Orchestrate inference, parsing, deterministic review policy, and safe telemetry."""
from dataclasses import dataclass, asdict
from time import perf_counter
import math
from .contracts import ContractError, DecisionRefused, parse_decision
from .policy import apply_policy, POLICY_VERSION
from .questions import PROMPT_VERSION
from .providers import ProviderError


@dataclass(frozen=True)
class Result:
    mode: str
    status: str
    recommendation: object
    decision: object | None
    latency_ms: float
    attempts: int
    input_tokens: int | None
    estimated_cost_usd: float | None
    cost_complete: bool
    prompt_version: str = PROMPT_VERSION
    policy_version: str = POLICY_VERSION

    def to_dict(self):
        return asdict(self)


def run(email, provider, input_price_per_million=None):
    if input_price_per_million is not None:
        try:
            valid_price = (type(input_price_per_million) in (int, float)
                           and input_price_per_million >= 0 and math.isfinite(input_price_per_million))
        except OverflowError:
            valid_price = False
        if not valid_price:
            raise ValueError("Price must be a finite nonnegative USD input-token rate.")
    started = perf_counter()
    decision, payload, status, attempts = None, {}, "ok", 0
    try:
        response = provider.classify(email)
        attempts, payload = response.attempts, response.payload
        decision = parse_decision(payload)
    except DecisionRefused:
        status = "model_refusal"
    except ContractError:
        status = "invalid_response"
    except ProviderError as exc:
        status, attempts = exc.code, exc.attempts
    elapsed = (perf_counter() - started) * 1000
    recommendation = apply_policy(email, decision, None if status == "ok" else status)
    # Read only documented usage fields, and never estimate token counts from characters.
    usage = payload.get("usage") if isinstance(payload, dict) else None
    tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
    if type(tokens) is not int or tokens < 0:
        tokens = None
    cost = None
    complete = provider.mode == "mock"
    if provider.mode == "mock":
        tokens, cost = 0, 0.0
    elif attempts == 1 and tokens is not None and input_price_per_million is not None:
        try:
            estimate = (tokens / 1_000_000) * input_price_per_million
        except OverflowError:
            estimate = None
        if estimate is not None and math.isfinite(estimate):
            cost, complete = estimate, True
    # A failed/retried request can be billed without returning usage; keep total cost unknown.
    return Result(provider.mode, status, recommendation, decision, elapsed, attempts, tokens, cost, complete)
