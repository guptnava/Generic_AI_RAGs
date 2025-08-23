"""
app_oracle.py

Flask service that:
- Embeds NL queries with all-MiniLM-L6-v2
- Retrieves closest SQL template (semantic similarity)
- Extracts parameters (regex & rules)
- Executes queries on an Oracle DB
- Returns results as x-ndjson stream

Run:
  pip install flask sentence-transformers numpy oracledb

Set Oracle env vars:
  export ORACLE_USER=...
  export ORACLE_PASS=...
  export ORACLE_DSN=host:port/service_name

Run app:
  python app_oracle.py

Query:
  curl -X POST http://127.0.0.1:5011/query \
       -H "Content-Type: application/json" \
       -H "Accept: application/x-ndjson" \
       -d '{"prompt":"top 3 customers by revenue in 2024"}'
"""

import os
import re
import json
import datetime as dt
from typing import Dict, Any, List, Tuple

import numpy as np
from flask import Flask, request, Response, jsonify
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
# 2) Templates (Oracle SQL syntax)
###############################################################################

TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "top_customers_by_revenue_year",
        "intent_text": "Get the top N customers by total revenue in a given year",
        "sql": """
            SELECT customer_id, SUM(total_amount) AS total_revenue
            FROM sales
            WHERE TO_CHAR(sale_date, 'YYYY') = :year
            GROUP BY customer_id
            ORDER BY total_revenue DESC
            FETCH FIRST :limit ROWS ONLY
        """,
        "required": ["year"],
        "optional": ["limit"],
        "defaults": {"limit": DEFAULT_LIMIT}
    },
    {
        "name": "sales_by_region_year",
        "intent_text": "Show total sales for each region in a given year",
        "sql": """
            SELECT region, SUM(total_amount) AS total_revenue
            FROM sales
            WHERE TO_CHAR(sale_date, 'YYYY') = :year
            GROUP BY region
            ORDER BY total_revenue DESC
        """,
        "required": ["year"],
        "optional": []
    },
    {
        "name": "product_sales_between_dates",
        "intent_text": "Show top products by revenue between a start and end date",
        "sql": """
            SELECT product_id, SUM(total_amount) AS total_revenue
            FROM sales
            WHERE sale_date BETWEEN TO_DATE(:start_date, 'YYYY-MM-DD') AND TO_DATE(:end_date, 'YYYY-MM-DD')
            GROUP BY product_id
            ORDER BY total_revenue DESC
            FETCH FIRST :limit ROWS ONLY
        """,
        "required": ["start_date", "end_date"],
        "optional": ["limit"],
        "defaults": {"limit": DEFAULT_LIMIT}
    },
    {
        "name": "daily_sales_on_date",
        "intent_text": "Show total revenue on a specific date",
        "sql": """
            SELECT sale_date, SUM(total_amount) AS total_revenue
            FROM sales
            WHERE sale_date = TO_DATE(:date, 'YYYY-MM-DD')
            GROUP BY sale_date
        """,
        "required": ["date"],
        "optional": []
    },
]

###############################################################################
# 3) Embeddings + retrieval
###############################################################################

print("Loading embedder:", EMBEDDER_MODEL)
EMBEDDER = SentenceTransformer(EMBEDDER_MODEL)

TEMPLATE_SENTENCES = [t["intent_text"] for t in TEMPLATES]
TEMPLATE_EMBS = EMBEDDER.encode(TEMPLATE_SENTENCES, normalize_embeddings=True)

def retrieve_best_template(query: str):
    q_emb = EMBEDDER.encode([query], normalize_embeddings=True)[0]
    sims = TEMPLATE_EMBS @ q_emb
    ranked = sorted(list(enumerate(sims.tolist())), key=lambda x: x[1], reverse=True)
    best_idx, best_sim = ranked[0]
    return TEMPLATES[best_idx], best_sim, ranked

###############################################################################
# 4) Param extraction
###############################################################################

YEAR_RE = re.compile(r"\b(20\d{2})\b")
TOP_N_RE = re.compile(r"\btop\s+(\d+)", re.IGNORECASE)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
BETWEEN_RE = re.compile(
    r"(?:between|from)\s+(20\d{2}-\d{2}-\d{2})\s+(?:and|to)\s+(20\d{2}-\d{2}-\d{2})",
    re.IGNORECASE
)

def extract_params(query: str) -> Dict[str, Any]:
    q = query.lower()
    today = dt.date.today()
    params = {}

    if "last year" in q:
        params["year"] = str(today.year - 1)
    elif "this year" in q:
        params["year"] = str(today.year)

    my = YEAR_RE.search(q)
    if my:
        params["year"] = my.group(1)

    mtop = TOP_N_RE.search(q)
    if mtop:
        params["limit"] = int(mtop.group(1))

    mbetween = BETWEEN_RE.search(q)
    if mbetween:
        params["start_date"], params["end_date"] = mbetween.groups()

    mdate = DATE_RE.search(q)
    if mdate:
        params["date"] = mdate.group(1)

    return params

def validate_and_fill(template, params):
    missing = [p for p in template["required"] if p not in params]
    filled = dict(params)
    for k, v in template.get("defaults", {}).items():
        filled.setdefault(k, v)
    return len(missing) == 0, missing, filled

###############################################################################
# 5) Flask app
###############################################################################

app = Flask(__name__)

@app.route("/query", methods=["POST"])
def query():
    print("inside the call")
    user_query = request.json.get("prompt", "").strip()
    if not user_query:
        return Response(json.dumps({"matched": False, "error": "missing query"}) + "\n",
                        mimetype="application/x-ndjson")

    template, sim, ranked = retrieve_best_template(user_query)
    print("template=====", template)
    params = extract_params(user_query)
    ok, missing, full_params = validate_and_fill(template, params)
    if sim < SIMILARITY_THRESHOLD or not ok:
        suggestions = [TEMPLATES[i]["intent_text"] for i, _ in ranked[:100]]

        def generate():
            # metadata line first
            # meta = {
            #     "matched": False,
            #     "similarity": round(sim, 3),
            #     "missing_params": missing,
            #     "suggestion_count": len(suggestions)
            # }
            # yield json.dumps(meta) + "\n"

            # one line per suggestion
            for s in suggestions:
                yield json.dumps({"suggestion": s}) + "\n"

        return Response(generate(), mimetype="application/x-ndjson")


    # success path — stream rows
    def generate():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(template["sql"], full_params)
        cols = [d[0] for d in cur.description]
        # emit metadata first

        print("matched", "True")
        print("similarity", round(sim, 3))
        print("template", template["name"])
        print("params", full_params)
        print("columns", cols)

        for row in cur:
            obj = dict(zip(cols, row))
            yield json.dumps(obj) + "\n"
        cur.close()
        conn.close()

    return Response(generate(), mimetype="application/x-ndjson")

###############################################################################

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, debug=True)
