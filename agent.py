import os, json, re
from dotenv import load_dotenv
from google import genai
from google.genai import types
from ingest import fetch_docs

from groq import Groq

load_dotenv()

gclient = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

def _ask(prompt, json_mode=False):
    for attempt in range(2):
        for m in MODELS:
            try:
                r = gclient.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if json_mode else None,
                )
                return (r.choices[0].message.content or "").strip()
            except Exception as ex:
                print(f"{m} failed:", str(ex)[:80])
    return None



def decompose(claim, trace):
    out = _ask(f"""Split this claim into 1-3 atomic factual assertions.
Return ONLY JSON in this exact shape: {{"assertions": ["...", "..."]}}
Claim: {claim}""", json_mode=True)
    try:
        parts = json.loads(out or "{}").get("assertions", [])
        if not isinstance(parts, list) or not parts:
            raise ValueError
    except Exception:
        parts = [claim]

    trace.append({"step": "decompose", "detail": f"{len(parts)} assertion(s)", "output": parts})
    return parts

def retrieve(assertion, docs, trace, k=3):
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", assertion)]
    scored = []
    for d in docs:
        text = (d["title"] + " " + d["summary"]).lower()
        s = sum(1 for w in words if w in text)
        if s:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    hits = [d for _, d in scored[:k]]
    trace.append({"step": "retrieve", "detail": f"{len(hits)} source(s) matched",
                  "output": [{"title": h["title"][:100], "source": h["source"], "link": h["link"]} for h in hits]})
    return hits

def verdict(assertion, hits, trace):
    if not hits:
        v = {"verdict": "insufficient_evidence", "confidence": 0.0,
             "reason": "No supporting source found in live feeds.", "sources": []}
        trace.append({"step": "verdict", "detail": "no evidence -> refused", "output": v})
        return v
    ctx = "\n".join(f"[{i+1}] {h['title']} — {h['summary'][:300]}" for i, h in enumerate(hits))
    out = _ask(f"""You are a fact-checker. Judge the assertion using ONLY the sources below.
Return ONLY JSON: {{"verdict":"supported|contradicted|insufficient_evidence","confidence":0.0-1.0,"reason":"one sentence"}}

Assertion: {assertion}

Sources:
{ctx}""", json_mode=True)
    try:
        raw = (out or "{}").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end+1]
        v = json.loads(raw)
        if v.get("verdict") not in ("supported", "contradicted", "insufficient_evidence"):
            raise ValueError
    except Exception as ex:
        print("parse failed:", str(ex)[:100], "| raw:", (out or "")[:200])
        v = {"verdict": "insufficient_evidence", "confidence": 0.0,
             "reason": "Model output unparseable; abstaining.", "sources": []}
    v["sources"] = [{"title": h["title"], "source": h["source"], "link": h["link"]} for h in hits]
    trace.append({"step": "verdict", "detail": f"{v['verdict']} ({v['confidence']})", "output": v})
    return v


def verify(claim):
    trace = []
    if not claim or not claim.strip():
        return {"claim": claim, "results": [],
                "trace": [{"step": "guardrail", "detail": "empty input", "output": "Please enter a claim."}]}
    docs = fetch_docs()
    trace.append({"step": "ingest", "detail": f"{len(docs)} live documents", "output": []})
    results = []
    for a in decompose(claim, trace):
        hits = retrieve(a, docs, trace)
        results.append({"assertion": a, **verdict(a, hits, trace)})
    return {"claim": claim, "results": results, "trace": trace}

if __name__ == "__main__":
    r = verify("The Cabinet approved Dearness Allowance for central government employees.")
    print(json.dumps(r, indent=2)[:1500])
