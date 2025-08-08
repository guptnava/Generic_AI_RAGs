# query_db.py
import sys
import os
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_community.llms import Ollama
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE")

db_uri = f"oracle+oracledb://{db_user}:{db_password}@{db_host}:{db_port}/{db_service}"

db = SQLDatabase.from_uri(db_uri, include_tables=['sales', 'employees'])
llm = Ollama(model="llama3.2:1b")
db_chain = create_sql_query_chain(llm, db)

question = sys.argv[1]
response = db_chain.invoke({"question": question})
print(response)
