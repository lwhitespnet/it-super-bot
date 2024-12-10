import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow
import logging
from pprint import pformat

# Enable Debugging
DEBUG = True

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("google_auth_oauthlib").setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient").setLevel(logging.DEBUG)
    logging.debug("Debugging is enabled.")
else:
    logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Determine if running locally or on Streamlit Cloud
if os.getenv("STREAMLIT_CLOUD") == "true":  # Streamlit Cloud sets this env var
    REDIRECT_URI = "https://your-streamlit-app-name.streamlit.app"
else:
    REDIRECT_URI = "http://localhost:8501"

# Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Session state initialization
def initialize_session():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'oauth_state' not in st.session_state:
        st.session_state.oauth_state = None

initialize_session()

# OAuth flow configuration
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
        # Get the query parameters from the callback URL
        query_params = st.query_params
        logging.debug(f"Query parameters received: {query_params}")

        # Extract state and authorization code
        received_state = query_params.get('state', [None])[0]
        expected_state = st.session_state.get('oauth_state')
        code = query_params.get('code', [None])[0]
        logging.debug(f"State received: {received_state}, State expected: {expected_state}")
        logging.debug(f"Authorization code received: {code}")

        # Validate the state parameter
        if received_state != expected_state:
            raise ValueError("State parameter mismatch!")

        # Validate the authorization code
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

        # Check if the user is from the Sight Partners domain
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

    # Initialize assistant and thread
    if 'assistant' not in st.session_state:
        st.session_state.assistant = client.beta.assistants.create(
            name="IT Super Bot",
            instructions="You are an IT support assistant for Sight Partners. You help manage and retrieve IT-related information and documentation.",
            model="gpt-4-turbo",
        )
    if 'thread' not in st.session_state:
        st.session_state.thread = client.beta.threads.create()

    # Display IT assistant chat interface
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

        # Display assistant's responses
        messages = client.beta.threads.messages.list(
            thread_id=st.session_state.thread.id
        )
        for message in reversed(messages.data):
            role = message.role
            content = message.content[0].text.value
            st.chat_message(role).write(content)

# App entry point
if not st.session_state.authenticated:
    st.write("Sign in with your Sight Partners Google account.")
    
    if handle_oauth_callback():
        st.rerun()

    auth_url, state = flow.authorization_url(prompt='consent')
    st.session_state.oauth_state = state  # Save state for validation
    logging.debug(f"Generated OAuth URL: {auth_url}")
    logging.debug(f"Generated state: {state}")

    if st.button("Sign in with Google"):
        js_code = f"<script>window.location.href = '{auth_url}';</script>"
        st.components.v1.html(js_code, height=0)
else:
    main()