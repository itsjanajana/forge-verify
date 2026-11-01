import html
import streamlit as st
from agent import verify

st.set_page_config(page_title="Forge Verify", layout="wide")
st.title("Forge Verify")
st.caption("Evidence-grounded claim verification · live news and official feeds · No evidence. No verdict.")

# verdict -> (icon, label, text colour, background)
STYLE = {
    "supported":             ("🟢", "Supported",             "#1a7f37", "#e6f4ea"),
    "mixed":                 ("🟡", "Partially Supported",   "#9a6700", "#fff8e1"),
    "contradicted":          ("🔴", "Contradicted",          "#b42318", "#fdecea"),
    "insufficient_evidence": ("⚪", "Insufficient Evidence", "#475467", "#f2f4f7"),
}
TIER_BADGE = {"Official": "🏛️ Official", "Major outlet": "📰 Major outlet", "Aggregator": "🔎 Aggregator"}


def card(verdict, reason, confidence=None):
    icon, label, fg, bg = STYLE.get(verdict, STYLE["insufficient_evidence"])
    conf = f" — confidence {confidence:.2f}" if confidence is not None else ""
    st.markdown(
        f"""<div style="background:{bg};border-left:6px solid {fg};
        padding:14px 18px;border-radius:8px;margin-bottom:12px">
        <span style="font-size:1.05rem;font-weight:600;color:{fg}">
        {icon} {label}{conf}</span>
        <div style="color:#333;margin-top:6px">{html.escape(reason)}</div></div>""",
        unsafe_allow_html=True,
    )


claim = st.text_area("Paste a claim, headline, or forwarded message:", height=100)

if st.sidebar.checkbox("Display all verdict colours"):
    for v, reason in [
        ("supported", "Every assertion in this claim is confirmed by live sources."),
        ("mixed", "Some parts are confirmed; others could not be verified."),
        ("contradicted", "At least one assertion is disputed by the sources retrieved."),
        ("insufficient_evidence", "No source in the live feeds addresses this claim."),
    ]:
        card(v, reason)
    st.stop()

if st.button("Verify", type="primary"):
    if not claim.strip():
        st.warning("Enter a claim first.")
    else:
        with st.spinner("Agent running: decompose → retrieve → judge..."):
            try:
                r = verify(claim)
            except Exception as ex:
                st.error(f"Something went wrong: {str(ex)[:200]}")
                st.stop()

        overall = r.get("overall", "insufficient_evidence")
        if overall == "supported":
            headline = "Every assertion in this claim is confirmed by live sources."
        elif overall == "mixed":
            headline = "Some parts of this claim are confirmed; others could not be verified. Treat it as unproven, not false."
        elif overall == "contradicted":
            headline = "At least one assertion is disputed by the sources retrieved."
        else:
            headline = "No source in the live feeds addresses this claim. It is unverified, not disproven."

        card(overall, headline)  # no single confidence number on the headline

        st.subheader("Per-assertion breakdown")
        for res in r["results"]:
            v = res["verdict"]
            icon, label, fg, bg = STYLE.get(v, STYLE["insufficient_evidence"])
            st.markdown(f"**{icon} {label}** — judge confidence {res['confidence']}")
            st.write(f"**Assertion:** {res['assertion']}")
            st.write(f"**Reason:** {res['reason']}")
            for s in res["sources"]:
                badge = TIER_BADGE.get(s.get("tier"), "")
                when = f" · {s['published']}" if s.get("published") else ""
                st.markdown(f"- [{s['title']}]({s['link']}) · *{s['source']}* · {badge}{when}")
            st.divider()

        st.subheader("Agent trace")
        for t in r["trace"]:
            st.markdown(f"**{t['step']}** — {t['detail']}")

st.divider()
st.caption("Sources: live Google News, The Hindu and PIB RSS · No mock data")
