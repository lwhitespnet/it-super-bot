##############################################
# app.py
# GPT-4 Chat + Pinecone Serverless w/ correct name & host
# "Please add..." => upsert to Pinecone
# Normal Q => query Pinecone
# Assistant bold/left, user italic/right
##############################################

import streamlit as st
import openai
import uuid
from pinecone import Pinecone

##############################################
# 1) Session & Password
##############################################
def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "input_password" not in st.session_state:
        st.session_state.input_password = ""

def password_gate():
    st.title("Please enter the app password")
    st.text_input("Password:", type="password", key="input_password")
    if st.button("Submit"):
        if st.session_state.input_password.strip() == st.secrets["app_password"]:
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
    pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
    # "name" must match your 'index name' in Pinecone
    # "host" is the domain from the console
    index = pc.Index(
        name=st.secrets["PINECONE_INDEX_NAME"],
        host=st.secrets["PINECONE_INDEX_HOST"]
    )
    return index

def add_text_to_pinecone(text: str):
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
    out_texts = []
    if results.matches:
        for match in results.matches:
            out_texts.append(match.metadata.get("original_text", ""))
    return out_texts

##############################################
# 3) Chat Logic
##############################################
def handle_user_input():
    user_text = st.session_state["chat_input"].strip()
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
            "Relevant knowledge:\n"
            f"{context}\n\n"
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

def main_app():
    openai.api_key = st.secrets["openai_api_key"]
    st.title("IT Super Bot w/ Pinecone (Correct Index Name)")

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
        on_change=handle_user_input
    )

def run_app():
    init_session()
    if not st.session_state.authenticated:
        password_gate()
        st.stop()
    else:
        main_app()

if __name__ == "__main__":
    run_app()