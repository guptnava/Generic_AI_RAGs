from flask import Flask, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import os
import time
import diskcache
from sqlalchemy import create_engine, text

import json

import datetime

import decimal  # ✅ Added to handle Decimal types


# Load .env credentials
load_dotenv()

app = Flask(__name__)

# Cache setup (30 min)
CACHE_EXPIRATION_SECONDS = 1800
cache = diskcache.Cache("./llm_cache")

# DB setup
db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/{os.getenv('DB_SERVICE')}"
engine = create_engine(db_uri)



# Utility
def is_safe_sql(sql: str) -> bool:
    return sql.strip().lower().startswith("select")

def log_query(intent, sql, user_agent, client_ip, model):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open("query_log.txt", "a") as f:
        f.write(f"\n---\n[{ts}] IP: {client_ip}, UA: {user_agent}, Model: {model}\nIntent: {intent}\nSQL: {sql}\n")

# Predefined intent-to-SQL map
INTENT_SQL_MAP = {
    "list all employees": "SELECT * FROM employees",
    "list all sales": "SELECT * FROM sales",
    "top 5 sales by amount": "SELECT * FROM sales ORDER BY amount",
    "employee count": "SELECT COUNT(*) AS employee_count FROM employees",
    # Add more intents and safe queries here
}

def detect_intent(prompt: str) -> str:
    prompt_lower = prompt.lower()
    # Simple intent detection by checking if any intent phrase is contained in prompt
    for intent in INTENT_SQL_MAP.keys():
        if intent in prompt_lower:
            return intent
    return None

# ✅ Updated to handle Decimal serialization
def serialize_row(row, columns):
    def serialize_value(val):
        if isinstance(val, (datetime.date, datetime.datetime)):
            return val.isoformat()
        elif isinstance(val, decimal.Decimal):
            return float(val)  # or str(val) if precision must be preserved
        return val

    return {col: serialize_value(val) for col, val in zip(columns, row)}

@app.route("/query", methods=["POST"])
def query_db():
    data = request.get_json()
    prompt = data.get("prompt")
    model = data.get("model", "llama3.2:1b")  # model param kept for API compatibility, but not used here

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    # Session info
    user_agent = request.headers.get('User-Agent', 'unknown')
    client_ip = request.remote_addr or 'unknown'

    # Detect intent
    intent = detect_intent(prompt)
    if not intent:
        return jsonify({"error": "Sorry, I don't understand that query."}), 400

    sql = INTENT_SQL_MAP[intent]

    if not is_safe_sql(sql):
        return jsonify({"error": "Unsafe SQL detected."}), 403

    # # Cache check by intent + model
    # cache_key = f"{model}:{intent}"
    # cached = cache.get(cache_key)
    # if cached:
    #     return jsonify({"response": cached, "cached": True})

    try:


        def generate():
            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql))
                columns = result.keys()
                for row in result:
                    row_dict = serialize_row(row, columns)
                    yield json.dumps(row_dict) + "\n"
                    


        # Cache the full SQL result as text (optional: cache partial or JSON)
        # To cache the streamed result fully, we need to collect it first (here simplified)
        # with engine.connect() as conn:
        #     res = conn.execute(text(sql))
        #     all_rows = [dict(zip(res.keys(), row)) for row in res]

        #cache.set(cache_key, all_rows, expire=CACHE_EXPIRATION_SECONDS)
        log_query(intent, sql, user_agent, client_ip, model)

        # Return streamed CSV response
        return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

    except Exception as e:
        log_query(intent, str(e), user_agent, client_ip, model)
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    cache.clear()
    return jsonify({"message": "Cache cleared"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
