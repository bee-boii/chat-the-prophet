import os
import openai
import requests
import streamlit as st
import json

openai.api_key = st.secrets["OPENAI_API_KEY"]
api_key_pinecone = st.secrets["PINECONE_API_KEY"]
pinecone_environment = st.secrets["PINECONE_ENVIRONMENT"]
pinecone_endpoint = st.secrets["PINECONE_ENDPOINT"]

def get_embeddings_openai(text):
    try:
        response = openai.Embedding.create(
            input=text,
            model="text-embedding-ada-002"
        )
        response = response['data']
        return [x["embedding"] for x in response]
    except Exception as e:
        print(f"Error in get_embeddings_openai: {e}")
        raise

def semantic_search(query, index, **kwargs):
    try:
        xq = get_embeddings_openai(query)

        xr = index.query(vector=xq[0], top_k=kwargs.get('top_k', 1), include_metadata=kwargs.get('include_metadata', True))

        if xr.error:
            print(f"Invalid response: {xr}")
            raise Exception(f"Query failed: {xr.error}")

        title = [r["metadata"]["title"] for r in xr["matches"]]
        year = [r["metadata"]["year"] for r in xr["matches"]]
        month = [r["metadata"]["month"] for r in xr["matches"]]
        author = [r["metadata"]["author"] for r in xr["matches"]]
        print(title, month, year, author)
        transcripts = [r["metadata"]["text"] for r in xr["matches"]]
        return list(zip(title, transcripts, year, month, author))

    except Exception as e:
        print(f"Error in semantic_search: {e}")
        raise
