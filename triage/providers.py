"""Offline heuristic provider and explicitly enabled OpenAI provider."""
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import os
import time
from datetime import datetime, timezone

from .contracts import ROUTES, LEVEL_LABELS
from .questions import MODEL, questions


class ProviderError(RuntimeError):
    def __init__(self, code, attempts=0):
        self.code = code
        self.attempts = attempts
        super().__init__(code)  # Never include raw remote responses, input, or keys.


@dataclass(frozen=True)
class ProviderResponse:
    payload: dict
    attempts: int


def fixture_payload(action, route, urgency, confidence=0.90):
    """Manufactured probabilities, only for deterministic demonstrations and contract tests."""
    return {"model": "offline-heuristic", "answers": [
        {"name": "action_required", "type": "predicate", "probability": action},
        {"name": "workflow", "type": "choice", "choice": route, "confidence": confidence,
         "probabilities": [{"value": v, "probability": 0.9 if v == route else 0.025} for v in ROUTES]},
        {"name": "urgency", "type": "score", "score": float(urgency), "confidence": confidence,
         "probabilities": [{"value": n, "label": label, "probability": float(n == urgency)}
                           for n, label in enumerate(LEVEL_LABELS)]},
    ]}


class MockProvider:
    mode = "mock"

    def classify(self, email):
        text = (email.subject + "\n" + email.body).lower()
        # Intentional simple baseline; does not read cases, labels, IDs, or evaluation files.
        if any(s in text for s in ("no action needed", "for your information", "weekly newsletter", "all resolved", "thanks, received")):
            action, route = 0.05, "information"
        elif any(s in text for s in ("invoice", "refund", "payment", "charged", "bank account")):
            action, route = 0.95, "billing"
        elif any(s in text for s in ("meeting", "reschedule", "appointment", "calendar")):
            action, route = 0.95, "scheduling"
        elif any(s in text for s in ("error", "outage", "bug", "cannot log in", "not working", "feature request")):
            action, route = 0.95, "technical"
        else:
            action, route = 0.50, "review"
        urgency = 3 if any(s in text for s in ("service-wide outage", "all customers blocked", "active security incident")) else (
            2 if any(s in text for s in ("today", "within 24 hours", "no workaround")) else (0 if action < 0.2 else 1))
        return ProviderResponse(fixture_payload(action, route, urgency), 0)


def retry_delay(headers, attempt):
    """Honor Retry-After up to the bounded retry window; defer if it asks for longer."""
    value = headers.get("retry-after") if headers else None
    if value is not None:
        try:
            delay = float(value)
        except (ValueError, TypeError):
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return None
        # NaN/inf fail closed, as do delays exceeding this POC's small wait budget.
        if not 0 <= delay <= 2:
            return None
        return delay
    return 0.5 * attempt


class OpenAIProvider:
    mode = "live"

    def __init__(self, *, allow_live=False):
        # Opt-in checked before imports, credential reads, or client construction.
        if not allow_live:
            raise ProviderError("live_opt_in_required")
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ProviderError("missing_api_key")
        try:
            import openai
        except ImportError:
            raise ProviderError("install_live_dependencies") from None
        self.sdk = openai
        self.client = openai.OpenAI(
            api_key=key, base_url="https://api.openai.com/v1", timeout=20.0, max_retries=0,
        )
        if not hasattr(self.client, "decisions"):
            self.client.close()
            raise ProviderError("openai_sdk_3_26_or_newer_required")

    def close(self):
        self.client.close()

    def classify(self, email):
        for attempt in range(1, 3):
            try:
                response = self.client.decisions.create(model=MODEL, input=email.evidence(), questions=questions())
                dump = getattr(response, "model_dump", None)
                if not callable(dump):
                    raise ProviderError("invalid_response", attempt)
                payload = dump(warnings=False)
                if not isinstance(payload, dict):
                    raise ProviderError("invalid_response", attempt)
                return ProviderResponse(payload, attempt)
            except self.sdk.APIStatusError as exc:
                code = getattr(exc, "code", None)
                status = exc.status_code
                if code in ("insufficient_quota", "billing_hard_limit_reached"):
                    raise ProviderError("quota_or_billing_error", attempt) from None
                retryable = status in (408, 409, 429) or status >= 500
                delay = retry_delay(exc.response.headers, attempt)
                if retryable and attempt < 2 and delay is not None:
                    time.sleep(delay)
                    continue
                message = {401: "authentication_error", 403: "access_denied", 404: "endpoint_or_model_unavailable",
                           429: "rate_limited"}.get(status, "api_status_error")
                raise ProviderError(message, attempt) from None
            except self.sdk.APIConnectionError:
                # No resend after ambiguous connection/timeout failures: request may have run.
                raise ProviderError("connection_or_timeout_error", attempt) from None
            except (self.sdk.APIResponseValidationError, ValueError):
                raise ProviderError("invalid_response", attempt) from None
            except self.sdk.APIError:
                raise ProviderError("api_error", attempt) from None
        raise ProviderError("retry_limit_reached", 2)
