# Forge Verify — Real-Time Fact-Verification & Deepfake Audit Engine

Agentic verification pipeline that checks claims against live news feeds and refuses to answer without a citable source.

## Pipeline
Live RSS ingestion → claim decomposition → retrieval → evidence-constrained verdict

## Run
pip install -r requirements.txt
streamlit run app.py

## Design
- Grounded abstention: no source, no verdict
- Structured JSON output enforced at the model level
- Full agent trace for auditability
- Model fallback, request timeouts, and retry handling for resilience under load

## Sources
Live Google News and The Hindu RSS. No mock data.


## Known Limitation: API Rate Limits

The judge step depends on a hosted LLM API with a free-tier request quota. When that quota is exhausted, the API returns `429 RESOURCE_EXHAUSTED` and the pipeline cannot produce a verdict.

This is handled by design, not by failure:

- **Grounded abstention.** If the judge call fails or returns unparseable output, the system returns `insufficient_evidence` with confidence 0.0 rather than guessing. It never fabricates a verdict.
- **Model fallback.** The judge tries a second model before giving up.
- **Request timeouts.** A stalled call aborts after 20 seconds instead of hanging the pipeline.
- **Full trace.** Every run records ingestion count, assertions generated, sources matched, and the verdict path — so a degraded run is visible and auditable, not silent.

A live demo during a quota-exhausted window will show the retrieval step succeeding (correct sources matched) while the verdict step abstains. This is the intended behaviour: the system refuses to answer without a citable source.
