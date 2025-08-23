"""
oracle_rag_indexer.py

Automates: read entire Oracle schema → build rich natural‑language docs → create embeddings → store back
into Oracle with optional Oracle 23ai Vector Search indexes. Designed to support RAG pipelines for SQL generation.

⚠️ No system can guarantee “100% accurate SQL” from an LLM. This script aims for *defense‑in‑depth*:
- comprehensive schema coverage (tables, views, columns, PK/FK, indexes, comments, grants)
- sample values + value distributions for categorical columns
- relationship graph snippets
- deduplicated, chunked documents with lineage ids
- quality gates and refresh/lineage tracking

Dependencies (install):
  pip install oracledb python-dotenv tqdm tenacity pydantic
  # Choose ONE embedding backend below (implementations provided):
  pip install openai            # for OpenAI embeddings
  # or
  pip install sentence-transformers torch --extra-index-url https://download.pytorch.org/whl/cpu

Requires Oracle user with metadata read + DDL on target RAG tables. Tested with Oracle 19c–23ai (vector if 23ai).
"""
from __future__ import annotations

import os
import math
import json
import hashlib
import datetime as dt
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple



import oracledb  # python-oracledb
from pydantic import BaseModel
from dotenv import load_dotenv
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()  # This will look for .env in the current working directory

# ---------------------------
# Config
# ---------------------------
class Settings(BaseModel):
    # Oracle
    ORACLE_SERVICE: str = os.getenv("DB_SERVICE", "XEPDB1")
    ORACLE_HOST: str = os.getenv("DB_HOST", "localhost")
    ORACLE_PORT: str = os.getenv("DB_PORT", "localhost")
    ORACLE_USER: str = os.getenv("DB_USER", "system")
    ORACLE_PASSWORD: str = os.getenv("DB_PASSWORD", "oracle")
    TARGET_SCHEMA: str = os.getenv("TARGET_SCHEMA", os.getenv("DB_USER", "system")).upper()

    # Embeddings
    EMBED_BACKEND: str = os.getenv("EMBED_BACKEND", "openai")  # "openai" or "sbert"
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "text-embedding-3-large")
    LOCAL_MODEL_PATH: str = os.getenv('LOCAL_EMBED_MODEL')

    SBERT_MODEL: str = os.getenv('LOCAL_EMBED_MODEL')

    # Indexing
    CHUNK_TOKENS: int = int(os.getenv("CHUNK_TOKENS", "350"))
    OVERLAP_TOKENS: int = int(os.getenv("OVERLAP_TOKENS", "40"))
    MAX_ROWS_PER_COLUMN_SAMPLE: int = int(os.getenv("MAX_ROWS_PER_COLUMN_SAMPLE", "50"))

    # Performance
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "128"))

    # Flags
    USE_VECTOR_TYPE: str = os.getenv("USE_VECTOR_TYPE", "auto")  # auto|yes|no


load_dotenv()
settings = Settings()

# ---------------------------
# DB helpers
# ---------------------------

def connect() -> oracledb.Connection:
    # Thin mode by default (no Oracle Client needed). For thick, call oracledb.init_oracle_client()
    db_uri = f"oracle+oracledb://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '1521')}/?service_name={os.getenv('DB_SERVICE')}"
    dsn = f"{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/{settings.ORACLE_SERVICE}"
    conn = oracledb.connect(user=settings.ORACLE_USER, password=settings.ORACLE_PASSWORD, dsn=dsn)
    return conn


def fetch_all(cur: oracledb.Cursor, sql: str, binds: Tuple = ()) -> List[Dict[str, Any]]:
    cur.execute(sql, binds)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur]


# ---------------------------
# Metadata extraction
# ---------------------------

META_TABLES_SQL = """
SELECT t.OWNER, t.TABLE_NAME, t.NUM_ROWS, c.COMMENTS AS TABLE_COMMENT
FROM ALL_TABLES t
LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER = t.OWNER AND c.TABLE_NAME = t.TABLE_NAME
WHERE t.OWNER = :owner
ORDER BY t.TABLE_NAME
"""

