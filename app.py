import streamlit as st
from agent import verify

st.set_page_config(page_title="Forge Verify", layout="wide")
st.title("Forge Verify")
st.caption("Evidence-grounded claim verification · Agentic verification against live news feeds · Forge Buildathon")

STYLE = {
    "supported":             ("🟢", "Supported",             "#1a7f37", "#e6f4ea"),
    "mixed":                 ("🟡", "Partially Supported",   "#9a6700", "#fff8e1"),
    "contradicted":          ("🔴", "Contradicted",          "#b42318", "#fdecea"),
    "insufficient_evidence": ("⚪", "Insufficient Evidence", "#57606a", "#f0f1f3"),
}


def card(verdict, confidence, reason):
    icon, label, fg, bg = STYLE.get(verdict, STYLE["insufficient_evidence"])
    st.markdown(
        f"""<div style="background:{bg};border-left:6px solid {fg};
        padding:14px 18px;border-radius:8px;margin-bottom:12px">
        <span style="font-size:1.05rem;font-weight:600;color:{fg}">
        {icon} {label} — confidence {confidence:.1f}</span>
        <div style="color:#333;margin-top:6px">{reason}</div></div>""",
        unsafe_allow_html=True,
    )


claim = st.text_area("Paste a claim, headline, or forwarded message:", height=100)

if st.button("Verify", type="primary"):
    if not claim.strip():
        st.warning("Enter a claim first.")
    else:
        with st.spinner("Agent running: decompose → retrieve → judge..."):
            r = verify(claim)

        overall = r.get("overall", "insufficient_evidence")
        top_conf = max((x["confidence"] for x in r["results"]), default=0.0)
        bad = r.get("contradicted_assertion")

        if overall == "supported":
            headline = "Every assertion in this claim is confirmed by live sources."
        elif overall == "mixed":
            headline = "Some parts of this claim are confirmed; others could not be verified. Treat it as unproven, not false."
        elif overall == "contradicted":
            headline = f"A source explicitly disputes this assertion: \u201c{bad}\u201d"
        else:
            headline = "No source in the live feeds addresses this claim. It is unverified — not disproven."

        card(overall, top_conf, headline)

        st.subheader("Per-assertion breakdown")
        for res in r["results"]:
            v = res["verdict"]
            icon, label, fg, bg = STYLE.get(v, STYLE["insufficient_evidence"])
            st.markdown(f"**{icon} {label}** — confidence {res['confidence']}")
            st.write(f"**Assertion:** {res['assertion']}")
            st.write(f"**Reason:** {res['reason']}")
            for s in res["sources"]:
                st.markdown(f"- [{s['title']}]({s['link']}) · *{s['source']}* · `{s.get('tier', '—')}`")
            st.divider()

        st.subheader("Agent trace")
        for t in r["trace"]:
            st.markdown(f"**{t['step']}** — {t['detail']}")

st.divider()
st.caption("Sources: live PIB, The Hindu & Google News RSS · No mock data")