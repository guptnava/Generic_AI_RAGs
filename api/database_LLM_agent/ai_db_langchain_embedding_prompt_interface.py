from flask import Flask, request, jsonify, Response, stream_with_context
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
import datetime
import decimal
import json
import pickle

app = Flask(__name__)

# -- Oracle DB connection --
db_user = os.getenv("DB_USER", "your_user")
db_password = os.getenv("DB_PASSWORD", "your_pass")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE", "orclpdb1")

db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
print("db_uri====", db_uri)

engine = create_engine(db_uri)

LOCAL_EMBED_MODEL=os.getenv('LOCAL_EMBED_MODEL')

# -- Load embedder --
embedder = SentenceTransformer(LOCAL_EMBED_MODEL)

# -- Cache examples in memory --
cached_examples = []

def fetch_examples_from_db():
    global cached_examples
    if cached_examples:
        return cached_examples
    with engine.connect() as conn:
        result = conn.execute(text("SELECT example_input, example_sql, embedding FROM sql_prompt_examples_embedded"))
        for row in result:
            cached_examples.append({
                "input": row[0],
                "sql": row[1],
                "embedding": pickle.loads(row[2].read()) if hasattr(row[2], 'read') else pickle.loads(row[2])
            })
    return cached_examples

def clear_example_cache():
    global cached_examples
    cached_examples = []

# -- Prompt template --
prompt_template = PromptTemplate(
    input_variables=["question", "candidate_sql"],
    template="""
You are an expert Oracle SQL assistant.

Given a user question and a candidate SQL query, return **only the final corrected Oracle SQL query** if needed.

- Do not include explanations.
- Do not format the query with markdown.
- Do not use triple backticks.
- Just return the raw SQL.

### User Question:
{question}

### Candidate SQL:
{candidate_sql}

### Final SQL:
"""
)

llm = Ollama(model="llama3.2:1b", temperature=0.0)

def find_best_match(user_query):
    user_vec = embedder.encode(user_query)
    examples = fetch_examples_from_db()
    similarities = [cosine_similarity([user_vec], [ex["embedding"]])[0][0] for ex in examples]
    best_idx = int(np.argmax(similarities))
    return examples[best_idx]

def serialize_row(row, columns):
    def serialize_value(val):
        if isinstance(val, (datetime.date, datetime.datetime)):
            return val.isoformat()
        elif isinstance(val, decimal.Decimal):
            return float(val)
        return val

    return {col: serialize_value(val) for col, val in zip(columns, row)}

# -- Main query route with NDJSON streaming --
@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    user_input = data.get("prompt")
    model = data.get("model", "llama3.2:1b")  # model param kept for API compatibility, but not used here
    
    if not user_input:
        return jsonify({"error": "Missing prompt"}), 400

    best = find_best_match(user_input)
    print("Best match:", best["input"])

    prompt = prompt_template.format(question=user_input, candidate_sql=best["sql"])

    try:
        sql_query = llm(prompt).strip()
        print("Generated SQL:\n", sql_query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    def generate():
        try:
            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql_query))
                columns = result.keys()
                for row in result:
                    yield json.dumps(serialize_row(row, columns)) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e), "sql": sql_query}) + "\n"

    return Response(stream_with_context(generate()), content_type="application/x-ndjson")

# -- Route to clear example cache --
@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    clear_example_cache()
    return jsonify({"message": "Cache cleared"})

# -- Route to get cache info --
@app.route("/cache/info", methods=["GET"])
def cache_info():
    examples = fetch_examples_from_db()
    return jsonify({"cached_examples": len(examples)})

# -- Healthcheck --
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5004)