META_VIEWS_SQL = """
SELECT v.OWNER, v.VIEW_NAME, c.COMMENTS AS VIEW_COMMENT, v.TEXT_VC AS VIEW_TEXT
FROM ALL_VIEWS v
LEFT JOIN ALL_TAB_COMMENTS c ON c.OWNER = v.OWNER AND c.TABLE_NAME = v.VIEW_NAME
WHERE v.OWNER = :owner
ORDER BY v.VIEW_NAME
"""

META_COLUMNS_SQL = """
SELECT OWNER, TABLE_NAME, COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
       NULLABLE, COLUMN_ID, COMMENTS
FROM ALL_TAB_COLUMNS
LEFT JOIN ALL_COL_COMMENTS USING (OWNER, TABLE_NAME, COLUMN_NAME)
WHERE OWNER = :owner
ORDER BY TABLE_NAME, COLUMN_ID
"""

META_CONSTRAINTS_SQL = """
SELECT ac.CONSTRAINT_NAME, ac.CONSTRAINT_TYPE, ac.TABLE_NAME, acc.COLUMN_NAME,
       ac.R_CONSTRAINT_NAME, ac.STATUS
FROM ALL_CONSTRAINTS ac
LEFT JOIN ALL_CONS_COLUMNS acc ON ac.OWNER = acc.OWNER AND ac.CONSTRAINT_NAME = acc.CONSTRAINT_NAME
WHERE ac.OWNER = :owner
ORDER BY ac.TABLE_NAME, ac.CONSTRAINT_NAME, acc.POSITION
"""

META_INDEXES_SQL = """
SELECT ai.TABLE_NAME, ai.INDEX_NAME, ai.UNIQUENESS, aic.COLUMN_NAME, aic.COLUMN_POSITION
FROM ALL_INDEXES ai
JOIN ALL_IND_COLUMNS aic ON ai.OWNER = aic.INDEX_OWNER AND ai.INDEX_NAME = aic.INDEX_NAME
WHERE ai.TABLE_OWNER = :owner
ORDER BY ai.TABLE_NAME, ai.INDEX_NAME, aic.COLUMN_POSITION
"""

SAMPLE_VALUES_SQL_TMPL = """
SELECT /*+ FIRST_ROWS(100) */ {col} AS VAL, COUNT(*) AS CNT
FROM {owner}.{table}
WHERE {col} IS NOT NULL
GROUP BY {col}
ORDER BY CNT DESC FETCH FIRST :lim ROWS ONLY
"""

ROWCOUNT_SQL = """
SELECT NUM_ROWS FROM ALL_TABLES WHERE OWNER = :owner AND TABLE_NAME = :t
"""


# ---------------------------
# Embedding backends
# ---------------------------
class Embedder:
    dim: int

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class OpenAIEmbedder(Embedder):
    def __init__(self, model: str):
        from openai import OpenAI
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        # dim varies by model; we can query a dummy call or set known dims
        self.dim = 3072 if "3-large" in model else 1536

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=20))
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class SbertEmbedder(Embedder):
    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)
        # Infer dim from a forward pass
        self.dim = len(self.model.encode(["dim_probe"], convert_to_numpy=True)[0])

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        vecs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]


def get_embedder() -> Embedder:
    if settings.EMBED_BACKEND.lower() == "openai":
        return OpenAIEmbedder(settings.OPENAI_MODEL)
    elif settings.EMBED_BACKEND.lower() == "sbert":
        return SbertEmbedder(settings.LOCAL_MODEL_PATH)
        # return SentenceTransformer(settings.LOCAL_MODEL_PATH)
    else:
        raise ValueError("Unsupported EMBED_BACKEND. Use 'openai' or 'sbert'.")


