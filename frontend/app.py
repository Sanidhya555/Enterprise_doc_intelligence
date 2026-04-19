import streamlit as st
import requests
import uuid
import json

# Ensure this matches your Uvicorn port
API = "http://localhost:8000/api"

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "page" not in st.session_state:
    st.session_state.page = "chat"
if "latency_history" not in st.session_state:
    st.session_state.latency_history = []
if "sessions" not in st.session_state:
    st.session_state.sessions = []

# ─────────────────────────────────────────────
# API HELPER
# ─────────────────────────────────────────────
def api_call(path, method="GET", json_data=None, files=None):
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    url = f"{API}{path}"

    try:
        if method == "GET":
            return requests.get(url, headers=headers)
        elif method == "POST":
            # standard endpoints use json=, upload uses files=
            return requests.post(url, headers=headers, json=json_data, files=files)
        elif method == "DELETE":
            return requests.delete(url, headers=headers)
        elif method == "PUT":
            return requests.put(url, headers=headers, json=json_data)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# ─────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────
def load_sessions():
    res = api_call("/sessions")
    if res and res.status_code == 200:
        st.session_state.sessions = res.json()
    else:
        st.session_state.sessions = []
    return st.session_state.sessions


def load_session(session_id: str):
    res = api_call(f"/sessions/{session_id}/messages")
    if res is None:
        st.error("Unable to load session messages.")
        return False
    if res.status_code != 200:
        try:
            detail = res.json().get("detail", res.text)
        except Exception:
            detail = res.text
        st.error(f"Error loading session: {detail}")
        return False
    st.session_state.messages = res.json()
    st.session_state.session_id = session_id
    st.session_state.page = "chat"
    return True


def delete_session(session_id: str):
    res = api_call(f"/sessions/{session_id}", method="DELETE")
    if res is None:
        st.error("Unable to delete session.")
        return False
    if res.status_code != 200:
        try:
            detail = res.json().get("detail", res.text)
        except Exception:
            detail = res.text
        st.error(f"Error deleting session: {detail}")
        return False
    if st.session_state.session_id == session_id:
        st.session_state.messages = []
        st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
    load_sessions()
    return True


# ─────────────────────────────────────────────
# LOGIN UI
# ─────────────────────────────────────────────
def login_ui():
    st.title("🧠 Document Intelligence Login")
    st.caption("Enter your .env credentials to continue")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            # FastAPI OAuth2 requires 'data=' (form-encoded), NOT 'json='
            res = requests.post(f"{API}/login", data={
                "username": username,
                "password": password
            })

            if res.status_code == 200:
                st.session_state.token = res.json()["access_token"]
                st.success("Authenticated!")
                st.rerun()
            else:
                st.error("Login failed. Check your username/password.")

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.title("📂 Document Intelligence")
        st.info(f"Session: {st.session_state.session_id}")
        
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
            st.session_state.messages = []
            api_call("/sessions/new", "POST", {"session_id": st.session_state.session_id})
            load_sessions()
            st.rerun()

        st.markdown("---")
        if st.button("💬 Chat", use_container_width=True):
            st.session_state.page = "chat"
        if st.button("📄 Documents", use_container_width=True):
            st.session_state.page = "docs"
        if st.button("📊 Metrics", use_container_width=True):
            st.session_state.page = "metrics"

        st.markdown("---")
        if st.session_state.token and not st.session_state.sessions:
            load_sessions()

        if st.session_state.sessions:
            st.subheader("🕘 Previous Chats")
            for idx, session in enumerate(st.session_state.sessions):
                title = session.get("title") or "New Chat"
                created = session.get("created_at", "")[:10]
                last_active = session.get("last_active", "")[:16]
                with st.container():
                    col1, col2, col3 = st.columns([7, 1.5, 1.5])
                    col1.markdown(
                        f"**{title[:30]}{'...' if len(title) > 30 else ''}**  \n"
                        f"<small>ID: `{session['session_id'][:8]}` | Created: {created} | Last: {last_active}</small>"
                    )
                    if col2.button("📂", key=f"open_session_{idx}", use_container_width=True):
                        if load_session(session["session_id"]):
                            st.experimental_rerun()
                    if col3.button("🗑️", key=f"delete_session_{idx}", use_container_width=True):
                        if delete_session(session["session_id"]):
                            st.success("Session deleted.")
                            st.experimental_rerun()

            if st.button("🔄 Refresh", use_container_width=True):
                load_sessions()
                st.experimental_rerun()
        else:
            st.info("No saved sessions available yet.")

