#!/usr/bin/env python3
"""
Flask RAG -> Ollama SQL generator & executor (streams x-ndjson results)
Supports Oracle 12c (embedding_json + Python cosine) and Oracle 23c (native VECTOR search).

Environment variables (use .env or export):
  ORACLE_USER
  ORACLE_PASSWORD
  ORACLE_HOST (optional, for easy connect)
  ORACLE_PORT (optional)
  ORACLE_SERVICE (optional)
  ORACLE_DSN (optional; if provided used as-is)
  TARGET_SCHEMA (owner of RAG_DOCUMENTS/RAG_CHUNKS)
  LOCAL_EMBED_MODEL (path to local sentence-transformers model)
  TOP_K (optional, default 5)
  OLLAMA_BIN (optional; default 'ollama')
"""

import os
import json
import subprocess
import math
from typing import List, Tuple, Iterator

from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv
import oracledb
import numpy as np
from sentence_transformers import SentenceTransformer

load_dotenv()

# -------------------------
# Config
# -------------------------
ORACLE_DSN = os.getenv("ORACLE_DSN")  # if set, used directly
ORACLE_USER = os.getenv("DB_USER")
ORACLE_PASSWORD = os.getenv("DB_PASSWORD")
ORACLE_HOST = os.getenv("DB_HOST", "localhost")
ORACLE_PORT = os.getenv("DB_PORT", "1521")
ORACLE_SERVICE = os.getenv("DB_SERVICE", "XEPDB1")
TARGET_SCHEMA = (os.getenv("TARGET_SCHEMA") or ORACLE_USER or "").upper()

LOCAL_EMBED_MODEL = os.getenv(
    "LOCAL_EMBED_MODEL",
    "/Users/naveengupta/veda-chatbot/api/local_all-MiniLM-L6-v2",
)
TOP_K = int(os.getenv("TOP_K", "5"))
OLLAMA_BIN = os.getenv("OLLAMA_BIN", "ollama")

# Safety: allowed SQL start tokens (read-only)
ALLOWED_SQL_PREFIXES = ("SELECT", "WITH", "WITH RECURSIVE")

# -------------------------
# Initialize models
# -------------------------
embedder = SentenceTransformer(LOCAL_EMBED_MODEL)

# -------------------------
# Helper: DB connection
# -------------------------
def get_db_conn():
    """
    Returns an oracledb connection.
    If ORACLE_DSN provided, use it. Otherwise use easy connect from host/service.
    """
    if ORACLE_DSN:
        dsn = ORACLE_DSN
    else:
        dsn = f"{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}"
        
        print("dsn=", dsn)
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


