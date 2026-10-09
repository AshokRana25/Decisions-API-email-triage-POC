"""No dependencies needed for mock mode: python -m triage --help."""
import argparse
import json
import sys
from pathlib import Path
from .contracts import Email
from .data import load_cases
from .evaluation import evaluate
from .providers import MockProvider, OpenAIProvider, ProviderError
from .service import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetic email triage. All actions are review-only simulations.")
    parser.add_argument("command", choices=["demo", "evaluate"], nargs="?", default="demo")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--allow-live", action="store_true", help="Consent to paid API processing of selected content by OpenAI.")
    parser.add_argument("--split", choices=["development", "heldout"], default="development")
    parser.add_argument("--case", default=None, help="Synthetic case ID; defaults to first in split.")
    parser.add_argument("--email-file", type=Path, help="Explicitly selected local JSON containing only subject and body.")
    parser.add_argument("--input-price-per-million", type=float, default=None, help="Verified effective USD input-token rate, optional.")
    args = parser.parse_args(argv)
    if args.mode == "live" and not args.allow_live:
        parser.error("Live mode requires --allow-live. It sends selected content to OpenAI and may incur charges.")
    if args.email_file and args.command != "demo":
        parser.error("--email-file is only valid for demo.")
    provider = None
    try:
        if args.email_file:
            if args.email_file.stat().st_size > 64000:
                raise ValueError("Selected email file is too large.")
            content = json.loads(args.email_file.read_text(encoding="utf-8"))
            if not isinstance(content, dict) or set(content) != {"subject", "body"}:
                raise ValueError("Email JSON must contain only subject and body.")
            email = Email(**content)
        else:
            cases = load_cases(args.split)
            if args.command == "demo":
                case = next((c for c in cases if c["id"] == args.case), None) if args.case else cases[0]
                if case is None:
                    raise ValueError("Unknown case ID.")
                email = Email(case["subject"], case["body"])
        provider = OpenAIProvider(allow_live=args.allow_live) if args.mode == "live" else MockProvider()
        output = (evaluate(cases, provider, args.input_price_per_million) if args.command == "evaluate"
                  else run(email, provider, args.input_price_per_million).to_dict())
        print(json.dumps(output, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, ProviderError):
        # No raw SDK exception, file content, environment, or API key in output.
        print("Unable to run. Check your selected input, live opt-in, SDK installation, and local key configuration.", file=sys.stderr)
        return 2
    finally:
        if provider is not None and hasattr(provider, "close"):
            provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
