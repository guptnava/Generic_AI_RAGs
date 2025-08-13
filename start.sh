#!/bin/bash

echo "🚀 Starting all services..."

# Start Flask API
echo "🔌 Starting Flask APIs on port 5000/01/02/03/04/05/06..."
cd api
source venv/bin/activate
FLASK_APP=ai_db_intent_interface.py FLASK_RUN_PORT=5000 flask run &
FLASK_PID=$!

FLASK_APP=ai_db_langchain_interface.py FLASK_RUN_PORT=5001 flask run &
FLASK_PID1=$!

FLASK_APP=ai_db_langchain_prompt_interface.py FLASK_RUN_PORT=5002 flask run &
FLASK_PID2=$!

# FLASK_APP=ai_db_llamaindex_interface.py FLASK_RUN_PORT=5003 flask run &
# FLASK_PID3=$!


FLASK_APP=ai_db_langchain_embedding_prompt_interface.py FLASK_RUN_PORT=5004 flask run &
FLASK_PID4=$!

FLASK_APP=rado.py FLASK_RUN_PORT=5005 flask run &
FLASK_PID5=$!

FLASK_APP=ai_restful_embedding_prompt_interface.py FLASK_RUN_PORT=5006 flask run &
FLASK_PID6=$!



#FLASK_APP=ai_confluence_embedding_interface.py FLASK_RUN_PORT=5007 flask run &
#FLASK_PID7=$!

#FLASK_APP=ai_data_analysis_assistant.py FLASK_RUN_PORT=5008 flask run &
#FLASK_PID8=$!

FLASK_APP=ai_db_langchain_embedding_prompt_narrated_interface.py FLASK_RUN_PORT=5009 flask run &
FLASK_PID9=$!


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
trap "echo '🛑 Stopping services...'; kill $FLASK_PID $FLASK_PID1 $FLASK_PID2 $FLASK_PID3 $FLASK_PID4 $FLASK_PID5 $FLASK_PID6 $FLASK_PID7 $FLASK_PID8 $FLASK_PID9 $NODE_PID $FRONTEND_PID; exit" INT

wait
