# Portfolio walkthrough

## The problem

Support email triage mixes three different questions: whether action is needed, who should review it, and how soon it needs attention. A single free-form answer makes validation and measurement harder.

## The design

Use three typed Decisions API questions over shared evidence, validate every answer, and make application permissions deterministic. Uncertain or invalid output goes to manual review. Even confident output stays review-only.

## A short demonstration

1. Show the offline mock label and explain that no API key is needed.
2. Classify a technical support request and inspect the three output types.
3. Classify the instruction-attack example and explain why a prediction cannot authorize an action.
4. Run the held-out mock evaluation and point out the abstention column and baseline errors.
5. Show the optional live adapter and its consent, retry, failure, and usage-accounting boundaries. Be explicit that live results have not been measured yet.

## What this project demonstrates

Typed integration, defensive parsing, separation of model output from execution authority, synthetic data design, conservative abstention, deterministic offline tests, in-memory SDK contract testing, and honest measurement.

## What a production version would still need

Privacy-approved representative data, independent labeling, calibrated thresholds, monitoring, real access control, audit trails, idempotent approved actions, account-specific API validation, a deployment threat model, and robust prompt-injection defenses. Connecting a real mailbox would be a separately authorized project, not a small configuration switch.
