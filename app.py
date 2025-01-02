##############################################
# app.py - Store Flow in Session State to Fix "State mismatch"
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
REDIRECT_URI = "https://it-super-bot.streamlit.app"  # your base domain
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


def create_flow():
    """
    Create a new OAuth Flow instance (with redirect URIs, scopes, etc.)
    """
    return Flow.from_client_config(
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


##############################################
# Session State Defaults
##############################################
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "flow" not in st.session_state:
    # Create & store a single Flow instance in session state
    st.session_state.flow = create_flow()
    st.session_state.flow.redirect_uri = REDIRECT_URI


##############################################
# Handle OAuth Callback
##############################################
def handle_oauth_callback(code: str, returned_state: str) -> bool:
    """
    Uses the same Flow instance from st.session_state,
    exchanges code for tokens, checks domain = s-p.net.
    """
    try:
        # Pull out the stored Flow instance
        flow: Flow = st.session_state.flow

        # If the returned state doesn't match flow's internal state, mismatch.
        if returned_state != flow.oauth2session.state:
            raise ValueError("State mismatch or missing.")

        # Exchange the code for tokens
        flow.fetch_token(code=code)

        # Verify ID token
        credentials = flow.credentials
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

        # If we reach here, authentication is good
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
    # Initialize OpenAI
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
    # Check for code/state in the URL
    query_params = st.query_params
    logging.debug(f"query_params: {query_params}")

    if not st.session_state.authenticated:
        if "code" in query_params and "state" in query_params:
            code = query_params["code"][0]
            returned_state = query_params["state"][0]

            if handle_oauth_callback(code, returned_state):
                # Clear out code/state from the URL
                st.experimental_set_query_params()
                st.experimental_rerun()
            else:
                return  # If it failed, show the error

        if not st.session_state.authenticated:
            st.title("IT Super Bot (Login)")
            st.write("Sign in with your Sight Partners Google account.")

            # Pull out the single Flow object from session_state
            flow: Flow = st.session_state.flow

            # Get the auth URL & state from the existing Flow
            auth_url, _ = flow.authorization_url(prompt="consent")
            # Flow manages its own internal "state" now

            logging.debug(f"auth_url={auth_url}")
            st.markdown(f"[**Sign in with Google**]({auth_url})")
            return

    # If we get here, user is authenticated
    main()


if __name__ == "__main__":
    run_app()