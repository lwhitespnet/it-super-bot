##############################################
# streamlit_app.py
# Minimal Google OAuth example with a cache_resource store for 'state'
##############################################

import os
import secrets
import logging

import streamlit as st
from dotenv import load_dotenv

import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

import openai

##############################################
# Load environment variables
##############################################
load_dotenv()

##############################################
# Logging
##############################################
logging.basicConfig(level=logging.DEBUG)

##############################################
# Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"  # Use your domain here
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scopes to request from Google
OAUTH_SCOPES = ["openid", "email", "profile"]

##############################################
# 1) A "singleton" (cache_resource) store for valid states
##############################################
@st.cache_resource
def get_state_store() -> dict:
    """
    Returns a dictionary that will persist as long as the app
    isn't fully shut down or redeployed.
    Keys: state strings
    Values: True (or any truthy value)
    """
    return {}

##############################################
# 2) Function: Generate an auth URL manually & store the state in our dict
##############################################
def build_auth_url_and_store_state() -> str:
    state_store = get_state_store()

    # Generate random state
    random_state = secrets.token_urlsafe(16)

    # Put it in our persistent dictionary
    state_store[random_state] = True

    # Build the OAuth URL manually
    scope_str = "+".join(OAUTH_SCOPES)
    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scope_str}"
        f"&response_type=code"
        f"&state={random_state}"
        f"&prompt=consent"
        f"&access_type=offline"
    )
    logging.debug(f"Generated new state={random_state} and stored in dict.")
    return auth_url

##############################################
# 3) Function: Exchange code for token + domain check
##############################################
def exchange_code_for_token(code: str) -> dict:
    """
    Manually exchange the 'code' for tokens by POSTing to Google.
    """
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if resp.status_code != 200:
        raise ValueError(f"Token exchange failed: {resp.text}")
    return resp.json()

def verify_domain(id_token_jwt: str):
    """
    Ensure the user is from the 's-p.net' domain.
    """
    info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    domain = info.get("hd")
    if domain != "s-p.net":
        raise ValueError(f"Access restricted to 's-p.net'. Your domain: {domain}")
    return info

##############################################
# 4) The Main IT Interface
##############################################
def main_it_app():
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot - Using a Singleton State Store")
    st.write("You're authenticated and from s-p.net—welcome!")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write(f"**(Pretending to store)**: {user_input[10:].strip()}")
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
# 5) The Entry Point
##############################################
def run_app():
    query_params = st.query_params
    logging.debug(f"Query params: {query_params}")

    # Show debug info in the UI for clarity
    st.write("**DEBUG**: Query params:", query_params)

    # If we see ?code=...&state=..., attempt callback
    if "code" in query_params and "state" in query_params:
        code = query_params["code"]
        returned_state = query_params["state"]
        logging.debug(f"Returned code={code}, state={returned_state}")

        # Check the store
        state_store = get_state_store()
        if returned_state not in state_store:
            st.error("State mismatch or missing. (No record in our state store.)")
            st.stop()
        else:
            # We found the state in our dictionary—remove it so it can't be reused
            del state_store[returned_state]

            # Exchange code for tokens
            try:
                token_json = exchange_code_for_token(code)
                id_info = verify_domain(token_json["id_token"])
                # If no exception so far, we're good
                st.experimental_set_query_params()  # clear out the code/state
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                logging.error(f"Auth error: {e}")
                st.stop()

    # If domain check succeeded, or we haven't triggered callback yet, show main
    # But first we confirm we have an ID token in session? Actually, we didn't store it
    # or do st.session_state. We'll rely on "did we pass domain check"?
    # For a real app, you'd want to store a "authenticated=True" state or a user token.
    # We'll do a simple approach: if user hasn't triggered code & state, show sign in link.

    # We'll keep it even simpler:
    #  - If the user hasn't just come from Google, we show a sign-in link.
    #  - Once they come back from Google and domain check passes, we just re-run without code/state in URL -> show main app.

    # If we made it here and there's no code/state in URL, we must be "authenticated"
    # or we haven't started yet. Let's do a quick session approach.
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated is False:
        # They haven't been through the domain check yet
        st.title("IT Super Bot (Login w/ Singleton State Store)")
        st.write("Sign in with your s-p.net Google account.")
        auth_url = build_auth_url_and_store_state()
        st.markdown(f"[**Sign in with Google**]({auth_url})")
        st.stop()
    else:
        # Already authenticated
        main_it_app()

# Let's do that final domain check in the same step
# We'll store "authenticated" in st.session_state after verifying domain
# We'll do that in verify_domain.


def verify_domain(id_token_jwt: str):
    info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    domain = info.get("hd")
    if domain != "s-p.net":
        raise ValueError(f"Access restricted to 's-p.net'. Your domain: {domain}")
    # If no error, we set st.session_state.authenticated = True
    st.session_state.authenticated = True
    return info


if __name__ == "__main__":
    run_app()