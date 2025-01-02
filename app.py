##############################################
# app.py - Single Flow + Single Auth URL
# to avoid generating multiple states
##############################################

import streamlit as st
import os
import logging
from dotenv import load_dotenv

from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
from google.oauth2 import id_token

import openai

# Load .env
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

##############################################
# Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

def create_flow():
    """
    Create a new OAuth Flow instance (with redirect URIs, scopes, etc.)
    """
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
    return flow

##############################################
# Session State Defaults
##############################################
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "flow" not in st.session_state:
    st.session_state.flow = create_flow()

# We'll store the generated sign-in link here
if "auth_url" not in st.session_state:
    st.session_state.auth_url = None

##############################################
# Handle OAuth Callback
##############################################
def handle_oauth_callback(code: str, returned_state: str) -> bool:
    """
    Uses the same Flow instance from st.session_state,
    exchanges code for tokens, checks domain = s-p.net.
    """
    try:
        flow: Flow = st.session_state.flow

        # Compare returned_state with flow's internal state
        if returned_state != flow.oauth2session.state:
            raise ValueError(f"State mismatch. flow.oauth2session.state={flow.oauth2session.state}, returned={returned_state}")

        # Exchange code for tokens
        flow.fetch_token(code=code)

        # Verify ID token
        credentials = flow.credentials
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        logging.debug(f"ID token info: {id_info}")

        # Check domain
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
    query_params = st.query_params
    logging.debug(f"query_params: {query_params}")

    # If we're not authed, check for code/state
    if not st.session_state.authenticated:
        if "code" in query_params and "state" in query_params:
            code = query_params["code"][0]
            returned_state = query_params["state"][0]
            if handle_oauth_callback(code, returned_state):
                # Clear out code/state from URL
                st.experimental_set_query_params()
                st.experimental_rerun()
            else:
                return

        # If still not authed, show sign-in
        if not st.session_state.authenticated:
            st.title("IT Super Bot (Login)")
            st.write("Sign in with your Sight Partners Google account.")

            flow: Flow = st.session_state.flow

            # Only create an auth_url if we don't have one yet
            # or if flow.oauth2session.state is None
            if st.session_state.auth_url is None or flow.oauth2session.state is None:
                auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
                st.session_state.auth_url = auth_url
                logging.debug(f"Generated new auth_url={auth_url}")
            else:
                # Reuse existing URL if it exists
                auth_url = st.session_state.auth_url
                logging.debug(f"Reusing existing auth_url={auth_url}")

            st.markdown(f"[**Sign in with Google**]({auth_url})")
            st.info("**Important**: Click the link in the same browser/window so that the session is shared.")

            return

    # If we're here, user is authenticated
    main()

if __name__ == "__main__":
    run_app()