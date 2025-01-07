##############################################
# app.py
# Password-protected Streamlit app using Pinecone
# for persistent "Please add..." storage + GPT-4 chat
# - Assistant: bold/left
# - User: italic/right
# - Extra spacing
##############################################

import streamlit as st
import openai
import pinecone
import uuid

##############################################
# 0) Session Init
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

##############################################
# 1) Pinecone Initialization
##############################################
@st.cache_resource
def init_pinecone():
    """
    Initialize Pinecone once (cached).
    Create or connect to the 'it-super-bot' index (1536-dim, cosine).
    Returns a reference to the index.
    """
    pinecone.init(
        api_key=st.secrets["PINECONE_API_KEY"],
        environment=st.secrets["PINECONE_ENV"]
    )

    # If index doesn't exist, create it
    index_name = "it-super-bot"  # change if needed
    if index_name not in pinecone.list_indexes():
        pinecone.create_index(index_name, dimension=1536, metric="cosine")

    # Return the index object
    return pinecone.Index(index_name)

##############################################
# 2) Password Gate (Submit Button)
##############################################
def password_gate():
    st.title("Please enter the app password")

    # Password input box
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
# 3) Pinecone Helpers (Add + Query)
##############################################
def add_text_to_pinecone(text: str, index):
    """
    Takes the text, creates an embedding, upserts to Pinecone with unique ID.
    """
    emb_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[text]
    )
    embedding = emb_resp["data"][0]["embedding"]
    vector_id = str(uuid.uuid4())

    index.upsert([(vector_id, embedding, {"original_text": text})])

def query_pinecone(query: str, index, top_k=3):
    """
    Embeds query, searches Pinecone, returns top matched texts.
    """
    emb_resp = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[query]
    )
    query_emb = emb_resp["data"][0]["embedding"]

    results = index.query(vector=query_emb, top_k=top_k, include_metadata=True)
    retrieved_texts = []
    if results and results.matches:
        for match in results.matches:
            retrieved_texts.append(match.metadata["original_text"])
    return retrieved_texts

##############################################
# 4) Handle Chat Input
##############################################
def handle_user_input():
    """
    Called when the user hits Enter in the chat_input.
    - If "Please add...", store in Pinecone
    - Else query Pinecone, pass top results to GPT
    - Then add GPT response to chat history
    """
    index = init_pinecone()  # ensure we have the Pinecone index
    user_text = st.session_state["chat_input"].strip()
    if not user_text:
        return

    # Add the user message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    if user_text.lower().startswith("please add"):
        # e.g. "Please add We installed a new router at Site X"
        to_store = user_text[10:].strip()
        add_text_to_pinecone(to_store, index)
        # Add a quick confirmation from the assistant
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Added to knowledge base: {to_store}"
        })
    else:
        # Query Pinecone for context
        relevant_texts = query_pinecone(user_text, index, top_k=3)
        context = "\n".join(relevant_texts)

        # Build system prompt with that context
        system_prompt = (
            "You are a helpful IT assistant.\n"
            "Below is relevant context from your knowledge base:\n"
            f"{context}\n\n"
            "Use this info if relevant when answering."
        )

        # Build full conversation
        conversation = []
        # Insert system message first
        conversation.append({"role": "system", "content": system_prompt})
        # Add the entire chat history
        for msg in st.session_state.chat_history:
            conversation.append(msg)

        # GPT-4 call
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=conversation,
                max_tokens=200,
                temperature=0.7,
            )
            answer = response["choices"][0]["message"]["content"].strip()
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer}
            )
        except Exception as e:
            st.session_state.chat_history.append(
                {"role": "assistant", "content": f"OpenAI error: {e}"}
            )

    # Clear user input
    st.session_state["chat_input"] = ""

##############################################
# 5) Main Chat Interface
##############################################
def main_app():
    # You likely store openai_api_key in st.secrets as well
    openai.api_key = st.secrets["openai_api_key"]

    # Title
    st.title("IT Super Bot (Using Pinecone)")

    # Display chat history
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

    # The text input for new messages
    st.text_input(
        "Type your message (or 'Please add...' to store info)",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...'..."
    )

##############################################
# 6) The Entry Point
##############################################
def run_app():
    init_session()

    # If not authenticated, show password gate
    if not st.session_state.authenticated:
        password_gate()
        st.stop()
    else:
        main_app()

if __name__ == "__main__":
    run_app()