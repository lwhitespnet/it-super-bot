##############################################
# app.py
# Permanent knowledge base in Google Sheets
# with gspread + openai ChatCompletion
##############################################

import os
import secrets

import streamlit as st
from dotenv import load_dotenv

import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

import openai

# NEW: gspread for Google Sheets
import gspread
from google.oauth2.service_account import Credentials

##############################################
# Load environment variables
##############################################
load_dotenv()

REDIRECT_URI = "https://it-super-bot.streamlit.app"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_SCOPES = ["openid", "email", "profile"]

# NEW: Sheets config
#  - This is your service account credentials JSON, stored as a file or env var
SERVICE_ACCOUNT_INFO = os.getenv("GSPREAD_CREDS")  # Could be a JSON string
SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]

# The Google Sheet key/ID (from its URL). Example:
SHEET_ID = os.getenv("SHEET_ID")  # or paste in the actual sheet ID

##############################################
# 1) Singleton for valid states
##############################################
@st.cache_resource
def get_state_store() -> dict:
    return {}

##############################################
# 2) Build auth URL
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
        raise ValueError("Access restricted to 's-p.net'.")
    st.session_state.authenticated = True
    return info

##############################################
# 5) Google Sheets Helper
##############################################
def get_gsheet():
    """
    Creates a gspread client using service account credentials
    and returns a Worksheet object for the given SHEET_ID (first worksheet).
    """
    # If you stored the entire JSON as an env var:
    import json
    creds_dict = json.loads(SERVICE_ACCOUNT_INFO)

    creds = Credentials.from_service_account_info(
        creds_dict, scopes=SHEETS_SCOPE
    )
    gc = gspread.authorize(creds)

    # Open the spreadsheet by ID
    sh = gc.open_by_key(SHEET_ID)
    # Return the first worksheet
    return sh.get_worksheet(0)

def read_knowledge_base():
    """
    Reads all rows from the Google Sheet. 
    Returns a list of strings (each row's content).
    """
    ws = get_gsheet()
    data = ws.get_all_values()  # list of lists
    # If your sheet's first column holds the text, extract it
    knowledge = []
    for row in data:
        if row and row[0].strip():
            knowledge.append(row[0].strip())
    return knowledge

def add_to_knowledge_base(text: str):
    """
    Appends a new row to the sheet with the given text.
    """
    ws = get_gsheet()
    ws.append_row([text])

##############################################
# 6) Main IT Interface
##############################################
def main_it_app():
    openai.api_key = OPENAI_API_KEY

    st.title("IT Super Bot with Google Sheets KB")
    st.write("You’re authenticated and from s-p.net — welcome!")

    # Read knowledge base from sheet
    knowledge_base = read_knowledge_base()
    st.write(f"Current knowledge base has **{len(knowledge_base)}** entries.")

    user_input = st.text_input("Ask something or say 'Please add...' to store info:")
    if user_input:
        if user_input.lower().startswith("please add"):
            new_info = user_input[10:].strip()
            add_to_knowledge_base(new_info)
            st.write(f"**Stored**: {new_info}")
        else:
            # Build system prompt using knowledge base
            if knowledge_base:
                context = "\n".join(knowledge_base)
                system_content = (
                    "You are a helpful IT assistant. Here's your knowledge base:\n"
                    f"{context}\n\n"
                    "Use the above info if relevant when answering questions."
                )
            else:
                system_content = "You are a helpful IT assistant. You have no knowledge base."

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
# 7) Entry Point
##############################################
def run_app():
    query_params = st.experimental_get_query_params()

    # Handle OAuth callback
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
                if st.button("Continue"):
                    pass
                st.stop()
            except Exception as e:
                st.error(f"Authentication failed: {e}")
                st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("IT Super Bot (Login)")

        # Build auth URL
        auth_url = build_auth_url_and_store_state()
        # Link to open in same tab
        link_html = f'<a href="{auth_url}" target="_self">Sign in with Google</a>'
        st.markdown(link_html, unsafe_allow_html=True)
        st.stop()
    else:
        main_it_app()


if __name__ == "__main__":
    run_app()