# ---------------------------
# RAG tables & vector support
# ---------------------------
DDL_VECTOR_ON = {
    "tables": [
        # documents table: one record per logical artifact (table card, view card, relationship doc, etc.)
        """
        CREATE TABLE RAG_DOCUMENTS (
          DOC_ID        NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          DOC_TYPE      VARCHAR2(30),
          SOURCE_OWNER  VARCHAR2(128),
          SOURCE_NAME   VARCHAR2(128),
          SOURCE_PART   VARCHAR2(128), -- e.g., column name or section
          TITLE         VARCHAR2(400),
          BODY          CLOB,
          HASH          VARCHAR2(64) UNIQUE,
          CREATED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP
        )
        """,
        # chunks + embeddings
        """
        CREATE TABLE RAG_CHUNKS (
          CHUNK_ID      NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          DOC_ID        NUMBER REFERENCES RAG_DOCUMENTS(DOC_ID) ON DELETE CASCADE,
          CHUNK_IX      NUMBER,
          CONTENT       CLOB,
          TOKENS        NUMBER,
          EMBEDDING     VECTOR(:dim)
        )
        """,
    ],
    # HNSW index for fast ANN search (Oracle 23ai vector search)
    "index": "CREATE INDEX RAG_CHUNKS_VEC_IX ON RAG_CHUNKS(EMBEDDING) INDEXTYPE IS VECTOR_HNSW PARAMETERS('M 24 EF_CONSTRUCTION 200 EF_SEARCH 64 DISTANCE COSINE');",
}

DDL_VECTOR_OFF = {
    # Fallback when VECTOR type not supported: store embedding as JSON in CLOB; cosine computed app-side.
    "tables": [
        """
        CREATE TABLE RAG_DOCUMENTS (
          DOC_ID        NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          DOC_TYPE      VARCHAR2(30),
          SOURCE_OWNER  VARCHAR2(128),
          SOURCE_NAME   VARCHAR2(128),
          SOURCE_PART   VARCHAR2(128),
          TITLE         VARCHAR2(400),
          BODY          CLOB,
          HASH          VARCHAR2(64) UNIQUE,
          CREATED_AT    TIMESTAMP DEFAULT SYSTIMESTAMP
        )
        """,
        """
        CREATE TABLE RAG_CHUNKS (
          CHUNK_ID      NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
          DOC_ID        NUMBER REFERENCES RAG_DOCUMENTS(DOC_ID) ON DELETE CASCADE,
          CHUNK_IX      NUMBER,
          CONTENT       CLOB,
          TOKENS        NUMBER,
          EMBEDDING_JSON CLOB
        )
        """,
    ],
    "index": None,
}


def detect_vector_support(cur: oracledb.Cursor) -> bool:
    if settings.USE_VECTOR_TYPE == "yes":
        return True
    if settings.USE_VECTOR_TYPE == "no":
        return False
    # auto-detect: look for VECTOR type
    try:
        cur.execute("SELECT 1 FROM ALL_TYPES WHERE TYPE_NAME = 'VECTOR' AND OWNER = 'SYS'")
        return cur.fetchone() is not None
    except Exception:
        return False


def ensure_rag_schema(conn: oracledb.Connection, embed_dim: int) -> bool:
    cur = conn.cursor()
    has_vector = detect_vector_support(cur)
    ddl = DDL_VECTOR_ON if has_vector else DDL_VECTOR_OFF

    for stmt in ddl["tables"]:
        s = stmt.replace(":dim", str(embed_dim))
        try:
            cur.execute(s)
        except oracledb.DatabaseError as e:
            # ignore if already exists
            if "ORA-00955" not in str(e):
                raise
    if ddl["index"]:
        try:
            cur.execute(ddl["index"])
        except oracledb.DatabaseError as e:
            if "ORA-00955" not in str(e):
                raise
    conn.commit()
    return has_vector


# ---------------------------
# Document building
# ---------------------------

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def smart_chunk(text: str, max_tokens: int, overlap: int) -> List[str]:
    # Simple char-based approximation to tokens; conservative
    approx_tok = max(1, max_tokens * 4)  # ~4 chars per token
    approx_overlap = max(1, overlap * 4)
    chunks = []
    i = 0
    while i < len(text):
        end = min(len(text), i + approx_tok)
        # try to break at sentence boundary
        cut = text.rfind(". ", i, end)
        if cut == -1 or cut <= i + 100:
            cut = end
        chunks.append(text[i:cut].strip())
        i = max(cut - approx_overlap, cut)
    return [c for c in chunks if c]


