from flask import Flask, request, Response, jsonify, stream_with_context
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from langchain_community.llms import Ollama
import requests
import numpy as np
import json
import os
from sqlalchemy import create_engine, text

app = Flask(__name__)

# DB connection
db_user = os.getenv("DB_USER", "your_user")
db_password = os.getenv("DB_PASSWORD", "your_pass")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE", "orclpdb1")

db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
print("db_uri====", db_uri)

engine = create_engine(db_uri)

# Embedding and LLM
embedder = SentenceTransformer(os.getenv('LOCAL_EMBED_MODEL'))
llm = Ollama(model="llama3.2:1b", temperature=0.0)

# Cache mapping in memory
intent_cache = []

def load_intents_from_db():
    global intent_cache
    with engine.connect() as conn:
        result = conn.execute(text("SELECT intent, endpoint, expected_params FROM api_mappings"))
        intent_cache = []
        for row in result:
            intent_cache.append({
                "intent": row[0],
                "endpoint": row[1],
                "expected_params": json.loads(row[2]),
                "embedding": embedder.encode(row[0])
            })

# Reload mappings at startup
load_intents_from_db()

import re

def count_param_hits(prompt, expected_params):
    prompt_lower = prompt.lower()
    return sum(1 for param in expected_params if re.search(param.lower(), prompt_lower))

def find_best_intent(user_query):
    user_vec = embedder.encode(user_query)
    similarities = [
        cosine_similarity([user_vec], [ex["embedding"]])[0][0] for ex in intent_cache
    ]

    print("similarities:", similarities)

    # Take top 3
    top_matches = sorted(
        zip(intent_cache, similarities),
        key=lambda x: x[1],
        reverse=True
    )[:3]

    # Re-rank by how many params are mentioned in prompt
    ranked = sorted(
        top_matches,
        key=lambda x: count_param_hits(user_query, x[0]["expected_params"]),
        reverse=True
    )

    best_match = ranked[0][0]
    print("Chosen match:", best_match["intent"])
    return best_match


def extract_parameters(prompt, expected_params):
    param_str = ", ".join(expected_params)
    
    # dynamically build example JSON
    example_dict = {k: f"<{k}>" for k in expected_params}
    example_json = json.dumps(example_dict, indent=4)

    extraction_prompt = f"""
You are given a user prompt and a list of expected parameters: {param_str}

Extract only those parameters that are actually mentioned in the prompt. Do not guess missing ones.

User Prompt:
\"\"\"{prompt}\"\"\"

Return a valid JSON object with only the mentioned parameters. No code, no explanation.

Example format:
{example_json}
"""


    result = llm(extraction_prompt).strip()
    try:
        if result.startswith("```json"):
            result = result.lstrip("```json").rstrip("```").strip()
        elif result.startswith("```"):
            result = result.lstrip("```").rstrip("```").strip()
        print("LLM result:", result)
        return json.loads(result)
    except Exception as e:
        raise ValueError(f"LLM output could not be parsed as JSON: {e}\nOutput was:\n{result}")

@app.route("/query", methods=["POST"])
def smart_query():
    data = request.get_json()
    user_prompt = data.get("prompt")
    model = data.get("model", "llama3.2:1b")

    # Run LLM to get SQL
    llm = Ollama(
        model=model,
        temperature=0.0,
        top_k=40,
        top_p=0.9
    )
    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400

    matched = find_best_intent(user_prompt)
    expected_params = matched["expected_params"]
   
    print("expected params:", expected_params)

    try:
        extracted_params = extract_parameters(user_prompt, expected_params)
    except Exception as e:
        return jsonify({"error": "Parameter extraction failed", "details": str(e)}), 500

    try:
        def stream():
            with requests.post(f"http://localhost:5005{matched['endpoint']}", json=extracted_params, stream=True) as r:
                for line in r.iter_lines():
                    if line:
                        yield line.decode() + "\n"
        return Response(stream_with_context(stream()), content_type="application/x-ndjson")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reload-intents", methods=["POST"])
def reload():
    load_intents_from_db()
    return jsonify({"status": "reloaded", "total": len(intent_cache)})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006)
