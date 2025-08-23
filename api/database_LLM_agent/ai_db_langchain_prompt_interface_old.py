from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import re
import time
import diskcache
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_community.llms import Ollama

from langchain_core.prompts import PromptTemplate

import time
from sqlalchemy import create_engine, text
from flask import Response, stream_with_context

import json
import datetime

# Load .env for DB credentials
load_dotenv()

app = Flask(__name__)

# Cache setup with expiration (30 minutes)
CACHE_EXPIRATION_SECONDS = 1800
cache = diskcache.Cache("./llm_cache")

# DB Setup
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE")

db_uri = f"oracle+oracledb://{db_user}:{db_password}@{db_host}:{db_port}/{db_service}"
print(f"Connecting to DB with URI: {db_uri}")

engine = create_engine(
    db_uri,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    echo_pool=True  # Enable pool logging
)

# Pass engine to SQLDatabase; specify tables for safety
db = SQLDatabase(engine, include_tables=['sales', 'employees'])
#db = SQLDatabase.from_uri(db_uri, include_tables=['sales', 'employees'])

def is_safe_sql(sql: str) -> bool:
    sql = sql.strip().lower()
    return sql.startswith("select")

def log_query(prompt, sql, user_agent, client_ip, model):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open("query_log.txt", "a") as f:
        f.write(f"\n---\n[{timestamp}] IP: {client_ip}, UA: {user_agent}, Model: {model}\nPrompt: {prompt}\nGenerated SQL: {sql}\n")


