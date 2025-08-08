from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine

from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.settings import Settings

load_dotenv()

# Flask app
app = Flask(__name__)

# Oracle DB connection
db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_SERVICE')}"
engine = create_engine(db_uri)
sql_database = SQLDatabase(engine, include_tables=["employees", "sales"])

print(db_uri)

# Set global settings
Settings.llm = Ollama(model="llama3.2:1b",temperature=0.0,
                        top_k=1,
                        repeat_penalty=1.1,
                        top_p=0.8,
                        num_predict=256
                        # max_tokens=300,
                        #stop=["\n\n"]
                        )
Settings.embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    try:
        # Oracle-friendly prompt
        oracle_prompt = f"You are an Oracle SQL expert. Use WHERE ROWNUM <= N instead of FETCH.\n{prompt}"

        # Query engine
        query_engine = NLSQLTableQueryEngine(sql_database=sql_database)
        response = query_engine.query(oracle_prompt)

        print("Generated SQL:", response.metadata.get("sql_query", ""))

        return jsonify({
            "response": str(response),
            "sql": response.metadata.get("sql_query", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5003)
