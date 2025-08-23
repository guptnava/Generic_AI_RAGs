#!/bin/bash

echo "🚀 Starting all services..."

#start ollama
#OLLAMA_HOST=0.0.0.0:11434 ollama serve &
#OLLAMA_PID=$!

# Start Flask API
echo "🔌 Starting Flask APIs on port 5000/01/02/03/04/05/06..."
cd api
source venv/bin/activate

cd database_NoLLM_agent

FLASK_APP=ai_db_intent_interface.py FLASK_RUN_PORT=5000 FLASK_RUN_HOST=0.0.0.0 flask run &
FLASK_PID=$!

FLASK_APP=ai_db_intent_embeded_nomodel_interface.py FLASK_RUN_PORT=5011 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID11=$!

cd ..

cd database_LLM_agent
FLASK_APP=ai_db_langchain_interface.py FLASK_RUN_PORT=5001 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID1=$!



FLASK_APP=ai_db_langchain_prompt_interface.py FLASK_RUN_PORT=5002 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID2=$!

# FLASK_APP=ai_db_llamaindex_interface.py FLASK_RUN_PORT=5003 flask run &
# FLASK_PID3=$!


FLASK_APP=ai_db_langchain_embedding_prompt_interface.py FLASK_RUN_PORT=5004 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID4=$!

FLASK_APP=ai_db_langchain_embedding_prompt_narrated_interface.py FLASK_RUN_PORT=5009 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID9=$!

cd ..

cd restful_LLM_agent

FLASK_APP=rado.py FLASK_RUN_PORT=5005 FLASK_RUN_HOST=0.0.0.0 flask run &
FLASK_PID5=$!

FLASK_APP=ai_restful_embedding_prompt_interface.py FLASK_RUN_PORT=5006 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID6=$!

cd ..

#FLASK_APP=ai_confluence_embedding_interface.py FLASK_RUN_PORT=5007 FLASK_RUN_HOST=0.0.0.0  flask run &
#FLASK_PID7=$!

#FLASK_APP=ai_data_analysis_assistant.py FLASK_RUN_PORT=5008 FLASK_RUN_HOST=0.0.0.0  flask run &
#FLASK_PID8=$!

cd database_generic_rag_LLM_agent

FLASK_APP=ai_generic_database_rag_agent.py FLASK_RUN_PORT=5010 FLASK_RUN_HOST=0.0.0.0  flask run &
FLASK_PID10=$!

cd ..


cd ..

# Start Node.js server
echo "🖥️ Starting Node.js backend on port 8000..."

# Go to server directory
cd server
# Start the server
node server.js &
NODE_PID=$!
cd ..

# Start React frontend
echo "🌐 Starting Vite frontend on port 5173..."
cd client
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for user to quit
echo "🔄 All services running. Press Ctrl+C to stop."

# Trap Ctrl+C and clean up
trap "echo '🛑 Stopping services...'; kill $FLASK_PID $FLASK_PID1 $FLASK_PID2 $FLASK_PID3 $FLASK_PID4 $FLASK_PID5 $FLASK_PID6 $FLASK_PID7 $FLASK_PID8 $FLASK_PID9 $FLASK_PID10 $FLASK_PID11 $NODE_PID $FRONTEND_PID; exit" INT

wait
