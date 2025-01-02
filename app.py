##############################################
# app.py - Minimal Streamlit + Google OAuth + OpenAI Example
# Streamlit Cloud ONLY (no local fallback)
##############################################

import streamlit as st
import os
import logging
from dotenv import load_dotenv

from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
from google.oauth2 import id_token

import openai

# Load environment variables from .env
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
if "query_params" not in st.session_state:
    st.session_state.query_params = {}

##############################################
# Handle OAuth Callback
##############################################
def handle_oauth_callback():
    """
    Validates the state param, exchanges code for tokens,
    and restricts domain to s-p.net.
    Returns True if authenticated, False otherwise.
    """
    try:
        query_params = st.session_state.query_params
        logging.debug(f"Query params: {query_params}")

        received_state = query_params.get("state", [None])[0]
        code = query_params.get("code", [None])[0]
        expected_state = st.session_state.oauth_state

        logging.debug(f"Received state: {received_state}, expected state: {expected_state}")
        logging.debug(f"Authorization code: {code}")

        if received_state != expected_state:
            raise ValueError("State parameter mismatch or missing.")

        if not code:
            raise ValueError("Missing authorization code.")

        # Exchange the code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials
        logging.debug(f"Credentials: {credentials}")

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

        # If we made it here, authentication is successful
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
    Main interface for the IT Super Bot after authentication.
    """
    # Initialize OpenAI
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot")
    st.write(f"Welcome, {st.session_state.user_email}!")

    # Simple chat interface
    user_input = st.text_input("Ask a question or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write("Pretending to add that info to the knowledge base...")
            st.write(f"Added: {user_input[10:].strip()}")
        else:
            # Quick GPT response (completions API for a quick example)
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=user_input,
                max_tokens=60,
                temperature=0.7
            )
            st.write(response.choices[0].text.strip())

##############################################
# On App Startup
##############################################
def run_app():
    """
    Entry point for the Streamlit application.
    """
    # 1. Capture query params if not already captured
    if not st.session_state.query_params:
        st.session_state.query_params = st.query_params
        logging.debug(f"Captured query params: {st.session_state.query_params}")

    # 2. If we see 'code' and 'state' in the URL and user not yet authenticated, handle callback
    if (
        "code" in st.session_state.query_params
        and "state" in st.session_state.query_params
        and not st.session_state.authenticated
    ):
        logging.debug("Code and state found in query params, attempting OAuth callback...")
        if handle_oauth_callback():
            # Avoid infinite loop by clearing out the query params
            st.session_state.query_params = {}
            st.experimental_rerun()

    # 3. If not authenticated, show the sign-in button
    if not st.session_state.authenticated:
        st.write("Sign in with your Sight Partners Google account.")
        # Prepare the OAuth URL
        auth_url, state = flow.authorization_url(prompt="consent")
        st.session_state.oauth_state = state
        logging.debug(f"Generated auth_url: {auth_url}")
        logging.debug(f"Generated state: {state}")

        if st.button("Sign in with Google"):
            st.write("If not redirected automatically, please click the link below:")
            st.markdown(f"[Click here to sign in with Google]({auth_url})")
        return

    # 4. Authenticated - go to main
    main()


##############################################
# Run the App
##############################################
if __name__ == "__main__":
    run_app()