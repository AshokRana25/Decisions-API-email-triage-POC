"""Evaluation labels are loaded here, never by either provider."""
import json
from pathlib import Path
from .contracts import Email, ROUTES

ROOT = Path(__file__).resolve().parents[1]


def load_cases(split="development"):
    if split not in ("development", "heldout"):
        raise ValueError("Unknown split.")
    rows = [json.loads(line) for line in (ROOT / "data" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for row in rows:
        if row["id"] in seen or row["split"] != split or row.get("synthetic") is not True:
            raise ValueError("Invalid case metadata.")
        seen.add(row["id"])
        Email(row["subject"], row["body"])
        label = row["expected"]
        if type(label["action_required"]) is not bool or label["workflow"] not in ROUTES:
            raise ValueError("Invalid label.")
        if type(label["urgency"]) is not int or label["urgency"] not in range(4):
            raise ValueError("Invalid urgency label.")
        if type(label["must_review"]) is not bool:
            raise ValueError("Invalid review label.")
    return rows
