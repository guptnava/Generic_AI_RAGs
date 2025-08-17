# Oracle RAG Trainer & Evaluator (12c–23c)

An end‑to‑end Streamlit application that:
1) Extracts full schema DDL from Oracle using `DBMS_METADATA`  
2) Parses schema and auto‑generates questions, synonymous questions, and ground‑truth SQL  
3) Creates embeddings for all questions (and synonyms) and stores them **back in Oracle**  
4) Evaluates LLM‑generated SQL vs. stored ground truth by executing in Oracle and comparing results  
5) Stores all evaluations and metrics in Oracle for longitudinal tracking  
6) Visualizes metrics and supports iterative improvements to train your RAG system

> Works with Oracle 12c through 23c. Uses `oracledb` in Thin mode (no instant client required).

---

## Quick start

### 1) Prereqs
- Python 3.10+
- Oracle DB 12c–23c accessible from your machine
- `pip install -r requirements.txt`
- Create a `.env` (or set env vars) with:
  ```bash
  ORACLE_DSN="host:port/service_name"
  ORACLE_USER="your_user"
  ORACLE_PASSWORD="your_password"
  ORACLE_SCHEMA="YOUR_SCHEMA"   # owner to extract DDL for
  # Embeddings / LLM (choose one provider or mix)
  OPENAI_API_KEY="..."
  OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
  OPENAI_CHAT_MODEL="gpt-4o-mini"
  # Optional: HuggingFace as a local fallback for embeddings
  HF_EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
  ```

> Without OpenAI keys, embeddings fall back to HuggingFace if `HF_EMBEDDING_MODEL` is set and model can be downloaded.
> For air‑gapped environments you can pre‑download a local HF model and point to the folder path.

### 2) Create schema objects
Run `schema.sql` on your target database (or let the app create tables automatically from Settings).

### 3) Launch
```bash
streamlit run streamlit_app.py
```

### 4) Flow
- **Extract DDL** → **Generate Q&A** (questions + synonyms + ground truth SQL) → **Embed** → **Evaluate** → **Analyze & Iterate**.
- Everything is stored in Oracle tables prefixed with `RAG_`.

---

## Tables

- `RAG_DDL` — captured DDL per object
- `RAG_QUESTION` — base questions
- `RAG_QUESTION_SYNONYM` — synonymous variants
- `RAG_SQL` — ground truth SQL per question
- `RAG_EMBEDDING` — embeddings (BLOB float32) for questions/synonyms
- `RAG_EVAL_RUN` — an evaluation run header
- `RAG_EVAL_CASE` — per‑question evaluation details (LLM SQL, exec results, metrics)
- `RAG_PROMPT_TEMPLATE` — prompt templates used to talk to the LLM

> Designed for 12c compatibility: embeddings stored as BLOB with a separate dimension column. If you use 23ai with VECTOR type,
> you can add a materialized vector column and populate from the BLOB.

---

## Notes

- DDL extraction uses `DBMS_METADATA.GET_DDL`; you need sufficient privileges (e.g., `SELECT_CATALOG_ROLE`) or be the owner.
- SQL comparison runs the stored ground‑truth and the LLM‑generated SQL with a `ROWNUM` cap and compares shapes + sample rows.
- Streamlit includes dashboards and “Fix & Re‑run” actions to refine prompt templates and improve accuracy over time.
- This scaffold is production‑ready to extend but ships as a single, manageable application folder.
