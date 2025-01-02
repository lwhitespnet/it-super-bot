##############################################
# app.py - Minimal Streamlit + Google OAuth + OpenAI Example
# Single-step approach, uses /_stcore/oauth-callback
##############################################

import streamlit as st
import os
import logging
from dotenv import load_dotenv

from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
from google.oauth2 import id_token

import openai

# Load .env variables
load_dotenv()

##############################################
# Debug / Logging
##############################################
DEBUG = True
if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

##############################################
# Google OAuth Config
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app/_stcore/oauth-callback"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    },
    scopes=["openid", "email", "profile"],
)
flow.redirect_uri = REDIRECT_URI

##############################################
# Session State Defaults
##############################################
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = None

##############################################
# Handle OAuth Callback
##############################################
def handle_oauth_callback(code: str, state: str) -> bool:
    """
    Exchanges code for tokens, checks domain 's-p.net',
    sets st.session_state.authenticated if good.
    """
    try:
        if state != st.session_state.oauth_state:
            raise ValueError("State mismatch or missing.")

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Verify ID token
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        logging.debug(f"ID token info: {id_info}")

        # Domain restriction
        if id_info.get("hd") != "s-p.net":
            st.error("Access restricted to Sight Partners users.")
            return False

        st.session_state.authenticated = True
        st.session_state.user_email = id_info.get("email", "unknown")
        logging.debug(f"User authenticated as {st.session_state.user_email}")
        return True

    except Exception as e:
        logging.error(f"Error during OAuth callback: {e}")
        st.error("Authentication failed. Please try again.")
        return False

##############################################
# Main IT Assistant
##############################################
def main():
    """
    Show the main interface once authenticated.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot")
    st.write(f"Welcome, {st.session_state.user_email}!")

    user_input = st.text_input("Ask a question or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write(f"Pretending to add: {user_input[10:].strip()}")
        else:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=user_input,
                max_tokens=60,
                temperature=0.7
            )
            st.write(response.choices[0].text.strip())

##############################################
# Run the App
##############################################
def run_app():
    # Check if we got code & state in the URL
    query_params = st.query_params
    logging.debug(f"query_params: {query_params}")

    if not st.session_state.authenticated:
        # If code & state are present, handle the callback
        if "code" in query_params and "state" in query_params:
            code = query_params["code"][0]
            state = query_params["state"][0]
            success = handle_oauth_callback(code, state)
            # Clear query params on success to avoid re-processing
            if success:
                st.experimental_set_query_params()
                st.experimental_rerun()
            else:
                return  # Stop if failed

        # If still not authenticated, show sign-in link
        if not st.session_state.authenticated:
            st.title("IT Super Bot (Login)")
            st.write("Sign in with your Sight Partners Google account.")

            auth_url, current_state = flow.authorization_url(prompt="consent")
            st.session_state.oauth_state = current_state
            logging.debug(f"auth_url={auth_url}, state={current_state}")

            st.markdown(f"[**Sign in with Google**]({auth_url})")
            return

    # If authenticated, show main interface
    main()

if __name__ == "__main__":
    run_app()