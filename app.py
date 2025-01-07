##############################################
# app.py
# Minimal password-protected Streamlit app
# w/ ephemeral knowledge base & GPT-4
# Classic chat-style interface
##############################################

import streamlit as st
import openai

##############################################
# 0) Initialize Session State
##############################################
def init_session():
    """
    Make sure all session state variables exist.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # We'll store the entire chat (user & assistant) in this list
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

##############################################
# 1) Ephemeral Knowledge Base
##############################################
@st.cache_resource
def get_knowledge_base() -> list:
    """A simple list of knowledge base entries (strings)."""
    return []

##############################################
# 2) Password Gate (No 'Click to Continue')
##############################################
def password_gate():
    """
    Prompt for a password and authenticate immediately if correct.
    If incorrect, show error and stop.
    """
    st.title("Please enter the app password")

    pwd = st.text_input("Password:", type="password")

    if pwd:
        if pwd == st.secrets["app_password"]:
            # As soon as user enters correct password, set authenticated = True and stop
            st.session_state.authenticated = True
            st.stop()
        else:
            st.error("Incorrect password. Try again.")
            st.stop()

##############################################
# 3) Handle User Input in a Callback
##############################################
def handle_user_input():
    """
    Called when the user hits Enter on the text_input.
    We'll append to chat_history and optionally do the GPT call.
    """
    kb = get_knowledge_base()
    user_text = st.session_state["chat_input"].strip()

    if not user_text:
        # If they typed nothing, do nothing
        return

    # Add the user's message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    # If user says "Please add...", store in ephemeral KB
    if user_text.lower().startswith("please add"):
        new_data = user_text[10:].strip()
        kb.append(new_data)
        # We'll also append a quick assistant message so the user sees confirmation
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": f"Added to knowledge base: {new_data}"
            }
        )
    else:
        # Otherwise we do a GPT call. 
        # We'll build the system prompt by including the entire knowledge base.
        if kb:
            kb_text = "\n".join(kb)
            kb_context = (
                "You have the following ephemeral knowledge base:\n"
                f"{kb_text}\n\n"
                "In your answers, use this info if relevant."
            )
        else:
            kb_context = (
                "You have no knowledge base yet."
            )

        # We'll use the entire chat_history so the assistant has conversation context
        # (minus the ephemeral system context we generate on the fly).
        conversation = []
        # System message includes the knowledge base context
        conversation.append({"role": "system", "content": kb_context})

        # Then append all previous user/assistant messages
        for msg in st.session_state.chat_history:
            # We'll treat user messages as user, assistant messages as assistant
            conversation.append(msg)

        # Now call GPT-4
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=conversation,
                max_tokens=200,
                temperature=0.7,
            )
            answer = response["choices"][0]["message"]["content"].strip()

            # Add the GPT answer to chat history
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer}
            )
        except Exception as e:
            st.session_state.chat_history.append(
                {"role": "assistant", "content": f"OpenAI error: {e}"}
            )

    # Clear the input box
    st.session_state["chat_input"] = ""

##############################################
# 4) Main Chat Interface
##############################################
def main_app():
    openai.api_key = st.secrets["openai_api_key"]

    st.title("IT Super Bot")

    # Show ephemeral knowledge base size, just as an FYI
    kb = get_knowledge_base()
    st.write(f"**Knowledge Base Items:** {len(kb)}")

    # Display all chat messages from top to bottom
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            st.markdown(f"**Assistant:** {msg['content']}")
        elif msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")

    # The chat input
    st.text_input(
        "Type your message (or 'Please add...'):",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...' to store info."
    )

##############################################
# 5) The Entry Point
##############################################
def run_app():
    init_session()  # Make sure session_state variables exist

    if not st.session_state.authenticated:
        password_gate()
        st.stop()
    else:
        main_app()

if __name__ == "__main__":
    run_app()