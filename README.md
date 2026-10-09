# Decisions Email Triage Lab

A small, review-only email triage POC using the OpenAI Decisions API. Demonstrate how **predicate**, **choice**, and **score** answers become safe application recommendations.

Built with Python and Streamlit, the demo classifies whether an email needs action, recommends a technical, billing, scheduling, information, or manual-review queue, and scores urgency. It includes a deterministic offline baseline, an optional live OpenAI adapter, strict response validation, synthetic evaluation datasets, automated tests, and GitHub Actions checks.

**Runs offline by default.** All bundled emails are synthetic. Mock probabilities are manufactured for a deterministic keyword baseline; they are **not model results or quality evidence**. No inbox connection, email sending, payment, calendar update, or external workflow is implemented.

## A concrete use case

A support coordinator receives a billing question, a broken-product report, or a meeting request. The app estimates whether action is needed, selects a review workflow, and scores urgency. Python then validates the response and applies fixed review rules. A person decides what to do next.

The project demonstrates structured classification, probability-aware abstention, contract validation, failure handling, measurement, and separation of predictions from permissions. It is a portfolio learning project, not a production mail agent.

## Quick start on Windows 11

Python 3.11 or 3.12 is recommended. CPU-only is sufficient; no local model, Ollama, GPU, or large model download is needed. Live inference, if explicitly enabled, runs on OpenAI's servers.

### Get the source

