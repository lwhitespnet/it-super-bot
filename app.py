##############################################
# app.py
# Minimal password-protected Streamlit app (with Submit button)
# w/ ephemeral knowledge base & GPT-4
# Classic chat-style interface
# - Assistant: left-aligned & bold
# - User: right-aligned & italic
# - Extra spacing between messages
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
    """
    A simple list of knowledge base entries (strings).
    Stored in memory until the app is redeployed.
    """
    return []

##############################################
# 2) Password Gate (Using a Submit Button)
##############################################
def password_gate():
    """
    Shows a password input box and a "Submit" button.
    If password is correct, authenticate immediately.
    If incorrect, show an error and stop.
    """
    st.title("Please enter the app password")

    # Bind the text_input to st.session_state.input_password
    st.text_input(
        "Password:",
        type="password",
        key="input_password"
    )

    if st.button("Submit"):
        pwd = st.session_state.input_password.strip()
        if pwd == st.secrets["app_password"]:
            st.session_state.authenticated = True
            st.stop()  # Next run sees authenticated=True
        else:
            st.error("Incorrect password. Try again.")
            st.stop()

##############################################
# 3) Handle Chat Input
##############################################
def handle_user_input():
    """
    Called when the user hits Enter in the chat_input.
    We append the user input to chat_history, do GPT call if needed.
    """
    kb = get_knowledge_base()
    user_text = st.session_state["chat_input"].strip()

    if not user_text:
        return

    # Add user's message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_text})

    # Check if "Please add..."
    if user_text.lower().startswith("please add"):
        new_data = user_text[10:].strip()
        kb.append(new_data)
        # Let the user see a confirmation
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
        # Start with system message that includes knowledge base context
        conversation.append({"role": "system", "content": kb_context})

        # Then append the full user-assistant exchange so far
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
            # Add the GPT answer to the chat history
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

    # Display the conversation so far
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            # Left-align, bold, extra margin
            st.markdown(
                f"<div style='text-align:left; font-weight:bold; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )
        elif msg["role"] == "user":
            # Right-align, italic, extra margin
            st.markdown(
                f"<div style='text-align:right; font-style:italic; margin:10px 0;'>{msg['content']}</div>",
                unsafe_allow_html=True
            )

    # Chat input at the bottom
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

    # If not authenticated, show password gate
    if not st.session_state.authenticated:
        password_gate()
        st.stop()
    else:
        main_app()

if __name__ == "__main__":
    run_app()