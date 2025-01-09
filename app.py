##############################################
# app.py
# GPT-4 Chat + Pinecone (serverless) + PDF/TXT uploads
# with a password gate that fully disappears after one correct click
##############################################

import streamlit as st
import openai
import uuid
from pinecone import Pinecone
import PyPDF2  # for reading PDFs

##############################################
# 0) Session & Password
##############################################
def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

def password_gate():
    # Show a login prompt only if user isn't authenticated
    st.title("IT Super Bot")
    pwd = st.text_input("Password:", type="password")

    if st.button("Submit"):
        if pwd.strip() == st.secrets["app_password"]:
            # Mark user as authenticated
            st.session_state.authenticated = True
            # Rerun so the main app is shown immediately, hiding this login prompt
            st.experimental_rerun()
        else:
            st.error("Incorrect password. Try again.")
            st.stop()  # user can type again in the same pass

##############################################
# 1) Pinecone Setup
##############################################
@st.cache_resource
def get_pinecone_index():
    pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
    index = pc.Index(
        name=st.secrets["PINECONE_INDEX_NAME"],
        host=st.secrets["PINECONE_INDEX_HOST"]
    )
    return index

def embed_and_upsert(chunks, metadata_prefix=""):
    index = get_pinecone_index()
    for chunk in chunks:
        resp = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=[chunk]
        )
        embedding = resp["data"][0]["embedding"]
        vector_id = str(uuid.uuid4())

        index.upsert([
            {
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "original_text": chunk,
                    "doc_id": metadata_prefix
                }
            }
        ])

def add_text_to_pinecone(text: str):
    embed_and_upsert([text], metadata_prefix="manual_add")

##############################################
# 2) Parsing & Chunking for PDF/TXT
##############################################
def chunk_text(full_text, chunk_size=1500):
    chunks = []
    start = 0
    while start < len(full_text):
        end = start + chunk_size
        chunk = full_text[start:end]
        chunks.append(chunk.strip())
        start = end
    return chunks

def parse_file(uploaded_file):
    ext = uploaded_file.name.lower().split('.')[-1]

    if ext == "pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        return chunk_text(full_text)

    elif ext == "txt":
        raw_bytes = uploaded_file.read()
        text_str = raw_bytes.decode("utf-8", errors="ignore")
        return chunk_text(text_str)

    else:
        return []

##############################################
# 3) Chat Logic
##############################################
def query_pinecone(query: str, top_k=3):
    resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[query]
    )
    query_emb = resp["data"][0]["embedding"]

    index = get_pinecone_index()
    results = index.query(
        vector=query_emb,
        top_k=top_k,
        include_metadata=True
    )

    retrieved_texts = []
    if results.matches:
        for match in results.matches:
            retrieved_texts.append(match.metadata.get("original_text", ""))
    return retrieved_texts

def handle_user_input():
    user_text = st.session_state.get("chat_input", "").strip()
    if not user_text:
        return

    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if user_text.lower().startswith("please add"):
        new_data = user_text[10:].strip()
        add_text_to_pinecone(new_data)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Added to knowledge base: {new_data}"
        })
    else:
        retrieved_texts = query_pinecone(user_text, top_k=3)
        context = "\n".join(retrieved_texts)
        system_prompt = (
            "You are a helpful IT assistant.\n"
            f"Relevant knowledge:\n{context}\n\n"
            "Use it if relevant when answering."
        )
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(st.session_state.chat_history)

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=conversation,
                max_tokens=200,
                temperature=0.7
            )
            answer = response.choices[0].message.content.strip()
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer
            })
        except Exception as e:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"OpenAI error: {e}"
            })

    st.session_state["chat_input"] = ""

##############################################
# 4) Main Interface (Chat + File Upload)
##############################################
def main_app():
    openai.api_key = st.secrets["openai_api_key"]
    st.title("IT Super Bot")

    # Chat interface
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            st.markdown(
                f"<div style='text-align:left; font-weight:bold; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )
        elif msg["role"] == "user":
            st.markdown(
                f"<div style='text-align:right; font-style:italic; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )

    st.text_input(
        "Type your message (or 'Please add...' to store info)",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...'..."
    )

    st.write("---")
    st.subheader("Upload a PDF or text file to add it to Pinecone")

    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt"])
    if uploaded_file is not None:
        doc_name = st.text_input("Optional doc name (for metadata):", "")
        if st.button("Process file"):
            with st.spinner("Parsing & chunking file..."):
                chunks = parse_file(uploaded_file)
            if not chunks:
                st.error("Could not parse file (unsupported type?). Only .pdf or .txt allowed.")
            else:
                with st.spinner("Embedding & upserting to Pinecone..."):
                    embed_and_upsert(chunks, metadata_prefix=doc_name or uploaded_file.name)
                st.success("File successfully uploaded to Pinecone. You can now query it via chat.")

##############################################
# 5) Entry Point
##############################################
def run_app():
    init_session()

    # If user not yet authenticated, show password gate
    if not st.session_state.authenticated:
        password_gate()
        # no st.stop() here, so if they typed correct pass, the script sees
        # st.session_state.authenticated = True below
    
    # If now authenticated, show main UI
    if st.session_state.authenticated:
        main_app()

if __name__ == "__main__":
    run_app()