On the [GitHub repository page](https://github.com/AshokRana25/Decisions-API-email-triage-POC), choose **Code → Download ZIP**, extract the archive, and open the extracted folder containing `app.py` and `requirements.txt` in PowerShell. If you received the project as a ZIP attachment, extract that ZIP and open its `Decisions-API-email-triage-POC` folder instead.

If Git is installed, you can instead clone the project:

```powershell
git clone https://github.com/AshokRana25/Decisions-API-email-triage-POC.git
cd Decisions-API-email-triage-POC
```

No API key is needed to download or run the offline demo.

### Run the app

From PowerShell in this project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the localhost address printed by Streamlit, normally http://127.0.0.1:8501. Binding is loopback-only. Do not expose this development app publicly; it has no deployment authentication or multi-user isolation.

A virtual environment does not need activation, so no PowerShell execution-policy change is necessary.

### Zero-dependency CLI

```powershell
py -3.12 -m triage demo
py -3.12 -m triage demo --case development-09
py -3.12 -m triage evaluate --split development
py -3.12 -m unittest discover -s tests -v
```

On macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python`, and the same module commands. Core CLI/tests use only the standard library; UI and SDK transport tests run when the optional packages in requirements.txt are installed.

## Try the UI in three minutes

1. Keep **Offline mock** selected. Classify “Export error.” Inspect the technical review queue and structured output.
2. Select “Instruction attack.” Observe the manual-review escalation and execution-disabled policy.
3. Select “Two unrelated requests.” The simple mock can make a classification mistake; the human-review boundary still holds. Compare with the dataset label using the CLI evaluation.
4. Change the text. The displayed result disappears until you classify again. Nothing is sent on a widget rerun.

## Optional live API mode

The contract was verified against official documentation on **2026-10-09**. Decisions is documented as **public beta**, with `gpt-6-luna` and `POST /v1/decisions`. This project pins the documented minimum Python OpenAI SDK, **3.26.0**, and calls `client.decisions.create(model=..., input=..., questions=...)`. Account access, billing, model availability, and beta schemas can change. A ChatGPT subscription alone should not be assumed to grant API access.

Live mode sends **only the selected subject/body and fixed question rubric** to OpenAI. It does not read a mailbox, contacts, unrelated files, or evaluation labels. Default examples are synthetic. Do not put credentials, private email, personal information, or confidential work material into the demo. Using any real data needs a separate privacy and authorization review.

Set `OPENAI_API_KEY` privately on your own machine. Never put a key in chat, a CLI argument, screenshots, source, or a repository. One temporary PowerShell method prompts without displaying the key or putting its value in command history:

```powershell
$secureKey = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
Remove-Variable secureKey
```

The SDK needs the key in process memory. Anyone with sufficient local access can inspect a process environment. Prefer your organization's approved secret manager for ongoing use. The application does not save it or load `.env` automatically.

Then select **OpenAI API** in the UI and approve processing of the displayed input, or explicitly run:

```powershell
.\.venv\Scripts\python.exe -m triage demo --mode live --allow-live
```

Each click or CLI live run can incur charges; it is never triggered by startup or by finding an environment key. When finished, stop the app and clear the temporary environment value:

```powershell
Remove-Item Env:OPENAI_API_KEY
```

You may explicitly select a local JSON with exactly `subject` and `body` using `--email-file private-data/example.json`. In live mode, `--allow-live` also approves sending that selected content. No other file content is transmitted. The provided ignore rules are guardrails, not a secret scanner: review staged files before publishing.

**No paid API request was needed to develop or test this project.** Contract and transport tests use local manufactured responses. Successful live operation and live model quality remain unverified until you run them with authorized access.

## Architecture

```text
Synthetic example / explicitly selected text
                |
     MockProvider or OpenAIProvider
                |
     strict typed-answer validation
                |
     deterministic review-only policy
                |
       simulated queue + metrics
                |
             a person
```

- `questions.py`: versioned observable rubrics; three independent questions share evidence.
- `providers.py`: offline keyword baseline or explicitly enabled OpenAI SDK adapter. No tools or mailbox clients.
- `contracts.py`: names, types, finite ranges, complete probability distributions, and score consistency.
- `policy.py`: fixed thresholds and permission boundary. Low confidence, uncertain action, contradictions, refusal, or invalid results escalate.
- `service.py`: safe orchestration and non-content telemetry.
- `evaluation.py`: metrics with visible abstentions and honest cost completeness.
- `app.py`: Streamlit interface; `python -m triage`: dependency-free mock CLI.

### Rubrics and policy

Action-required is a predicate. Workflows are technical, billing, scheduling, information, or review. Urgency has ordered levels 0–3: routine, soon, today, critical. The API score is a weighted average of level indices and may be fractional. It is not a probability of “urgent.” Choice/score confidence is a separate value, not assumed to equal the winning probability.

Demo thresholds are deliberately explicit and **not calibrated**: predicate ≤0.20 means no task, ≥0.80 means task, and the middle abstains. Workflow and urgency confidence must be ≥0.75; the selected workflow probability must be ≥0.65. Application-side contradictions and simple suspicious-instruction patterns escalate. Pattern matching and prompt instructions cannot reliably prevent every injection or fraud attempt.

**Every result requires human review, including high-confidence billing and scheduling cases.** No model answer can grant execution permission. Even a missed injection cannot trigger an email, payment, deletion, or calendar edit because no such capability exists in the application.

### Failures and retries

- Per-question refusal, incomplete/malformed output, unknown workflow, NaN, invalid probabilities, or inconsistent score: fail closed to manual review; partial successful answers are not used.
- SDK automatic retries are disabled. At most two attempts are made for HTTP 408/409/429/5xx. A valid Retry-After is honored only within the 2-second wait budget; longer/invalid delays defer to review instead of retrying early. Quota/billing errors are not retried.
- Connection errors and timeouts are **not retried** because the server may already have processed the request. The configured HTTP timeout is 20 seconds per SDK request phase, not a guaranteed wall-clock deadline.
- Error text shown to the user is sanitized. Raw responses, email bodies, credentials, and transport exception details are not logged by application code. Do not enable SDK/HTTP debug logging with real data.
- A failed or retried live request may have cost not represented by the final successful usage. The demo reports such total cost as unknown.

## Evaluation without misleading claims

`data/development.jsonl` and `data/heldout.jsonl` contain 12 synthetic, hand-labeled cases each. Labels express the author's rubric judgment; they are not independently adjudicated truth. Held-out examples are separate from development examples. Providers receive only the subject/body, never IDs or labels, and do not read evaluation files. The mock rules are not fit to held-out labels.

Develop prompts/thresholds on the development split, freeze them, then evaluate held-out once for a meaningful model experiment. This repository's repeated deterministic held-out pipeline checks are **software checks**, not evidence of generalization. If you tune after looking at held-out mistakes, create a fresh independent holdout. Real deployment needs representative, privacy-approved data, adjudicated labels, class-balanced coverage, calibration, and uncertainty estimates.

```powershell
py -3.12 -m triage evaluate --split heldout
# Optional authorized live experiment: up to 12 initial API calls, with bounded retries.
.\.venv\Scripts\python.exe -m triage evaluate --split heldout --mode live --allow-live
```

Metrics include a binary confusion matrix with an explicit abstain column, action precision, recall counting positive abstentions as misses, recall on covered cases, abstention rate, raw workflow exact match across all cases, answer coverage, urgency MAE on valid answers, human-review coverage, and local elapsed p50/p95. Human-review coverage verifies a safety invariant, not model quality. Route metrics are raw classification metrics, separate from downstream policy abstention. Empty denominators return null.

Token usage uses the documented `usage.input_tokens` field. Cost estimates require an explicitly supplied, currently verified effective `--input-price-per-million` USD rate. We do not hard-code pricing or invent token counts. Regional/long-context adjustments and retried or failed usage can invalidate a simple estimate; the account's actual usage/billing is authoritative. Mock has zero API usage and cost. Latency includes local processing and retry delay and is not a model-speed benchmark.

The CLI prints structured output but does not automatically save it. If needed, redirect to an ignored `results/` folder. Do not publish real-input result files.

## Tests and publication

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py triage tests
```

Tests never need credentials or make live paid requests. They cover parsing, refusals, probability/range checks, fail-closed policy, retries, explicit live opt-in, data separation, metric denominators, and UI flows. See [verification notes](docs/VERIFICATION.md) for what was actually run.

The source is ready to review for a separate portfolio repository. No destination, repository visibility change, push, or deployment is performed by the app. Publish only after confirming the destination and reviewing staged contents. The example GitHub workflow runs offline tests and synthetic evaluations; it uses no API key.

## Primary references

- [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)
- [Decisions HTTP request/response reference](https://developers.openai.com/api/reference/resources/decisions/methods/create)
- [Decisions Python reference](https://developers.openai.com/api/reference/python/resources/decisions/methods/create)
- [Python SDK errors, retries and timeouts](https://developers.openai.com/api/reference/python)
- [API rate-limit guidance](https://developers.openai.com/api/docs/guides/rate-limits)
- [API pricing](https://developers.openai.com/api/docs/pricing)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)
