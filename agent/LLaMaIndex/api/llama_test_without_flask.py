from llama_index.core import SQLDatabase
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.llms.ollama import Ollama
from llama_index.core.settings import Settings
from sqlalchemy import create_engine

from llama_index.core.embeddings.base import BaseEmbedding

class DummyEmbedding(BaseEmbedding):
    def _get_text_embedding(self, text):
        return [0.0] * 384  # Minimal dummy embedding

engine = create_engine("oracle+oracledb://riskintegov2:riskintegov2@localhost:1521/riskintegov2")

db = SQLDatabase(engine, include_tables=["sales"])

Settings.llm = Ollama(model="llama3.2:1b")
Settings.embed_model = DummyEmbedding()  # Or use a basic dummy or instructor embedding if set up

query_engine = NLSQLTableQueryEngine(sql_database=db)

query = "list all sales"
print("Querying with:", query)
response = query_engine.query(query)

print("SQL:", response.metadata.get("sql_query"))
print("Response:", response)
