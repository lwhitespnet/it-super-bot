
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

# Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = 'https://it-super-bot.streamlit.app/_stcore/oauth-callback'

# Session state initialization
def initialize_session():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None

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
        query_params = st.experimental_get_query_params()
        logging.debug(f"Query parameters received: {query_params}")
        code = query_params.get('code', [None])[0]
        logging.debug(f"Authorization code: {code}")
        if not code:
            raise ValueError("Authorization code missing!")

        flow.fetch_token(code=code)
        credentials = flow.credentials

        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        logging.debug(f"Token info: {pformat(id_info)}")
        
        if id_info.get('hd') != 's-p.net':
            st.error("Please use your Sight Partners email address")
            return False

        st.session_state.authenticated = True
        st.session_state.user_email = id_info.get('email')
        return True

    except Exception as e:
        logging.error(f"Error during OAuth callback: {e}")
        st.error("Authentication failed. Please try again.")
        return False

def main():
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    except Exception as e:
        logging.error(f"OpenAI initialization error: {e}")
        st.error("Failed to initialize OpenAI API. Please check your key.")
        return

    # Initialize OpenAI assistant and thread
    if 'assistant' not in st.session_state:
        st.session_state.assistant = client.beta.assistants.create(
            name="IT Super Bot",
            instructions="You are an IT support assistant for Sight Partners. You help manage and retrieve IT-related information and documentation.",
            model="gpt-4-turbo",
        )
    if 'thread' not in st.session_state:
        st.session_state.thread = client.beta.threads.create()

    # Main app interface
    st.title("IT Super Bot")
    st.write(f"Welcome, {st.session_state.user_email}")

    # Chat interface
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

        # Wait for completion
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

# App entry point
if not st.session_state.authenticated:
    st.write("Please sign in with your Sight Partners Google account")
    
    if handle_oauth_callback():
        st.rerun()

    auth_url, _ = flow.authorization_url(prompt='consent')
    logging.debug(f"Generated OAuth URL: {auth_url}")
    if st.button("Sign in with Google"):
        js = f"""
        <script>
            window.location.href = "{auth_url}";
        </script>
        """
        st.components.v1.html(js)
else:
    main()
