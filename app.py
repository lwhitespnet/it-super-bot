##############################################
# app.py
# IT Super Bot
# - Google OAuth (opens in new tab, original approach)
# - Simple ephemeral knowledge base ("Please add...")
# - Using openai==0.28.1 with GPT-4
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
OAUTH_SCOPES = ["openid", "email", "profile"]

##############################################
# 1) Cache Resource for State & Knowledge Base
##############################################

@st.cache_resource
def get_state_store() -> dict:
    """
    Persists valid OAuth states until the app redeploys.
    Keys: random state strings
    Values: True/any truthy value
    """
    return {}

@st.cache_resource
def get_knowledge_base() -> list:
    """
    Persists knowledge base content in memory until the app redeploys.
    Returns a list of strings (each "Please add" entry).
    """
    return []

##############################################
# 2) Build Auth URL
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
# 4) Verify Domain
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

    # Grab the knowledge base
    knowledge_base = get_knowledge_base()

    st.write("You're authenticated and from s-p.net — welcome!")
    st.write(f"Current knowledge base has **{len(knowledge_base)}** entries.")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        # Check if user wants to add to the knowledge base
        if user_input.lower().startswith("please add"):
            new_info = user_input[10:].strip()
            knowledge_base.append(new_info)
            st.write(f"**Stored in knowledge base**: {new_info}")

        else:
            # Incorporate the knowledge base into GPT context
            if knowledge_base:
                knowledge_context = "\n".join(knowledge_base)
                system_content = (
                    "You are a helpful IT assistant. "
                    "Below is your knowledge base, which can help answer questions:\n"
                    f"{knowledge_context}\n\n"
                    "Use this information if relevant."
                )
            else:
                system_content = (
                    "You are a helpful IT assistant. You currently have no knowledge base."
                )

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_content},
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

    # If we see code/state, handle callback
    if "code" in query_params and "state" in query_params:
        code_list = query_params["code"]
        state_list = query_params["state"]

        code = code_list[0] if isinstance(code_list, list) else code_list
        returned_state = state_list[0] if isinstance(state_list, list) else state_list

        state_store = get_state_store()
        if returned_state not in state_store:
            st.error("State mismatch or missing.")
            st.stop()
        else:
            del state_store[returned_state]
            try:
                token_json = exchange_code_for_token(code)
                verify_domain(token_json["id_token"])
                st.experimental_set_query_params()
                st.success("Authentication succeeded! Please click below or refresh.")
                if st.button("Continue to IT Super Bot"):
                    pass  # triggers a new rerun; st.session_state.authenticated is True
                st.stop()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot (Login)")

        auth_url = build_auth_url_and_store_state()

        # REVERTED to the original Markdown approach, which typically opens a new tab
        st.markdown(f"[**Sign in with Google**]({auth_url})")

        st.stop()
    else:
        main_it_app()


if __name__ == "__main__":
    run_app()