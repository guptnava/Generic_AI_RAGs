import os
import subprocess
import json
from flask import Flask, request, Response, stream_with_context
import pandas as pd
import pyarrow.fs as fs
import cx_Oracle
from pyhive import hive

app = Flask(__name__)

# Kerberos and Hive config (same as before)
HIVE_HOST = os.environ.get("HIVE_HOST", "your.hive.server")
HIVE_PORT = int(os.environ.get("HIVE_PORT", 10000))
HIVE_USERNAME = os.environ.get("HIVE_USERNAME", "your_username")
HIVE_DATABASE = os.environ.get("HIVE_DATABASE", "default")
HIVE_AUTH_MECHANISM = 'KERBEROS'

KERBEROS_KEYTAB = os.environ.get("KERBEROS_KEYTAB", "/path/to/your.keytab")
KERBEROS_PRINCIPAL = os.environ.get("KERBEROS_PRINCIPAL", "your_principal@YOUR.REALM")

os.environ['KRB5_CLIENT_KTNAME'] = KERBEROS_KEYTAB
os.environ['KRB5_PRINCIPAL'] = KERBEROS_PRINCIPAL

# Oracle connection info (change accordingly)
ORACLE_DSN = os.environ.get("ORACLE_DSN", "host:port/service_name")
ORACLE_USER = os.environ.get("ORACLE_USER", "oracle_user")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "oracle_password")

def kinit():
    """Run kinit with keytab to obtain Kerberos ticket."""
    try:
        result = subprocess.run(
            ["kinit", "-kt", KERBEROS_KEYTAB, KERBEROS_PRINCIPAL],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            raise Exception(f"kinit failed: {result.stderr.strip()}")
    except Exception as e:
        raise Exception(f"Kerberos kinit error: {e}")

def get_oracle_connection():
    dsn = cx_Oracle.makedsn(*ORACLE_DSN.split(":")[:2], service_name=ORACLE_DSN.split("/")[-1])
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    return conn

def get_schema_info_from_oracle():
    """Fetch column names, types, descriptions from Oracle metadata table."""
    conn = get_oracle_connection()
    sql = "SELECT column_name, data_type, description FROM RISK_METADATA ORDER BY column_name"
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def get_data_query_from_oracle(source_type):
    """Get the hive query or parquet path from Oracle for the given source_type."""
    conn = get_oracle_connection()
    sql = "SELECT query_or_path FROM DATA_QUERIES WHERE source_type = :src"
    df = pd.read_sql(sql, conn, params={"src": source_type})
    conn.close()
    if df.empty:
        raise Exception(f"No query or path found in Oracle for source_type={source_type}")
    return df.iloc[0, 0]  # First row, first column string

def get_hive_connection():
    kinit()
    conn = hive.Connection(
        host=HIVE_HOST,
        port=HIVE_PORT,
        username=HIVE_USERNAME,
        database=HIVE_DATABASE,
        auth=HIVE_AUTH_MECHANISM,
        kerberos_service_name='hive'
    )
    return conn

def query_hive(sql):
    conn = get_hive_connection()
    df = pd.read_sql(sql, conn)
    return df

def read_parquet_from_hdfs(hdfs_path):
    kinit()
    hdfs = fs.HadoopFileSystem(
        host=None,
        port=0,
        user=HIVE_USERNAME,
        kerb_ticket=None
    )
    with hdfs.open_input_file(hdfs_path) as f:
        df = pd.read_parquet(f)
    return df

def query_oracle_data(sql):
    conn = get_oracle_connection()
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def build_prompt(schema_df, context, question):
    """Build a generic prompt using schema info and data context."""
    # Format schema info nicely
    schema_desc = "\n".join(
        [f"- {row['column_name']} ({row['data_type']}): {row['description'] or 'No description'}"
         for _, row in schema_df.iterrows()]
    )
    prompt = f"""
You are a Risk Analytics assistant. The dataset has the following columns with types and descriptions:

{schema_desc}

Dataset sample (first 50 rows or less):
{context}

Answer the user question clearly and succinctly.

---

User question: {question}

Answer:
"""
    return prompt

def ask_llm_stream(prompt):
    """Call Ollama with streaming output for the prompt."""
    command = [
        "ollama",
        "run",
        "llama3.2:1b",
        "--prompt",
        prompt,
        "--stream"
    ]

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        for stdout_line in iter(proc.stdout.readline, ''):
            if stdout_line.strip():
                yield json.dumps({'answer': stdout_line.strip()}) + "\n"

        proc.stdout.close()
        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            yield json.dumps({'error': f"Model error: {err.strip()}"}) + "\n"
            proc.stderr.close()

    except Exception as e:
        yield json.dumps({'error': f"LLM call failed: {str(e)}"}) + "\n"

@app.route('/query', methods=['POST'])
def data_qa():
    data = request.json or {}
    question = data.get('question')
    source = data.get('source')  # oracle, hive, parquet
    if not question or not source:
        error_obj = json.dumps({'error': 'Missing required parameters: question, source'}) + "\n"
        return Response(error_obj, status=400, content_type='application/x-ndjson')

    def generate_response():
        try:
            # Step 1: get schema info from Oracle
            schema_df = get_schema_info_from_oracle()

            # Step 2: get query/path from Oracle metadata table based on source
            query_or_path = get_data_query_from_oracle(source)

            # Step 3: fetch data depending on source
            if source == 'hive':
                df = query_hive(query_or_path)
            elif source == 'parquet':
                df = read_parquet_from_hdfs(query_or_path)
            elif source == 'oracle':
                df = query_oracle_data(query_or_path)
            else:
                yield json.dumps({'error': f'Invalid source: {source}. Must be "oracle", "hive" or "parquet".'}) + "\n"
                return

            context = df.head(50).to_string()

            # Step 4: build prompt dynamically
            prompt = build_prompt(schema_df, context, question)

            # Step 5: stream LLM response
            yield from ask_llm_stream(prompt)

        except Exception as e:
            yield json.dumps({'error': str(e)}) + "\n"

    return Response(stream_with_context(generate_response()), content_type='application/x-ndjson')

if __name__ == '__main__':
    # app.run(port=5001, debug=True)
    app.run(host="0.0.0.0" , port=5001)
