# LLaMA Search App with Oracle Vector Storage

This app scrapes a website, chunks the text, creates embeddings with Sentence Transformers, stores embeddings in Oracle DB, builds a LlamaIndex using a LLaMA 3.2 1B model, and allows efficient similarity search with streaming NDJSON responses.

## Setup

1. **Oracle DB**

Run the SQL script to create the required table:

```bash
sqlplus user/password@host:port/service_name @oracle_schema.sql


python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


export ORACLE_DB_URL="oracle+cx_oracle://user:password@host:port/service_name"


Explanation
ingest: Scrapes the website URL text, chunks it, embeds with sentence-transformers, stores in Oracle, inserts docs into LlamaIndex.
search: Queries the LlamaIndex with the LLaMA LLM for similarity and streaming response.
Oracle stores embeddings as JSON strings for simplicity.
You can later swap the OracleVectorStore with a proper vector DB.


Usage
POST /ingest with JSON {"url": "https://example.com"} to scrape and ingest website content.
POST /query with JSON {"query": "your question", "top_k": 5} to query the index.
Responses are streamed with application/x-ndjson content type.

Notes
Embeddings are stored as JSON strings in Oracle; optimize as needed.
LLaMA 3.2 1B is loaded via HuggingFaceHub; adjust model repo as needed.
Replace scraper with any custom logic if needed.

