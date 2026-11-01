import os, json, re
from dotenv import load_dotenv
from ingest import fetch_docs
from groq import Groq

load_dotenv()

gclient = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

STOPWORDS = {"the", "and", "for", "that", "with", "from", "this", "have", "has", "was",
             "were", "are", "will", "been", "its", "their", "which", "into", "over",
             "under", "about", "after", "before", "said", "says", "also", "than",
             "then", "they", "them", "not", "but", "all", "any", "can", "may", "more",
             "most", "such", "some", "only"}


def _ask(prompt, json_mode=False):
    for attempt in range(2):
        for m in MODELS:
            try:
                r = gclient.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if json_mode else None,
                    timeout=20,
                )
                return (r.choices[0].message.content or "").strip()
            except Exception as ex:
                print(f"{m} failed:", str(ex)[:80])
    return None


def keywords(assertion, k=8):
    words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]{3,}", assertion)]
    return [w for w in words if w not in STOPWORDS][:k]


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
    words = keywords(assertion)
    scored = []
    for d in docs:
        text = (d["title"] + " " + d["summary"]).lower()
        matched = {w for w in words if w in text}
        if len(matched) >= 2:
            scored.append((len(matched), d))
    scored.sort(key=lambda x: -x[0])
    hits = [d for _, d in scored[:k]]
    trace.append({"step": "retrieve", "detail": f"{len(hits)} source(s) matched",
                  "output": [{"title": h["title"][:100], "source": h["source"],
                              "tier": h.get("tier", "—"), "link": h["link"]} for h in hits]})
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

Rules:
- "contradicted" ONLY if a source explicitly states the opposite of the assertion.
- If the sources simply do not mention the assertion, return "insufficient_evidence".
- Never infer contradiction from silence.

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
    v["sources"] = [{"title": h["title"], "source": h["source"],
                     "tier": h.get("tier", "—"), "link": h["link"]} for h in hits]
    trace.append({"step": "verdict", "detail": f"{v['verdict']} ({v['confidence']})", "output": v})
    return v


def overall(results):
    """Roll per-assertion verdicts into one headline label."""
    if not results:
        return "insufficient_evidence", None
    kinds = [r["verdict"] for r in results]
    if all(k == "supported" for k in kinds):
        return "supported", None
    if all(k == "insufficient_evidence" for k in kinds):
        return "insufficient_evidence", None
    if "contradicted" in kinds:
        bad = next(r["assertion"] for r in results if r["verdict"] == "contradicted")
        return "contradicted", bad
    return "mixed", None


def verify(claim):
    trace = []
    if not claim or not claim.strip():
        return {"claim": claim, "results": [], "overall": "insufficient_evidence",
                "contradicted_assertion": None,
                "trace": [{"step": "guardrail", "detail": "empty input",
                           "output": "Please enter a claim."}]}

    base_docs = fetch_docs()
    trace.append({"step": "ingest", "detail": f"{len(base_docs)} live documents (fixed feeds)",
                  "output": []})

    results = []
    for a in decompose(claim, trace):
        query = " ".join(keywords(a))
        live = fetch_docs(extra_query=query, limit=20)
        trace.append({"step": "search", "detail": f"live search: {query}", "output": []})
        docs = live + base_docs
        hits = retrieve(a, docs, trace)
        results.append({"assertion": a, **verdict(a, hits, trace)})

    label, bad = overall(results)
    return {"claim": claim, "results": results, "overall": label,
            "contradicted_assertion": bad, "trace": trace}


if __name__ == "__main__":
    r = verify("The Cabinet approved Dearness Allowance for central government employees.")
    print(json.dumps(r, indent=2)[:1500])
