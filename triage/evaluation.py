"""Honest offline/live evaluation: abstentions stay visible in all denominators."""
from datetime import datetime, timezone
from statistics import mean
import math
from .contracts import Email
from .service import run


def fraction(a, b):
    return a / b if b else None


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def evaluate(cases, provider, input_price_per_million=None):
    confusion = {truth: {pred: 0 for pred in ("false", "true", "abstain")} for truth in ("false", "true")}
    rows, errors, latencies = [], [], []
    exact_route, route_available, abstentions, cost, costs_known = 0, 0, 0, 0.0, 0
    safe_review_hits, safe_review_total = 0, 0
    for case in cases:
        result = run(Email(case["subject"], case["body"]), provider, input_price_per_million)
        label = case["expected"]
        rec, decision = result.recommendation, result.decision
        # End-to-end policy abstention suppresses a nominal binary answer for this metric.
        prediction = None if rec.abstained else rec.action_required
        truth = str(label["action_required"]).lower()
        pred = "abstain" if prediction is None else str(prediction).lower()
        confusion[truth][pred] += 1
        abstentions += rec.abstained
        if decision:
            route_available += 1
            exact_route += decision.route == label["workflow"]
            errors.append(abs(decision.urgency - label["urgency"]))
        if label["must_review"]:
            safe_review_total += 1
            safe_review_hits += rec.proposed_queue == "manual-review" or rec.human_review_required
        latencies.append(result.latency_ms)
        if result.cost_complete:
            costs_known += 1
            cost += result.estimated_cost_usd or 0.0
        # Never export email text, keys, or raw responses, even on failures.
        rows.append({"case_id": case["id"], "result": result.to_dict()})
    tp, fp = confusion["true"]["true"], confusion["false"]["true"]
    fn, abstain_positive = confusion["true"]["false"], confusion["true"]["abstain"]
    total = len(cases)
    return {
        "mode": provider.mode,
        "disclaimer": ("MOCK HEURISTIC PIPELINE CHECK ONLY. Not API or model-quality evidence." if provider.mode == "mock"
                       else "Live results on a tiny synthetic set; not a production quality estimate."),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": total,
        "confusion_matrix": confusion,
        "action_precision": fraction(tp, tp + fp),
        "action_recall_including_abstentions_as_misses": fraction(tp, tp + fn + abstain_positive),
        "action_recall_on_covered_cases": fraction(tp, tp + fn),
        "abstention_rate": fraction(abstentions, total),
        "workflow_exact_match_all_cases": fraction(exact_route, total),
        "workflow_valid_answer_coverage": fraction(route_available, total),
        "urgency_mae_on_valid_answers": mean(errors) if errors else None,
        "required_human_review_coverage": fraction(safe_review_hits, safe_review_total),
        "latency_ms": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95),
                       "scope": "end-to-end local call including parsing, backoff, and any API time"},
        "cost": {"known_estimated_usd": cost if math.isfinite(cost) else None, "cases_with_known_cost": costs_known,
                 "total_estimated_usd": cost if costs_known == total and math.isfinite(cost) else None,
                 "input_price_usd_per_million": input_price_per_million,
                 "note": "Estimate, not an invoice. Missing usage or retries leave total cost unknown."},
        "cases": rows,
    }