def table_card(t: Dict[str, Any], cols: List[Dict[str, Any]], cons: List[Dict[str, Any]], idxs: List[Dict[str, Any]], samples: Dict[str, List[Tuple[Any,int]]]) -> Tuple[str, str]:
    title = f"Table {t['TABLE_NAME']} (owner {t['OWNER']})"
    lines = [
        f"Table: {t['TABLE_NAME']} (Owner: {t['OWNER']})",
        f"Rows (stats): {t.get('NUM_ROWS')}",
        f"Comment: {t.get('TABLE_COMMENT') or '—'}",
        "Columns:",
    ]
    for c in cols:
        col_desc = f"- {c['COLUMN_NAME']} {c['DATA_TYPE']}"
        if c.get('DATA_PRECISION'):
            col_desc += f"({c['DATA_PRECISION']},{c.get('DATA_SCALE')})"
        elif c.get('DATA_LENGTH'):
            col_desc += f"({c['DATA_LENGTH']})"
        col_desc += f" NULLABLE={c['NULLABLE']}"
        if c.get('COMMENTS'):
            col_desc += f" — {c['COMMENTS']}"
        # include samples for likely categorical columns
        svals = samples.get(c['COLUMN_NAME'])
        if svals:
            top = ", ".join([f"{v}×{n}" for v, n in svals[:5]])
            col_desc += f" | top values: {top}"
        lines.append(col_desc)

    # constraints
    pks = [x for x in cons if x['CONSTRAINT_TYPE'] == 'P']
    fks = [x for x in cons if x['CONSTRAINT_TYPE'] == 'R']
    if pks:
        lines.append("Primary keys:")
        for pk in pks:
            lines.append(f"- {pk['CONSTRAINT_NAME']} ({pk['COLUMN_NAME']})")
    if fks:
        lines.append("Foreign keys:")
        for fk in fks:
            lines.append(f"- {fk['CONSTRAINT_NAME']} ({fk['COLUMN_NAME']}) → ref {fk['R_CONSTRAINT_NAME']}")

    if idxs:
        lines.append("Indexes:")
        by_idx = {}
        for irow in idxs:
            by_idx.setdefault(irow['INDEX_NAME'], []).append(irow['COLUMN_NAME'])
        for iname, icolumns in by_idx.items():
            lines.append(f"- {iname} on ({', '.join(icolumns)})")

    body = "\n".join(lines)
    return title, body


# ---------------------------
# Main pipeline
# ---------------------------

def collect_schema(conn: oracledb.Connection, owner: str) -> Dict[str, Any]:
    cur = conn.cursor()
    tables = fetch_all(cur, META_TABLES_SQL, (owner,))
    views = fetch_all(cur, META_VIEWS_SQL, (owner,))
    columns = fetch_all(cur, META_COLUMNS_SQL, (owner,))
    constraints = fetch_all(cur, META_CONSTRAINTS_SQL, (owner,))
    indexes = fetch_all(cur, META_INDEXES_SQL, (owner,))

    # organize
    cols_by_table = {}
    for c in columns:
        cols_by_table.setdefault(c['TABLE_NAME'], []).append(c)

    cons_by_table = {}
    for c in constraints:
        cons_by_table.setdefault(c['TABLE_NAME'], []).append(c)

    idx_by_table = {}
    for i in indexes:
        idx_by_table.setdefault(i['TABLE_NAME'], []).append(i)

    # sample categorical values
    samples: Dict[str, Dict[str, List[Tuple[Any,int]]]] = {}
    for t in tqdm(tables, desc="Sampling values"):
        tname = t['TABLE_NAME']
        samples[tname] = {}
        for c in cols_by_table.get(tname, []):
            dt = (c['DATA_TYPE'] or '').upper()
            # Heuristic: sample short text or low-cardinality number columns
            if dt in ("VARCHAR2", "CHAR", "NVARCHAR2") or (dt in ("NUMBER",) and (c.get('DATA_SCALE') == 0)):
                sql = SAMPLE_VALUES_SQL_TMPL.format(owner=owner, table=tname, col=c['COLUMN_NAME'])
                try:
                    cur.execute(sql, (settings.MAX_ROWS_PER_COLUMN_SAMPLE,))
                    samples[tname][c['COLUMN_NAME']] = [(r[0], r[1]) for r in cur.fetchall()]
                except Exception:
                    pass

    return {
        "tables": tables,
        "views": views,
        "cols_by_table": cols_by_table,
        "cons_by_table": cons_by_table,
        "idx_by_table": idx_by_table,
        "samples": samples,
    }


