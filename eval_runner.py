"""
eval_runner.py: run Forge Verify over a CSV of labelled claims and report results.

Usage:   python eval_runner.py claims.csv
CSV columns: claim, expected
  expected is one of: supported, partially_supported, contradicted, insufficient_evidence

Writes eval_results.csv and prints a summary you can paste into the evaluation slide.
"""
import csv
import sys
import time

from agent import verify

DELAY_SECONDS = 2  # stay under free-tier rate limits
POSITIVE = {"supported", "partially_supported"}


def main(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("claim") or "").strip()]

    out = []
    for i, row in enumerate(rows, 1):
        claim, expected = row["claim"].strip(), (row.get("expected") or "").strip()
        try:
            r = verify(claim)
            got = {"mixed": "partially_supported"}.get(r["overall"], r["overall"])
        except Exception as ex:
            got = f"error: {str(ex)[:60]}"
        ok = got == expected
        out.append({"claim": claim, "expected": expected, "got": got, "correct": ok})
        print(f"[{i}/{len(rows)}] {'OK ' if ok else 'XX '} expected={expected:<22} got={got:<22} | {claim[:60]}")
        time.sleep(DELAY_SECONDS)

    n = len(out)
    scored = [o for o in out if o["expected"]]
    correct = sum(o["correct"] for o in scored)
    # A false support = we said supported/partial where the truth was contradicted or unverifiable
    false_support = sum(
        1 for o in scored
        if o["got"] in POSITIVE and o["expected"] in {"contradicted", "insufficient_evidence"}
    )
    abstained = sum(1 for o in out if o["got"] == "insufficient_evidence")
    contra_expected = [o for o in scored if o["expected"] == "contradicted"]
    contra_right = sum(o["correct"] for o in contra_expected)
    errors = sum(1 for o in out if str(o["got"]).startswith("error"))

    print("\n=== SUMMARY ===")
    print(f"Claims tested:              {n}")
    print(f"Correct labels:             {correct} / {len(scored)}")
    print(f"False 'supported' verdicts: {false_support}")
    print(f"Abstentions (insufficient): {abstained}")
    print(f"Contradicted correct:       {contra_right} / {len(contra_expected)}")
    print(f"Errors (API etc.):          {errors}")

    with open("eval_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["claim", "expected", "got", "correct"])
        w.writeheader()
        w.writerows(out)
    print("Saved eval_results.csv")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "claims.csv")
