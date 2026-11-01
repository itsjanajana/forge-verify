import os, json, re
from dotenv import load_dotenv
from groq import Groq

from ingest import fetch_docs, search_news

load_dotenv()

gclient = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
TIMEOUT = 20  # seconds per LLM call

TIER_RANK = {"Official": 0, "Major outlet": 1, "Aggregator": 2}


def _ask(prompt, json_mode=False):
    for attempt in range(2):
        for m in MODELS:
            try:
                kwargs = {
                    "model": m,
                    "messages": [{"role": "user", "content": prompt}],
                    "timeout": TIMEOUT,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                r = gclient.chat.completions.create(**kwargs)
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


# ---------------------------------------------------------------- retrieval
STOP = set("""
that this with from have been were will would about which their there than then
them they what when where while after before into over under also more most some
such only other these those your said says
government india indian
""".split())
# "government" / "india" are stopwords for MATCHING only: they appear in almost
# every article, which made unrelated documents count as hits.


def _norm(text):
    # "23,731" -> "23731" so numbers survive tokenizing and match across documents
    return re.sub(r"(?<=\d),(?=\d)", "", (text or "").lower())


def _stem(t):
    return t[:-1] if t.endswith("s") and len(t) > 4 else t  # employees -> employee


def _tokens(text):
    return [_stem(t) for t in re.findall(r"[a-z]+|\d+(?:\.\d+)?", _norm(text))]


def keywords(text):
    seen, out = set(), []
    for t in _tokens(text):
        if t in STOP or (t.isalpha() and len(t) < 4):
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def retrieve(assertion, docs, trace, k=3):
    kws = keywords(assertion)

    # 1) live search built from this assertion's own keywords
    query = " ".join(kws[:6])
    live = search_news(query) if query else []

    # 2) merge with the base feeds (fallback), de-duplicated by link
    pool = {d["link"] or d["title"]: d for d in list(docs) + live}.values()

    # 3) score: numbers count double; need at least 2 matching keywords
    need = min(2, len(kws))
    scored = []
    for d in pool:
        toks = set(_tokens(d["title"] + " " + d["summary"]))
        matched = [w for w in kws if w in toks]
        if matched and len(matched) >= need:
            score = sum(2 if w[0].isdigit() else 1 for w in matched)
            scored.append((score, TIER_RANK.get(d.get("tier"), 2), d))
    scored.sort(key=lambda x: (-x[0], x[1]))  # best match first; Official wins ties
    hits = [d for _, _, d in scored[:k]]

    trace.append({
        "step": "retrieve",
        "detail": f"{len(hits)} source(s) matched | live query: '{query}' ({len(live)} live results)",
        "output": [{"title": h["title"][:100], "source": h["source"], "tier": h.get("tier"),
                    "link": h["link"]} for h in hits],
    })
    return hits


# ------------------------------------------------------------------- judge
def verdict(assertion, hits, trace):
    if not hits:
        v = {"verdict": "insufficient_evidence", "confidence": 0.0,
             "reason": "No supporting source found in live feeds.", "sources": []}
        trace.append({"step": "verdict", "detail": "no evidence -> refused", "output": v})
        return v

    ctx = "\n".join(
        f"[{i+1}] ({h.get('tier', 'Aggregator')}: {h['source']}) {h['title']} — {h['summary'][:300]}"
        for i, h in enumerate(hits)
    )
    out = _ask(f"""You are a fact-checker. Judge the assertion using ONLY the sources below.

Verdict rules:
- "supported": a source directly states the assertion.
- "contradicted": ONLY if a source explicitly states the opposite, or gives a different figure or date for the same fact. If the sources simply do not mention the assertion, that is NOT contradicted.
- "insufficient_evidence": the sources do not address the assertion, or relate to it only loosely.

Return ONLY JSON: {{"verdict":"supported|contradicted|insufficient_evidence","confidence":0.0-1.0,"reason":"one sentence"}}

Assertion: {assertion}

Sources:
{ctx}""", json_mode=True)
    try:
        raw = (out or "{}").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        v = json.loads(raw)
        if v.get("verdict") not in ("supported", "contradicted", "insufficient_evidence"):
            raise ValueError
        try:
            v["confidence"] = round(float(v.get("confidence", 0.0)), 2)
        except Exception:
            v["confidence"] = 0.0
        v.setdefault("reason", "")
    except Exception as ex:
        print("parse failed:", str(ex)[:100], "| raw:", (out or "")[:200])
        v = {"verdict": "insufficient_evidence", "confidence": 0.0,
             "reason": "Model output unparseable; abstaining.", "sources": []}

    # Trust-tier rule: if every retrieved source is an aggregator, cap confidence at 0.8
    if v["verdict"] == "supported" and all(h.get("tier", "Aggregator") == "Aggregator" for h in hits):
        v["confidence"] = min(v["confidence"], 0.8)
        v["reason"] += " (Confidence capped: aggregator sources only.)"

    v["sources"] = [{"title": h["title"], "source": h["source"], "tier": h.get("tier"),
                     "link": h["link"], "published": h.get("published", "")} for h in hits]
    trace.append({"step": "verdict", "detail": f"{v['verdict']} ({v['confidence']})", "output": v})
    return v


# ------------------------------------------------------------------ rollup
def overall(results):
    """Roll per-assertion verdicts into one headline verdict."""
    if not results:
        return "insufficient_evidence"
    kinds = [r["verdict"] for r in results]
    if all(k == "supported" for k in kinds):
        return "supported"
    if all(k == "insufficient_evidence" for k in kinds):
        return "insufficient_evidence"
    if "contradicted" in kinds:
        return "contradicted"
    return "mixed"


# ------------------------------------------------------------------ pipeline
def verify(claim):
    trace = []
    if not claim or not claim.strip():
        return {"claim": claim, "results": [], "overall": "insufficient_evidence",
                "trace": [{"step": "guardrail", "detail": "empty input", "output": "Please enter a claim."}]}
    docs = fetch_docs()
    trace.append({"step": "ingest", "detail": f"{len(docs)} live documents", "output": []})
    results = []
    for a in decompose(claim, trace):
        hits = retrieve(a, docs, trace)
        results.append({"assertion": a, **verdict(a, hits, trace)})
    final = overall(results)
    trace.append({"step": "rollup", "detail": final, "output": final})
    return {"claim": claim, "results": results, "overall": final, "trace": trace}


if __name__ == "__main__":
    r = verify("The Cabinet approved Dearness Allowance for central government employees.")
    print(json.dumps(r, indent=2)[:1500])
