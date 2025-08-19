import os
import json
import math
from flask import Flask, request, Response, jsonify
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from llama_index import (
    Document,
    GPTVectorStoreIndex,
    LLMPredictor,
    ServiceContext,
    StorageContext,
    load_index_from_storage,
)
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.vector_stores.sql_vector_store import SQLVectorStore

from langchain.llms import Ollama
from sentence_transformers import SentenceTransformer
from llama_index import LangchainEmbedding


# Flask app
app = Flask(__name__)

# Oracle DB config
DATABASE_URL = os.getenv("ORACLE_DB_URL")
if not DATABASE_URL:
    raise RuntimeError("Please set ORACLE_DB_URL environment variable")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Load your local sentence transformer model directly
embedder = SentenceTransformer(os.getenv('LOCAL_EMBED_MODEL'))

# Wrap it for LlamaIndex / Langchain compatibility
embedding_model = LangchainEmbedding(embedder)

# Use Ollama local LLaMA 3.2 1B model
llm = Ollama(
    model="llama3.2:1b",  # your installed local Ollama model
    temperature=0,
    max_tokens=512
)

llm_predictor = LLMPredictor(llm=llm)

service_context = ServiceContext.from_defaults(
    llm_predictor=llm_predictor,
    embed_model=embedding_model,
)

# OracleVectorStore class: store embedding as JSON string (simple approach)
class OracleVectorStore(SQLVectorStore):
    def __init__(self, engine):
        table_name = "DOCUMENT_EMBEDDINGS"
        super().__init__(engine, table_name=table_name)

    def add(self, doc_id: str, embedding: list, text_content: str):
        embedding_json = json.dumps(embedding)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "MERGE INTO DOCUMENT_EMBEDDINGS d "
                    "USING (SELECT :doc_id AS doc_id FROM dual) src "
                    "ON (d.doc_id = src.doc_id) "
                    "WHEN MATCHED THEN UPDATE SET embedding = :embedding, text_content = :text_content "
                    "WHEN NOT MATCHED THEN INSERT (doc_id, embedding, text_content) VALUES (:doc_id, :embedding, :text_content)"
                ),
                {"doc_id": doc_id, "embedding": embedding_json, "text_content": text_content},
            )

    def similarity_search(self, query_embedding, top_k=5):
        # Naive: fetch all embeddings and compute similarity in Python
        with engine.connect() as conn:
            result = conn.execute(text("SELECT doc_id, embedding, text_content FROM DOCUMENT_EMBEDDINGS"))
            rows = result.fetchall()

        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot / (norm_a * norm_b + 1e-10)

        sims = []
        for doc_id, emb_json, text_content in rows:
            emb = json.loads(emb_json)
            score = cosine_sim(query_embedding, emb)
            sims.append((doc_id, text_content, score))

        sims.sort(key=lambda x: x[2], reverse=True)
        return sims[:top_k]

# Instantiate vector store
vector_store = OracleVectorStore(engine=engine)

# Storage context for llama_index
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# Try to load index or create fresh
try:
    index = load_index_from_storage(storage_context, service_context=service_context)
except Exception:
    index = GPTVectorStoreIndex([], service_context=service_context, storage_context=storage_context)

# Web scraper for URL
def scrape_text_from_url(url):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    texts = soup.find_all(text=True)
    visible_texts = filter(tag_visible, texts)
    return "\n".join(t.strip() for t in visible_texts if t.strip())

def tag_visible(element):
    from bs4.element import Comment
    if element.parent.name in ["style", "script", "head", "title", "meta", "[document]"]:
        return False
    if isinstance(element, Comment):
        return False
    return True

def chunk_text(text, max_len=512):
    words = text.split()
    chunks = []
    current_chunk = []
    current_len = 0
    for w in words:
        if current_len + len(w) + 1 > max_len:
            chunks.append(" ".join(current_chunk))
            current_chunk = [w]
            current_len = len(w) + 1
        else:
            current_chunk.append(w)
            current_len += len(w) + 1
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

# Prompt template to feed LLM
prompt_template = """
You are a helpful assistant. Use the following context to answer the question.

Context:
{context}

Question:
{question}

Answer:
"""

# Ingest endpoint
@app.route("/ingest", methods=["POST"])
def ingest():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    try:
        text = scrape_text_from_url(url)
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            doc_id = f"{url}__{i}"
            embedding = embedding_model.get_embedding(chunk)
            vector_store.add(doc_id=doc_id, embedding=embedding, text_content=chunk)
            # Also insert to LlamaIndex
            doc = Document(text=chunk, doc_id=doc_id)
            index.insert(doc)

        index.storage_context.persist()
        return jsonify({"status": "success", "chunks_ingested": len(chunks)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Search endpoint with streaming x-ndjson and prompt template applied
@app.route("/query", methods=["POST"])
def search():
    data = request.json
    query = data.get("query")
    top_k = data.get("top_k", 5)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    # Step 1: Embed the query
    query_embedding = embedding_model.get_embedding(query)

    # Step 2: Use vector store similarity search to get top_k docs
    similar_docs = vector_store.similarity_search(query_embedding, top_k=top_k)

    # Step 3: Prepare the context text from retrieved docs
    context_text = "\n\n".join(doc[1] for doc in similar_docs)

    # Step 4: Format prompt with context and question
    prompt = prompt_template.format(context=context_text, question=query)

    # Step 5: Query LLM with prompt and get response
    response_text = llm(prompt)

    def generate():
        # Streaming or chunked response can be implemented here if Ollama supports it
        yield json.dumps({"result": response_text}) + "\n"

    return Response(generate(), mimetype="application/x-ndjson")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
