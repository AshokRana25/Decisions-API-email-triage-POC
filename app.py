"""Local-only Streamlit presentation. Clicking classify is the only inference trigger."""
import hashlib
import json
import streamlit as st
from triage.contracts import Email
from triage.data import load_cases
from triage.providers import MockProvider, OpenAIProvider, ProviderError
from triage.service import run
from triage.policy import ACTION_LOW, ACTION_HIGH, CONFIDENCE_MIN

st.set_page_config(page_title="Decisions • Email Triage Lab", page_icon="✉️", layout="wide")
st.title("Email Triage Lab")
st.caption("A small Decisions API portfolio project · synthetic examples · human review always")

with st.sidebar:
    st.header("Run controls")
    mode = st.radio("Provider", ["Offline mock", "OpenAI API"])
    st.info("Mock is a keyword baseline with manufactured probabilities. It tests the pipeline, not model quality.")
    st.caption("No inbox connection, emails, payments, calendar changes, or workflow execution.")
    st.divider()
    st.write("Three independent questions")
    st.write("1. Does the recipient need to act?\n2. Which review workflow fits?\n3. How time-sensitive is it?")
    st.caption(f"Demo thresholds: action ≤ {ACTION_LOW} / ≥ {ACTION_HIGH}; confidence ≥ {CONFIDENCE_MIN}. Not calibrated.")

cases = load_cases("development")
selected = st.selectbox("Synthetic scenario", options=range(len(cases)),
                        format_func=lambda i: cases[i]["subject"])
case = cases[selected]
left, right = st.columns([1.05, 1])
with left:
    st.subheader("1 · Inspect the evidence")
    subject = st.text_input("Subject", value=case["subject"], max_chars=300, key=f"subject-{selected}")
    body = st.text_area("Email body", value=case["body"], height=220, max_chars=12000, key=f"body-{selected}")
    st.caption("Edits stay local in mock mode. Use synthetic text; do not paste private inbox data or secrets.")
    fingerprint = hashlib.sha256(json.dumps([mode, subject, body], ensure_ascii=False).encode()).hexdigest()
    allowed = True
    if mode == "OpenAI API":
        st.warning("Live mode sends this subject and body plus the fixed rubric to OpenAI and may incur API charges. "
                   "An eligible API account and a locally configured OPENAI_API_KEY are required. No key is entered here.")
        allowed = st.checkbox("I approve paid OpenAI processing of this selected content.", key="consent-" + fingerprint)
    clicked = st.button("Classify for human review", type="primary", disabled=not allowed)
    if clicked:
        provider = None
        try:
            email = Email(subject, body)
            provider = OpenAIProvider(allow_live=allowed) if mode == "OpenAI API" else MockProvider()
            with st.spinner("Evaluating the selected content…"):
                result = run(email, provider)
            st.session_state["latest"] = (fingerprint, result)
        except ValueError:
            st.error("Use a nonempty email body within the displayed size limits.")
        except ProviderError as exc:
            st.error("Live mode could not start: " + exc.code.replace("_", " ") + ". See the README setup steps.")
            st.session_state.pop("latest", None)
        finally:
            if provider is not None and hasattr(provider, "close"):
                provider.close()

with right:
    st.subheader("2 · Review the recommendation")
    latest = st.session_state.get("latest")
    if latest and latest[0] == fingerprint:
        result = latest[1]
        rec, dec = result.recommendation, result.decision
        if result.mode == "mock":
            st.warning("OFFLINE MOCK • manufactured probabilities • no API call")
        else:
            st.info("LIVE API • selected content was sent to OpenAI")
        st.success("Proposed queue: " + rec.proposed_queue)
        st.write("Human review required. Execution disabled.")
        st.caption("Policy reasons: " + ", ".join(r.replace("_", " ") for r in rec.reasons))
        if dec:
            a, b, c = st.columns(3)
            a.metric("Action probability", f"{dec.action_probability:.0%}")
            b.metric("Workflow", dec.route)
            c.metric("Urgency", f"{dec.urgency:.2f} / 3")
            st.caption("Urgency is a probability-weighted score, not an integer label. Confidence is a separate API field.")
            st.write(f"Workflow confidence: {dec.route_confidence:.2f} · Urgency confidence: {dec.urgency_confidence:.2f}")
        st.caption(f"Status: {result.status} · Local elapsed time: {result.latency_ms:.1f} ms · API attempts: {result.attempts}")
        with st.expander("Inspect safe structured output"):
            st.json(result.to_dict())
    else:
        st.info("Choose a scenario, inspect its text, and classify. Changing inputs clears the displayed result.")

st.divider()
st.subheader("3 · Understand the boundary")
st.write("Classification → validated answers → deterministic review policy → simulated queue. "
         "A model prediction is never permission to send, pay, delete, or schedule.")
with st.expander("Urgency rubric and evaluation"):
    st.write("0 Routine: no deadline or optional task. 1 Soon: ordinary unresolved task. "
             "2 Today: explicit 24-hour deadline or one person's work blocked. "
             "3 Critical: stated active security incident or widespread service interruption.")
    st.write("The CLI evaluates separate development and held-out synthetic files, including confusion matrices, "
             "abstentions, route exact match, urgency error, elapsed time, and optional token-cost estimates. "
             "No live model performance has been claimed.")
