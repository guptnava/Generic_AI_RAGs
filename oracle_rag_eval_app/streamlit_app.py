import os, io, json, time
import pandas as pd
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from db import ensure_tables, cursor
from ddl_extractor import persist_ddl, parse_tables_columns
from question_gen import auto_generate_from_schema, attach_ground_sql, add_synonyms_with_llm
from embedding import persist_embeddings_for_all, fetch_embedding_by_texts
from eval import run_evaluation
from llm_utils import llm_generate_synonyms_batch


load_dotenv()

# Helper function to safely convert LOBs to strings
def lob_to_str(val):
    if val is None:
        return ""
    if hasattr(val, "read"):  # Detects LOB objects
        return val.read()
    return val

st.set_page_config(page_title="SQL RAG Trainer & Evaluator", layout="wide")

st.title("🔧 SQL RAG Trainer & Evaluator")

with st.sidebar:
    st.header("Settings")
    owner = st.text_input("Schema owner (for DDL extract)", value=os.getenv("ORACLE_SCHEMA","HR"))
    if st.button("Ensure Tables"):
        ensure_tables()
        st.success("Tables ensured/created.")

    if st.button("Extract DDL"):
        with st.spinner("Extracting schema DDL..."):
            persist_ddl(owner)
        st.success("DDL extracted and saved.")

    if st.button("Auto-generate Questions + Ground SQL"):
        with st.spinner("Parsing schema and creating questions..."):
            tables = parse_tables_columns(owner)
            auto_generate_from_schema(tables)
            attach_ground_sql()
        st.success("Questions generated with baseline ground SQL.")

    
    if st.button("Create Embeddings for all Qs + Synonyms"):
        total_syns = 0  # ensure variable exists
        n = 0

        with st.spinner("Generating synonyms and embeddings..."):
            # Step 1: Fetch all questions without synonyms
            with cursor() as cur:
                cur.execute("""
                    SELECT id, question
                    FROM RAG_QUESTION
                    WHERE id NOT IN (SELECT DISTINCT question_id FROM RAG_QUESTION_SYNONYM)
                """)
                qrows = cur.fetchall()
                q_map = [(r[0], lob_to_str(r[1])) for r in qrows]

            # Step 2: Generate synonyms in batch
            syns_map = llm_generate_synonyms_batch(q_map, max_synonyms=5) if q_map else {}

            print("Synonyms map:", syns_map)


            # Step 3: Insert synonyms into DB
            if syns_map:
                add_synonyms_with_llm(syns_map)

            # Step 4: Create embeddings for all questions + synonyms
            n = persist_embeddings_for_all()

            # Step 5: Count total synonyms safely
            total_syns = sum(len(v) for v in syns_map.values()) if syns_map else 0

        st.success(f"Generated {total_syns} synonyms and created {n} new embeddings.")




    # with st.spinner("Creating embeddings for all questions + synonyms..."):
    #     n = persist_embeddings_for_all()

    # st.success(f"Created {n} new embeddings (including synonyms).")



    st.divider()
    st.subheader("Evaluation")
    prompt_id = st.number_input("Prompt Template ID", min_value=1, value=1, step=1)
    run_name = st.text_input("Run name", value="eval_run")
    if st.button("Run Evaluation"):
        with st.spinner("Evaluating..."):
            run_id = run_evaluation(owner, prompt_id, run_name)
        st.success(f"Evaluation completed. Run ID = {run_id}")

# Helper function to safely convert LOBs to strings
def lob_to_str(val):
    if val is None:
        return ""
    if hasattr(val, "read"):  # Detects LOB objects
        return val.read()
    return val

st.subheader("📊 Data Browser")

tabs = st.tabs(["DDL", "Questions", "Synonyms", "SQL", "Embeddings", "Eval Runs", "Eval Cases", "Analytics"])

# Tab 0: DDL
with tabs[0]:
    with cursor() as cur:
        cur.execute("SELECT id, owner, object_type, object_name, created_at FROM RAG_DDL ORDER BY id DESC FETCH FIRST 200 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 1: Questions
with tabs[1]:
    with cursor() as cur:
        cur.execute("SELECT id, question, table_name, created_at FROM RAG_QUESTION ORDER BY id DESC FETCH FIRST 500 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 2: Synonyms
with tabs[2]:
    with cursor() as cur:
        cur.execute("SELECT id, question_id, synonym_text, created_at FROM RAG_QUESTION_SYNONYM ORDER BY id DESC FETCH FIRST 500 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 3: SQL
with tabs[3]:
    with cursor() as cur:
        cur.execute("SELECT id, question_id, sql_text, created_at FROM RAG_SQL ORDER BY id DESC FETCH FIRST 500 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 4: Embeddings
with tabs[4]:
    with cursor() as cur:
        cur.execute("SELECT id, question_id, synonym_id, provider, model, dim, created_at FROM RAG_EMBEDDING ORDER BY id DESC FETCH FIRST 500 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 5: Eval Runs
with tabs[5]:
    with cursor() as cur:
        cur.execute("SELECT id, name, prompt_id, created_at FROM RAG_EVAL_RUN ORDER BY id DESC FETCH FIRST 100 ROWS ONLY")
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 6: Eval Cases
with tabs[6]:
    with cursor() as cur:
        cur.execute("""
            SELECT id, eval_run_id, question_id, synonym_id, ground_sql_id, ground_ok, llm_ok, same_shape, same_sample,
                   exec_ms_ground, exec_ms_llm, SUBSTR(error_text,1,120) AS err_snip, created_at
            FROM RAG_EVAL_CASE ORDER BY id DESC FETCH FIRST 1000 ROWS ONLY
        """)
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df, use_container_width=True)

# Tab 7: Analytics
with tabs[7]:
    st.write("**Run-level metrics**")
    with cursor() as cur:
        cur.execute("""
            SELECT e.id AS run_id,
                   AVG(CASE WHEN same_sample='Y' THEN 1 ELSE 0 END) AS exact_match_rate,
                   AVG(CASE WHEN same_shape='Y' THEN 1 ELSE 0 END)  AS shape_match_rate,
                   AVG(CASE WHEN llm_ok='Y' THEN 1 ELSE 0 END)       AS llm_success_rate
            FROM RAG_EVAL_CASE c
            JOIN RAG_EVAL_RUN e ON e.id=c.eval_run_id
            GROUP BY e.id
            ORDER BY e.id DESC
        """)
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.bar_chart(df.set_index("RUN_ID"))

    st.write("**Per-question trouble spots**")
    with cursor() as cur:
        cur.execute("""
            SELECT question_id,
                   AVG(CASE WHEN same_sample='Y' THEN 1 ELSE 0 END) AS exact_match_rate,
                   COUNT(*) AS attempts
            FROM RAG_EVAL_CASE
            GROUP BY question_id
            HAVING AVG(CASE WHEN same_sample='Y' THEN 1 ELSE 0 END) < 0.5
            ORDER BY exact_match_rate ASC
        """)
        rows = cur.fetchall()
        rows = [[lob_to_str(col) for col in row] for row in rows]
        df2 = pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    st.dataframe(df2, use_container_width=True)


st.divider()
st.caption("Tip: Use the Questions/SQL tabs to edit ground truth, add synonyms, and re-run evaluation for iterative RAG training.")
