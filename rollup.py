"""
rollup.py: claim-level label computed in code from per-assertion verdicts.

The LLM judge still returns only supported / contradicted / insufficient_evidence
for each assertion. This module decides the label for the WHOLE claim.

Rules:
  any contradicted                          -> contradicted (failing assertions named)
  all supported                             -> supported
  all insufficient_evidence                 -> insufficient_evidence
  supported + insufficient, none contradicted -> partially_supported
"""

DISPLAY = {
    "supported": ("🟢", "Supported"),
    "partially_supported": ("🟠", "Partially supported"),
    "contradicted": ("🔴", "Contradicted"),
    "insufficient_evidence": ("⚪", "Insufficient evidence"),
}


def claim_label(results):
    """results: list of dicts from verify()['results'], each with 'verdict' and 'assertion'."""
    verdicts = [r.get("verdict", "insufficient_evidence") for r in results]

    if not verdicts:
        label, failing = "insufficient_evidence", []
    elif "contradicted" in verdicts:
        label = "contradicted"
        failing = [r["assertion"] for r in results if r.get("verdict") == "contradicted"]
    elif all(v == "supported" for v in verdicts):
        label, failing = "supported", []
    elif all(v == "insufficient_evidence" for v in verdicts):
        label, failing = "insufficient_evidence", []
    else:
        label = "partially_supported"
        failing = [r["assertion"] for r in results if r.get("verdict") != "supported"]

    icon, name = DISPLAY[label]
    return {"label": label, "icon": icon, "name": name, "failing": failing}


if __name__ == "__main__":
    def mk(*vs):
        return [{"assertion": f"a{i}", "verdict": v} for i, v in enumerate(vs)]

    assert claim_label(mk("supported", "supported"))["label"] == "supported"
    assert claim_label(mk("insufficient_evidence", "insufficient_evidence"))["label"] == "insufficient_evidence"
    assert claim_label(mk("supported", "insufficient_evidence"))["label"] == "partially_supported"
    assert claim_label(mk("supported", "contradicted"))["label"] == "contradicted"
    assert claim_label(mk("insufficient_evidence", "contradicted"))["label"] == "contradicted"
    assert claim_label(mk("contradicted"))["failing"] == ["a0"]
    assert claim_label([])["label"] == "insufficient_evidence"
    print("rollup: all checks passed")
