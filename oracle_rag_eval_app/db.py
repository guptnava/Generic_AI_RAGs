import os
import oracledb
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DSN = os.getenv("ORACLE_DSN")
USER = os.getenv("ORACLE_USER")
PASSWORD = os.getenv("ORACLE_PASSWORD")

_conn = None

def get_connection():
    """Return a persistent Oracle connection, reconnecting if needed."""
    global _conn
    if not all([DSN, USER, PASSWORD]):
        raise RuntimeError("Missing ORACLE_DSN/ORACLE_USER/ORACLE_PASSWORD in environment")
    if _conn is None or not _conn.ping():
        _conn = oracledb.connect(user=USER, password=PASSWORD, dsn=DSN)
    return _conn

@contextmanager
def cursor():
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass

def ensure_tables():
    """Create core tables if they don't exist."""
    ddl_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(ddl_path, "r", encoding="utf-8") as f:
        sql_text = f.read()
    stmts = [s.strip() for s in sql_text.split(";\n") if s.strip()]
    with cursor() as cur:
        for s in stmts:
            try:
                cur.execute(s)
            except oracledb.DatabaseError:
                pass  # ignore errors for existing objects
