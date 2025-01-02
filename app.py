##############################################
# app.py - Minimal Streamlit + Google OAuth + OpenAI Example
# Streamlit Cloud ONLY, with direct link sign-in
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

##############################################
# Handle OAuth Callback
##############################################
def handle_oauth_callback(code: str, state: str) -> bool:
    """
    Validates the state param, exchanges code for tokens,
    and restricts domain to s-p.net.
    Returns True if authenticated, False otherwise.
    """
    try:
        if state != st.session_state.oauth_state:
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
    # Gather query params directly from the URL
    query_params = st.experimental_get_query_params()
    logging.debug(f"Current URL query_params: {query_params}")

    # If we see 'code' and 'state' and not yet authenticated, handle callback
    if not st.session_state.authenticated:
        if "code" in query_params and "state" in query_params:
            code = query_params["code"][0]
            state = query_params["state"][0]
            logging.debug(f"Got code={code} & state={state} from URL.")
            
            success = handle_oauth_callback(code, state)
            if success:
                # Clear query params from URL to prevent re-calling
                st.experimental_set_query_params()  # Clears them out
                st.experimental_rerun()
        else:
            # Not authenticated, so show the sign-in link
            st.title("IT Super Bot (Login)")
            st.write("Sign in with your Sight Partners Google account.")

            # Generate our Google OAuth link
            auth_url, generated_state = flow.authorization_url(prompt="consent")
            st.session_state.oauth_state = generated_state
            logging.debug(f"Generated auth_url: {auth_url}")
            logging.debug(f"Generated state: {generated_state}")

            # DIRECT LINK
            st.markdown(f"[**Sign in with Google**]({auth_url})")

            # Stop execution so user can click the link
            return

    # If authenticated, proceed to main interface
    main()

if __name__ == "__main__":
    run_app()