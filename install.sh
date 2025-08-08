#!/bin/bash

# install Ollama  e.g on mac
# brew install ollama
# brew services start ollama
# ollama list

# ollama pull codellama
# ollama pull phi3  
# ollama pull gemma   
# ollama pull llama3.2     
# ollama pull llama3        
# ollama pull mistral   


echo "🔧 Setting up the project..."

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
#npm create vite@latest client -- --template react
cd client
npm install || exit 1
cd ..

# Install backend dependencies
echo "📦 Installing Node.js backend dependencies..."
cd server

# Initialize package.json if missing
if [ ! -f package.json ]; then
  npm init -y
fi

# Install dependencies
npm install || exit 1
cd ..

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
cd api
python3.9 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt || exit 1
deactivate
cd ..

echo "✅ All dependencies installed!"
