##############################################
# app.py
# Minimal password-protected Streamlit app
# w/ ephemeral knowledge base & GPT-4,
# using a callback to clear the text input
##############################################

import streamlit as st
import openai

##############################################
# 1) Ephemeral Knowledge Base
##############################################
@st.cache_resource
def get_knowledge_base() -> list:
    """A simple list of knowledge base entries (strings)."""
    return []

##############################################
# 2) Password Gate
##############################################
def password_gate():
    """Prompt for a password and store auth in session_state if correct."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("Please enter the app password")
        pwd = st.text_input("Password:", type="password")
        if pwd:
            if pwd == st.secrets["app_password"]:
                st.success("Password correct! Click below to continue.")
                if st.button("Go to main app"):
                    st.session_state.authenticated = True
                st.stop()
            else:
                st.error("Incorrect password. Try again.")
                st.stop()
    else:
        # Already authenticated, do nothing
        return

##############################################
# 3) The Callback for Handling User Input
##############################################
def handle_user_input():
    """
    This function is called automatically whenever
    the user hits Enter or the text_input changes.
    """
    kb = get_knowledge_base()
    user_input = st.session_state.chat_input  # read what's currently typed

    if user_input:
        if user_input.lower().startswith("please add"):
            new_data = user_input[10:].strip()
            kb.append(new_data)
            st.success(f"Added to knowledge base: {new_data}")
        else:
            # Build a simple system prompt with current knowledge base
            if kb:
                kb_text = "\n".join(kb)
                system_prompt = (
                    "You are a helpful IT assistant. Here is your knowledge base:\n"
                    f"{kb_text}\n\n"
                    "Use this information if relevant. Be concise and helpful."
                )
            else:
                system_prompt = (
                    "You are a helpful IT assistant. You have no knowledge base yet."
                )

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                    max_tokens=200,
                    temperature=0.7,
                )
                answer = response["choices"][0]["message"]["content"].strip()
                st.write(answer)
            except Exception as e:
                st.error(f"OpenAI API error: {e}")

    # Clear the input so it resets the text box
    st.session_state.chat_input = ""

##############################################
# 4) The Main App
##############################################
def main_app():
    openai.api_key = st.secrets["openai_api_key"]

    st.title("IT Super Bot")

    kb = get_knowledge_base()
    st.write(f"You have **{len(kb)}** items in the knowledge base so far.")

    # We set up the text_input with a key and an on_change callback
    st.text_input(
        "Ask something or say 'Please add...' to store info:",
        key="chat_input",
        on_change=handle_user_input
    )

##############################################
# 5) Entry Point
##############################################
def run_app():
    # Check password
    password_gate()

    # If authenticated, show main app
    if st.session_state.authenticated:
        main_app()

if __name__ == "__main__":
    run_app()