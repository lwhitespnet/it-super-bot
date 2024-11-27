import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize session state for assistant and thread
if 'assistant' not in st.session_state:
    st.session_state.assistant = client.beta.assistants.create(
        name="IT Super Bot",
        instructions="You are an IT support assistant for Sight Partners. You help manage and retrieve IT-related information and documentation.",
        model="gpt-4-turbo",
    )

if 'thread' not in st.session_state:
    st.session_state.thread = client.beta.threads.create()

# Streamlit app layout
st.title("IT Super Bot")

# Chat input
if prompt := st.chat_input("Ask me anything about IT support..."):
    # Add user message to thread
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread.id,
        role="user",
        content=prompt
    )
    
    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id
    )

    # Wait for the run to complete
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=run.id
        )

    # Get messages
    messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )

    # Display chat messages
    for message in reversed(messages.data):
        if message.role == "user":
            st.chat_message("user").write(message.content[0].text.value)
        else:
            st.chat_message("assistant").write(message.content[0].text.value)