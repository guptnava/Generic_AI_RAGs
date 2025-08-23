import oracledb
import numpy as np
import json
from sentence_transformers import SentenceTransformer

# Oracle connection
conn = oracledb.connect(user="riskintegov2", password="riskintegov2", dsn="localhost:1521/riskintegov2")
cur = conn.cursor()

# Load embedder
model = SentenceTransformer("/Users/naveengupta/veda-chatbot/api/local_all-MiniLM-L6-v2")

# Example templates
templates = [
    {
        "name": "sales_by_region_year",
        "intent_text": "Get sales for a specific region and year with minimum revenue",
        "sql": "SELECT * FROM sales WHERE region={region} AND to_char(date, 'YYYY')={year} AND total_amount >= {min_revenue}",
    },
    {
        "name": "top_customers",
        "intent_text": "Top N customers by total revenue in a given year",
        "sql": "SELECT * FROM (SELECT customer_id, SUM(total_amount) total_revenue FROM sales WHERE to_char(sale_date, 'YYYY')={year} GROUP BY customer_id ORDER BY total_revenue DESC) WHERE ROWNUM <= {limit}"
    }
]

for t in templates:
    emb = model.encode([t["intent_text"]], normalize_embeddings=True)[0].astype(np.float32)
    emb_blob = emb.tobytes()
    # Parameters can be empty or optional
    params_json = None
    cur.execute("""
        INSERT INTO query_templates (name, intent_text, sql_template, embedding, parameters)
        VALUES (:name, :intent_text, :sql_template, :embedding, :parameters)
    """, {
        "name": t["name"],
        "intent_text": t["intent_text"],
        "sql_template": t["sql"],
        "embedding": emb_blob,
        "parameters": params_json
    })

conn.commit()
cur.close()
conn.close()
