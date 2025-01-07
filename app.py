##############################################
# app.py
# Minimal password-protected Streamlit app
# w/ ephemeral knowledge base & GPT-4
# - Password submits on Enter
# - Classic chat interface: user msg right-aligned, assistant msg left-aligned & bold
##############################################

import streamlit as st
import openai

##############################################
# 0) Initialize Session State
##############################################
def init_session():
    """Ensure all session state variables exist."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # We'll store the entire chat (user & assistant) in this list
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # For the password input, we store in session_state as well
    if "input_password" not in st.session_state:
        st.session_state.input_password = ""

##############################################
# 1) Ephemeral Knowledge Base
##############################################
@st.cache_resource
def get_knowledge_base() -> list:
    """A simple list of knowledge base entries (strings)."""
    return []

##############################################
# 2) Password Auth via on_change
##############################################
def attempt_auth():
    """Called when user presses Enter on the password box."""
    pwd = st.session_state.input_password.strip()
    if pwd:
        if pwd == st.secrets["app_password"]:
            st.session_state.authenticated = True
            st.stop()  # Stop here; next run sees authenticated==True
        else:
            st.error("Incorrect password. Try again.")
            # We keep st.session_state.authenticated = False
            # so the user can retype the password
            # Optionally, clear st.session_state.input_password if you want
            # st.session_state.input_password = ""
            st.stop()

def password_gate():
    """
    Shows a password input box. If correct password is typed,
    we set authenticated = True in attempt_auth().
    """
    st.title("Please enter the app password")
    st.text_input(
        "Password:",
        type="password",
        key="input_password",
        on_change=attempt_auth
    )

##############################################
# 3) Handle Chat Input in a Callback
##############################################
def handle_user_input():
    """
    Called when the user hits Enter in the chat_input.
    We append user input to chat_history, do GPT call if needed.
    """
    kb = get_knowledge_base()
    user_text = st.session_state["chat_input"].strip()

    if not user_text:
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
        # Build the system prompt by including the entire knowledge base
        if kb:
            kb_text = "\n".join(kb)
            kb_context = (
                "You have the following ephemeral knowledge base:\n"
                f"{kb_text}\n\n"
                "In your answers, use this info if relevant."
            )
        else:
            kb_context = "You have no knowledge base yet."

        # We'll use the entire chat_history so the assistant has conversation context
        conversation = []
        conversation.append({"role": "system", "content": kb_context})

        for msg in st.session_state.chat_history:
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

    kb = get_knowledge_base()
    st.write(f"**Knowledge Base Items:** {len(kb)}")

    # Display all chat messages from top to bottom
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            # Left-align & bold
            st.markdown(
                f"<p style='text-align:left;'><b>{msg['content']}</b></p>",
                unsafe_allow_html=True
            )
        elif msg["role"] == "user":
            # Right-align, normal text
            st.markdown(
                f"<p style='text-align:right;'>{msg['content']}</p>",
                unsafe_allow_html=True
            )

    # The chat input at the bottom
    st.text_input(
        "Type your message (or 'Please add...' to store info)",
        key="chat_input",
        on_change=handle_user_input,
        placeholder="Ask me something or say 'Please add...' to store info."
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