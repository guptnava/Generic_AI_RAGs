from flask import Flask, request, jsonify, Response, stream_with_context
from langchain_community.llms import Ollama
from sqlalchemy import create_engine, text
import os
import datetime
import decimal
import json
import hashlib
import diskcache as dc  # ✅ Added for caching

app = Flask(__name__)

# Oracle DB connection setup
db_user = os.getenv("DB_USER", "your_user")
db_password = os.getenv("DB_PASSWORD", "your_pass")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE", "orclpdb1")

db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
print("db_uri====", db_uri)

engine = create_engine(db_uri)

# Initialize persistent cache
cache = dc.Cache("./query_cache")  # Folder-based cache

BASE_INSTRUCTIONS = """
You are an expert Oracle SQL assistant.

### Important:
Only generate the SQL query for the last Input provided.
Do NOT generate SQL for the example Inputs.

### Instructions:
- Use only the 'sales' table with these columns:
  sale_id, customer_id, product_id, sale_date, quantity, unit_price, total_amount, region
- Use Oracle SQL syntax.
- Do NOT use JOINs or subqueries.
- Do NOT use table aliases.
- Do NOT use LIMIT; use ROWNUM if needed.
- Do NOT use column aliases.
- Do NOT end your SQL with a semicolon.
- Use simple SELECT, WHERE, GROUP BY, ORDER BY clauses only.
- Only include GROUP BY if there are non-aggregated columns in SELECT.

### Examples:
"""

def fetch_examples_from_db():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT example_input, example_output FROM sql_prompt_examples ORDER BY id"))
        return result.fetchall()

def build_prompt(user_input):
    examples = fetch_examples_from_db()
    example_text = ""
    for inp, outp in examples:
        example_text += f"Input: {inp}\n\nOutput:\n{outp}\n\n---\n\n"
    return f"""{BASE_INSTRUCTIONS}{example_text}Only output the SQL for this Input:\n\nInput: {user_input}\n\nOutput:\n"""

def serialize_row(row, columns):
    def serialize_value(val):
        if isinstance(val, (datetime.date, datetime.datetime)):
            return val.isoformat()
        elif isinstance(val, decimal.Decimal):
            return float(val)
        return val
    return {col: serialize_value(val) for col, val in zip(columns, row)}

def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    user_input = data.get("prompt")
    model_name = data.get("model", "llama3.2:1b")

    if not user_input:
        return jsonify({"error": "Missing prompt"}), 400

    prompt = build_prompt(user_input)
    print("Prompt sent to LLM:\n", prompt)

    prompt_hash = hash_prompt(prompt)

    if prompt_hash in cache:
        sql_query = cache[prompt_hash]["sql"]
        cached_result = cache[prompt_hash]["results"]
        print("✅ Using cached SQL and results.")
        def stream_cached():
            for row in cached_result:
                yield json.dumps(row) + "\n"
        return Response(stream_with_context(stream_cached()), content_type="application/x-ndjson")

    # Run LLM to get SQL
    llm = Ollama(
        model=model_name,
        temperature=0.0,
        top_k=40,
        top_p=0.9
    )

    try:
        sql_query = llm(prompt).strip()
        print("Generated SQL:\n", sql_query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Run and stream + cache results
    def stream_and_cache():
        results_to_cache = []
        try:
            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql_query))
                columns = result.keys()
                for row in result:
                    row_dict = serialize_row(row, columns)
                    results_to_cache.append(row_dict)
                    yield json.dumps(row_dict) + "\n"

            # Store SQL and full result
            cache[prompt_hash] = {
                "sql": sql_query,
                "results": results_to_cache
            }

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return Response(stream_with_context(stream_and_cache()), content_type="application/x-ndjson")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/cache-info", methods=["GET"])
def cache_info():
    info = {
        "size": cache.volume(),  # in bytes
        "count": len(cache),
        "hits": cache.stats().get("hits", 0),
        "misses": cache.stats().get("misses", 0),
        "disk_usage_mb": round(cache.volume() / (1024 * 1024), 2)
    }
    return jsonify(info)

@app.route("/clear-cache", methods=["POST"])
def clear_cache():
    cache.clear()
    return jsonify({"status": "cache cleared", "count": len(cache)})



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
