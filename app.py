##############################################
# fresh_app.py - A "from scratch" minimal approach
##############################################

import os
import secrets
import logging

import streamlit as st
from dotenv import load_dotenv

import openai

import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Load environment vars
load_dotenv()

##############################################
# Logging
##############################################
logging.basicConfig(level=logging.DEBUG)

##############################################
# Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"  # Only the base domain
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# We'll ask for OIDC scopes
OAUTH_SCOPES = [
    "openid",
    "email",
    "profile",
]

# The Google endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


##############################################
# Session State Defaults
##############################################
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "state" not in st.session_state:
    st.session_state.state = None

##############################################
# Helper: Build the Authorization URL
##############################################
def build_auth_url(client_id, redirect_uri, scopes, state):
    """
    Manually build the Google OAuth consent screen URL
    using the standard query params for "response_type=code".
    """
    scope_str = "+".join(scopes)
    # We only ask for offline if we want refresh tokens; up to you
    url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope_str}"
        f"&response_type=code"
        f"&state={state}"
        f"&prompt=consent"
        f"&access_type=offline"
    )
    return url

##############################################
# Helper: Exchange Auth Code for Tokens
##############################################
def exchange_code_for_token(code, client_id, client_secret, redirect_uri):
    """
    Manually exchange the 'code' for tokens by POSTing to Google.
    """
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        raise ValueError(f"Token exchange failed: {response.text}")
    return response.json()

##############################################
# Helper: Validate Domain
##############################################
def validate_id_token(id_token_jwt, client_id):
    """
    Use google-auth to verify the JWT from Google's token endpoint.
    """
    id_info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        client_id
    )
    # We only allow s-p.net domain
    if id_info.get("hd") != "s-p.net":
        raise ValueError(f"Domain not allowed: {id_info.get('hd')}")
    return id_info

##############################################
# The Main IT Interface
##############################################
def main_it_app():
    """
    A simple placeholder for your GPT or "add to KB" functionality.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot - Fresh Start")
    st.write(f"Welcome, {st.session_state.user_email}!")

    user_input = st.text_input("Ask a question or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write(f"**(Pretending to store in knowledge base)**: {user_input[10:].strip()}")
        else:
            # Minimal GPT call
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=user_input,
                max_tokens=60,
                temperature=0.7
            )
            st.write(response.choices[0].text.strip())

##############################################
# The "From Scratch" Flow
##############################################
def run_app():
    query_params = st.query_params
    logging.debug(f"Query params: {query_params}")

    if not st.session_state.authenticated:
        # If we see ?code=..., ?state=..., handle callback
        if "code" in query_params and "state" in query_params:
            code = query_params["code"][0]
            returned_state = query_params["state"][0]
            logging.debug(f"Returned code={code}, state={returned_state}")

            # 1) Check if the returned_state matches our stored st.session_state.state
            expected_state = st.session_state.state
            if returned_state != expected_state:
                st.error("State mismatch or missing.")
                st.stop()

            # 2) If it matches, exchange code for token
            try:
                token_json = exchange_code_for_token(
                    code,
                    GOOGLE_CLIENT_ID,
                    GOOGLE_CLIENT_SECRET,
                    REDIRECT_URI
                )
                logging.debug(f"Token JSON from Google: {token_json}")

                # 3) Validate the ID token domain
                id_info = validate_id_token(token_json["id_token"], GOOGLE_CLIENT_ID)

                # If domain is s-p.net, success
                st.session_state.authenticated = True
                st.session_state.user_email = id_info.get("email", "unknown")

                # Clear the query params so we don’t re-process them
                st.experimental_set_query_params()
                st.experimental_rerun()

            except Exception as e:
                st.error(f"Authentication failed: {e}")
                logging.error(f"Auth error: {e}")
                st.stop()

        # If still not authenticated, show sign-in link
        if not st.session_state.authenticated:
            st.title("IT Super Bot (Fresh Flow)")
            st.write("Please sign in with your s-p.net Google account.")

            # If we don't have a "session-level" state yet, generate one
            if st.session_state.state is None:
                st.session_state.state = secrets.token_urlsafe(16)
                logging.debug(f"Generated fresh random state: {st.session_state.state}")

            # Build the URL manually
            sign_in_url = build_auth_url(
                GOOGLE_CLIENT_ID,
                REDIRECT_URI,
                OAUTH_SCOPES,
                st.session_state.state
            )
            st.write("Click the link below to sign in (in the same tab if possible).")
            st.markdown(f"[**Sign in with Google**]({sign_in_url})")

            st.info("**Note**: If your browser opens a brand-new window with no shared session, the state might mismatch. Try SHIFT-click or simply left-click to open in this tab.")
            st.stop()

    # If we get here, user is authenticated
    main_it_app()


##############################################
# Entry Point
##############################################
if __name__ == "__main__":
    run_app()