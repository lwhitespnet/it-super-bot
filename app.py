import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow
import logging
from pprint import pformat

# Load environment variables
load_dotenv()

# Debugging
DEBUG = True
if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("google_auth_oauthlib").setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient").setLevel(logging.DEBUG)
    logging.debug("Debugging is enabled.")
else:
    logging.basicConfig(level=logging.INFO)

# Determine Redirect URI
if os.getenv("STREAMLIT_CLOUD") == "true":  # For deployment on Streamlit Cloud
    REDIRECT_URI = "https://it-super-bot.streamlit.app/_stcore/oauth-callback"
else:
    REDIRECT_URI = "http://localhost:8501"

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'oauth_state' not in st.session_state:
    st.session_state.oauth_state = None
if 'query_params' not in st.session_state:
    st.session_state.query_params = {}

# OAuth Flow Setup
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI]
        }
    },
    scopes=['openid', 'email', 'profile']
)
flow.redirect_uri = REDIRECT_URI

def handle_oauth_callback():
    try:
        # Use the query parameters captured in session state
        query_params = st.session_state.query_params
        logging.debug(f"Query parameters received: {query_params}")

        # Extract `state` and `code`
        received_state = query_params.get('state', [None])[0]
        expected_state = st.session_state.get('oauth_state')
        code = query_params.get('code', [None])[0]
        logging.debug(f"State received: {received_state}, State expected: {expected_state}")
        logging.debug(f"Authorization code received: {code}")

        # Validate state
        if received_state != expected_state:
            raise ValueError("State parameter mismatch!")

        # Validate authorization code
        if not code:
            raise ValueError("Authorization code is missing!")

        # Exchange the authorization code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials
        logging.debug(f"Credentials: {credentials}")

        # Verify the ID token
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        logging.debug(f"ID token info: {pformat(id_info)}")

        # Restrict access to specific domain
        if id_info.get('hd') != 's-p.net':
            st.error("Access restricted to Sight Partners users.")
            return False

        # Update session state
        st.session_state.authenticated = True
        st.session_state.user_email = id_info.get('email')
        logging.debug(f"User authenticated: {st.session_state.user_email}")
        return True

    except Exception as e:
        logging.error(f"Error during OAuth callback: {e}")
        st.error("Authentication failed. Please try again.")
        return False

def main():
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    except Exception as e:
        logging.error(f"Error initializing OpenAI: {e}")
        st.error("Failed to initialize OpenAI. Check your API key.")
        return

    # IT Assistant Main Interface
    st.title("IT Super Bot")
    st.write(f"Welcome, {st.session_state.user_email}")

    if prompt := st.chat_input("Ask me anything about IT support..."):
        logging.debug(f"User input received: {prompt}")
        message = client.beta.threads.messages.create(
            thread_id=st.session_state.thread.id,
            role="user",
            content=prompt
        )
        
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread.id,
            assistant_id=st.session_state.assistant.id
        )

        # Wait for assistant response
        while run.status in ["queued", "in_progress"]:
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread.id,
                run_id=run.id
            )

        # Display messages
        messages = client.beta.threads.messages.list(
            thread_id=st.session_state.thread.id
        )
        for message in reversed(messages.data):
            role = message.role
            content = message.content[0].text.value
            st.chat_message(role).write(content)

# Capture query parameters at the start
if not st.session_state.query_params:
    # Log the full URL for debugging
    logging.debug(f"App URL: {st.query_params}")

    # Capture query parameters if present
    st.session_state.query_params = st.query_params
    logging.debug(f"Captured query parameters: {st.session_state.query_params}")

    # Check if `state` and `code` exist in the captured query parameters
    if 'state' in st.session_state.query_params and 'code' in st.session_state.query_params:
        logging.debug("State and code parameters received.")
    else:
        logging.debug("State or code parameters missing in query.")

# Entry Point
if not st.session_state.authenticated:
    logging.debug("User not authenticated. Showing login screen.")
    st.write("Sign in with your Sight Partners Google account.")
    
    if handle_oauth_callback():
        logging.debug("OAuth callback handled successfully. Rerunning app...")
        st.rerun()

    # Generate OAuth URL
    auth_url, state = flow.authorization_url(prompt='consent')
    st.session_state.oauth_state = state  # Save state for validation
    logging.debug(f"Generated OAuth URL: {auth_url}")
    logging.debug(f"Generated state: {state}")

    if st.button("Sign in with Google"):
        logging.debug("Sign in button clicked. Redirecting to Google...")
        js_code = f"<script>window.location.href = '{auth_url}';</script>"
        st.components.v1.html(js_code, height=0)
else:
    logging.debug("User authenticated. Loading IT assistant...")
    main()