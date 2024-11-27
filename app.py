import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow
from pathlib import Path
import json

load_dotenv()

if 'authenticated' not in st.session_state:
   st.session_state.authenticated = False

if 'user_email' not in st.session_state:
   st.session_state.user_email = None

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = 'https://it-super-bot.streamlit.app/_stcore/oauth-callback'

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

def authenticate_user(token):
   try:
       idinfo = id_token.verify_oauth2_token(
           token, 
           requests.Request(), 
           GOOGLE_CLIENT_ID
       )

       if idinfo['hd'] != 's-p.net':
           return False, None

       return True, idinfo['email']
   except:
       return False, None

def handle_oauth_callback():
   try:
       code = st.query_params.get("code")
       
       if code:
           flow.fetch_token(code=code)
           credentials = flow.credentials
           
           id_info = id_token.verify_oauth2_token(
               credentials.id_token,
               requests.Request(),
               GOOGLE_CLIENT_ID
           )
           
           if id_info.get('hd') == 's-p.net':
               st.session_state.authenticated = True
               st.session_state.user_email = id_info.get('email')
               return True
   except Exception as e:
       st.error(f"Authentication failed: {str(e)}")
   return False

def main():
   client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

   if 'assistant' not in st.session_state:
       st.session_state.assistant = client.beta.assistants.create(
           name="IT Super Bot",
           instructions="You are an IT support assistant for Sight Partners. You help manage and retrieve IT-related information and documentation.",
           model="gpt-4-turbo",
       )

   if 'thread' not in st.session_state:
       st.session_state.thread = client.beta.threads.create()

   st.title("IT Super Bot")
   st.write(f"Welcome, {st.session_state.user_email}")

   if prompt := st.chat_input("Ask me anything about IT support..."):
       client.beta.threads.messages.create(
           thread_id=st.session_state.thread.id,
           role="user",
           content=prompt
       )
       
       run = client.beta.threads.runs.create(
           thread_id=st.session_state.thread.id,
           assistant_id=st.session_state.assistant.id
       )

       while run.status == "queued" or run.status == "in_progress":
           run = client.beta.threads.runs.retrieve(
               thread_id=st.session_state.thread.id,
               run_id=run.id
           )

       messages = client.beta.threads.messages.list(
           thread_id=st.session_state.thread.id
       )

       for message in reversed(messages.data):
           if message.role == "user":
               st.chat_message("user").write(message.content[0].text.value)
           else:
               st.chat_message("assistant").write(message.content[0].text.value)

if not st.session_state.authenticated:
   st.write("Please sign in with your Sight Partners Google account")
   
   if handle_oauth_callback():
       st.rerun()
   
   auth_url, _ = flow.authorization_url(prompt='consent')
   if st.button("Sign in with Google"):
       st.switch_page(auth_url)
else:
   main()