@app.route("/query", methods=["POST"])
def query_db():
    data = request.get_json()
    prompt = data.get("prompt")
    model = data.get("model", "llama3.2:1b")  # fallback model if not sent

    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400
    
    # Get user/session info
    user_agent = request.headers.get('User-Agent', 'unknown')
    client_ip = request.remote_addr or 'unknown'

    # Cache check
    # cache_key = f"{model}:{prompt}"
    # cached = cache.get(cache_key)
    # if cached:
    #     return jsonify({"response": cached, "cached": True})

    table_info = """sales(
            sale_id NUMBER,
            customer_id NUMBER,
            product_id NUMBER,
            sale_date DATE,
            quantity NUMBER,
            unit_price NUMBER,
            total_amount NUMBER,
            region VARCHAR2(50)
            )"""

    template="""
        You are a highly skilled SQL assistant that generates correct, optimized Oracle SQL queries based on a given table schema and natural language questions.

            
        ### Important Guidelines:
            - Use only the tables and columns listed in the schema.
            - Assume the database is Oracle; use correct Oracle SQL syntax.
            - Always qualify column names with table aliases if the query involves multiple tables.
            - Use `SYSDATE` for current date if needed.
            - Use `TO_DATE('YYYY-MM-DD', 'YYYY-MM-DD')` when dealing with date literals.
            - Avoid using functions or syntax not supported by Oracle.
            - Do not use semi colon at the end of the query
            - do not use Limit in sql syntax but instead use rownum
            - do not use column aliases, keep the column name same as the column name
            - Do NOT use JOINs or subqueries.
            - Do NOT use table aliases.
            - Use only simple SELECT, GROUP BY, ORDER BY, WHERE clauses.
       
        ### Table Schema:
        {table_info}



        ### Examples:

        Example Input 1:
        Get total sales amount per region.

        Output 1:
        SELECT region, SUM(total_amount) AS total_sales
        FROM sales
        GROUP BY region

        ---

        Example Input 2:
        Get the top 5 products by total sales amount.

        Output 2:
        SELECT product_id, SUM(total_amount) AS total_sales
        FROM sales
        GROUP BY product_id
        ORDER BY total_sales DESC


        ---

        Example Input 3:
        Find all sales records made in March 2025.

        Output 3:
        SELECT *
        FROM sales
        WHERE sale_date BETWEEN TO_DATE('2025-03-01', 'YYYY-MM-DD') AND TO_DATE('2025-03-31', 'YYYY-MM-DD')

        ---

        Now use the schema below to answer the next question.

        Schema:
        sales(
            sale_id NUMBER,
            customer_id NUMBER,
            product_id NUMBER,
            sale_date DATE,
            quantity NUMBER,
            unit_price NUMBER,
            total_amount NUMBER,
            region VARCHAR2(50)
        )

        Example Bad Output:
        SELECT T1.region, SUM(T2.total_amount) AS total_sales
        FROM sales T1
        JOIN (SELECT region, SUM(total_amount) AS total_sales FROM sales GROUP BY region) T2
        ON T1.region = T2.region
        GROUP BY T1.region

        This query is incorrect because:
        - It uses JOIN unnecessarily
        - It uses table aliases which are forbidden
        - It is syntactically incorrect for Oracle

        Question: {input}

        Top K: {top_k}        
                
        SQL:
        """
    
    def serialize_row(row, columns):
        return {
        col: (val.isoformat() if isinstance(val, datetime.datetime) else val)
        for col, val in zip(columns, row)
    }


    def generate():
        try:

            prompt_template = PromptTemplate(input_variables=["input", "table_info", "top_k"],template=template.strip())

            top_k=5  # using 40 to test


            # Dynamically instantiate LLM and chain
           # llm = Ollama(model=model)
            llm = Ollama(model=model,
                        temperature=0.0,
                        top_k=top_k,
                        repeat_penalty=1.1,
                        top_p=0.8,
                        num_predict=256
                        # max_tokens=300,
                        #stop=["\n\n"]
                )
            
            # Core Parameters for Fine-tuning / Inference Control

            # Parameter	        What It Does	                                                                Typical Values / Tips
            # temperature	    Controls randomness.                                                            Lower = deterministic; higher = creative.	0.0 (deterministic) to 1.0 (more random). For SQL, 0 or 0.1 recommended.
            # top_k	            Limits sampling to the top K probable tokens.	                                40-100 is common. Lower = less diversity.
            # top_p	            Nucleus sampling. Limits tokens to smallest set with cumulative probability p.	0.8–0.95 typical. Lower = more conservative.
            # repeat_penalty	Penalizes repeated tokens to reduce repetition.	                                >1.0 (e.g., 1.1–1.2) to discourage repeats.
            # max_tokens	    Max number of tokens to generate.	                                            Set based on expected query length (e.g., 256-512).
            # frequency_penalty	Penalizes new tokens based on their existing frequency.                     	Helps reduce overuse of tokens. Often 0-2 scale.
            # presence_penalty	Penalizes tokens that have already appeared.	                                Similar to frequency_penalty but on presence basis.



            db_chain = create_sql_query_chain(llm, db, prompt=prompt_template)

            # If db_chain.invoke is not streamable, yield as one line
            sql = db_chain.invoke({"input": prompt, "question": prompt,"table_info": table_info,"top_k": top_k})

            log_query(prompt, sql, user_agent, client_ip, model)

            # if not is_safe_sql(sql):
            # return jsonify({"error": "Unsafe SQL detected. Only SELECT is allowed."}), 403

            # result = db.run(sql)



            # cache.set(cache_key, result, expire=CACHE_EXPIRATION_SECONDS)

            with engine.connect() as conn:
                result = conn.execution_options(stream_results=True).execute(text(sql))
                columns=result.keys()


            for row in result:
                row_dict = serialize_row(row, columns)
                yield json.dumps(row_dict) + "\n"
            # for row in result:
            #     yield json.dumps({serialize_row(row, columns)}) + "\n"  # NDJSON line

        except Exception as e:
             yield json.dumps({"error": str(e)}) + "\n"

    return Response(stream_with_context(generate()), content_type="application/x-ndjson")

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/clear_cache", methods=["POST"])
def clear_cache():
    cache.clear()
    return jsonify({"status": "Cache cleared"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
