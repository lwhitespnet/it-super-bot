##############################################
# app.py
# Minimal Google OAuth example with a cache_resource store for 'state'
# Fallback approach (no st.experimental_rerun),
# and using openai==0.28.1 with ChatCompletion (GPT-4).
##############################################

import sys
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
# 0) Debug Info
##############################################
st.write(f"**Streamlit version:** {st.__version__}")
streamlit_file = sys.modules["streamlit"].__file__
st.write(f"**Streamlit imported from:** {streamlit_file}")
has_exp_rerun = "experimental_rerun" in dir(st)
st.write(f"**'experimental_rerun' in dir(st)?** {has_exp_rerun}")

logging.basicConfig(level=logging.DEBUG)
logging.info(f"Streamlit version: {st.__version__}")
logging.info(f"Streamlit imported from: {streamlit_file}")
logging.info(f"'experimental_rerun' in dir(st)? {has_exp_rerun}")

##############################################
# 1) Load environment variables
##############################################
load_dotenv()

##############################################
# 2) Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"  # Use your domain here
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Requesting basic user info: openid, email, profile
OAUTH_SCOPES = ["openid", "email", "profile"]

##############################################
# 3) A "singleton" (cache_resource) store for valid states
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
# 4) Build the auth URL & store random state
##############################################
def build_auth_url_and_store_state() -> str:
    state_store = get_state_store()

    # Generate a random state
    random_state = secrets.token_urlsafe(16)

    # Store it in our dictionary
    state_store[random_state] = True

    # Build the manual OAuth URL
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
# 5) Exchange code for token
##############################################
def exchange_code_for_token(code: str) -> dict:
    """
    Manually exchange the 'code' for tokens via POST to Google.
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
# 6) Verify the 's-p.net' domain
##############################################
def verify_domain(id_token_jwt: str):
    info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    domain = info.get("hd")
    if domain != "s-p.net":
        raise ValueError(f"Access restricted to 's-p.net'. Your domain: {domain}")
    # Mark user as authenticated
    st.session_state.authenticated = True
    return info

##############################################
# 7) The Main IT Interface
##############################################
def main_it_app():
    # Set your OpenAI API key from environment
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot - Fallback, using GPT-4")
    st.write("You're authenticated and from s-p.net—welcome!")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        # If they say "Please add...", pretend to store the info
        if user_input.lower().startswith("please add"):
            st.write(f"**(Pretending to store)**: {user_input[10:].strip()}")
        else:
            # Use ChatCompletion with GPT-4
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful IT assistant."},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=200,
                temperature=0.7
            )
            answer = response["choices"][0]["message"]["content"].strip()
            st.write(answer)

##############################################
# 8) The Entry Point
##############################################
def run_app():
    # Use st.experimental_get_query_params (there's a deprecation warning, but fine for now)
    query_params = st.experimental_get_query_params()
    logging.debug(f"Query params: {query_params}")

    # Display debug info
    st.write("**DEBUG**: experimental_get_query_params:", query_params)

    # Handle OAuth callback if we see code & state
    if "code" in query_params and "state" in query_params:
        code_list = query_params["code"]
        state_list = query_params["state"]

        code = code_list[0] if isinstance(code_list, list) else code_list
        returned_state = state_list[0] if isinstance(state_list, list) else state_list

        logging.debug(f"Returned code={code}, state={returned_state}")

        # Check our state store
        state_store = get_state_store()
        if returned_state not in state_store:
            st.error("State mismatch or missing. (No record in our state store.)")
            st.stop()
        else:
            # Remove used state from the dictionary
            del state_store[returned_state]

            # Exchange the code for tokens
            try:
                token_json = exchange_code_for_token(code)
                verify_domain(token_json["id_token"])
                # Clear out code & state from the URL
                st.experimental_set_query_params()

                # We'll do a simple fallback approach (no st.experimental_rerun)
                st.success("Authentication succeeded! Please click below or refresh.")
                if st.button("Click to continue"):
                    pass  # triggers a fresh run, 'authenticated' is True
                st.stop()

            except Exception as e:
                st.error(f"Authentication failed: {e}")
                logging.error(f"Auth error: {e}")
                st.stop()

    # If not yet authenticated or no callback
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot - Fallback, using GPT-4")
        st.write("Sign in with your s-p.net Google account.")

        auth_url = build_auth_url_and_store_state()
        st.markdown(f"[**Sign in with Google**]({auth_url})")
        st.stop()
    else:
        # Already authenticated
        main_it_app()


if __name__ == "__main__":
    run_app()