##############################################
# app.py - Debug version
# We'll print environment details about Streamlit
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
# Extra Debug
##############################################
# 1) Print out Streamlit version
# 2) Print out the file that provided the 'streamlit' module
# 3) Check if 'experimental_rerun' is in dir(st)
st.write(f"**Streamlit version:** {st.__version__}")
logging.info(f"Streamlit version reported by st.__version__: {st.__version__}")

streamlit_file = sys.modules["streamlit"].__file__
st.write(f"**Streamlit imported from:** {streamlit_file}")
logging.info(f"Streamlit imported from: {streamlit_file}")

has_exp_rerun = "experimental_rerun" in dir(st)
st.write(f"**'experimental_rerun' in dir(st)?** {has_exp_rerun}")
logging.info(f"'experimental_rerun' in dir(st)? {has_exp_rerun}")

##############################################
# Load environment variables
##############################################
load_dotenv()

##############################################
# Logging
##############################################
logging.basicConfig(level=logging.DEBUG)
logging.info("Running Python code...")

##############################################
# Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"
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
    return {}

##############################################
# 2) Function: Generate an auth URL manually & store the state in our dict
##############################################
def build_auth_url_and_store_state() -> str:
    state_store = get_state_store()
    random_state = secrets.token_urlsafe(16)
    state_store[random_state] = True

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
    info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    domain = info.get("hd")
    if domain != "s-p.net":
        raise ValueError(f"Access restricted to 's-p.net'. Your domain: {domain}")
    st.session_state.authenticated = True
    return info

##############################################
# 5) The Main IT Interface
##############################################
def main_it_app():
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.title("IT Super Bot - Debug Version")
    st.write("You're authenticated and from s-p.net—welcome!")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write(f"**(Pretending to store)**: {user_input[10:].strip()}")
        else:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=user_input,
                max_tokens=60,
                temperature=0.7
            )
            st.write(response.choices[0].text.strip())

##############################################
# 6) Attempt a rerun safely
##############################################
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.warning("Unable to do an automatic re-run. Please refresh your browser manually.")
        st.stop()

##############################################
# 7) The Entry Point
##############################################
def run_app():
    # Use st.experimental_get_query_params for now
    query_params = st.experimental_get_query_params()
    logging.debug(f"Query params: {query_params}")

    st.write("**DEBUG**: experimental_get_query_params:", query_params)

    if "code" in query_params and "state" in query_params:
        code_list = query_params["code"]
        state_list = query_params["state"]

        code = code_list[0] if isinstance(code_list, list) else code_list
        returned_state = state_list[0] if isinstance(state_list, list) else state_list

        logging.debug(f"Returned code={code}, state={returned_state}")
        state_store = get_state_store()

        if returned_state not in state_store:
            st.error("State mismatch or missing. (No record in our state store.)")
            st.stop()
        else:
            del state_store[returned_state]
            try:
                token_json = exchange_code_for_token(code)
                verify_domain(token_json["id_token"])
                st.experimental_set_query_params()
                safe_rerun()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                logging.error(f"Auth error: {e}")
                st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot - Debug Version")
        st.write("Sign in with your s-p.net Google account.")

        auth_url = build_auth_url_and_store_state()
        st.markdown(f"[**Sign in with Google**]({auth_url})")
        st.stop()
    else:
        main_it_app()


if __name__ == "__main__":
    run_app()