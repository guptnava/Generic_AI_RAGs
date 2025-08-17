import os, time, json
import numpy as np
import pandas as pd
from typing import Optional, Dict
from db import cursor
from dotenv import load_dotenv
load_dotenv()

# LLM client (OpenAI example)
OPENAI = None
try:
    from openai import OpenAI
    OPENAI = OpenAI()
except Exception:
    OPENAI = None

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

def get_prompt_template(prompt_id: int) -> str:
    with cursor() as cur:
        cur.execute("SELECT template FROM RAG_PROMPT_TEMPLATE WHERE id=:id", {"id": prompt_id})
        r = cur.fetchone()
        if not r:
            raise RuntimeError("Prompt template not found")
        return r[0]

def build_prompt(tpl: str, ddl_excerpt: str, question: str) -> str:
    # ddl_excerpt is guaranteed to be plain string
    return f"{tpl}\n\n# DDL\n{ddl_excerpt}\n\n# Question\n{question}\n\n# SQL:"

from typing import Optional
from db import cursor

def fetch_ddl_excerpt(owner: str, table_name: Optional[str]) -> str:
    sql = (
        "SELECT ddl FROM RAG_DDL WHERE owner=:o AND ROWNUM <= 20"
        if not table_name
        else """
            SELECT ddl 
            FROM RAG_DDL 
            WHERE owner=:o 
              AND object_type='TABLE' 
              AND object_name=:t
        """
    )
    
 
    params = {"o": owner.upper()}
    if table_name:
        params["t"] = table_name.upper()
    
    ddls = []
    with cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()  # Fetch LOB proxies first

    for r in rows:
        val = r[0]
        if hasattr(val, "read"):
            try:
                # Open a new connection just for reading if necessary
                val = val.read()
            except Exception as e:
                val = f"-- ERROR reading LOB: {e}"
        ddls.append(str(val) if val else "")
    
    return "\n".join(ddls)


def call_llm(prompt: str) -> str:
    if not OPENAI or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("No LLM available. Set OPENAI_API_KEY to use OpenAI chat models.")
    resp = OPENAI.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.0,
    )
    txt = resp.choices[0].message.content.strip()
    return txt.split(";")[0] + ";" if not txt.strip().endswith(";") else txt

def safe_exec(sql_text: str, row_cap: int = 1000):
    limited = f"SELECT * FROM ( {sql_text.rstrip(';')} ) WHERE ROWNUM <= {row_cap}"
    cols, rows = [], []
    err, ms = None, None
    start = time.time()
    try:
        with cursor() as cur:
            cur.execute(limited)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        ms = int((time.time() - start) * 1000)
    except Exception as e:
        err = str(e)[:4000]
        ms = int((time.time() - start) * 1000)
    return cols, rows, err, ms

def compare_results(g_cols, g_rows, l_cols, l_rows, sample_n=10):
    same_shape = (len(g_cols) == len(l_cols))
    g_s = [str(r) for r in g_rows[:sample_n]]
    l_s = [str(r) for r in l_rows[:sample_n]]
    same_sample = (g_s == l_s and same_shape)
    return same_shape, same_sample

def run_evaluation(owner: str, prompt_id: int, run_name: str = None):
    # Create run
    with cursor() as cur:
        cur.execute("INSERT INTO RAG_EVAL_RUN(name, prompt_id) VALUES (:n, :p)", {"n": run_name or 'eval_run', "p": prompt_id})
        cur.execute("SELECT MAX(id) FROM RAG_EVAL_RUN")
        run_id = int(cur.fetchone()[0])

    # Iterate questions (and synonyms)
    qsql = "SELECT id, question, table_name FROM RAG_QUESTION"
    ssql = "SELECT id, question_id, synonym_text FROM RAG_QUESTION_SYNONYM"
    gsql = "SELECT id, question_id, sql_text FROM RAG_SQL"
    with cursor() as cur:
        cur.execute(qsql); qs = cur.fetchall()
        cur.execute(ssql); syns = cur.fetchall()
        cur.execute(gsql); gmap = cur.fetchall()
    ground_by_q = {int(qid): (int(sid), sql) for sid, qid, sql in gmap}

    # build synonym map
    syn_by_q = {}
    for sid, qid, stext in syns:
        syn_by_q.setdefault(int(qid), []).append((int(sid), stext))

    tpl = get_prompt_template(prompt_id)

    ins_case = """INSERT INTO RAG_EVAL_CASE(eval_run_id, question_id, synonym_id, ground_sql_id,
                   llm_sql, ground_ok, llm_ok, same_shape, same_sample, error_text, exec_ms_ground, exec_ms_llm)
                   VALUES (:run, :qid, :sid, :gid, :llm_sql, :gok, :lok, :shape, :sample, :err, :gms, :lms)"""

    for qid, qtext, tname in qs:
        qid = int(qid)
        gid, gsql_text = ground_by_q.get(qid, (None, None))
        ddl = fetch_ddl_excerpt(owner, tname)
        prompt = build_prompt(tpl, ddl, qtext)
        llm_sql = None
        l_cols, l_rows, l_err, l_ms = [],[],None,None
        g_cols, g_rows, g_err, g_ms = [],[],None,None

        if gsql_text:
            g_cols, g_rows, g_err, g_ms = safe_exec(gsql_text, 1000)

        try:
            llm_sql = call_llm(prompt)
            l_cols, l_rows, l_err, l_ms = safe_exec(llm_sql, 1000)
        except Exception as e:
            l_err = str(e)[:4000]

        shape, sample = compare_results(g_cols, g_rows, l_cols, l_rows)
        with cursor() as cur:
            cur.execute(ins_case, {
                "run": run_id, "qid": qid, "sid": None,
                "gid": gid, "llm_sql": llm_sql,
                "gok": 'N' if g_err else 'Y',
                "lok": 'N' if l_err else 'Y',
                "shape": 'Y' if shape else 'N',
                "sample": 'Y' if sample else 'N',
                "err": (g_err or '') + (' | ' if g_err and l_err else '') + (l_err or ''),
                "gms": g_ms, "lms": l_ms
            })

        # Evaluate synonyms too
        for sid, stext in syn_by_q.get(qid, []):
            ddl = fetch_ddl_excerpt(owner, tname)
            prompt = build_prompt(tpl, ddl, stext)
            llm_sql = None
            l_cols, l_rows, l_err, l_ms = [],[],None,None
            try:
                llm_sql = call_llm(prompt)
                l_cols, l_rows, l_err, l_ms = safe_exec(llm_sql, 1000)
            except Exception as e:
                l_err = str(e)[:4000]

            shape, sample = compare_results(g_cols, g_rows, l_cols, l_rows)
            with cursor() as cur:
                cur.execute(ins_case, {
                    "run": run_id, "qid": qid, "sid": sid,
                    "gid": gid, "llm_sql": llm_sql,
                    "gok": 'N' if g_err else 'Y',
                    "lok": 'N' if l_err else 'Y',
                    "shape": 'Y' if shape else 'N',
                    "sample": 'Y' if sample else 'N',
                    "err": (g_err or '') + (' | ' if g_err and l_err else '') + (l_err or ''),
                    "gms": g_ms, "lms": l_ms
                })

    return run_id
