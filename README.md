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
