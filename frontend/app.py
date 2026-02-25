import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.title("Enterprise Document Intelligence")

if "token" not in st.session_state:
    st.session_state.token = None

# ---------------- LOGIN ----------------
if not st.session_state.token:
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        response = requests.post(
            f"{API_URL}/login",
            data={"username": username, "password": password}
        )

        if response.status_code == 200:
            st.session_state.token = response.json()["access_token"]
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

# ---------------- MAIN APP ----------------
else:
    headers = {
        "Authorization": f"Bearer {st.session_state.token}"
    }

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Upload", "Ask Question", "Documents", "Metrics"]
    )

    # -------- Upload --------
    if page == "Upload":
        st.subheader("Upload Document")
        file = st.file_uploader("Upload PDF/DOCX")

        if file and st.button("Upload"):
            files = {"file": file}
            response = requests.post(
                f"{API_URL}/upload",
                headers=headers,
                files=files
            )

            if response.status_code == 200:
                st.success("Document uploaded successfully")
            else:
                st.error(response.text)

    # -------- Ask Question --------
    if page == "Ask Question":
        st.subheader("Ask a Question")
        question = st.text_input("Enter your question")

        if st.button("Submit"):
            response = requests.post(
                f"{API_URL}/query",
                headers=headers,
                json={"question": question}
            )

            if response.status_code == 200:
                st.write(response.json())
            else:
                st.error(response.text)
                
    # -------- Documents --------
    if page == "Documents":
        st.subheader("Indexed Documents")

        response = requests.get(
            f"{API_URL}/documents",
            headers=headers
        )

        if response.status_code == 200:
            docs = response.json()
            for doc in docs:
                col1, col2 = st.columns([3,1])
                col1.write(doc["filename"])
                if col2.button("Delete", key=doc["filename"]):
                    del_res = requests.delete(
                        f"{API_URL}/documents/{doc['filename']}",
                        headers=headers
                    )
                    if del_res.status_code == 200:
                        st.success("Deleted")
                        st.rerun()

    # -------- Metrics --------
    if page == "Metrics":
        st.subheader("System Metrics")

        response = requests.get(
            f"{API_URL}/metrics",
            headers=headers
        )

        if response.status_code == 200:
            st.json(response.json())