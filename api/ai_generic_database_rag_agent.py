from flask import Flask, request, Response, jsonify
import oracledb
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import subprocess

# ---- CONFIG ----
ORACLE_DSN = os.getenv("ORACLE_DSN", "riskintegov2/riskintegov2@localhost:1521/riskintegov2")
LOCAL_EMBED_MODEL = "/Users/naveengupta/veda-chatbot/api/local_all-MiniLM-L6-v2"

# Load embedding model once
embedder = SentenceTransformer(LOCAL_EMBED_MODEL)

# ---- Oracle connection ----
def get_db_conn():
    return oracledb.connect(ORACLE_DSN)

# ---- Check if vector support exists ----
def has_vector_support(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT VECTOR_COUNT FROM USER_VECTORS WHERE ROWNUM = 1")  # dummy check
        cur.close()
        return True
    except Exception:
        return False

# ---- RAG retrieval ----
def retrieve_context(user_input, top_k=5):
    emb = embedder.encode([user_input])[0]
    conn = get_db_conn()
    use_db_vector = has_vector_support(conn)
    cur = conn.cursor()

    if use_db_vector:
        sql = """
        SELECT CONTENT
        FROM RAG_CHUNKS
        ORDER BY EMBEDDING <=> :vec DESC
        FETCH FIRST :k ROWS ONLY
        """
        cur.execute(sql, vec=emb.tolist(), k=top_k)
        rows = cur.fetchall()
        context = [r[0] for r in rows]
    else:
        cur.execute("SELECT CONTENT, EMBEDDING FROM RAG_CHUNKS")
        rows = cur.fetchall()
        scored = []
        for content, db_emb in rows:
            db_vec = np.array(json.loads(db_emb)) if isinstance(db_emb, str) else np.array(db_emb)
            score = np.dot(emb, db_vec) / (np.linalg.norm(emb) * np.linalg.norm(db_vec))
            scored.append((score, content))
        scored.sort(reverse=True, key=lambda x: x[0])
        context = [c for _, c in scored[:top_k]]

    cur.close()
    conn.close()
    return context

# ---- Prompt builder ----
def build_prompt(user_input, context):
    return f"""
You are an expert Oracle SQL generator. 
Using the following database schema context, create the most accurate SQL query possible to answer the user request.

Context:
{context}

User request:
{user_input}

Return only the SQL query without explanations.
""".strip()

# ---- Ollama model SQL generation ----
def generate_sql(model_name, prompt):
    """
    Calls Ollama local model using CLI. 
    Requires 'ollama' to be installed and the model to be available locally.
    """
    try:
        result = subprocess.run(
            ["ollama", "generate", model_name, "--prompt", prompt],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print("Ollama error:", e.stderr)
        return ""

# ---- Execute SQL ----
def execute_sql(sql_query):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(sql_query)
    cols = [d[0] for d in cur.description]
    for row in cur:
        yield json.dumps(dict(zip(cols, row))) + "\n"
    cur.close()
    conn.close()

# ---- Flask App ----
app = Flask(__name__)

@app.route("/query", methods=["POST"])
def sqlgen():
    data = request.json
    user_input = data.get("user_input")
    model_name = data.get("model_name")
    mode = data.get("mode")

    if not user_input or not model_name:
        return jsonify({"error": "Missing required parameters"}), 400

    # Retrieve context
    context_chunks = retrieve_context(user_input)
    context = "\n".join(context_chunks)

    # Build prompt
    prompt = build_prompt(user_input, context)

    # Generate SQL using Ollama
    sql_query = generate_sql(model_name, prompt)
    print("Generated SQL:", sql_query)

    # Execute SQL and stream NDJSON
    def generate():
        for line in execute_sql(sql_query):
            yield line
        yield json.dumps({"_narration": f"The generated SQL was:\n{sql_query}"}) + "\n"

    return Response(generate(), mimetype="application/x-ndjson")

if __name__ == "__main__":
    app.run(port=3000, debug=True)
