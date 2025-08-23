from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import re
import time
import diskcache
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_community.llms import Ollama

from langchain_core.prompts import PromptTemplate

import time
from sqlalchemy import create_engine
from flask import Response, stream_with_context

import json

# Load .env for DB credentials
load_dotenv()

app = Flask(__name__)

# Cache setup with expiration (30 minutes)
CACHE_EXPIRATION_SECONDS = 1800
cache = diskcache.Cache("./llm_cache")

# DB Setup
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE")

db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
print("db_uri====", db_uri)

engine = create_engine(
    db_uri,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    echo_pool=True  # Enable pool logging
)

# Pass engine to SQLDatabase; specify tables for safety
db = SQLDatabase(engine, include_tables=['sales', 'employees'])
#db = SQLDatabase.from_uri(db_uri, include_tables=['sales', 'employees'])

@app.route("/query", methods=["POST"])
def query_db():
    data = request.get_json()
    prompt = data.get("prompt")
    model = data.get("model", "llama3.2:1b")  # fallback model if not sent

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    def generate():
        try:
            # Dynamically instantiate LLM and chain
            llm = Ollama(model=model,
                        temperature=0.0,
                        top_k=40,
                        repeat_penalty=1.1,
                        top_p=0.8,
                        num_predict=256
                        # max_tokens=300,
                        #stop=["\n\n"]
                )
            db_chain = create_sql_query_chain(llm, db)

            # If db_chain.invoke is not streamable, yield as one line
            result = db_chain.invoke({"question": prompt})
            yield json.dumps({"response": result, "cached": False}) + "\n"

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return Response(stream_with_context(generate()), content_type="application/x-ndjson")

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    cache.clear()
    return jsonify({"status": "Cache cleared"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
