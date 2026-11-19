import os
import requests
import streamlit as st

API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="CTI Sentinel AI Advisor", layout="wide")
st.title("CTI Sentinel — LLM Threat Intelligence & Remediation Chat")

with st.sidebar:
    st.header("Target Environment")
    platform_choice = st.selectbox("Platform", ["ALL", "Windows", "Linux", "macOS", "Android", "iOS"])
    lifecycle_choice = st.selectbox("Threat Lifecycle", ["ALL", "Anticipated", "Active", "Evolving", "Resolved"])
    session_id = st.text_input("MongoDB Session ID", value="rayhaan-24btrcl122")
    if st.button("Run Background Vulnerability Scan"):
        r = requests.post(f"{API_URL}/scan/trigger", json={"platform": None if platform_choice == "ALL" else platform_choice})
        if r.ok:
            st.success(f"Scanned {r.json().get('platform')} — {len(r.json().get('findings', []))} findings checked.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask about Anticipated, Active, Evolving, or Resolved threats..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    resp = requests.post(
        f"{API_URL}/chat",
        json={"message": prompt, "session_id": session_id, "platform": platform_choice, "lifecycle": lifecycle_choice}
    )
    answer = resp.json().get("answer", "Error contacting backend.")
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.chat_message("assistant").write(answer)