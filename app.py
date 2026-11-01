import streamlit as st
from agent import verify

st.set_page_config(page_title="Forge Verify", layout="wide")
st.title("Real-Time Fact-Verification & Deepfake Audit Engine")
st.caption("Agentic verification against live news feeds · Forge Buildathon")

claim = st.text_area("Paste a claim, headline, or forwarded message:", height=100)

if st.button("Verify", type="primary"):
    if not claim.strip():
        st.warning("Enter a claim first.")
    else:
        with st.spinner("Agent running: decompose → retrieve → judge..."):
            r = verify(claim)

        for res in r["results"]:
            v = res["verdict"]
            color = {"supported": "🟢", "contradicted": "🔴"}.get(v, "🟡")
            st.subheader(f"{color} {v.replace('_', ' ').title()} — confidence {res['confidence']}")
            st.write(f"**Assertion:** {res['assertion']}")
            st.write(f"**Reason:** {res['reason']}")
            for s in res["sources"]:
                st.markdown(f"- [{s['title']}]({s['link']}) · *{s['source']}*")

        st.divider()
        st.subheader("Agent trace")
        for t in r["trace"]:
            st.markdown(f"**{t['step']}** — {t['detail']}")

st.divider()
st.caption("Sources: live Google News & The Hindu RSS · No mock data")