# -------------------------
# Detect vector support & schema shape
# -------------------------
def detect_vector_support_and_columns(conn) -> Tuple[bool, bool]:
    """
    Returns (has_vector_column, has_embedding_json_column)
    - has_vector_column: RAG_CHUNKS has EMBEDDING column of VECTOR type (Oracle 23ai)
    - has_embedding_json_column: RAG_CHUNKS has EMBEDDING_JSON column (fallback)
    """
    cur = conn.cursor()
    print("inside detect vector or json")
    try:
        cur.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :owner AND TABLE_NAME = 'RAG_CHUNKS'
            """
            , {"owner": TARGET_SCHEMA}
        )
        cols = {r[0].upper(): r[1].upper() for r in cur.fetchall()}
        has_vector = ("EMBEDDING" in cols) and ("VECTOR" in cols.get("EMBEDDING", ""))
        has_json = "EMBEDDING_JSON" in cols
        return has_vector, has_json
    finally:
        cur.close()


# -------------------------
# Utility: cosine similarity (batched)
# -------------------------
def top_k_similar_python(query_vec: np.ndarray, rows_iter: Iterator[Tuple[str, str]], k: int) -> List[str]:
    """
    rows_iter yields (content, embedding_json) where embedding_json is JSON array (string) or python list.
    Returns top-k content by cosine similarity (descending).
    This processes rows in streaming/batched fashion to avoid huge mem.
    """
    # We keep a small heap of best (score, content)
    import heapq

    heap = []  # min-heap of (score, content), size <= k

    qnorm = np.linalg.norm(query_vec) + 1e-12

    for content, emb_val in rows_iter:
        if emb_val is None:
            continue
        if isinstance(emb_val, str):
            try:
                v = np.array(json.loads(emb_val), dtype=float)
            except Exception:
                continue
        else:
            v = np.array(emb_val, dtype=float)

        if v.size == 0:
            continue
        score = float(np.dot(query_vec, v) / (qnorm * (np.linalg.norm(v) + 1e-12)))

        if len(heap) < k:
            heapq.heappush(heap, (score, content))
        else:
            # pushpop keeps heap min at top
            if score > heap[0][0]:
                heapq.heapreplace(heap, (score, content))

    # Return contents sorted by score desc
    heap.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in heap]


# -------------------------
# Retrieval: adaptive for 23c vs 12c
# -------------------------
def retrieve_context(user_input: str, top_k: int = TOP_K) -> List[str]:
    """
    Encodes user_input, then either:
      - uses DB native vector search if EMBEDDING VECTOR exists, or
      - fetches EMBEDDING_JSON and computes cosine in Python.
    Returns list of top-k CONTENT strings.
    """
    qvec = embedder.encode([user_input])[0]
    conn = get_db_conn()
    try:
        has_vector, has_json = detect_vector_support_and_columns(conn)
        print(has_vector)
        print(has_json)

        cur = conn.cursor()
        # Case A: DB vector support (try DB-side search)
        if has_vector:
            # Try a query that uses the vector operator; syntax may vary by Oracle version/config.
            # We'll try the "<=>" operator first, and fall back to VECTOR_DISTANCE() syntax if it errors.
            try:
                sql = "SELECT CONTENT FROM RAG_CHUNKS ORDER BY EMBEDDING <=> :vec DESC FETCH FIRST :k ROWS ONLY"
                cur.execute(sql, {"vec": qvec.tolist(), "k": top_k})
                rows = cur.fetchall()
                return [r[0] for r in rows]
            except Exception:
                # fallback attempt with VECTOR_DISTANCE
                try:
                    sql2 = "SELECT CONTENT FROM RAG_CHUNKS ORDER BY VECTOR_DISTANCE(EMBEDDING, :vec) USING COSINE FETCH FIRST :k ROWS ONLY"
                    cur.execute(sql2, {"vec": qvec.tolist(), "k": top_k})
                    rows = cur.fetchall()
                    return [r[0] for r in rows]
                except Exception:
                    # final fallback -> fetch embeddings and compute locally
                    pass

       # Case B: Python-side similarity using EMBEDDING_JSON (or any raw embedding storage)
       # Stream rows to avoid loading everything
        if has_json:
            cur.execute("SELECT CONTENT, EMBEDDING_JSON FROM RAG_CHUNKS")
        else:
            # fallback - selecting EMBEDDING_JSON if EMBEDDING not available
            cur.execute("SELECT CONTENT, EMBEDDING_JSON FROM RAG_CHUNKS")

        def safe_load_embedding(emb_val):
            """Convert Oracle CLOB or string to list of floats."""
            if emb_val is None:
                return None
            # If it's a CLOB, convert to string
            if hasattr(emb_val, "read"):
                emb_val = emb_val.read()
            # Ensure string
            if not isinstance(emb_val, str):
                emb_val = str(emb_val)
            try:
                return np.array(json.loads(emb_val), dtype=float)
            except Exception as e:
                raise ValueError(f"Failed to parse embedding JSON: {e}")
        
        def clob_to_str(val):
            """Convert Oracle CLOB to Python string if needed."""
            if hasattr(val, "read"):
                return val.read()
            return str(val) if val is not None else ""
        
        def rows_iter():
            for content, emb_json in cur:
                content_str = clob_to_str(content)
                emb_vec = safe_load_embedding(emb_json)
                if emb_vec is not None:
                    yield (content_str, emb_vec)

        top_contents = top_k_similar_python(np.array(qvec, dtype=float), rows_iter(), top_k)
        return top_contents

    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


# -------------------------
# Prompt builder
# -------------------------
def build_prompt(user_input: str, context_chunks: List[str]) -> str:
    context_text = "\n\n".join(context_chunks)
    prompt = f"""
You are an expert Oracle SQL generator.

Given ONLY the schema/context below, write ONE syntactically correct Oracle SQL query that answers the request.

STRICT RULES:
1. Use ONLY the tables and columns explicitly mentioned in the schema/context.
2. Never introduce tables, aliases, or columns not in the schema/context.
3. If multiple tables are used, use explicit JOIN ... ON ... syntax, not commas.
4. Every JOIN must have a valid ON condition using real columns from both tables.
5. Fully qualify column names when multiple tables are involved (table.column).
6. No semicolons, no comments, no markdown, no extra text — SQL only.
7. SQL must start with SELECT or WITH.
8. Do not return duplicate rows unless explicitly requested — use DISTINCT if needed.
10.Use Oracle SQL syntax only.
11.Do NOT use LIMIT; use ROWNUM if needed.
12.Do NOT end your SQL with a semicolon.

