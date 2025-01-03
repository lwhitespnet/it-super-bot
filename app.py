##############################################
# app.py
# Minimal Google OAuth example with a cache_resource store for 'state'
# Using st.experimental_get_query_params() / st.experimental_set_query_params()
# and extracting the first element of each param.
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
# 3) Function: Exchange code for token
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

##############################################
# 4) Domain Check
##############################################
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
    # Mark user as authenticated in session
    st.session_state.authenticated = True
    return info

##############################################
# 5) The Main IT Interface
##############################################
def main_it_app():
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot - Using a Singleton State Store (Lists -> Single Strings)")
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
# 6) The Entry Point
##############################################
def run_app():
    # Use st.experimental_get_query_params to avoid conflict
    query_params = st.experimental_get_query_params()
    logging.debug(f"Query params: {query_params}")

    # Show debug info in the UI for clarity
    st.write("**DEBUG**: experimental_get_query_params:", query_params)

    # If we see ?code=...&state=..., attempt callback
    if "code" in query_params and "state" in query_params:
        # Because query_params can have lists, we take the first element
        code_list = query_params["code"]
        state_list = query_params["state"]

        code = code_list[0] if isinstance(code_list, list) else code_list
        returned_state = state_list[0] if isinstance(state_list, list) else state_list

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
                # If no exception so far, we set ourselves as authenticated
                # (verify_domain does st.session_state.authenticated = True)

                # Clear out the code/state from the URL
                st.experimental_set_query_params()
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                logging.error(f"Auth error: {e}")
                st.stop()

    # If the user hasn't triggered a callback or wasn't authed yet, show sign-in
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot (Login w/ Singleton State Store, Lists -> Single Strings)")
        st.write("Sign in with your s-p.net Google account.")

        auth_url = build_auth_url_and_store_state()
        st.markdown(f"[**Sign in with Google**]({auth_url})")
        st.stop()
    else:
        # Already authenticated
        main_it_app()


if __name__ == "__main__":
    run_app()