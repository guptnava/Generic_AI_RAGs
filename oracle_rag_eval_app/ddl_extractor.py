from typing import List, Dict, Any
from db import cursor
import oracledb
import os

def get_all_objects(owner: str) -> List[Dict[str, str]]:
    sql = """
        SELECT object_type, object_name
        FROM all_objects
        WHERE owner = :owner
          AND object_type IN ('TABLE','VIEW','MATERIALIZED VIEW')
          AND object_name in ('CUSTOMERS' , 'EMPLOYEES' , 'SALES' , 'PRODUCTS' , 'ORDERS')
        ORDER BY object_type, object_name
    """
    with cursor() as cur:
        cur.execute(sql, {"owner": owner.upper()})
        return [{"object_type": r[0], "object_name": r[1]} for r in cur.fetchall()]

def get_ddl(owner: str, object_type: str, object_name: str) -> str:
    with cursor() as cur:
        cur.execute("""
            BEGIN
              DBMS_METADATA.set_transform_param(DBMS_METADATA.SESSION_TRANSFORM,'STORAGE',false);
              DBMS_METADATA.set_transform_param(DBMS_METADATA.SESSION_TRANSFORM,'SEGMENT_ATTRIBUTES',false);
              DBMS_METADATA.set_transform_param(DBMS_METADATA.SESSION_TRANSFORM,'SQLTERMINATOR',true);
            END;
        """)
        q = "SELECT DBMS_METADATA.GET_DDL(:otype, :oname, :owner) FROM dual"
        cur.execute(q, {"otype": object_type, "oname": object_name, "owner": owner.upper()})
        row = cur.fetchone()
        return row[0].read() if row and row[0] else ""

def persist_ddl(owner: str):
    objects = get_all_objects(owner)
    ins = "INSERT INTO RAG_DDL(owner, object_type, object_name, ddl) VALUES (:o, :t, :n, :d)"
    with cursor() as cur:
        for obj in objects:
            ddl = get_ddl(owner, obj['object_type'], obj['object_name'])
            cur.execute(ins, {"o": owner.upper(), "t": obj['object_type'], "n": obj['object_name'], "d": ddl})

def parse_tables_columns(owner: str):
    """Return dict: {table_name: [ (col_name, data_type), ... ] }"""
    sql = """
    SELECT t.table_name, c.column_name, c.data_type
    FROM all_tables t
    JOIN all_tab_columns c
      ON c.owner=t.owner AND c.table_name=t.table_name
    WHERE t.owner=:owner and t.table_name in ('CUSTOMERS' , 'EMPLOYEES' , 'SALES' , 'PRODUCTS' , 'ORDERS')
    ORDER BY t.table_name, c.column_id
    """
    tables = {}
    with cursor() as cur:
        cur.execute(sql, {"owner": owner.upper()})
        for tname, col, dtype in cur.fetchall():
            tables.setdefault(tname, []).append((col, dtype))
    return tables
