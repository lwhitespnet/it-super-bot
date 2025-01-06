##############################################
# app.py
# Minimal Google OAuth example with a cache_resource store for 'state'
# - Opens the OAuth flow in a pop-up window
# - Fallback approach for re-run (no st.experimental_rerun)
# - Using openai==0.28.1 (ChatCompletion) with GPT-4
##############################################

import os
import secrets

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
# Constants
##############################################
REDIRECT_URI = "https://it-super-bot.streamlit.app"  # Your Streamlit domain
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# OAuth scopes for basic user info
OAUTH_SCOPES = ["openid", "email", "profile"]

##############################################
# 1) Singleton store for valid states
##############################################
@st.cache_resource
def get_state_store() -> dict:
    """
    Returns a dictionary that persists until the app is redeployed.
    Keys: state strings
    Values: True (or any truthy value)
    """
    return {}

##############################################
# 2) Build the auth URL & store random state
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
    return auth_url

##############################################
# 3) Exchange code for token
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
    resp.raise_for_status()
    return resp.json()

##############################################
# 4) Verify s-p.net domain
##############################################
def verify_domain(id_token_jwt: str):
    info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
    )
    domain = info.get("hd")
    if domain != "s-p.net":
        raise ValueError("Access restricted to 's-p.net'.")
    st.session_state.authenticated = True
    return info

##############################################
# 5) Main IT Super Bot Interface
##############################################
def main_it_app():
    openai.api_key = OPENAI_API_KEY

    st.title("IT Super Bot")
    st.write("You’re authenticated and from s-p.net — welcome!")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            st.write(f"(Pretending to store): {user_input[10:].strip()}")
        else:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful IT assistant."},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            answer = response["choices"][0]["message"]["content"].strip()
            st.write(answer)

##############################################
# 6) Entry Point
##############################################
def run_app():
    query_params = st.experimental_get_query_params()

    # If we see code/state, handle OAuth callback
    if "code" in query_params and "state" in query_params:
        code_list = query_params["code"]
        state_list = query_params["state"]

        # Extract single values
        code = code_list[0] if isinstance(code_list, list) else code_list
        returned_state = state_list[0] if isinstance(state_list, list) else state_list

        # Check our stored state
        state_store = get_state_store()
        if returned_state not in state_store:
            st.error("State mismatch or missing.")
            st.stop()
        else:
            # Remove used state
            del state_store[returned_state]

            # Exchange code and verify domain
            try:
                token_json = exchange_code_for_token(code)
                verify_domain(token_json["id_token"])
                st.experimental_set_query_params()
                st.success("Authentication succeeded! Please click below or refresh.")
                if st.button("Continue to IT Super Bot"):
                    pass  # triggers a new rerun; session_state.authenticated = True
                st.stop()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                st.stop()

    # If not authenticated, show sign-in
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot (Login)")
        st.write("Sign in with your s-p.net Google account in a pop-up window.")

        auth_url = build_auth_url_and_store_state()

        # JavaScript snippet to open the sign-in URL in a pop-up window
        popup_js = f"""
            <script>
            function openPopup() {{
                window.open("{auth_url}", "oauthPopup",
                            "width=600,height=700,left=200,top=100");
            }}
            </script>
            <button onclick="openPopup()">Sign in with Google (Pop-up)</button>
        """

        st.markdown(popup_js, unsafe_allow_html=True)

        st.stop()
    else:
        main_it_app()


if __name__ == "__main__":
    run_app()