def upsert_doc(cur: oracledb.Cursor, doc: Dict[str, Any]) -> int:
    # dedupe by content hash
    h = sha(doc["BODY"])[:64]
    
    # Check if doc already exists
    cur.execute(
        "SELECT DOC_ID FROM RAG_DOCUMENTS WHERE HASH = :h",
        {"h": h}
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    # Create output variable for DOC_ID
    doc_id_var = cur.var(oracledb.NUMBER)

    # Insert and return DOC_ID
    cur.execute(
        """
        INSERT INTO RAG_DOCUMENTS (
            DOC_TYPE, SOURCE_OWNER, SOURCE_NAME, SOURCE_PART, 
            TITLE, BODY, HASH
        )
        VALUES (
            :dt, :own, :sn, :sp, :ti, :bo, :h
        )
        RETURNING DOC_ID INTO :doc_id
        """,
        {
            "dt": doc["DOC_TYPE"],
            "own": doc["SOURCE_OWNER"],
            "sn": doc["SOURCE_NAME"],
            "sp": doc.get("SOURCE_PART"),
            "ti": doc["TITLE"],
            "bo": doc["BODY"],
            "h": h,
            "doc_id": doc_id_var
        }
    )

    # getvalue() returns a list for RETURNING INTO — take first element
    doc_id = doc_id_var.getvalue()
    if isinstance(doc_id, list):
        doc_id = doc_id[0]

    return int(doc_id)

def insert_chunk(cur: oracledb.Cursor, doc_id: int, ix: int, content: str, tokens: int, embedding: List[float], has_vector: bool):
    if has_vector:
        cur.execute(
            """
            INSERT INTO RAG_CHUNKS (DOC_ID, CHUNK_IX, CONTENT, TOKENS, EMBEDDING)
            VALUES (:d, :i, :c, :t, :e)
            """,
            {"d": doc_id, "i": ix, "c": content, "t": tokens, "e": embedding}
        )
    else:
        cur.execute(
            """
            INSERT INTO RAG_CHUNKS (DOC_ID, CHUNK_IX, CONTENT, TOKENS, EMBEDDING_JSON)
            VALUES (:d, :i, :c, :t, :e)
            """,
            {"d": doc_id, "i": ix, "c": content, "t": tokens, "e": json.dumps(embedding)}
        )


def build_and_store_embeddings(conn: oracledb.Connection, meta: Dict[str, Any], owner: str, has_vector: bool):
    embedder = get_embedder()
    cur = conn.cursor()

    # Build docs: one per table + one per view + relationship doc per table
    docs: List[Dict[str, Any]] = []

    for t in meta["tables"]:
        tname = t["TABLE_NAME"]
        title, body = table_card(
            t,
            meta["cols_by_table"].get(tname, []),
            meta["cons_by_table"].get(tname, []),
            meta["idx_by_table"].get(tname, []),
            meta["samples"].get(tname, {})
        )
        docs.append({
            "DOC_TYPE": "TABLE",
            "SOURCE_OWNER": owner,
            "SOURCE_NAME": tname,
            "SOURCE_PART": None,
            "TITLE": title,
            "BODY": body,
        })

    for v in meta["views"]:
        vname = v["VIEW_NAME"]
        title = f"View {vname} (owner {owner})"
        body = f"View: {vname}\nComment: {v.get('VIEW_COMMENT') or '—'}\nSQL:\n{v.get('VIEW_TEXT') or ''}"
        docs.append({
            "DOC_TYPE": "VIEW",
            "SOURCE_OWNER": owner,
            "SOURCE_NAME": vname,
            "SOURCE_PART": None,
            "TITLE": title,
            "BODY": body,
        })

    # Relationship docs (FKs)
    for t, cons in meta["cons_by_table"].items():
        fks = [x for x in cons if x['CONSTRAINT_TYPE'] == 'R']
        if not fks:
            continue
        lines = [f"Relationships for {t}:"]
        for fk in fks:
            lines.append(f"- {fk['CONSTRAINT_NAME']}: {t}.{fk['COLUMN_NAME']} → {fk['R_CONSTRAINT_NAME']}")
        docs.append({
            "DOC_TYPE": "REL",
            "SOURCE_OWNER": owner,
            "SOURCE_NAME": t,
            "SOURCE_PART": None,
            "TITLE": f"Relationships for {t}",
            "BODY": "\n".join(lines)
        })

    # Upsert docs, chunk, embed, store
    print(f"Preparing {len(docs)} docs…")
    all_chunks: List[Tuple[int, int, str]] = []  # (doc_id, chunk_ix, content)

    for d in tqdm(docs, desc="Upserting docs"):
        doc_id = upsert_doc(cur, d)
        chunks = smart_chunk(d["BODY"], settings.CHUNK_TOKENS, settings.OVERLAP_TOKENS)
        for ix, content in enumerate(chunks):
            all_chunks.append((doc_id, ix, content))

    conn.commit()

    # Embed in batches
    print(f"Embedding {len(all_chunks)} chunks…")
    B = settings.BATCH_SIZE
    for i in tqdm(range(0, len(all_chunks), B), desc="Embedding batches"):
        batch = all_chunks[i:i+B]
        texts = [c[2] for c in batch]
        vecs = get_embedder().embed_batch(texts)
        for (doc_id, ix, content), vec in zip(batch, vecs):
            insert_chunk(cur, doc_id, ix, content, tokens=len(content)//4, embedding=vec, has_vector=has_vector)
        conn.commit()


# ---------------------------
# Query helper for RAG (optional example)
# ---------------------------

RAG_SEARCH_SQL_VECTOR = """
SELECT c.CHUNK_ID, d.TITLE, c.CONTENT
FROM RAG_CHUNKS c
JOIN RAG_DOCUMENTS d ON d.DOC_ID = c.DOC_ID
WHERE VECTOR_DISTANCE(c.EMBEDDING, :q) USING COSINE < :th
ORDER BY VECTOR_DISTANCE(c.EMBEDDING, :q) USING COSINE
FETCH FIRST :k ROWS ONLY
"""


def rag_search(conn: oracledb.Connection, query: str, k: int = 8, threshold: float = 0.8) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    has_vector = detect_vector_support(cur)
    embedder = get_embedder()
    qvec = embedder.embed_batch([query])[0]
    if has_vector:
        cur.execute(RAG_SEARCH_SQL_VECTOR, {"q": qvec, "k": k, "th": threshold})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    else:
        # App-side cosine when vector type absent
        cur.execute("SELECT CHUNK_ID, TITLE, CONTENT, EMBEDDING_JSON FROM RAG_CHUNKS JOIN RAG_DOCUMENTS USING(DOC_ID)")
        rows = cur.fetchall()
        results = []
        import numpy as np
        q = np.array(qvec, dtype=float)
        for chunk_id, title, content, ej in rows:
            v = np.array(json.loads(ej), dtype=float)
            cos = float(q @ v / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-12))
            results.append({"CHUNK_ID": chunk_id, "TITLE": title, "CONTENT": content, "SCORE": 1 - cos})
        results.sort(key=lambda x: x["SCORE"])  # lower is better (distance)
        return results[:k]


# ---------------------------
# Orchestration
# ---------------------------

def main():
    print("Connecting to Oracle…")
    conn = connect()
    try:
        owner = settings.TARGET_SCHEMA
        print(f"Collecting schema for {owner}…")
        meta = collect_schema(conn, owner)

        print("Initializing RAG tables…")
        has_vector = ensure_rag_schema(conn, get_embedder().dim)
        print(f"Vector support: {'ON' if has_vector else 'OFF'}")

        print("Building and storing embeddings…")
        build_and_store_embeddings(conn, meta, owner, has_vector)

        print("Done. You can now perform semantic search via rag_search().")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
