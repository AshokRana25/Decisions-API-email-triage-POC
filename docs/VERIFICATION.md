# Verification record

Verified on 2026-10-09 using Python 3.12.14 in a Linux cloud workspace. This record is about software behavior, not live model accuracy.

## Passed

- Full suite: **40 tests passed, no skips**, with OpenAI SDK 3.26.0 and Streamlit 1.50.0 installed in an isolated virtual environment.
- The full suite was also run with socket connections blocked at the Python socket layer. SDK tests used an in-memory transport; no paid API request was made.
- Standard-library-only run: **25 tests passed, 15 optional SDK/UI tests skipped** as designed.
- Python compilation of app, modules, and tests.
- `pip check`: no broken requirements in the test environment.
- Mock CLI demo, suspicious-instruction demo, development evaluation, and held-out evaluation completed.
- Streamlit server started on loopback; `/_stcore/health` returned HTTP 200 with `ok`.
- Streamlit AppTest checked classification, repeated clicks, scenario switches, stale-result clearing, live opt-in, consent reset on changed content, unambiguous consent fingerprints, and missing-key handling.
- The installed SDK generated the documented `POST /v1/decisions` request with three question types, using a local fake HTTP response. This is a contract/serialization test, not a live integration test.
- Independent review found malformed response, serialization warning, numeric overflow, and consent-fingerprint edge cases. These were fixed and regression-tested.

## Examples of tested failure handling

Partial refusal, missing/duplicate answers, unknown route, wrong type, non-object JSON, malformed JSON, out-of-range/NaN/infinite/oversized numeric values, inconsistent distributions, contradictory classifications, suspicious instruction patterns, quota/authentication errors, bounded rate-limit/server retries, long Retry-After, and ambiguous connection/timeout failure.

Remote error bodies and malformed field values are not echoed into application output or serializer warnings. Cost remains unknown when usage is incomplete, requests were retried, or arithmetic cannot represent an estimate safely.

## Deliberately not claimed

- No live OpenAI API call, account-access test, paid usage, model-quality benchmark, latency benchmark, or production calibration.
- No Windows execution was available. Windows instructions use standard Python/PowerShell commands but were not run on Windows.
- No pixel-level browser screenshot review. UI behavior was tested using Streamlit AppTest and server health.
- No GitHub repository creation, push, CI run, deployment, mailbox connection, or workflow execution.
- No penetration test, independent label adjudication, production privacy/compliance review, or complete dependency security audit.

Both synthetic data splits are tiny and author-labeled. Their mock metrics only show that the evaluation pipeline works and can expose baseline mistakes. They must not be presented as Decisions API accuracy results.

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py triage tests
python -m triage evaluate --split development
python -m triage evaluate --split heldout
python -m pip check
```

No credential is required. Keep offline mode selected for reproducible checks.
