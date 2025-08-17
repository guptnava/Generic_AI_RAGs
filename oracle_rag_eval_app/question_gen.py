from typing import Dict, List, Tuple
from db import cursor
import json

TEMPLATES = [
    "List all {table} with their {cols}.",
    "How many {table} are there?",
    "Show the top 10 {table} ordered by {first_col}.",
    "Find {table} where {first_col} is not null.",
    "Show {table} grouped by {first_col} with counts."
]

def auto_generate_from_schema(tables: Dict[str, List[Tuple[str, str]]]):
    ins_q = "INSERT INTO RAG_QUESTION(question, table_name, column_list) VALUES (:q, :t, :c)"
    with cursor() as cur:
        for tname, cols in tables.items():
            col_names = [c[0] for c in cols]
            first_col = col_names[0] if col_names else "1"
            for tmpl in TEMPLATES:
                q = tmpl.format(table=tname, cols=", ".join(col_names[:4]), first_col=first_col)
                cur.execute(ins_q, {"q": q, "t": tname, "c": json.dumps(col_names)})
    # Returns nothing; rows inserted


def safe_str(clob_or_str):
    """Convert Oracle LOB or string to Python string safely."""
    if clob_or_str is None:
        return ""
    if hasattr(clob_or_str, "read"):
        return clob_or_str.read()
    return str(clob_or_str)

def safe_json_loads(clob_or_str):
    """Safely convert Oracle LOB or string to Python list/object."""
    if clob_or_str is None:
        return []
    if hasattr(clob_or_str, "read"):
        clob_str = clob_or_str.read()
    else:
        clob_str = clob_or_str
    try:
        return json.loads(clob_str)
    except Exception:
        return []  # fallback if invalid JSON

def attach_ground_sql():
    """Naive ground truth SQL for basic templates; CLOB-safe."""
    select_q = "SELECT id, question, table_name, column_list FROM RAG_QUESTION WHERE ground_sql IS NULL"
    upd = "UPDATE RAG_QUESTION SET ground_sql=:sql WHERE id=:id"
    
    with cursor() as cur:
        cur.execute(select_q)
        for qid, qtext, tname, col_json in cur.fetchall():
            # Convert LOBs to safe Python objects
            qtext = safe_str(qtext)
            tname = safe_str(tname)
            col_list = safe_json_loads(col_json)
            
            cols = ", ".join(col_list[:4]) if col_list else "*"
            
            # Build ground SQL based on question type
            if "How many" in qtext:
                sql = f"SELECT COUNT(*) AS CNT FROM {tname}"
            elif "top 10" in qtext.lower():
                sql = f"SELECT {cols} FROM {tname} ORDER BY {cols.split(',')[0]} FETCH FIRST 10 ROWS ONLY"
            elif "not null" in qtext.lower():
                first_col = col_list[0] if col_list else "1"
                sql = f"SELECT {cols} FROM {tname} WHERE {first_col} IS NOT NULL"
            elif "grouped by" in qtext.lower():
                first_col = col_list[0] if col_list else "1"
                sql = f"SELECT {first_col}, COUNT(*) AS CNT FROM {tname} GROUP BY {first_col}"
            else:
                sql = f"SELECT {cols} FROM {tname}"
            
            # Update DB
            cur.execute(upd, {"sql": sql, "id": qid})



def add_synonyms_with_llm(syns_map):
    """Insert provided synonyms: syns_map = {question_id: [syn1, syn2, ...]}"""
    ins = "INSERT INTO RAG_QUESTION_SYNONYM(question_id, synonym_text) VALUES (:qid, :txt)"
    with cursor() as cur:
        for qid, syns in syns_map.items():
            for s in syns:
                cur.execute(ins, {"qid": qid, "txt": s})
