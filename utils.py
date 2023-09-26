import openai
import streamlit as st
from pymongo.mongo_client import MongoClient
import json

openai.api_key = st.secrets["OPENAI_API_KEY"]

mongodb_password = st.secrets["ATLAS_PASSWORD"]
mongodb_username = st.secrets["ATLAS_USERNAME"]
mongodb_database = st.secrets["ATLAS_DATABASE_NAME"]

connection_string = f"mongodb+srv://{mongodb_username}:{mongodb_password}@{mongodb_database}.svlfufy.mongodb.net/?retryWrites=true&w=majority"

# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    return MongoClient(connection_string)

client = init_connection()

gen_conf_db = client.general_conference
rmn_speeches = gen_conf_db.russell_m_nelson


def convert_to_atlas_keywords_and_phrases(query):
    """
    See the content associated with "system" in the chat completion to get an idea of the functions purpose.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": 'You are tasked with generating search criteria based on user queries. When presented with a query, you are to:\n\n1. Extract Keywords:\nGenerate a list of single-word keywords derived from the user\'s query.\n\n2. Formulate Search Phrases:\nCreate a list of search phrases based on the user query. Each phrase should be between 2 to 4 words long.\n\nRemember, the generated keywords and phrases are intended for a NoSQL database search. This database contains religious speeches by President Russell M Nelson. Do not include his name, "Russell M Nelson", or his title, "President", in any of the keywords or search phrases.\n\nPresent your response in the following JSON format:\n\n{"keywords": [list_of_keywords], "search_phrases": list_of_search_phrases]}',
            },
            {
                "role": "user",
                "content": "What can I learn from President Nelson's teachings about finding happiness and joy in my life?",
            },
            {
                "role": "assistant",
                "content": '{"keywords": ["happiness","joy"], "search_phrases": ["finding happiness","finding joy","happiness in life" "joy in life"]}',
            },
            {
                "role": "user",
                "content": "What has Russell M. Nelson said about repentance",
            },
            {
                "role": "assistant",
                "content": '{"keywords": ["repentance","repent"], "search_phrases": ["practicing repentance","learning to repent","repentance and forgiveness","process of repentance"]}',
            },
            {
                "role": "user",
                "content": "What has he taught regarding women and their relationship with the priesthood",
            },
            {
                "role": "assistant",
                "content": '{"keywords": ["priesthood"], "search_phrases": ["women\'s role in priesthood","women and priesthood","women\'s relationship with priesthood","equality and priesthood","women\'s role in church"]}',
            },
            {"role": "user", "content": "Has President Nelson spoken about abortion?"},
            {
                "role": "assistant",
                "content": '{"keywords": ["abortion"], "search_phrases": ["teachings on abortion","abortion and morality","sanctity of life","abortion and the commandments","value of unborn life","unborn children"]}',
            },
            {"role": "user", "content": "How can I become a kinder person"},
            {
                "role": "assistant",
                "content": '{"keywords": ["kinder","kindness"], "search_phrases": ["becoming kind","developing kindness","cultivating kindness","practicing kindness","kindness in daily life"]}',
            },
            {
                "role": "user",
                "content": "Remind me the story he told about the angry surgeon and the scalpel",
            },
            {
                "role": "assistant",
                "content": '{"keywords": ["surgeon","scalpel"], "search_phrases": ["angry surgeon", "surgeon and scalpel","anger and a scalpel"]}',
            },
            {
                "role": "user",
                "content": "What does Russell Nelson say about gathering Israel?",
            },
            {
                "role": "assistant",
                "content": '{"keywords": ["Israel","gathering"], "search_phrases": ["mission to gather Israel", "gathering scattered Israel","redeeming the covenant people"]}',
            },
            {
                "role": "user",
                "content": query,
            },
        ],
    )

    json_response = json.loads(response["choices"][0]["message"]["content"])

    if type(json_response) == dict:
        if "keywords" in json_response and "search_phrases" in json_response:
            if (
                type(json_response["keywords"]) == list
                and type(json_response["search_phrases"]) == list
            ):
                for kw in json_response["keywords"]:
                    if type(kw) != str:
                        return None
                for sp in json_response["search_phrases"]:
                    if type(sp) != str:
                        return None
            else:
                return None
        else:
            return None
    else:
        return None

    return json_response


def atlas_search(keywords, search_phrases, top_k=3):
    """
    Returns as list of three lists: [[],[],[]]
    In each of the inner lists there may be a maximum of top_k "documents"
    The first list contains the top matches to the keyword search generated from the query, the second contains the top matches from the phraase search, while the third list contains the top mathces of the moreLikeThis search which searches for documents that are like the top matches from the first two lists.
    Each document is a dictionary with the following keys: "year", "month", "author", "title", "text", "score"
    The score is assigned by atlas search based on its algorithm. Higher is better match to the query.

    top_k refers to how many results should be returned. default is 3.
    That means the top three results from each search will be returned, totally up to 9 results
    """
    text_search_result = rmn_speeches.aggregate(
        [
            {
                "$search": {
                    "index": "russell_m_nelson_search",
                    "text": {"query": keywords, "path": "text", "fuzzy": {}},
                    # "scoreDetails": True,
                }
            },
            {"$limit": top_k},
            {
                "$project": {
                    "_id": 1,
                    "author": 1,
                    "title": 1,
                    "month": 1,
                    "year": 1,
                    "text": 1,
                    "score": {"$meta": "searchScore"},
                    # "scoreDetails": {"$meta": "searchScoreDetails"},
                }
            },
        ]
    )
    text_search_result = list(text_search_result)

    phrase_search_result = rmn_speeches.aggregate(
        [
            {
                "$search": {
                    "index": "russell_m_nelson_search",
                    "phrase": {"query": search_phrases, "path": "text", "slop": 5},
                    # "scoreDetails": True,
                }
            },
            {"$limit": top_k},
            {
                "$project": {
                    "_id": 1,
                    "author": 1,
                    "title": 1,
                    "month": 1,
                    "year": 1,
                    "text": 1,
                    "score": {"$meta": "searchScore"},
                    # "scoreDetails": {"$meta": "searchScoreDetails"},
                }
            },
        ]
    )
    phrase_search_result = list(phrase_search_result)

    # Search the top result from each of the previous two searches using the moreLikeThis atlas search
    top_score_texts = []
    if text_search_result:
        top_score_texts.append(text_search_result[0])
    if phrase_search_result:
        top_score_texts.append(phrase_search_result[0])

    if len(top_score_texts) == 2:
        moreLikeThis_search_result = rmn_speeches.aggregate(
            [
                {
                    "$search": {
                        "index": "russell_m_nelson_search",
                        "compound": {
                            "must": [
                                {
                                    "moreLikeThis": {
                                        "like": {
                                            "text": [
                                                top_score_texts[0]["text"],
                                                top_score_texts[1]["text"],
                                            ]
                                        }
                                    }
                                }
                            ],
                            "mustNot": [
                                {
                                    "equals": {
                                        "path": "_id",
                                        "value": top_score_texts[0]["_id"],
                                    }
                                },
                                {
                                    "equals": {
                                        "path": "_id",
                                        "value": top_score_texts[1]["_id"],
                                    }
                                },
                            ],
                        },
                    }
                },
                {"$limit": top_k},
                {
                    "$project": {
                        "_id": 1,
                        "author": 1,
                        "title": 1,
                        "month": 1,
                        "year": 1,
                        "text": 1,
                        "score": {"$meta": "searchScore"},
                        # "scoreDetails": {"$meta": "searchScoreDetails"},
                    }
                },
            ]
        )
        moreLikeThis_search_result = list(moreLikeThis_search_result)
    elif len(top_score_texts) == 1:
        moreLikeThis_search_result = rmn_speeches.aggregate(
            [
                {
                    "$search": {
                        "index": "russell_m_nelson_search",
                        "compound": {
                            "must": [
                                {
                                    "moreLikeThis": {
                                        "like": {
                                            "text": [
                                                top_score_texts[0]["text"],
                                            ]
                                        }
                                    }
                                }
                            ],
                            "mustNot": [
                                {
                                    "equals": {
                                        "path": "_id",
                                        "value": top_score_texts[0]["_id"],
                                    }
                                },
                            ],
                        },
                    }
                },
                {"$limit": top_k},
                {
                    "$project": {
                        "_id": 1,
                        "author": 1,
                        "title": 1,
                        "month": 1,
                        "year": 1,
                        "text": 1,
                        "score": {"$meta": "searchScore"},
                        # "scoreDetails": {"$meta": "searchScoreDetails"},
                    }
                },
            ]
        )
        moreLikeThis_search_result = list(moreLikeThis_search_result)
    else:
        moreLikeThis_search_result = []

    all_search_results = []
    all_search_results.append(text_search_result)
    all_search_results.append(phrase_search_result)
    all_search_results.append(moreLikeThis_search_result)

    for l in all_search_results:
        for d in l:
            del d["_id"]

    return all_search_results


# Below based on hormozi gpt
def get_embeddings_openai(text):
    try:
        response = openai.Embedding.create(input=text, model="text-embedding-ada-002")
        response = response["data"]
        return [x["embedding"] for x in response]
    except Exception as e:
        print(f"Error in get_embeddings_openai: {e}")
        raise


def pinecone_semantic_search(query, index, **kwargs):
    try:
        xq = get_embeddings_openai(query)

        xr = index.query(
            vector=xq[0],
            top_k=kwargs.get("top_k", 1),
            include_metadata=kwargs.get("include_metadata", True),
        )

        if xr.error:
            print(f"Invalid response: {xr}")
            raise Exception(f"Query failed: {xr.error}")

        title = [r["metadata"]["title"] for r in xr["matches"]]
        year = [r["metadata"]["year"] for r in xr["matches"]]
        month = [r["metadata"]["month"] for r in xr["matches"]]
        author = [r["metadata"]["author"] for r in xr["matches"]]
        transcripts = [r["metadata"]["text"] for r in xr["matches"]]

        sr_list = list(zip(title, author, month, year, transcripts))

        search_results = []
        for sr in sr_list:
            search_results.append(
                {
                    "title": sr[0],
                    "author": sr[1],
                    "month": sr[2],
                    "year": int(sr[3]),
                    "text": sr[4],
                }
            )

        return search_results

    except Exception as e:
        print(f"Error in semantic_search: {e}")
        raise
