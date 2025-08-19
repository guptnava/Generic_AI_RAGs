import os
import oracledb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import json

# Config
ORACLE_DSN = os.getenv("ORACLE_DSN")
ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
TARGET_SCHEMA = os.getenv("TARGET_SCHEMA")
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "sbert").lower()
LOCAL_MODEL_PATH = os.getenv('LOCAL_EMBED_MODEL')

# Embedding loader
def get_embedder():
    if EMBED_BACKEND == "sbert":
        return SentenceTransformer(LOCAL_MODEL_PATH)
    else:
        raise ValueError("Unsupported EMBED_BACKEND. Only 'sbert' is configured for local use.")

# Connect to Oracle
conn = oracledb.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)

# Load embedding model
embed_model = get_embedder()

def fetch_schema_metadata():
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT table_name, column_name, data_type, data_length, nullable
        FROM all_tab_columns
        WHERE owner = '{TARGET_SCHEMA}'
        ORDER BY table_name, column_id
    """)
    return cursor.fetchall()

def create_embedding(text):
    return embed_model.encode(text).tolist()

def store_embeddings(table_name, column_name, embedding):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO RAG_CHUNKS (TABLE_NAME, COLUMN_NAME, EMBEDDING)
        VALUES (:1, :2, :3)
    """, (table_name, column_name, json.dumps(embedding)))
    conn.commit()

# Main process
metadata = fetch_schema_metadata()
for table_name, column_name, data_type, data_length, nullable in tqdm(metadata):
    doc_text = f"Table: {table_name}, Column: {column_name}, Type: {data_type}({data_length}), Nullable: {nullable}"
    embedding = create_embedding(doc_text)
    store_embeddings(table_name, column_name, embedding)

conn.close()
print("✅ Embeddings generated and stored in Oracle.")
