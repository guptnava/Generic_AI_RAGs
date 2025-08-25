import pandas as pd
import numpy as np
import oracledb

# ----------------------
# Ensure required tables exist
# ----------------------
def ensure_tables(conn):
    cur = conn.cursor()

    # NL2SQL_SCHEMA
    cur.execute("""
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE NL2SQL_SCHEMA (
            id NUMBER GENERATED ALWAYS AS IDENTITY,
            schema_name VARCHAR2(128),
            table_name VARCHAR2(128),
            column_name VARCHAR2(128),
            data_type VARCHAR2(128),
            PRIMARY KEY (id)
        )';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF; -- ORA-00955 = name already used
    END;
    """)

    # NL2SQL_TRAINING
    cur.execute("""
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE NL2SQL_TRAINING (
            id NUMBER GENERATED ALWAYS AS IDENTITY,
            schema_name VARCHAR2(128),
            table_name VARCHAR2(128),
            question CLOB,
            sql_template CLOB,
            PRIMARY KEY (id)
        )';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
    END;
    """)

    # NL2SQL_SYNONYMS
    cur.execute("""
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE NL2SQL_SYNONYMS (
            id NUMBER GENERATED ALWAYS AS IDENTITY,
            training_id NUMBER,
            question_syn CLOB,
            FOREIGN KEY (training_id) REFERENCES NL2SQL_TRAINING(id)
        )';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
    END;
    """)

    # NL2SQL_EMBEDDINGS
    cur.execute("""
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE NL2SQL_EMBEDDINGS (
            id NUMBER GENERATED ALWAYS AS IDENTITY,
            training_id NUMBER,
            question CLOB,
            embedding BLOB,
            FOREIGN KEY (training_id) REFERENCES NL2SQL_TRAINING(id)
        )';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
    END;
    """)

    conn.commit()


# ----------------------
# DB Connection
# ----------------------
def connect_oracle(user, password, host, port, service):
    dsn = f"{host}:{port}/{service}"
    conn = oracledb.connect(user=user, password=password, dsn=dsn)
    ensure_tables(conn)
    return conn


# ----------------------
# Schema Extraction
# ----------------------
# ----------------------
# Schema Extraction
# ----------------------
def insert_schema(conn, schema_owner: str):
    cur = conn.cursor()

    # Create table if not exists


    # Clean old rows
    cur.execute("DELETE FROM NL2SQL_SCHEMA WHERE schema_name = :owner", {"owner": schema_owner.upper()})

    # Fetch schema (excluding CLOB/BLOB)
    cur.execute("""
        SELECT owner, table_name, column_name, data_type
        FROM all_tab_columns
        WHERE owner = :owner and table_name='SALES'
          AND data_type NOT IN ('CLOB','BLOB','NCLOB','BFILE')
    """, {"owner": schema_owner.upper()})
    rows = cur.fetchall()

    # Insert into table
    cur.executemany(
        "INSERT INTO NL2SQL_SCHEMA (schema_name, table_name, column_name, data_type) VALUES (:1,:2,:3,:4)",
        rows
    )
    conn.commit()



def fetch_schema_from_db(conn):
    return pd.read_sql("SELECT * FROM NL2SQL_SCHEMA", conn)


# ----------------------
# Questions + Synonyms
# ----------------------
def insert_questions(conn, df):
    """
    Insert synthetic questions and SQL templates into Oracle table.
    Automatically creates the table if it does not exist.
    """
    cur = conn.cursor()



    # Convert DataFrame to list of tuples
    # Make sure df is a pandas DataFrame
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df)}")

    rows = df.loc[:, ["schema_name", "table_name", "question", "sql_template"]].values.tolist()

    # Insert into Oracle
    cur.executemany(
        "INSERT INTO NL2SQL_TRAINING (schema_name, table_name, question, sql_template) VALUES (:1,:2,:3,:4)",
        rows
    )
    conn.commit()


def insert_synonyms(conn, df):
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO NL2SQL_SYNONYMS (training_id, question_syn) VALUES (:1,:2)",
        df[["training_id","question_syn"]].values.tolist()
    )
    conn.commit()

def fetch_training_data(conn):
    return pd.read_sql("SELECT id, question, sql_template FROM NL2SQL_TRAINING", conn)

def fetch_training_synonym_data(conn):
    return pd.read_sql("SELECT training_id, question_syn FROM NL2SQL_SYNONYMS", conn)

# ----------------------
# Embeddings
# ----------------------
def insert_embeddings(conn, q_df, embeddings, questOrSyn: str):
    cur = conn.cursor()
    cur.execute("DELETE FROM NL2SQL_EMBEDDINGS")  # refresh
    for i, row in q_df.iterrows():
        emb_bytes = np.asarray(embeddings[i], dtype=np.float32).tobytes()
        
        if questOrSyn == 'Quest':
            cur.execute(
                "INSERT INTO NL2SQL_EMBEDDINGS (training_id, question, embedding) VALUES (:1, :2, :3)",
                (int(row["ID"]), row["QUESTION"], emb_bytes)
            )
        else:
            cur.execute(
                "INSERT INTO NL2SQL_EMBEDDINGS (training_id, question, embedding) VALUES (:1, :2, :3)",
                (int(row["TRAINING_ID"]), row["QUESTION_SYN"], emb_bytes)
            )

    conn.commit()

def search_embeddings(conn, query_emb, top_k=3):
    cur = conn.cursor()
    cur.execute("SELECT id, training_id, question, embedding FROM NL2SQL_EMBEDDINGS")
    rows = cur.fetchall()

    results = []
    for r in rows:
        emb = np.frombuffer(r[3].read(), dtype=np.float32)  # convert BLOB back
        sim = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
        results.append((sim, r[1], r[2]))

    results = sorted(results, key=lambda x: -x[0])[:top_k]
    out = []
    for sim, tid, q in results:
        sql = pd.read_sql(f"SELECT sql_template FROM NL2SQL_TRAINING WHERE id={tid}", conn).iloc[0,0]
        out.append({"question": q, "sql_template": sql, "similarity": float(sim)})
    return out
