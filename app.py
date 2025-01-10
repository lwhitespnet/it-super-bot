##############################################
# app.py
# GPT-4 Chat + Pinecone (serverless) + PDF/TXT
# With 200-char overlap & top_k=8 for better retrieval
##############################################

import streamlit as st
import openai
import uuid
from pinecone import Pinecone
import PyPDF2  # for reading PDFs

##############################################
# 0) Session & Chat
##############################################
def init_session():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

##############################################
# 1) Pinecone Setup
##############################################
@st.cache_resource
def get_pinecone_index():
    """
    Create a Pinecone object in serverless mode,
    referencing your short index name + full host domain from secrets.
    """
    pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
    index = pc.Index(
        name=st.secrets["PINECONE_INDEX_NAME"],
        host=st.secrets["PINECONE_INDEX_HOST"]
    )
    return index

def embed_and_upsert(chunks, metadata_prefix=""):
    """
    Takes a list of text chunks, embeds each,
    and upserts to Pinecone with optional doc_name in metadata.
    """
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
    """For the 'Please add...' flow: embed single text line."""
    embed_and_upsert([text], metadata_prefix="manual_add")

##############################################
# 2) Parsing & Chunking for PDF/TXT
##############################################
def chunk_text(full_text, chunk_size=1500, overlap=200):
    """
    Splits the text into chunks of `chunk_size` characters,
    overlapping each chunk by `overlap` characters.
    """
    chunks = []
    start = 0
    text_length = len(full_text)

    while start < text_length:
        end = start + chunk_size
        chunk = full_text[start:end]
        chunks.append(chunk.strip())

        # Move the start forward by (chunk_size - overlap)
        # so that the next chunk overlaps by `overlap` characters.
        start += (chunk_size - overlap)

    return chunks

def parse_file(uploaded_file):
    """
    Handle PDF or TXT.
    Return a list of chunked text with overlap=200, chunk_size=1500.
    """
    ext = uploaded_file.name.lower().split('.')[-1]

    if ext == "pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        # chunk with overlap
        return chunk_text(full_text, chunk_size=1500, overlap=200)

    elif ext == "txt":
        raw_bytes = uploaded_file.read()
        text_str = raw_bytes.decode("utf-8", errors="ignore")
        return chunk_text(text_str, chunk_size=1500, overlap=200)

    else:
        return []

##############################################
# 3) Chat Logic
##############################################
def query_pinecone(query: str):
    """
    Embeds the query and retrieves top 8 matches from Pinecone.
    """
    resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[query]
    )
    query_emb = resp["data"][0]["embedding"]

    index = get_pinecone_index()
    # top_k=8 to get more chunks for improved retrieval
    results = index.query(
        vector=query_emb,
        top_k=8,
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

    # Add the user message to the chat
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if user_text.lower().startswith("please add"):
        new_data = user_text[10:].strip()
        add_text_to_pinecone(new_data)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Added to knowledge base: {new_data}"
        })
    else:
        retrieved_texts = query_pinecone(user_text)
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
    main_app()

if __name__ == "__main__":
    run_app()