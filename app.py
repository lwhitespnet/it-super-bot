##############################################
# app.py
# Password-protected Streamlit app w/ Pinecone
# using the new approach (host-based) for serverless indexes.
#
# GPT-4 chat:
# - "Please add..." => upserts to Pinecone
# - Normal Q => queries Pinecone for context
# - Assistant is bold/left, user is italic/right
##############################################

import streamlit as st
import openai
import uuid
from pinecone import Pinecone

##############################################
# 0) Session & Setup
##############################################
def init_session():
    """
    Ensure all session-state variables exist.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # We'll store user input for password in session_state
    if "input_password" not in st.session_state:
        st.session_state.input_password = ""

def get_pinecone_index():
    """
    Create a Pinecone client using the new approach,
    returning a pointer to your serverless index via its full host name.
    """
    # Retrieve secrets from .streamlit/secrets.toml
    pc = Pinecone(
        api_key=st.secrets["PINECONE_API_KEY"]
        # environment not needed for serverless host approach
    )
    # e.g. "itsuperbot-xy83vwf.svc.aped-4627-b74a.pinecone.io"
    return pc.Index(st.secrets["PINECONE_INDEX_HOST"])

##############################################
# 1) Password Gate
##############################################
def password_gate():
    """Show a password box + Submit. If correct, set authenticated=True."""
    st.title("Please enter the app password")

    # Password input
    st.text_input(
        "Password:",
        type="password",
        key="input_password"
    )

    # Submit button
    if st.button("Submit"):
        pwd = st.session_state.input_password.strip()
        if pwd == st.secrets["app_password"]:
            st.session_state.authenticated = True
            st.stop()  # Next run sees authenticated=True
        else:
            st.error("Incorrect password. Try again.")
            st.stop()

##############################################
# 2) Pinecone Helpers
##############################################
def add_text_to_pinecone(text: str):
    """Embed text w/ OpenAI, upsert to Pinecone w/ unique ID."""
    emb_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[text]
    )
    embedding = emb_resp["data"][0]["embedding"]
    vector_id = str(uuid.uuid4())

    index = get_pinecone_index()
    # Upsert in the Pinecone "vectors" format
    index.upsert([
        {
            "id": vector_id,
            "values": embedding,
            "metadata": {"original_text": text}
        }
    ])

def query_pinecone(query: str, top_k=3):
    """
    Embed the query, search Pinecone, return top matched texts.
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
            retrieved_texts.append(match.metadata.get("original_text", ""))
    return retrieved_texts

##############################################
# 3) Handle Chat Input
##############################################
def handle_user_input():
    """
    Called when user hits Enter in the chat_input.
    - "Please add..." => store in Pinecone
    - Else => query Pinecone, pass context to GPT
    - Then show GPT answer
    """
    user_text = st.session_state["chat_input"].strip()
    if not user_text:
        return

    # Add user's message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if user_text.lower().startswith("please add"):
        # e.g. "Please add we replaced the router at site X"
        new_data = user_text[10:].strip()
        add_text_to_pinecone(new_data)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Added to knowledge base: {new_data}"
        })
    else:
        # Query Pinecone for relevant context
        retrieved_texts = query_pinecone(user_text, top_k=3)
        context = "\n".join(retrieved_texts)

        # Build system prompt with that context
        system_prompt = (
            "You are a helpful IT assistant.\n"
            "Below is relevant context from your knowledge base:\n"
            f"{context}\n\n"
            "Use this info if relevant when answering."
        )

        # Combine with chat history
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(st.session_state.chat_history)

        # GPT call
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=conversation,
                max_tokens=200,
                temperature=0.7,
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
# 4) Main Chat Interface
##############################################
def main_app():
    openai.api_key = st.secrets["openai_api_key"]

    st.title("IT Super Bot (Pinecone Serverless)")

    # Display the chat so far
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            # Bold, left, spacing
            st.markdown(
                f"<div style='text-align:left; font-weight:bold; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )
        elif msg["role"] == "user":
            # Italic, right, spacing
            st.markdown(
                f"<div style='text-align:right; font-style:italic; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )

    # The text input
    st.text_input(
        "Type your message (or 'Please add...' to store info)",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...'..."
    )

##############################################
# 5) The Entry Point
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