Schema/context:
{context_text}

User request:
{user_input}

<SQL QUERY ONLY — NO EXTRA TEXT>
"""
    return prompt.strip()





# -------------------------
# SQL generation via Ollama (CLI)
# -------------------------
def generate_sql_ollama(model_name: str, prompt: str, timeout: int = 60) -> str:
    """
    Calls Ollama CLI to generate the SQL. Uses subprocess to call:
      ollama generate <model_name> --prompt "<prompt>"
    Returns the raw generated text (stdout).
    """
    try:
        p = subprocess.run(
            [OLLAMA_BIN, "run", model_name, "--prompt", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        return p.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Ollama failed: {e.stderr.strip()}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Ollama generation timed out")

import requests

def generate_sql_ollama_http(model_name: str, prompt: str, stream: bool = False):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": stream
    }
    with requests.post(url, json=payload, stream=stream) as r:
        if not stream:
            return r.json()["response"]
        else:
            for line in r.iter_lines():
                if line:
                    yield line.decode("utf-8")


# -------------------------
# SQL safety check
# -------------------------
def is_allowed_sql(sql: str) -> bool:
    if not sql:
        return False
    s = sql.strip().upper()
    # allow SELECT or WITH only
    return any(s.startswith(pref) for pref in ALLOWED_SQL_PREFIXES)


# -------------------------
# Execute SQL and stream rows as NDJSON
# -------------------------
def stream_query_results(sql_query: str):
    """
    Generator that executes the SQL and yields NDJSON lines (one JSON object per row).
    Errors are yielded as JSON objects with 'error'.
    """
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql_query)
    except Exception as e:
        # immediate execution error
        yield json.dumps({"error": f"SQL execution error: {str(e)}"}) + "\n"
        cur.close()
        conn.close()
        return

    cols = [d[0] for d in cur.description] if cur.description else []
    try:
        # Fetch rows in a streaming manner (iterator)
        for row in cur:
            obj = dict(zip(cols, row))
            yield json.dumps(obj, default=str) + "\n"
    except Exception as e:
        yield json.dumps({"error": f"Error while streaming results: {str(e)}"}) + "\n"
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


# -------------------------
# Flask app
# -------------------------
app = Flask(__name__)


@app.route("/query", methods=["POST"])
def sqlgen_endpoint():
    payload = request.get_json(force=True)
    user_input = payload.get("prompt")
    model_name = payload.get("model")
    mode = payload.get("mode", "default")

    if not user_input or not model_name:
        return jsonify({"error": "Missing 'user_input' or 'model_name'"}), 400

    # 1) Retrieve context via RAG
    try:
        context_chunks = retrieve_context(user_input, top_k=TOP_K)
    except Exception as e:
        return jsonify({"error": f"RAG retrieval error: {str(e)}"}), 500

    # 2) Build prompt and call model
    prompt = build_prompt(user_input, context_chunks)
    try:
            import re

            sql_fragments = []
            for line in generate_sql_ollama_http(model_name, prompt, stream=True):
                try:
                    data = json.loads(line)
                    if "response" in data:
                        sql_fragments.append(data["response"])
                except json.JSONDecodeError:
                    sql_fragments.append(line)

            sql_text = "".join(sql_fragments)

            # Remove markdown fences or extra labels
            sql_text = re.sub(r"```[\s\S]*?```", "", sql_text)
            sql_text = re.sub(r"(?i)^sql", "", sql_text).strip()

            # Keep only the first SELECT/WITH statement
            match = re.search(r"(SELECT|WITH)\b[\s\S]+", sql_text, re.IGNORECASE)
            if match:
                sql_text = match.group(0).strip()

            print("=== Generated SQL ===")
            print(sql_text)
            print("=====================")
        
    except Exception as e:
        return jsonify({"error": f"Model generation error: {str(e)}"}), 500

    # 3) Ensure model returned only SQL (safety check)
    if not is_allowed_sql(sql_text):
        return jsonify({"error": "Generated SQL not allowed or non-SELECT statement. Aborting."}), 400

    # Print generated SQL server-side for debugging
    print("=== Generated SQL ===")
    print(sql_text)
    print("=====================")

    # 4) Stream back results as x-ndjson
    return Response(stream_query_results(sql_text), mimetype="application/x-ndjson")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=True)
