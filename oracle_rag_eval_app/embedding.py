import os
import numpy as np
from typing import List, Tuple
from db import cursor
from dotenv import load_dotenv
import oracledb  # make sure this is imported

load_dotenv()

# Provider abstraction
PROVIDER = None
OPENAI = None

try:
    from openai import OpenAI
    OPENAI = OpenAI()
    if os.getenv("OPENAI_API_KEY"):
        PROVIDER = "openai"
except Exception:
    OPENAI = None

HF_MODEL = os.getenv("HF_EMBEDDING_MODEL")
HF_EMBED = None
if HF_MODEL:
    try:
        from sentence_transformers import SentenceTransformer
        HF_EMBED = SentenceTransformer(HF_MODEL)
        PROVIDER = PROVIDER or "hf"
    except Exception:
        HF_EMBED = None

def lob_to_str(val):
    """Safely read a CLOB/BLOB from Oracle."""
    if val is None:
        return ""
    if isinstance(val, (str, bytes)):
        return val
    return val.read()

def embed_texts(texts: List[str]) -> Tuple[str, str, np.ndarray]:
    """Returns (provider, model_name, 2D numpy float32 array)."""
    global PROVIDER
    if PROVIDER == "openai" and OPENAI and os.getenv("OPENAI_EMBEDDING_MODEL"):
        model = os.getenv("OPENAI_EMBEDDING_MODEL")
        resp = OPENAI.embeddings.create(model=model, input=texts)
        vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
        return "openai", model, vecs
    elif HF_EMBED:
        vecs = HF_EMBED.encode(texts, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
        return "hf", HF_MODEL, vecs
    raise RuntimeError("No embedding provider available. Set OPENAI_API_KEY/OPENAI_EMBEDDING_MODEL or HF_EMBEDDING_MODEL.")

def lob_to_str(val):
    """Convert Oracle LOB to string safely."""
    if val is None:
        return None
    return val.read() if hasattr(val, "read") else val

def persist_embeddings_for_all():
    # Collect texts lacking embeddings
    sel_q = "SELECT id, question FROM RAG_QUESTION WHERE id NOT IN (SELECT NVL(question_id, -1) FROM RAG_EMBEDDING)"
    sel_s = "SELECT id, synonym_text FROM RAG_QUESTION_SYNONYM WHERE id NOT IN (SELECT NVL(synonym_id, -1) FROM RAG_EMBEDDING)"
    rows = []
    q_map = []
    s_map = []

    with cursor() as cur:
        cur.execute(sel_q)
        qrows = cur.fetchall()
        cur.execute(sel_s)
        srows = cur.fetchall()

        # Read LOBs **while cursor/connection is still open**
        if qrows:
            q_map = [(int(r[0]), lob_to_str(r[1])) for r in qrows]
            rows.extend([r[1] for r in q_map])

        if srows:
            s_map = [(int(r[0]), lob_to_str(r[1])) for r in srows]
            rows.extend([r[1] for r in s_map])

    if not rows:
        return 0

    provider, model, vecs = embed_texts(rows)
    dim = vecs.shape[1]

    ins = """INSERT INTO RAG_EMBEDDING(question_id, synonym_id, provider, model, dim, vector_blob)
               VALUES (:qid, :sid, :prov, :model, :dim, :blob)"""
    
    import oracledb

    with cursor() as cur:
        for i, (qid, _) in enumerate(q_map):
            vec = vecs[i]
            cur.setinputsizes(blob=oracledb.DB_TYPE_BLOB)
            cur.execute(ins, {
                "qid": qid,
                "sid": None,
                "prov": provider,
                "model": model,
                "dim": dim,
                "blob": vec.tobytes()
            })

        for j, (sid, _) in enumerate(s_map):
            vec = vecs[len(q_map) + j]
            cur.setinputsizes(blob=oracledb.DB_TYPE_BLOB)
            cur.execute(ins, {
                "qid": None,
                "sid": sid,
                "prov": provider,
                "model": model,
                "dim": dim,
                "blob": vec.tobytes()
            })

    return len(rows)



def fetch_embedding_by_texts(texts: List[str]) -> Tuple[np.ndarray, int]:
    provider, model, vecs = embed_texts(texts)
    return vecs, vecs.shape[1]
