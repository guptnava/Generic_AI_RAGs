"""
app_oracle_ndjson_named_params.py

Flask service:
- Matches SQL templates in Oracle using embeddings
- Allows user queries to provide parameters in {param=value} format
- Automatically maps parameters to SQL placeholders
- Streams results in x-ndjson format

Requirements:
pip install flask sentence-transformers numpy oracledb
Set Oracle environment variables:
export ORACLE_USER=...
export ORACLE_PASS=...
export ORACLE_DSN=host:port/service_name
"""

import os
import json
import re
import numpy as np
from flask import Flask, request, Response
from sentence_transformers import SentenceTransformer
import oracledb

###############################################################################
# 0) Config
###############################################################################

ORACLE_USER = os.environ.get("DB_USER", "user")
ORACLE_PASS = os.environ.get("DB_PASSWORD", "pass")
ORACLE_HOST  = os.environ.get("DB_HOST", "localhost")
ORACLE_PORT = os.environ.get("DB_PASS", "1521")
ORACLE_SERVICE  = os.environ.get("DB_SERVICE", "orcl")


EMBEDDER_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "/Users/naveengupta/veda-chatbot/api/local_all-MiniLM-L6-v2")
SIMILARITY_THRESHOLD = 0.52
DEFAULT_LIMIT = 10

###############################################################################
# 1) Oracle connection
###############################################################################

def get_conn():
    return oracledb.connect(user=ORACLE_USER, password=ORACLE_PASS, dsn=f"{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}")

###############################################################################
# Load Templates + Embeddings
###############################################################################
print("Loading embedder...")
EMBEDDER = SentenceTransformer(EMBEDDER_MODEL)

def load_templates():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, intent_text, sql_template, embedding FROM query_templates")
    templates = []
    for row in cur:
        id_, name, intent_text, sql_template, embedding_blob = row
        
        # Convert CLOB -> str
        sql_text = sql_template.read() if hasattr(sql_template, "read") else sql_template

        # Convert BLOB -> numpy array
        emb = None
        if embedding_blob is not None:
            emb_bytes = embedding_blob.read()
            emb = np.frombuffer(emb_bytes, dtype=np.float32)

        templates.append({
            "id": id_,
            "name": name,
            "intent_text": intent_text,
            "sql": sql_text,   # use str, not LOB
            "embedding": emb
        })

    cur.close()
    conn.close()
    return templates

TEMPLATES = load_templates()
TEMPLATE_EMBS = np.array([t["embedding"] for t in TEMPLATES])

def retrieve_best_template(query: str):
    q_emb = EMBEDDER.encode([query], normalize_embeddings=True)[0]
    sims = TEMPLATE_EMBS @ q_emb
    ranked = sorted(list(enumerate(sims.tolist())), key=lambda x: x[1], reverse=True)
    best_idx, best_sim = ranked[0]
    return TEMPLATES[best_idx], best_sim, ranked

###############################################################################
# Named Parameter Extraction
###############################################################################
def extract_named_parameters(user_query: str) -> dict:
    """
    Extract parameters in the format {param=value} from user query.
    Returns a dict of param_name -> value
    """
    params = {}
    matches = re.findall(r"\{(.*?)=(.*?)\}", user_query)
    for name, value in matches:
        name = name.strip()
        value = value.strip()
        # Convert numeric if possible
        if value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass
        params[name] = value
    return params

import re

def inject_named_parameters(sql_template: str, param_dict: dict) -> str:
    """
    Replace {param_name} in SQL template with :param_name bind variables.
    Case-insensitive for parameter names.
    """
    new_sql = sql_template

    # Build lowercase dict for matching
    lower_param_dict = {k.lower(): v for k, v in param_dict.items()}

    # Find all placeholders like {param}
    placeholders = re.findall(r"\{(.*?)\}", sql_template)

    for ph in placeholders:
        key = ph.lower()
        if key not in lower_param_dict:
            raise ValueError(f"Missing value for parameter: {ph}")
        # Replace exactly as it appears in the template with the bind variable
        new_sql = new_sql.replace(f"{{{ph}}}", f":{key}")

    return new_sql, lower_param_dict


###############################################################################
# Flask App
###############################################################################
app = Flask(__name__)

@app.route("/query", methods=["POST"])
def query():
    user_query = request.json.get("prompt", "").strip()
    if not user_query:
        return Response(json.dumps({"matched": False, "error": "missing query"}) + "\n",
                        mimetype="application/x-ndjson")

    template, sim, ranked = retrieve_best_template(user_query)
    #Fallback message - user can use it like help or ?
    if sim < SIMILARITY_THRESHOLD:
        suggestions = [TEMPLATES[i]["intent_text"] for i, _ in ranked[:3]]

        def fallback():
            for i, s in ranked[:3]:
                template_sql = TEMPLATES[i]["sql"]
                # Extract expected parameters from template
                placeholders = re.findall(r"\{(.*?)\}", template_sql)
                yield json.dumps({
                    "suggestion": TEMPLATES[i]["intent_text"],
                    "parameters": placeholders  # just the names, not values
                }) + "\n"

        return Response(fallback(), mimetype="application/x-ndjson")



    try:
        param_dict = extract_named_parameters(user_query)
        # new_sql = inject_named_parameters(template["sql"], param_dict)
        new_sql, param_dict = inject_named_parameters(template["sql"], param_dict)
        print("new_Sql========", new_sql)
    except ValueError as e:
        return Response(json.dumps({"matched": False, "error": str(e)}) + "\n",
                        mimetype="application/x-ndjson")

    def generate():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(new_sql, param_dict)
        cols = [d[0] for d in cur.description]
        # meta = {
        #     "matched": True,
        #     "similarity": round(sim,3),
        #     "template": template["name"],
        #     "params": param_dict,
        #     "columns": cols
        # }
        # yield json.dumps(meta) + "\n"
        for row in cur:
            yield json.dumps(dict(zip(cols, row))) + "\n"
        cur.close()
        conn.close()

    return Response(generate(), mimetype="application/x-ndjson")

###############################################################################
# Run App
###############################################################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
