from utils import (
    convert_to_atlas_keywords_and_phrases,
    atlas_search,
    pinecone_semantic_search,
)
from render import bot_msg_container_html_template, user_msg_container_html_template
import streamlit as st
import openai, pinecone
import prompts
import json, pprint

openai.api_key = st.secrets["OPENAI_API_KEY"]
pinecone.init(
    api_key=st.secrets["PINECONE_API_KEY"],
    environment=st.secrets["PINECONE_ENVIRONMENT"],
)
index = pinecone.Index(st.secrets["PINECONE_INDEX_NAME"])

# Based on hormozi gpt
st.header("Chat The Prophet - By BCG")

# Define chat history storage
if "history" not in st.session_state:
    st.session_state.history = []


# Construct messages from chat history
def construct_messages(history):
    messages = [{"role": "system", "content": prompts.system_message}]

    for entry in history:
        role = "user" if entry["is_user"] else "assistant"
        messages.append({"role": role, "content": entry["message"]})

    return messages


# Generate response to user prompt
def generate_response():
    user_query = st.session_state.prompt

    st.session_state.history.append({"message": user_query, "is_user": True})

    print(f"Query: {user_query}")

    atlas_json_query = convert_to_atlas_keywords_and_phrases(user_query)

    print(f"Altas Seach Keywords: {atlas_json_query['keywords']}")
    print(f"Altas Seach Phrases: {atlas_json_query['search_phrases']}")

    atlas_search_results = atlas_search(
        atlas_json_query["keywords"], atlas_json_query["search_phrases"]
    )

    # Perform semantic search and format results
    semantic_search_results = pinecone_semantic_search(user_query, index, top_k=9)

    context = "Speech Quotes:\n\n"

    for search_list in atlas_search_results:
        for speech in search_list:
            if speech:
                context += f"\"{speech['text']}\"\n({speech['title']} by {speech['author']}, {speech['month']} {speech['year']})\n\n"

    for speech in semantic_search_results:
        context += f"\"{speech['text']}\"\n({speech['title']} by {speech['author']}, {speech['month']} {speech['year']})\n\n"

    # Convert chat history to a list of messages
    chat_messages = construct_messages(st.session_state.history)
    chat_messages.append({"role": "user", "content": context})
    chat_messages.append({"role": "user", "content": f"User Query: {user_query}"})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=chat_messages,
        temperature=0.5,
        max_tokens=3500,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    # Parse response
    bot_response = response["choices"][0]["message"]["content"]
    st.session_state.history.append({"message": bot_response, "is_user": False})


# User input prompt
user_prompt = st.text_input(
    "Enter your prompt:",
    key="prompt",
    placeholder="e.g. 'What has Russell M. Nelson taught about Jesus Christ?'",
    on_change=generate_response,
)

# Display chat history
for message in st.session_state.history:
    if message["is_user"]:
        st.write(
            user_msg_container_html_template.replace("$MSG", message["message"]),
            unsafe_allow_html=True,
        )
    else:
        st.write(
            bot_msg_container_html_template.replace("$MSG", message["message"]),
            unsafe_allow_html=True,
        )