# CHAT UI
# ─────────────────────────────────────────────
def chat_ui():
    st.title("💬 Chat")
    
    # Display message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about your documents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            payload = {
                "question": prompt,
                "session_id": st.session_state.session_id,
                "stream": False
            }

            res = requests.post(f"{API}/query", headers=headers, json=payload)
            if res is None:
                st.error("Request failed.")
                return
            if res.status_code != 200:
                st.error(f"Error {res.status_code}: {res.text}")
                return

            data = res.json()
            answer = data.get("answer", "")
            placeholder = st.empty()
            placeholder.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

            metrics = data.get("metrics", {})
            if metrics:
                st.session_state.latency_history.append({
                    "timestamp": __import__('datetime').datetime.now().strftime('%H:%M:%S'),
                    "total_latency": metrics.get('total_latency', 0.0),
                    "retrieval_time": metrics.get('retrieval_time', 0.0),
                    "generation_time": metrics.get('generation_time', 0.0),
                })

            with st.expander("⏱️ Performance Metrics"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Latency", f"{metrics.get('total_latency', 0.0)}s")
                c2.metric("Retrieval", f"{metrics.get('retrieval_time', 0.0)}s")
                c3.metric("Generation", f"{metrics.get('generation_time', 0.0)}s")
                c4.metric("Faithfulness", f"{metrics.get('faithfulness_score', 0.0)}")

# ─────────────────────────────────────────────
# DOCUMENTS UI
# ─────────────────────────────────────────────
def documents_ui():
    st.title("📄 Document Management")
    
    uploaded_files = st.file_uploader("Upload PDFs or DOCX", type=["pdf", "docx"], accept_multiple_files=True)

    if uploaded_files:
        for file in uploaded_files:
            with st.spinner(f"Processing {file.name}..."):
                # Correct format for Multi-part form upload
                files = {"file": (file.name, file.getvalue(), file.type)}
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                
                res = requests.post(f"{API}/upload", headers=headers, files=files)
                
                if res.status_code == 200:
                    st.success(f"Success: {file.name}")
                else:
                    try:
                        error_detail = res.json().get("detail", "Unknown error")
                    except:
                        error_detail = res.text
                    st.error(f"Failed {file.name}: {error_detail}")

    st.markdown("---")
    res = api_call("/documents")
    if res and res.status_code == 200:
        docs = res.json()
        if not docs:
            st.info("No documents indexed yet.")
        for d in docs:
            col1, col2 = st.columns([4, 1])
            col1.write(f"📄 **{d['filename']}** ({d.get('chunks', 0)} chunks)")
            if col2.button("🗑️", key=d['filename']):
                api_call(f"/documents/{d['filename']}", "DELETE")
                st.rerun()

# ─────────────────────────────────────────────
# METRICS UI
# ─────────────────────────────────────────────
def metrics_ui():
    st.title("📊 System Metrics")
    res = api_call("/metrics")
    if res and res.status_code == 200:
        m = res.json()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Docs", m.get("documents_indexed", 0))
        c2.metric("Chunks", m.get("total_chunks", 0))
        c3.metric("Sessions", m.get("active_sessions", 0))
        c4.metric("Cache", m.get("query_cache_size", 0))
    else:
        st.warning("Could not load metrics.")

    st.markdown("---")
    st.subheader("📈 Evaluation Run")
    if st.button("▶️ Run Evaluation", use_container_width=True):
        with st.spinner("Running evaluation against eval_set.json..."):
            eval_res = api_call("/evaluate/batch", "POST")
        if eval_res is None:
            st.error("Evaluation request failed.")
        elif eval_res.status_code != 200:
            st.error(f"Evaluation failed: {eval_res.text}")
        else:
            payload = eval_res.json()
            rows = payload.get("rows", [])
            summary = payload.get("summary", {})
            if rows:
                st.success(f"Evaluated {summary.get('num_samples', len(rows))} questions.")
                st.dataframe(rows)

                chart_data = {
                    "Faithfulness": [summary.get("avg_faithfulness", 0)],
                    "Relevancy": [summary.get("avg_answer_relevancy", 0)],
                    "Context Precision": [summary.get("avg_context_precision", 0)],
                }
                st.bar_chart(chart_data)

                if payload.get("ragas_score") is not None:
                    st.markdown("**RAGAS aggregated scores**")
                    st.write(payload["ragas_score"])
            else:
                st.warning("Evaluation completed but returned no rows.")

    if st.session_state.latency_history:
        st.markdown("---")
        st.subheader("⏱️ Latency History")
        st.write("Recent query latency trends from this session.")
        history_df = st.session_state.latency_history[-20:]
        st.line_chart(
            {
                "total_latency": [row["total_latency"] for row in history_df],
                "retrieval_time": [row["retrieval_time"] for row in history_df],
                "generation_time": [row["generation_time"] for row in history_df],
            }
        )
        st.dataframe(history_df)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not st.session_state.token:
        login_ui()
    else:
        sidebar()
        if st.session_state.page == "chat":
            chat_ui()
        elif st.session_state.page == "docs":
            documents_ui()
        elif st.session_state.page == "metrics":
            metrics_ui()

if __name__ == "__main__":
    main()
