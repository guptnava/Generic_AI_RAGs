from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import os
import pickle
from dotenv import load_dotenv

load_dotenv()


# Oracle DB connection setup
db_user = os.getenv("DB_USER", "your_user")
db_password = os.getenv("DB_PASSWORD", "your_pass")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE", "orclpdb1")

db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
print("db_uri====", db_uri)


engine = create_engine(db_uri)


# Define your SQL examples
sql_examples = [
    {
        "input": "Get total sales per region",
        "sql": "SELECT region, SUM(total_amount) FROM sales GROUP BY region"
    },
    {
        "input": "Show total revenue for customer 101 in 2023",
        "sql": "SELECT SUM(total_amount) FROM sales WHERE customer_id = 101 AND sale_date BETWEEN TO_DATE('2023-01-01', 'YYYY-MM-DD') AND TO_DATE('2023-12-31', 'YYYY-MM-DD')"
    },
    {
        "input": "List all sales in January 2024",
        "sql": "SELECT * FROM sales WHERE sale_date BETWEEN TO_DATE('2024-01-01', 'YYYY-MM-DD') AND TO_DATE('2024-01-31', 'YYYY-MM-DD')"
    }
]

# Load model from your local folder
embedder = SentenceTransformer(os.getenv('LOCAL_EMBED_MODEL'))



# Insert data
with engine.begin() as conn:  # `begin()` handles transactions cleanly
    for ex in sql_examples:
        embedding_vector = embedder.encode(ex["input"])
        embedding_blob = pickle.dumps(embedding_vector)
        conn.execute(
            text("""
                INSERT INTO sql_prompt_examples_embedded (example_input, example_sql, embedding)
                VALUES (:inp, :sql, :emb)
            """),
            {"inp": ex["input"], "sql": ex["sql"], "emb": embedding_blob}
        )

