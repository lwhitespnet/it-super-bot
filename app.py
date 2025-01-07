##############################################
# app.py
# Password-protected Streamlit app w/ GPT-4
# using Pinecone in serverless mode.
# - "Please add..." => upserts to Pinecone
# - Normal Q => queries Pinecone for context
# - Assistant: bold/left, user: italic/right
##############################################

import streamlit as st
import openai
import uuid
from pinecone import Pinecone  # Works in newer pinecone-client>=5.0

##############################################
# 0) Init Session
##############################################
def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "input_password" not in st.session_state:
        st.session_state.input_password = ""

##############################################
# 1) Password Gate
##############################################
def password_gate():
    st.title("Please enter the app password")
    st.text_input("Password:", type="password", key="input_password")

    if st.button("Submit"):
        pwd = st.session_state.input_password.strip()
        if pwd == st.secrets["app_password"]:
            st.session_state.authenticated = True
            st.stop()
        else:
            st.error("Incorrect password. Try again.")
            st.stop()

##############################################
# 2) Pinecone Setup
##############################################
@st.cache_resource
def get_pinecone_index():
    """
    Create a Pinecone object (serverless approach).
    We pass the 'PINECONE_INDEX_HOST' from secrets to .Index().
    """
    pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
    # The index host is something like "myserverless-xxx.svc.region-xxxx.pinecone.io"
    index = pc.Index(st.secrets["PINECONE_INDEX_HOST"])
    return index

def add_text_to_pinecone(text: str):
    """
    Embed text w/ OpenAI, upsert to Pinecone (serverless).
    """
    emb_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[text]
    )
    embedding = emb_resp["data"][0]["embedding"]
    vector_id = str(uuid.uuid4())

    index = get_pinecone_index()
    index.upsert([
        {
            "id": vector_id,
            "values": embedding,
            "metadata": {"original_text": text}
        }
    ])

def query_pinecone(query: str, top_k=3):
    """
    Embed the query, retrieve best matches from Pinecone.
    Return list of matched text strings.
    """
    emb_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[query]
    )
    query_emb = emb_resp["data"][0]["embedding"]

    index = get_pinecone_index()
    results = index.query(
        vector=query_emb,
        top_k=top_k,
        include_metadata=True
    )

    retrieved_texts = []
    if results.matches:
        for match in results.matches:
            # We store the original text in metadata
            retrieved_texts.append(match.metadata.get("original_text", ""))
    return retrieved_texts

##############################################
# 3) Handle Chat
##############################################
def handle_user_input():
    """
    Called when user hits Enter in the chat_input box.
      - If 'Please add...' => store in Pinecone.
      - Else => query Pinecone for context => call GPT-4.
    """
    user_text = st.session_state["chat_input"].strip()
    if not user_text:
        return

    # Append user msg to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if user_text.lower().startswith("please add"):
        # e.g. "Please add installed a router at site X"
        new_data = user_text[10:].strip()
        add_text_to_pinecone(new_data)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Added to knowledge base: {new_data}"
        })
    else:
        # Retrieve relevant texts from Pinecone
        retrieved_texts = query_pinecone(user_text, top_k=3)
        context = "\n".join(retrieved_texts)

        # System prompt w/ that context
        system_prompt = (
            "You are a helpful IT assistant.\n"
            "Here is relevant context from your knowledge base:\n"
            f"{context}\n\n"
            "Use it if relevant when answering."
        )

        # Combine system msg + chat history
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(st.session_state.chat_history)

        # Call GPT-4
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=conversation,
                max_tokens=200,
                temperature=0.7
            )
            answer = response["choices"][0]["message"]["content"].strip()
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer
            })
        except Exception as e:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"OpenAI error: {e}"
            })

    # Clear input
    st.session_state["chat_input"] = ""

##############################################
# 4) Main Chat
##############################################
def main_app():
    openai.api_key = st.secrets["openai_api_key"]

    st.title("IT Super Bot (Serverless Pinecone, Up-to-Date)")

    # Display chat so far
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

    # Chat input
    st.text_input(
        "Type your message (or 'Please add...' to store info)",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...'..."
    )

##############################################
# 5) run_app
##############################################
def run_app():
    init_session()

    if not st.session_state.authenticated:
        password_gate()
        st.stop()
    else:
        main_app()

if __name__ == "__main__":
    run_app()